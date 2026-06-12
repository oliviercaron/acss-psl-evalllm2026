"""Tests for the literal-escape normalize fix + the data-quality audit.

Run: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_data_quality.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linker import normalize
import data_quality


# ---------- normalize() strips literal escape sequences ----------

def test_normalize_strips_literal_backslash_n():
    """The test set has 'Sierra Leone\\n\\n' with the 2 chars backslash+n."""
    assert normalize("Sierra Leone\\n\\n") == "sierra leone"
    assert normalize("province de Hubei\\n\\n") == "province de hubei"


def test_normalize_strips_literal_r_t_f():
    assert normalize("Paris\\t") == "paris"
    assert normalize("Lyon\\r\\n") == "lyon"


def test_normalize_collapses_whitespace_and_nbsp():
    assert normalize("Sierra   Leone") == "sierra leone"      # double space
    assert normalize("Sierra Leone") == "sierra leone"   # non-breaking space
    assert normalize("  Paris  ") == "paris"                  # trim


def test_normalize_preserves_normal_names():
    """Must not damage legit mentions (no false stripping)."""
    assert normalize("Saint-Romain-en-Jarez") == "saint-romain-en-jarez"
    assert normalize("L’Hexagone") == "l'hexagone"            # smart quote
    assert normalize("Nouvelle-Aquitaine") == "nouvelle-aquitaine"


# ---------- data_quality audit ----------

def test_scan_detects_literal_escape():
    docs = [{"entities": [{"text": "Sierra Leone\\n\\n", "label": "LOCATION"}]}]
    report = data_quality.scan_documents(docs)
    assert "Sierra Leone\\n\\n" in report.get("literal_escape", [])


def test_high_signal_summary_empty_when_clean():
    docs = [{"entities": [{"text": "Paris", "label": "LOCATION"},
                          {"text": "Sierra Leone", "label": "LOCATION"}]}]
    assert data_quality.high_signal_summary(docs) == ""


def test_high_signal_summary_flags_artifacts():
    docs = [{"entities": [{"text": "Sierra Leone\\n\\n", "label": "LOCATION"}]}]
    summary = data_quality.high_signal_summary(docs)
    assert "literal_escape" in summary
