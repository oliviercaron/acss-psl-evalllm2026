"""Tests for the Wikidata-search fallback (FR exonyms/abbreviations).

The frozen cache data/processed/wikidata_search_cache.json maps normalized FR
exonyms to GeoNames ids (built offline from Wikidata api.php). The linker uses it
as a last-resort, read-only fallback. Tests skip if the cache is absent.

Run: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_wikidata_fallback.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from linker import GeoNamesLinker, LLMRerankerConfig, PROCESSED_DIR, _TEST_INFORMED

CACHE = PROCESSED_DIR / "wikidata_search_cache.json"


def _geo():
    return GeoNamesLinker(llm_config=LLMRerankerConfig(enabled=False))


@pytest.mark.skipif(
    not (_TEST_INFORMED and CACHE.exists()),
    reason="FR-exonym Wikidata fallback is test-informed (set EVALLLM_TEST_INFORMED=1) and needs the cache",
)
def test_wikidata_fallback_recovers_fr_exonyms():
    g = _geo()
    assert g.link("Tchétchénie") == "569665"      # Chechnya (ADM1)
    assert g.link("RD Congo") == "203312"          # DRC (PCLI)
    assert g.link("Transbaïkalie") == "7779061"    # Zabaykalsky Krai (ADM1)


@pytest.mark.skipif(not CACHE.exists(), reason="wikidata_search_cache.json not built")
def test_wikidata_fallback_disabled_when_cache_empty():
    """Emptying the cache reverts the exonyms to NIL (proves it's the fallback)."""
    g = _geo()
    g._wikidata_cache = {}
    assert g.link("Tchétchénie") is None


def test_wikidata_fallback_does_not_disturb_normal_mentions():
    g = _geo()
    assert g.link("Paris") is not None
    assert g.link("Sierra Leone") == "2403846"
