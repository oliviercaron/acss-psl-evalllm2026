"""Tests for the GeoNames coverage fallbacks (end-of-cascade, general rules).

Rule 1 (hyphen↔space) and Rule 2 (bare admin-prefix strip) only fire when the
normal cascade returns NIL, and never link an over-precise class R/S entry
(streets/buildings). Run:
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_coverage_fallbacks.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from linker import GeoNamesLinker, LLMRerankerConfig


def _geo():
    return GeoNamesLinker(llm_config=LLMRerankerConfig(enabled=False))


def test_hyphen_space_fallback_grande_comore():
    """'Grande-Comore' (hyphen) → 'Grande Comore' (space) = 921882 (ADM1)."""
    g = _geo()
    assert g.link("Grande-Comore") == "921882"


def test_bare_admin_prefix_region_nouvelle_aquitaine():
    """'région Nouvelle-Aquitaine' (no 'de') → strip → 'Nouvelle-Aquitaine' = 11071620."""
    g = _geo()
    assert g.link("région Nouvelle-Aquitaine") == "11071620"


def test_fallback_never_links_a_street():
    """'rue Sergent-Blandan' must stay NIL (street = class R, NIL per guide),
    even though the hyphen↔space variant matches a GeoNames street entry."""
    g = _geo()
    assert g.link("rue Sergent-Blandan") is None


def test_fallback_is_off_switch_works():
    """With coverage_fallbacks disabled, the recovered mentions go back to NIL
    (proves the recovery is due to the fallback, not the normal cascade)."""
    g = _geo()
    g.coverage_fallbacks = False
    assert g.link("Grande-Comore") is None
    assert g.link("région Nouvelle-Aquitaine") is None


def test_fallback_does_not_disturb_normal_mentions():
    """A mention that already links via the normal cascade is unchanged."""
    g = _geo()
    assert g.link("Paris") is not None        # links with or without fallbacks
    assert g.link("Sierra Leone") == "2403846"
