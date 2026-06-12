"""Regenerate the cached Run 3 baseline predictions on the train set.

Several diagnostics (error_analysis.py, error_patterns.py,
geo_candidate_diagnostic.py, test_prefix_fcode_rule.py) operate POST-HOC on a
frozen baseline prediction file so their results are deterministic and isolated
from LLM test-retest variance. That cache is gitignored and regenerated here.

Config = Run 3: use_memory=False (no train leakage), LLM reranker ON, default
context_window=±200, max_candidates=10. Writes experiments/train_preds_llm.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
# Optional output path (sys.argv[1]); default = the top-10-era baseline cache.
# NB: the default reflects whatever EntityLinker defaults to NOW (top-5 + all the
# coverage rules). To regenerate the FROZEN top-10 baseline used by §6.1/§7, that
# code state would be needed — keep the existing file; write fresh runs elsewhere.
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "experiments" / "train_preds_llm.json"


def main():
    from linker import EntityLinker

    with open(ROOT / "data" / "protected" / "train_evalLLM.json", encoding="utf-8") as f:
        gold = json.load(f)

    el = EntityLinker(use_memory=False, use_llm_reranker=True)
    pred = el.process_documents(gold)
    el.close()

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(pred, f, ensure_ascii=False)
    print(f"Wrote {len(pred)} docs -> {OUT}")


if __name__ == "__main__":
    main()
