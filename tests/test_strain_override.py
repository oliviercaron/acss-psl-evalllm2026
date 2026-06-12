"""Tests for the MeSH strain override (Phase 1 safety net).

Run: `python -m pytest tests/ -v`

Goal: lock the behaviour of `_resolve_strain_override` so future changes do
not silently introduce false positives on the test set. Critical cases :
- E. coli + strain marker + strain candidate available -> force strain
- Other pathogens + strain marker -> NO override (fallback LLM)
- E. coli + no strain marker -> NO override
- Plural "souches" must NOT trigger the override (avoids generic-context FP)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linker import MeSHLinker, LLMRerankerConfig


def _mesh():
    return MeSHLinker(llm_config=LLMRerankerConfig(enabled=True))


def test_strain_override_forces_ecoli_o104():
    """A context with 'souche' + a strain candidate (E. coli O104) forces
    the strain descriptor over the generic species.
    """
    m = _mesh()
    ctx = "Une souche d'E. coli responsable de cas groupes a ete identifiee"
    result = m._resolve_strain_override(ctx, ["D004926", "D000069981"])
    assert result == "D000069981"


def test_strain_override_meme_souche_phrase():
    """'la meme souche' counts as a strain indicator."""
    m = _mesh()
    ctx = "la bacterie est de la meme souche que celle precedemment isolee"
    result = m._resolve_strain_override(ctx, ["D004926", "D000069981"])
    assert result == "D000069981"


def test_strain_override_no_marker_returns_none():
    m = _mesh()
    ctx = "la bacterie E. coli est tres frequente dans la flore intestinale"
    result = m._resolve_strain_override(ctx, ["D004926", "D000069981"])
    assert result is None


def test_strain_override_plural_souches_does_not_trigger():
    """\\bsouche\\b must not match 'souches' (plural), so generic contexts
    like 'se premunir des souches pathogenes' fall back to the LLM."""
    m = _mesh()
    ctx = ("la plupart des bacteries E. coli ne sont pas nocives. "
           "Pour se premunir des souches pathogenes, le ministere...")
    result = m._resolve_strain_override(ctx, ["D004926", "D000069981"])
    assert result is None


def test_strain_override_salmonella_no_false_positive():
    """Even if the context mentions 'souche', if no candidate descriptor
    matches a strain key (o104/o157/ehec/stec), no override happens.
    This protects against false positives on other pathogens like Salmonella."""
    m = _mesh()
    ctx = "Une souche de Salmonella a ete isolee dans les prelevements"
    # D012475 = Salmonella (generic), no strain alternative passed
    result = m._resolve_strain_override(ctx, ["D012475", "D012480"])
    assert result is None


def test_strain_override_single_candidate_returns_none():
    m = _mesh()
    ctx = "souche d'E. coli O104:H4"
    result = m._resolve_strain_override(ctx, ["D000069981"])
    assert result is None


def test_strain_override_empty_context_returns_none():
    m = _mesh()
    result = m._resolve_strain_override("", ["D004926", "D000069981"])
    assert result is None


def test_strain_markers_regex_hits_serotype():
    m = _mesh()
    assert m._STRAIN_MARKERS.search("le serotype O157:H7 est responsable") is not None


def test_strain_markers_regex_hits_ehec():
    m = _mesh()
    assert m._STRAIN_MARKERS.search("infection EHEC confirmee en laboratoire") is not None
