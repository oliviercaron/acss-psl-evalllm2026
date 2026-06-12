"""Validate a predictions JSON file against the EvalLLM 2026 expected format.

Usage:
    python src/validate_predictions.py <test_input.json> <predictions.json>

Returns exit code 0 if the file is submission-ready, 1 otherwise.

What it checks (structural conformity to avoid wasting a submission slot):

    Hard errors (block submission)
    ------------------------------
    H1  predictions.json is valid UTF-8 JSON
    H2  top-level structure is a list (same length as test_input.json)
    H3  every document keeps its `text` field unchanged (no rewriting)
    H4  every document has an `entities` list of the same length
    H5  every entity preserves text/label/start/end (spans must match input)
    H6  every entity has both `id_kb` and `source` fields
    H7  `source` is in {"GeoNames", "MeSH", ""}
    H8  if source == "GeoNames": id_kb is digits only
    H9  if source == "MeSH": id_kb matches one of the accepted formats:
            "D\\d{6,9}"                       descriptor only
            "C\\d{6,9}"                       supplementary concept only
            "D\\d+ & D\\d+ ..."               composite descriptors
            "D\\d+ : C\\d+( | C\\d+)*"        descriptor + supplementary concepts
    H10 if source == "": id_kb must be ""
    H11 if source != "": id_kb must not be empty

    Soft warnings (do not block, but flag)
    --------------------------------------
    S1  predicted GeoNames IDs that are absent from the local GeoNames DB
    S2  predicted MeSH DUIs absent from the local MeSH index
    S3  rate of NIL predictions (source=="") outside [0.5%, 15%] range
    S4  any encoding hint of cp1252 corruption (e.g. "Ã©", "Ã ", "Â°")
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = DATA_DIR / "processed"

VALID_SOURCES = {"GeoNames", "MeSH", ""}

# Accepted MeSH id formats:
#   "D004926"
#   "C501880"
#   "D001943 & D002583"
#   "D009498 : C501880"
#   "D009498 : C083624 | C121745"
#   "D013111 & D009498 : C500354 | C533889 | ..."
_MESH_ENTITY = r"[DC]\d{6,9}"
_MESH_ENTITIES = rf"{_MESH_ENTITY}(?:\s*&\s*{_MESH_ENTITY})*"
_MESH_CONCEPTS = rf"C\d{{6,9}}(?:\s*\|\s*C\d{{6,9}})*"
MESH_ID_RE = re.compile(rf"^{_MESH_ENTITIES}(?:\s*:\s*{_MESH_CONCEPTS})?$")

GEO_ID_RE = re.compile(r"^\d{1,12}$")
CP1252_HINTS = ("Ã©", "Ã¨", "Ãª", "Ã ", "Ã§", "Â°", "Â«", "Â»", "â")


def _normalize_span(value):
    if isinstance(value, list):
        return tuple(value)
    return value


def _load_geonames_ids():
    db_path = PROCESSED_DIR / "geonames.db"
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    ids = {str(r[0]) for r in conn.execute("SELECT geonameid FROM locations")}
    conn.close()
    return ids


def _load_mesh_duis():
    import pickle

    idx_path = PROCESSED_DIR / "mesh_index.pkl"
    if not idx_path.exists():
        return None
    with open(idx_path, "rb") as f:
        idx = pickle.load(f)
    duis = set(idx.get("descriptors", {}).keys())
    suis = set(idx.get("supplementals", {}).keys())
    return duis, suis


def _check_mesh_id(id_kb: str, duis: set | None, suis: set | None) -> list[str]:
    """Return list of unknown IDs (descriptors or supplementals)."""
    unknown: list[str] = []
    if duis is None or suis is None:
        return unknown
    # Split "D... [& D... ...] [: C... [| C... ...]]"
    if ":" in id_kb:
        entities_part, concepts_part = id_kb.split(":", 1)
    else:
        entities_part, concepts_part = id_kb, ""
    for token in re.split(r"\s*&\s*", entities_part.strip()):
        if token and token.startswith("D") and token not in duis:
            unknown.append(token)
    for token in re.split(r"\s*\|\s*", concepts_part.strip()):
        token = token.strip()
        if token and token.startswith("C") and token not in suis:
            unknown.append(token)
    return unknown


def validate(input_path: Path, pred_path: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    # H1 - JSON valid + utf-8
    try:
        with open(pred_path, encoding="utf-8") as f:
            pred = json.load(f)
    except UnicodeDecodeError as e:
        print(f"H1 FATAL: predictions file is not valid UTF-8: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"H1 FATAL: predictions file is not valid JSON: {e}")
        return 1

    with open(input_path, encoding="utf-8") as f:
        gold = json.load(f)

    # H2 - top-level list same length
    if not isinstance(pred, list):
        errors.append(f"H2: top-level is {type(pred).__name__}, expected list")
    elif len(pred) != len(gold):
        errors.append(f"H2: {len(pred)} documents predicted vs {len(gold)} expected")

    if errors:
        for e in errors:
            print(e)
        return 1

    n_entities = 0
    n_nil = 0
    n_geonames = 0
    n_mesh = 0

    geo_ids_db = _load_geonames_ids()
    mesh_indexes = _load_mesh_duis()

    cp1252_seen = 0

    for i, (g_doc, p_doc) in enumerate(zip(gold, pred)):
        # H3 - text unchanged
        if g_doc.get("text", "") != p_doc.get("text", ""):
            errors.append(f"H3 doc{i}: 'text' field differs from input")

        g_ents = g_doc.get("entities", [])
        p_ents = p_doc.get("entities", [])

        # H4 - entities list same length
        if len(g_ents) != len(p_ents):
            errors.append(
                f"H4 doc{i}: {len(p_ents)} entities predicted vs {len(g_ents)} expected"
            )
            continue

        for j, (ge, pe) in enumerate(zip(g_ents, p_ents)):
            tag = f"doc{i}.ent{j}"
            # H5 - mention/label/spans unchanged
            for key in ("text", "label", "start", "end"):
                if _normalize_span(ge.get(key)) != _normalize_span(pe.get(key)):
                    errors.append(
                        f"H5 {tag}: '{key}' differs (input={ge.get(key)!r}, "
                        f"pred={pe.get(key)!r})"
                    )

            # H6 - id_kb + source present
            if "id_kb" not in pe or "source" not in pe:
                errors.append(f"H6 {tag}: missing id_kb or source field")
                continue
            source = pe["source"]
            id_kb = pe["id_kb"]

            # CP1252 hint
            if any(h in pe.get("text", "") for h in CP1252_HINTS):
                cp1252_seen += 1

            # H7 - source valid
            if source not in VALID_SOURCES:
                errors.append(
                    f"H7 {tag}: source={source!r}, expected one of {VALID_SOURCES}"
                )
                continue

            # H10/H11 - source/id_kb consistency
            if source == "" and id_kb != "":
                errors.append(f"H10 {tag}: NIL source but id_kb={id_kb!r} is not empty")
                continue
            if source != "" and id_kb == "":
                errors.append(f"H11 {tag}: source={source!r} but id_kb is empty")
                continue

            if source == "GeoNames":
                n_geonames += 1
                # H8 - GeoNames id format
                if not GEO_ID_RE.match(id_kb):
                    errors.append(
                        f"H8 {tag}: GeoNames id_kb={id_kb!r} is not a pure-digit string"
                    )
                elif geo_ids_db is not None and id_kb not in geo_ids_db:
                    warnings.append(
                        f"S1 {tag}: GeoNames id {id_kb} not found in local DB"
                    )

            elif source == "MeSH":
                n_mesh += 1
                # H9 - MeSH id format
                if not MESH_ID_RE.match(id_kb):
                    errors.append(
                        f"H9 {tag}: MeSH id_kb={id_kb!r} does not match expected format "
                        f"(D###### [& D######…] [: C###### [| C######…]])"
                    )
                else:
                    unknown = _check_mesh_id(id_kb, *mesh_indexes) if mesh_indexes else []
                    for unk in unknown:
                        warnings.append(f"S2 {tag}: MeSH ID {unk} not in local index")
            else:
                n_nil += 1

            n_entities += 1

    # S3 - NIL rate sanity
    if n_entities > 0:
        nil_rate = n_nil / n_entities
        if nil_rate < 0.005:
            warnings.append(
                f"S3: NIL rate is {nil_rate*100:.2f}% (< 0.5%), suspiciously low"
            )
        elif nil_rate > 0.15:
            warnings.append(
                f"S3: NIL rate is {nil_rate*100:.2f}% (> 15%), suspiciously high"
            )

    # S4 - cp1252 corruption
    if cp1252_seen > 0:
        warnings.append(
            f"S4: {cp1252_seen} entity text(s) look like cp1252-corrupted UTF-8 "
            f"(e.g. 'Ã©' instead of 'é'). Check encoding=utf-8 in your read/write."
        )

    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print(f"  Documents predicted : {len(pred)}")
    print(f"  Total entities       : {n_entities}")
    print(f"    GeoNames linked   : {n_geonames}")
    print(f"    MeSH linked       : {n_mesh}")
    print(f"    NIL (source=='')  : {n_nil}")
    if n_entities:
        print(f"    NIL rate          : {n_nil / n_entities * 100:.2f}%")
    print()

    if errors:
        print(f"BLOCKING ERRORS ({len(errors)}) — do NOT submit:")
        for e in errors[:40]:
            print(f"  - {e}")
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more")
        return 1

    if warnings:
        print(f"Soft warnings ({len(warnings)}) — review before submission:")
        for w in warnings[:40]:
            print(f"  - {w}")
        if len(warnings) > 40:
            print(f"  ... and {len(warnings) - 40} more")
        print()

    print("OK — file is submission-ready.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/validate_predictions.py <test_input.json> <predictions.json>")
        sys.exit(2)
    sys.exit(validate(Path(sys.argv[1]), Path(sys.argv[2])))
