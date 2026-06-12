"""Self-consistency (majority-vote) benchmark for the LLM reranker.

Monkeypatches EntityLinker._llm_rerank / _llm_rerank_mesh with a voting version:
N independent calls at temperature>0 (guided-choice → clean valid indices), then
majority vote. linker.py itself is UNTOUCHED (submission path unaffected).

Run (server must already serve a model via vLLM + SSH tunnel on :8000):
  VOTE_N=5 VOTE_TEMP=0.6 LLM_BASE_URL=http://localhost:8000/v1 \
    LLM_MODEL=RedHatAI/gemma-4-31B-it-FP8-Dynamic OPENAI_API_KEY=EMPTY \
    python experiments/bench_vote.py
"""
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import linker as L
from linker import EntityLinker

VOTE_N = int(os.environ.get("VOTE_N", "5"))
VOTE_TEMP = float(os.environ.get("VOTE_TEMP", "0.6"))


def _vote(client, model, prompt, n_cands, cfg):
    """N guided calls at temperature>0; return the majority candidate index or None."""
    choices = []
    for _ in range(VOTE_N):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=16,
                temperature=VOTE_TEMP,
                timeout=cfg.request_timeout,
                extra_body={"structured_outputs": {"choice": [str(i) for i in range(n_cands)]}},
            )
            content = (resp.choices[0].message.content or "").strip()
            m = re.match(r"\d+", content)
            if m:
                v = int(m.group())
                if 0 <= v < n_cands:
                    choices.append(v)
        except Exception as e:  # noqa: BLE001
            L.logger.debug("vote call failed: %s", e)
    if not choices:
        return None
    return Counter(choices).most_common(1)[0][0]


def _vote_geo(self, mention, context, candidates):
    client = self._get_llm_client()
    if client is None:
        return None
    cfg = self.llm_config
    cands = candidates[:cfg.max_candidates]
    prompt = self._build_rerank_prompt(mention, context[:cfg.context_chars], cands)
    model = os.environ.get("LLM_MODEL") or cfg.model
    idx = _vote(client, model, prompt, len(cands), cfg)
    return cands[idx]["id"] if idx is not None else None


def _vote_mesh(self, mention, label, context, candidates):
    forced = self._resolve_strain_override(context, candidates)
    if forced:
        return forced
    client = self._get_llm_client()
    if client is None:
        return None
    cfg = self.llm_config
    cands = candidates[:cfg.max_candidates]
    prompt = self._build_mesh_rerank_prompt(mention, label, context[:cfg.context_chars], cands)
    model = os.environ.get("LLM_MODEL") or cfg.model
    idx = _vote(client, model, prompt, len(cands), cfg)
    return cands[idx] if idx is not None else None


if __name__ == "__main__":
    EntityLinker._llm_rerank = _vote_geo
    EntityLinker._llm_rerank_mesh = _vote_mesh
    print(f"=== majority-vote benchmark: VOTE_N={VOTE_N}, VOTE_TEMP={VOTE_TEMP}, "
          f"model={os.environ.get('LLM_MODEL')} ===")
    L.evaluate_on_train(use_memory=False, use_llm_reranker=True)
