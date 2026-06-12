"""Tests for the lexical NIL detection (Phase 3).

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_nil_detection.py -v`

Goal: lock the behaviour of `EntityLinker._is_likely_nil` so future changes
do not silently introduce false negatives by widening the regex patterns.
Patterns are validated on the train (100% NIL precision on matched mentions,
0 linked mention matches).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linker import EntityLinker


# --- LOCATION patterns (should return True = NIL) ---


def test_fort_de_pattern_removed():
    """The `^fort\\s+d[eu]\\b` NIL pattern was REMOVED in Run 2.

    Rationale: it blocked Fort-de-France (PPLC Martinique, GeoNames 3570675),
    a real city with ~90k inhabitants and a perfect GeoNames match. Fort-de-X
    mentions that genuinely lack a GeoNames entry (e.g. `fort de Corbas` in
    train) still fall back to NIL naturally because the linker does not
    strip `fort de` in `strip_prefix()`.

    This negative test locks the decision: `fort de Vincennes` MUST NOT be
    pre-blocked anymore. The linker will try, find nothing, and return NIL
    on its own.
    """
    assert EntityLinker._is_likely_nil("fort de Vincennes", "LOCATION") is False
    assert EntityLinker._is_likely_nil("Fort-de-France", "LOCATION") is False
    assert EntityLinker._is_likely_nil("fort de Corbas", "LOCATION") is False


def test_nil_quartier_simple():
    assert EntityLinker._is_likely_nil("quartier Exemple", "LOCATION") is True


def test_nil_quartier_des_compose():
    assert EntityLinker._is_likely_nil("quartier des Vignes", "LOCATION") is True


def test_nil_zone_compose():
    assert EntityLinker._is_likely_nil("zone industrielle Sud", "LOCATION") is True


def test_nil_bassins():
    assert EntityLinker._is_likely_nil("Bassins du Port", "LOCATION") is True


def test_nil_ceinture():
    assert EntityLinker._is_likely_nil(
        "ceinture épidémique tropicale", "LOCATION"
    ) is True


# --- BIO_TOXIN patterns (should return True = NIL) ---


def test_nil_venom():
    assert EntityLinker._is_likely_nil(
        "Pholcus phalangioides venom", "BIO_TOXIN"
    ) is True


def test_nil_venin():
    assert EntityLinker._is_likely_nil("venin de scorpion", "BIO_TOXIN") is True


# --- Cases that MUST NOT be flagged as NIL (linked in train) ---


def test_not_nil_chateau_bourdaisiere():
    """'chateau de la Bourdaisière' is linked in the train -> must not match."""
    assert EntityLinker._is_likely_nil(
        "château de la Bourdaisière", "LOCATION"
    ) is False


def test_not_nil_rue_de_trevise():
    """'rue de Trévise' is linked in the train -> 'rue' pattern excluded."""
    assert EntityLinker._is_likely_nil("rue de Trévise", "LOCATION") is False


def test_not_nil_ville_d_argaiach():
    """'ville d'Argaïach' is linked in the train -> 'ville' not flagged."""
    assert EntityLinker._is_likely_nil("ville d’Argaïach", "LOCATION") is False


def test_not_nil_village_de_kamenka():
    """'village de Kamenka' is linked in the train -> 'village' not flagged."""
    assert EntityLinker._is_likely_nil("village de Kamenka", "LOCATION") is False


def test_not_nil_paris():
    assert EntityLinker._is_likely_nil("Paris", "LOCATION") is False


def test_not_nil_aflatoxine():
    """'aflatoxine' is a MeSH descriptor -> must not match the venom pattern."""
    assert EntityLinker._is_likely_nil("aflatoxine", "BIO_TOXIN") is False


def test_not_nil_acronym_toxin():
    """A toxin acronym without 'venom/venin' word must NOT be flagged NIL."""
    assert EntityLinker._is_likely_nil("MyTox1", "BIO_TOXIN") is False


# --- Labels other than LOCATION/BIO_TOXIN -> always False ---


def test_not_nil_mesh_disease():
    assert EntityLinker._is_likely_nil("zone X", "INF_DISEASE") is False


def test_not_nil_empty_string():
    assert EntityLinker._is_likely_nil("", "LOCATION") is False


# --- Train-set guard: validates the regex patterns against ALL train data ---


def test_train_set_no_false_negative():
    """Walk the whole train set: every NIL pattern hit must be a real NIL.

    Locks the guarantee that widening the regex patterns will break this test
    if it accidentally swallows a linked mention.

    SKIPPED if `train_evalLLM.json` is not available (protected data, not
    distributed with the public repo).
    """
    import json
    import pytest

    train_path = Path(__file__).resolve().parent.parent / "train_evalLLM.json"
    if not train_path.exists():
        pytest.skip(
            "train_evalLLM.json not available (protected challenge data). "
            "Request it from the EvalLLM 2026 organizers to run this guard."
        )
    with open(train_path, encoding="utf-8") as f:
        train = json.load(f)

    detected_nil = 0
    false_negatives = []
    for doc in train:
        for ent in doc.get("entities", []):
            if not EntityLinker._is_likely_nil(ent["text"], ent["label"]):
                continue
            if ent["source"] == "":
                detected_nil += 1
            else:
                false_negatives.append(
                    f"'{ent['text']}' [{ent['label']}] -> {ent['source']}:{ent['id_kb']}"
                )

    assert false_negatives == [], (
        f"NIL patterns now match {len(false_negatives)} linked mentions: "
        f"{false_negatives}"
    )
    # Lower bound: at minimum 7 NIL detected (current state on train).
    # Was 9 before Run 2; dropped to 7 when `^fort\s+d[eu]\b` was removed
    # (the 2 `fort de Corbas` mentions are no longer pre-blocked but still
    # resolve to NIL naturally via the standard cascade — `strip_prefix`
    # does not strip 'fort de', so the full mention finds no GeoNames match).
    assert detected_nil >= 7, (
        f"Expected >= 7 NIL detections on the train set, got {detected_nil}"
    )
