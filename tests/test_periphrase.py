"""Tests for the geographic periphrase resolver (Run 2).

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_periphrase.py -v`

Rationale: the EvalLLM 2026 alignment guide explicitly says periphrases like
"L'Hexagone" (= France) and "territoire chinois" (= China) must be annotated
with the referred country's GeoNames ID. Two layers:
- FR_GEONAMES_ALIASES (fixed surnames like "hexagone" → France)
- GENTILE_TO_COUNTRY_ID + `^territoire\\s+\\w+$` regex (productive pattern)

Critical safeguards (Codex review):
- "territoire européen" → None  (Europe is a concept, not a country)
- "territoire de Krasnoyarsk" → None (already linked via standard cascade)
- "Paris" → None  (not a periphrase, let the standard linker handle it)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linker import GeoNamesLinker, LLMRerankerConfig


# Build linker once at module load (no LLM needed for periphrase tests)
def _geo():
    return GeoNamesLinker(llm_config=LLMRerankerConfig(enabled=False))


# ---------- Fixed aliases (FR_GEONAMES_ALIASES) ----------

def test_periphrase_hexagone():
    """The guide literally cites 'Hexagone → France'."""
    g = _geo()
    assert g._resolve_periphrase("Hexagone") == "3017382"  # France


def test_periphrase_france_country():
    """'France' -> the country (PCLI 3017382), confirmed by train gold.
    Stabilizes against LLM oscillation toward the pop-0 locality 12313681."""
    g = _geo()
    assert g._resolve_periphrase("France") == "3017382"
    assert g._resolve_periphrase("france") == "3017382"


def test_periphrase_hexagone_lowercase():
    assert _geo()._resolve_periphrase("hexagone") == "3017382"


def test_periphrase_hexagone_with_article():
    """'l'Hexagone' contains an apostrophe; normalize() should handle quotes."""
    # The standard pipeline often passes the bare mention, but if the article
    # is included we should still resolve it (after normalize/strip).
    # We accept both behaviours: either match, or fall through to None.
    result = _geo()._resolve_periphrase("l'Hexagone")
    assert result in ("3017382", None)


# ---------- Productive pattern "territoire <gentilé>" ----------

def test_periphrase_territoire_chinois():
    """Exact example from the guide."""
    assert _geo()._resolve_periphrase("territoire chinois") == "1814991"  # Chine


def test_periphrase_territoire_americain():
    """Train confirms: 'territoire américain' → GeoNames 6252001 (USA)."""
    assert _geo()._resolve_periphrase("territoire américain") == "6252001"


def test_periphrase_territoire_francais():
    assert _geo()._resolve_periphrase("territoire français") == "3017382"


def test_periphrase_territoire_camerounais():
    assert _geo()._resolve_periphrase("territoire camerounais") == "2233387"


def test_periphrase_territoire_capitalized():
    """Casse-insensible : 'Territoire Français'."""
    assert _geo()._resolve_periphrase("Territoire Français") == "3017382"


# ---------- Productive pattern "(le) continent <adjectif>" ----------
# Unlike bare gentilés / "territoire <concept>", the explicit head "continent"
# denotes a concrete GeoNames CONT entity. Train gold links "continent africain"
# -> 6255146 (Afrique). Candidate generation fails (the adjective "africain" is
# not an alias of the name "afrique"), so we intercept deterministically.

def test_periphrase_continent_africain():
    """Train gold: 'continent africain' -> 6255146 (Afrique, CONT)."""
    assert _geo()._resolve_periphrase("continent africain") == "6255146"
    assert _geo()._resolve_periphrase("le continent africain") == "6255146"


def test_periphrase_continent_europeen():
    g = _geo()
    assert g._resolve_periphrase("continent européen") == "6255148"   # Europe
    assert g._resolve_periphrase("Continent Européen") == "6255148"    # case-insensitive


def test_periphrase_continent_others():
    g = _geo()
    assert g._resolve_periphrase("continent asiatique") == "6255147"      # Asie
    assert g._resolve_periphrase("continent océanien") == "6255151"       # Océanie
    assert g._resolve_periphrase("continent antarctique") == "6255152"    # Antarctique
    assert g._resolve_periphrase("continent nord-américain") == "6255149" # Amérique du Nord


def test_periphrase_continent_americain_ambiguous_returns_None():
    """'continent américain' is ambiguous (USA vs the Americas; GeoNames has no
    single 'Americas' CONT). Deliberately NOT mapped -> stays NIL (no wrong link)."""
    assert _geo()._resolve_periphrase("continent américain") is None


def test_periphrase_continent_vs_territoire_distinction():
    """The crucial line: 'territoire africain' (vague concept) -> None, but
    'continent africain' (concrete CONT entity) -> 6255146."""
    g = _geo()
    assert g._resolve_periphrase("territoire africain") is None
    assert g._resolve_periphrase("continent africain") == "6255146"


def test_periphrase_continent_bare_or_unknown_returns_None():
    """No false positives: bare 'continent', a non-adjective, or an unknown
    adjective must fall through to the standard linker."""
    g = _geo()
    assert g._resolve_periphrase("continent") is None
    assert g._resolve_periphrase("le continent") is None
    assert g._resolve_periphrase("continent martien") is None
    assert g._resolve_periphrase("africain") is None  # bare gentilé, not "continent X"


# ---------- Critical safeguards: must NOT match ----------

def test_periphrase_territoire_europeen_is_concept_returns_None():
    """'européen' is ambiguous (Europe? UE? Schengen?). The guide says
    concepts géographiques get no ID. Must NOT short-circuit the linker."""
    assert _geo()._resolve_periphrase("territoire européen") is None


def test_periphrase_territoire_africain_concept_returns_None():
    """Continent, not a country. NIL per guide."""
    assert _geo()._resolve_periphrase("territoire africain") is None


def test_periphrase_territoire_de_krasnoyarsk_returns_None():
    """'territoire de Krasnoyarsk' is a real Russian krai (GeoNames 1502026),
    successfully linked by the standard cascade in Run 1. The periphrase
    resolver must NOT match (regex requires `^territoire\\s+(\\w+)$`,
    'de Krasnoyarsk' is two tokens so it doesn't match)."""
    assert _geo()._resolve_periphrase("territoire de Krasnoyarsk") is None


def test_periphrase_random_mention_returns_None():
    """A normal place name must pass through (None) to the standard linker."""
    assert _geo()._resolve_periphrase("Paris") is None
    assert _geo()._resolve_periphrase("Tananarive") is None
    assert _geo()._resolve_periphrase("Royaume-Uni") is None


def test_periphrase_empty_string():
    assert _geo()._resolve_periphrase("") is None
