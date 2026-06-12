"""Tests for Run 3 additions.

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_run3_additions.py -v`

Covers:
- Tier 1 dictionary additions (Marburg cluster, TBE/TBEV, sub-regions UN).
- Tier 1 label overrides (Marburg DIS_REF_TO_PATH, VHC by label).
- Tier 2 acronym-definition propagation mechanism (CRE, SG) with FP guards.

All MeSH/GeoNames IDs were verified against the local indexes and (for the
sub-regions) against the train gold, before being added.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linker import (
    EntityLinker, GeoNamesLinker, MeSHLinker, LLMRerankerConfig, _TEST_INFORMED,
)

# Marburg/TBE/VHC are test-informed extras, OFF by default (EVALLLM_TEST_INFORMED=1
# reinstates them); their tests skip in the clean default pipeline. The sub-region
# (train-justified) and acronym (general mechanism) tests below always run.
_skip_ti = pytest.mark.skipif(
    not _TEST_INFORMED,
    reason="test-informed (Marburg/TBE/VHC) off by default; set EVALLLM_TEST_INFORMED=1",
)


@pytest.fixture(scope="module")
def mesh():
    return MeSHLinker(llm_config=LLMRerankerConfig(enabled=False))


@pytest.fixture(scope="module")
def geo():
    return GeoNamesLinker(llm_config=LLMRerankerConfig(enabled=False))


# ---------- Tier 1: Marburg cluster (MeSH) ----------

@_skip_ti
@pytest.mark.parametrize("mention,label,expected", [
    ("fièvre de Marburg", "INF_DISEASE", "D008379"),
    ("maladie à virus de Marburg", "INF_DISEASE", "D008379"),
    ("fièvre hémorragique à virus de Marburg", "INF_DISEASE", "D008379"),
    ("fièvre à virus de Marburg", "INF_DISEASE", "D008379"),
    ("Marburg", "INF_DISEASE", "D008379"),       # disease
    ("Marburg", "DIS_REF_TO_PATH", "D029024"),   # pathogen (label override)
])
def test_marburg(mesh, mention, label, expected):
    assert mesh.link(mention, label, "") == expected


# ---------- Tier 1: tick-borne encephalitis (MeSH) ----------

@_skip_ti
@pytest.mark.parametrize("mention,label,expected", [
    ("TBE", "INF_DISEASE", "D004675"),
    ("encéphalite à tique", "INF_DISEASE", "D004675"),       # singular variant
    ("méningoencéphalite à tique", "INF_DISEASE", "D004675"),
    ("TBEV", "PATHOGEN", "D004669"),                          # virus
])
def test_tbe(mesh, mention, label, expected):
    assert mesh.link(mention, label, "") == expected


# ---------- Tier 1: VHC by label (MeSH) ----------

@_skip_ti
def test_vhc_pathogen(mesh):
    assert mesh.link("VHC", "PATHOGEN", "") == "D016174"      # Hepacivirus


@_skip_ti
def test_vhc_path_ref_to_dis(mesh):
    assert mesh.link("VHC", "PATH_REF_TO_DIS", "") == "D006526"  # Hepatitis C


# ---------- Tier 1: UN macro-regions (GeoNames, train-gold-confirmed) ----------

@pytest.mark.parametrize("mention,expected", [
    ("Amérique latine", "7730009"),   # Latin America and the Caribbean
    ("Caraïbes", "7729891"),          # Caribbean
    ("Europe orientale", "7729884"),  # Eastern Europe
])
def test_un_subregions(geo, mention, expected):
    assert geo.link(mention, "") == expected


# ---------- Tier 2: acronym-definition propagation ----------

@pytest.fixture(scope="module")
def linker():
    el = EntityLinker(use_memory=False, use_llm_reranker=False)
    yield el
    el.close()


def test_acronym_cre_propagated(linker):
    """CRE <- 'carbapenem-resistant Enterobacteriaceae (CRE)' (same label)."""
    text = "la famille des carbapenem-resistant Enterobacteriaceae (CRE), détectée"
    ents = [
        {"text": "carbapenem-resistant Enterobacteriaceae", "label": "PATHOGEN",
         "id_kb": "D000073182", "source": "MeSH"},
        {"text": "CRE", "label": "PATHOGEN", "id_kb": "", "source": ""},
    ]
    linker._propagate_acronym_definitions(text, ents)
    assert ents[1]["source"] == "MeSH"
    assert ents[1]["id_kb"] == "D000073182"


def test_acronym_sg_propagated(linker):
    """SG <- 'syphilis congénitale (SG)' (same label INF_DISEASE)."""
    text = "morts à cause de la syphilis congénitale (SG), sur plusieurs cas"
    ents = [
        {"text": "syphilis congénitale", "label": "INF_DISEASE",
         "id_kb": "D013590", "source": "MeSH"},
        {"text": "SG", "label": "INF_DISEASE", "id_kb": "", "source": ""},
    ]
    linker._propagate_acronym_definitions(text, ents)
    assert ents[1]["id_kb"] == "D013590"


def test_acronym_different_label_not_propagated(linker):
    """FP guard: a PATHOGEN acronym must NOT inherit a disease-labelled id."""
    text = "le virus de l'hépatite C (VHC) circule"
    ents = [
        {"text": "hépatite C", "label": "INF_DISEASE", "id_kb": "D006526", "source": "MeSH"},
        {"text": "VHC", "label": "PATHOGEN", "id_kb": "", "source": ""},
    ]
    linker._propagate_acronym_definitions(text, ents)
    assert ents[1]["source"] == ""  # not propagated (label mismatch)


def test_acronym_no_parenthetical_not_propagated(linker):
    """FP guard: no 'X (ACR)' definition in text -> no propagation."""
    text = "Paris et IDF sont touchés cette année"
    ents = [
        {"text": "Île-de-France", "label": "LOCATION", "id_kb": "2971090", "source": "GeoNames"},
        {"text": "IDF", "label": "LOCATION", "id_kb": "", "source": ""},
    ]
    linker._propagate_acronym_definitions(text, ents)
    assert ents[1]["source"] == ""  # not propagated (no definition)


def test_acronym_with_parenthetical_propagated(linker):
    """IDF <- 'Île-de-France (IDF)' (LOCATION)."""
    text = "vivant en Île-de-France (IDF) selon l'étude ANRS"
    ents = [
        {"text": "Île-de-France", "label": "LOCATION", "id_kb": "2971090", "source": "GeoNames"},
        {"text": "IDF", "label": "LOCATION", "id_kb": "", "source": ""},
    ]
    linker._propagate_acronym_definitions(text, ents)
    assert ents[1]["source"] == "GeoNames"
    assert ents[1]["id_kb"] == "2971090"


def test_acronym_no_linked_entities_noop(linker):
    """No linked entities at all -> method is a safe no-op."""
    text = "ABC (DEF) something"
    ents = [{"text": "DEF", "label": "PATHOGEN", "id_kb": "", "source": ""}]
    linker._propagate_acronym_definitions(text, ents)
    assert ents[0]["source"] == ""
