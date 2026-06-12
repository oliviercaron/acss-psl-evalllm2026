"""LLM test-retest variance experiment (for the article).

Runs the SAME Run 3 pipeline (--no-memory --llm-reranker) N times on the train
set and measures how much the LLM listwise reranker's stochasticity (at
temperature=0) perturbs (a) per-entity predictions and (b) the final ranking.

Motivation: even at temperature=0, the OpenAI API is not deterministic
(server-side batching, MoE routing, GPU float non-associativity). We quantify
this to (1) report reproducibility honestly and (2) justify deterministic
rule-based stabilization over costly self-consistency voting.

Usage: python experiments/llm_variance.py [N]   (default N=3)
Outputs a markdown summary to stdout (capture into notes/).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from linker import EntityLinker  # noqa: E402


def ranking_of(gold, pred):
    from eval_linking import LinkingEvaluationPipeline
    pipe = LinkingEvaluationPipeline()
    g = pipe.evaluate(gold, pred)
    return (g["partial_KB_accuracy"] + g["f1"]) / 2, g["f1"], g["partial_KB_accuracy"]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    train_path = ROOT / "data" / "protected" / "train_evalLLM.json"
    with open(train_path, encoding="utf-8") as f:
        gold = json.load(f)

    runs = []          # list of prediction lists
    rankings = []      # list of (ranking, f1, pkb)
    for i in range(n):
        linker = EntityLinker(use_memory=False, use_llm_reranker=True)
        # Safety against the intermittent network hang seen on big builds:
        # shorten the per-call timeout so a stalled call fails fast (the mention
        # becomes NIL for that run) instead of blocking the whole experiment.
        linker.geo.llm_config.request_timeout = 30
        linker.mesh.llm_config.request_timeout = 30
        pred = linker.process_documents(gold)
        linker.close()
        runs.append(pred)
        r = ranking_of(gold, pred)
        rankings.append(r)
        print(f"[run {i+1}/{n}] ranking={r[0]:.2f}  f1={r[1]:.2f}  pKB={r[2]:.2f}",
              file=sys.stderr)

    # Per-entity stability: collect the set of (source/id) seen across runs for
    # each entity position (doc i, entity j).
    n_entities = sum(len(d.get("entities", [])) for d in gold)
    n_unstable = 0
    unstable_examples = []
    for di in range(len(gold)):
        for ej in range(len(gold[di].get("entities", []))):
            seen = set()
            for pred in runs:
                e = pred[di]["entities"][ej]
                seen.add(f"{e.get('source','')}/{e.get('id_kb','')}")
            if len(seen) > 1:
                n_unstable += 1
                if len(unstable_examples) < 25:
                    txt = gold[di]["entities"][ej]["text"]
                    lbl = gold[di]["entities"][ej]["label"]
                    unstable_examples.append((di, txt, lbl, sorted(seen)))

    ranks = [r[0] for r in rankings]
    print("\n" + "=" * 60)
    print("# LLM test-retest variance — train, N={} runs".format(n))
    print("=" * 60)
    print(f"\nRanking per run : {[f'{r:.2f}' for r in ranks]}")
    print(f"Ranking min/max : {min(ranks):.2f} / {max(ranks):.2f}  "
          f"(spread {max(ranks)-min(ranks):.2f})")
    print(f"Ranking mean    : {sum(ranks)/len(ranks):.2f}")
    print(f"\nEntities total          : {n_entities}")
    print(f"Entities unstable (id varies across runs): {n_unstable} "
          f"({100*n_unstable/n_entities:.2f}%)")
    print("\nUnstable examples:")
    for di, txt, lbl, seen in unstable_examples:
        print(f"  doc#{di} {txt!r} [{lbl}]: {seen}")


if __name__ == "__main__":
    main()
