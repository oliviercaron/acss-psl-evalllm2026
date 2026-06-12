"""Ablation: sensitivity of the listwise LLM to the GeoNames candidate-list size.

Isolates the candidate-count effect: context fixed at ±200, only
GeoNamesLinker.llm_config.max_candidates varies (MeSH untouched). Each config is
run --repeats times to separate the effect from LLM test-retest variance (±0.21,
cf. notes §17). Reports mean and range (min..max) of RANKING and GeoNames f1.

Usage:
  python experiments/sweep_candidates.py --cands 5,10,15,20 --repeats 2
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands", default="5,10,15,20")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--win", type=int, default=200)
    args = ap.parse_args()
    cand_values = [int(x) for x in args.cands.split(",")]

    from linker import EntityLinker
    from eval_linking import LinkingEvaluationPipeline

    gold = json.load(open(ROOT / "data" / "protected" / "train_evalLLM.json", encoding="utf-8"))
    pipe = LinkingEvaluationPipeline()

    def run_once(cands):
        el = EntityLinker(use_memory=False, use_llm_reranker=True)
        el.context_window = args.win
        el.geo.llm_config.max_candidates = cands   # vary GeoNames only
        pred = el.process_documents(gold)
        el.close()
        g = pipe.evaluate(gold, pred)
        kb = pipe.evaluate_by_kb(gold, pred)
        ranking = (g["partial_KB_accuracy"] + g["f1"]) / 2
        return ranking, kb.get("GeoNames", {}).get("f1"), kb.get("MeSH", {}).get("f1"), g["f1"]

    results = {}
    for cands in cand_values:
        runs = []
        for r in range(args.repeats):
            t0 = time.time()
            rk, gf1, mf1, f1 = run_once(cands)
            dt = time.time() - t0
            runs.append((rk, gf1, mf1, f1))
            print(f"[top-{cands} run {r+1}/{args.repeats}] RANKING={rk:.3f} "
                  f"GeoNames_f1={gf1} MeSH_f1={mf1} ({dt:.0f}s)", flush=True)
        results[cands] = runs

    print("\n" + "=" * 70)
    print(f"# Candidate-list size sweep (context ±{args.win}, GeoNames only, "
          f"{args.repeats} runs/config)")
    print("=" * 70)
    print(f"{'top-k':>6} | {'RANKING mean':>12} | {'range':>14} | {'GeoNames f1 mean':>16}")
    print("-" * 60)
    for cands in cand_values:
        rks = [x[0] for x in results[cands]]
        gf1s = [x[1] for x in results[cands] if x[1] is not None]
        mean_rk = statistics.mean(rks)
        rng = f"{min(rks):.3f}..{max(rks):.3f}"
        mean_gf1 = statistics.mean(gf1s) if gf1s else float("nan")
        print(f"{('top-'+str(cands)):>6} | {mean_rk:>12.3f} | {rng:>14} | {mean_gf1:>16.3f}")
    print("\n(anchors déjà connus : top-10 submission=91.42 ; top-10 ablation=91.635 ;"
          " top-30 @±600=91.21. Variance test-retest ≈ ±0.21.)")


if __name__ == "__main__":
    main()
