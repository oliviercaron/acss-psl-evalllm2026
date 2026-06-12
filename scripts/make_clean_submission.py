"""Produce a TEST-INFORMED-FREE ("clean") submission from the current Run 3 by
deterministically reverting to NIL every prediction that came from a test-informed
source: (a) the Wikidata exonym cache, (b) the Marburg / TBE / VHC clusters that
were hand-added after inspecting the test (task #12).

Deterministic surgical revert — no LLM re-run, so the clean run = Run 3 minus exactly
the test-informed contributions (no re-roll variance). The general medical lexicon,
train/guide-justified aliases, and the mpox/anthracis bug-fixes are KEPT.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from linker import normalize  # noqa: E402

RUN3 = ROOT / "runs" / "run3" / "acss-psl_run_3.json"
OUT_DIR = ROOT / "runs" / "run_clean"
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "acss-psl_run_clean.json"

# --- the test-informed (normalized mention, id) pairs to revert ---
pairs = set()
# Marburg disease cluster -> D008379  (hand-added test surface variants)
for m in ["fièvre de marburg", "fievre de marburg", "fièvre à virus de marburg",
          "fièvre hémorragique à virus de marburg", "fievre hemorragique a virus de marburg",
          "maladie à virus de marburg", "maladie a virus de marburg"]:
    pairs.add((normalize(m), "D008379"))
# TBE cluster
for m in ["tbe", "encéphalite à tique", "encephalite a tique", "méningoencéphalite à tique",
          "meningoencephalite a tique", "méningoencéphalite à tiques"]:
    pairs.add((normalize(m), "D004675"))
pairs.add((normalize("tbev"), "D004669"))
# Marburg LABEL_OVERRIDES (pathogen / disease)
pairs.add((normalize("marburg"), "D029024"))
pairs.add((normalize("marburg"), "D008379"))
# VHC LABEL_OVERRIDES
pairs.add((normalize("vhc"), "D016174"))
pairs.add((normalize("vhc"), "D006526"))
# Wikidata exonym cache (every cached mention -> every cached id)
cache = json.load(open(ROOT / "data" / "processed" / "wikidata_search_cache.json", encoding="utf-8"))
for m, ids in cache.items():
    for i in ids:
        pairs.add((normalize(m), i))

sub = json.load(open(RUN3, encoding="utf-8"))
reverted = []
for doc in sub:
    for e in doc.get("entities", []):
        if e.get("id_kb") and (normalize(e["text"]), e["id_kb"]) in pairs:
            reverted.append((e["text"], e["id_kb"]))
            e["id_kb"] = ""
            e["source"] = ""

json.dump(sub, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

n_ents = sum(len(d["entities"]) for d in sub)
n_link = sum(1 for d in sub for e in d["entities"] if e["source"])
print(f"Reverted {len(reverted)} predictions -> NIL:")
for (t, i), c in sorted(Counter(reverted).items(), key=lambda x: -x[1]):
    print(f"   {t!r:42} {i}  x{c}")
print(f"\nClean submission: {n_ents} entities, {n_link} linked, {n_ents - n_link} NIL "
      f"({100*(n_ents-n_link)/n_ents:.2f}% NIL) -> {OUT}")
