"""Tests for the predictions validator.

Locks the contract that catches format errors before submission, to avoid
wasting one of the 3 allowed runs on an unparseable file.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from validate_predictions import validate


# --- Helpers --------------------------------------------------------------


def _write_json(obj) -> Path:
    tmp = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return tmp


def _minimal_input():
    return [
        {
            "text": "Une explosion à Paris.",
            "entities": [
                {"text": "Paris", "label": "LOCATION", "start": 16, "end": 21},
            ],
        }
    ]


def _minimal_pred(id_kb="2988507", source="GeoNames"):
    return [
        {
            "text": "Une explosion à Paris.",
            "entities": [
                {
                    "text": "Paris", "label": "LOCATION",
                    "start": 16, "end": 21,
                    "id_kb": id_kb, "source": source,
                },
            ],
        }
    ]


# --- OK cases -------------------------------------------------------------


def test_validator_accepts_well_formed_geonames():
    inp = _write_json(_minimal_input())
    pred = _write_json(_minimal_pred("2988507", "GeoNames"))
    assert validate(inp, pred) == 0


def test_validator_accepts_well_formed_mesh_descriptor():
    inp = _write_json([
        {"text": "Cas de cholera.", "entities": [
            {"text": "cholera", "label": "INF_DISEASE", "start": 8, "end": 15}
        ]}
    ])
    pred = _write_json([
        {"text": "Cas de cholera.", "entities": [
            {"text": "cholera", "label": "INF_DISEASE", "start": 8, "end": 15,
             "id_kb": "D002771", "source": "MeSH"}
        ]}
    ])
    assert validate(inp, pred) == 0


def test_validator_accepts_composite_mesh():
    inp = _write_json([
        {"text": "Test composite.", "entities": [
            {"text": "cancers", "label": "NON_INF_DISEASE", "start": 0, "end": 7}
        ]}
    ])
    pred = _write_json([
        {"text": "Test composite.", "entities": [
            {"text": "cancers", "label": "NON_INF_DISEASE", "start": 0, "end": 7,
             "id_kb": "D001943 & D002583", "source": "MeSH"}
        ]}
    ])
    assert validate(inp, pred) == 0


def test_validator_accepts_supplementary_concept():
    inp = _write_json([
        {"text": "Toxine.", "entities": [
            {"text": "APETx2", "label": "BIO_TOXIN", "start": 0, "end": 6}
        ]}
    ])
    pred = _write_json([
        {"text": "Toxine.", "entities": [
            {"text": "APETx2", "label": "BIO_TOXIN", "start": 0, "end": 6,
             "id_kb": "D009498 : C501880", "source": "MeSH"}
        ]}
    ])
    assert validate(inp, pred) == 0


def test_validator_accepts_nil():
    inp = _write_json(_minimal_input())
    pred = _write_json(_minimal_pred("", ""))
    assert validate(inp, pred) == 0


# --- Hard errors ----------------------------------------------------------


def test_validator_rejects_invalid_json():
    inp = _write_json(_minimal_input())
    pred = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
    pred.write_text("not valid json {", encoding="utf-8")
    assert validate(inp, pred) == 1


def test_validator_rejects_doc_count_mismatch():
    inp = _write_json(_minimal_input() * 2)  # 2 docs
    pred = _write_json(_minimal_pred("2988507", "GeoNames"))  # 1 doc
    assert validate(inp, pred) == 1


def test_validator_rejects_text_modified():
    inp = _write_json(_minimal_input())
    p = _minimal_pred()
    p[0]["text"] = "Texte modifié"
    pred = _write_json(p)
    assert validate(inp, pred) == 1


def test_validator_rejects_entity_count_mismatch():
    inp = _write_json(_minimal_input())
    p = _minimal_pred()
    p[0]["entities"].append({
        "text": "Inventé", "label": "LOCATION", "start": 0, "end": 7,
        "id_kb": "1", "source": "GeoNames",
    })
    pred = _write_json(p)
    assert validate(inp, pred) == 1


def test_validator_rejects_span_modified():
    inp = _write_json(_minimal_input())
    p = _minimal_pred()
    p[0]["entities"][0]["start"] = 0
    pred = _write_json(p)
    assert validate(inp, pred) == 1


def test_validator_rejects_invalid_source():
    inp = _write_json(_minimal_input())
    pred = _write_json(_minimal_pred("2988507", "geonames"))  # lowercase
    assert validate(inp, pred) == 1


def test_validator_rejects_geonames_non_digit():
    inp = _write_json(_minimal_input())
    pred = _write_json(_minimal_pred("D2988507", "GeoNames"))
    assert validate(inp, pred) == 1


def test_validator_rejects_mesh_bad_format():
    inp = _write_json([
        {"text": "x.", "entities": [
            {"text": "x", "label": "INF_DISEASE", "start": 0, "end": 1}
        ]}
    ])
    pred = _write_json([
        {"text": "x.", "entities": [
            {"text": "x", "label": "INF_DISEASE", "start": 0, "end": 1,
             "id_kb": "XYZ123", "source": "MeSH"}
        ]}
    ])
    assert validate(inp, pred) == 1


def test_validator_rejects_nil_with_id():
    inp = _write_json(_minimal_input())
    pred = _write_json(_minimal_pred("2988507", ""))  # NIL but has id
    assert validate(inp, pred) == 1


def test_validator_rejects_source_with_empty_id():
    inp = _write_json(_minimal_input())
    pred = _write_json(_minimal_pred("", "GeoNames"))  # source but no id
    assert validate(inp, pred) == 1


def test_validator_rejects_missing_id_kb_field():
    inp = _write_json(_minimal_input())
    p = _minimal_pred()
    del p[0]["entities"][0]["id_kb"]
    pred = _write_json(p)
    assert validate(inp, pred) == 1


def test_validator_rejects_missing_source_field():
    inp = _write_json(_minimal_input())
    p = _minimal_pred()
    del p[0]["entities"][0]["source"]
    pred = _write_json(p)
    assert validate(inp, pred) == 1
