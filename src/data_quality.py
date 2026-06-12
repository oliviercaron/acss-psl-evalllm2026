"""Data-quality audit of entity mentions — a control to run BEFORE building.

Surface artifacts can silently break the index lookup and leave an obviously
linkable mention NIL. The canonical case: the test set contains "Sierra Leone\\n\\n"
where \\n is the two literal characters backslash+n (not a newline) — no GeoNames
entry matches, so a *country* is wrongly NIL. `normalize()` now strips literal
escapes, but new artifacts can appear in future data; this module SURFACES them.

Categories detected (high-signal first):
  literal_escape    : literal \\n \\r \\t \\f  (data corruption — almost always a bug)
  html_entity       : &amp; &#39; ...           (unescaped HTML)
  control_char      : real control chars (<0x20)
  nbsp_or_zerowidth : non-breaking / zero-width / bidi marks
  double_space      : two+ consecutive spaces
  long_dash         : – — ‒ ― (vs ASCII hyphen)
  edge_punct        : starts/ends with a non-alphanumeric char
  case_glue         : lower→Upper with no separator (e.g. "SaintRomain"; noisy —
                      also matches legit acronyms like "NmC", so informational only)

CLI:  python src/data_quality.py train_evalLLM.json test_evalLLM.json
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# High-signal categories = unambiguous corruption worth a build-time warning.
HIGH_SIGNAL = ("literal_escape", "html_entity", "control_char", "nbsp_or_zerowidth")

ARTIFACT_CHECKS = {
    "literal_escape": lambda t: bool(re.search(r"\\[nrtf]", t)),
    "html_entity": lambda t: bool(re.search(r"&(?:[a-zA-Z]+|#\d+);", t)),
    "control_char": lambda t: any(ord(c) < 32 for c in t),
    "nbsp_or_zerowidth": lambda t: any(c in t for c in "\xa0 ​﻿‎‏"),
    "double_space": lambda t: "  " in t,
    "long_dash": lambda t: any(c in t for c in "‐‒–—―"),
    "edge_punct": lambda t: bool(t) and (not t[0].isalnum() or not t[-1].isalnum()),
    "case_glue": lambda t: any(a.islower() and b.isupper() for a, b in zip(t, t[1:])),
}


def scan_documents(documents: List[dict]) -> Dict[str, List[str]]:
    """Return {category: sorted unique mention texts} for artifacts found."""
    found: Dict[str, set] = defaultdict(set)
    for doc in documents:
        for ent in doc.get("entities", []):
            t = ent.get("text", "")
            for name, fn in ARTIFACT_CHECKS.items():
                if fn(t):
                    found[name].add(t)
    return {k: sorted(v) for k, v in found.items()}


def high_signal_summary(documents: List[dict]) -> str:
    """One-line summary of HIGH_SIGNAL artifacts (for build-time logging).

    Returns "" if none — callers can `if summary: logger.warning(...)`.
    """
    s = scan_documents(documents)
    hits = {k: s[k] for k in HIGH_SIGNAL if s.get(k)}
    if not hits:
        return ""
    return " ; ".join(f"{k}: {len(v)} ({', '.join(repr(x) for x in v[:3])}…)"
                      for k, v in hits.items())


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/data_quality.py <file.json> [file2.json ...]")
        sys.exit(1)
    for path in sys.argv[1:]:
        docs = json.load(open(path, encoding="utf-8"))
        report = scan_documents(docs)
        print("=" * 70)
        print(f"# {Path(path).name} — {len(docs)} docs")
        print("=" * 70)
        if not report:
            print("  (aucun artefact détecté)")
            continue
        for cat in list(ARTIFACT_CHECKS):
            if cat not in report:
                continue
            mark = "⚠️ " if cat in HIGH_SIGNAL else "   "
            print(f"{mark}{cat}: {len(report[cat])}")
            for m in report[cat][:10]:
                print(f"      {m!r}")


if __name__ == "__main__":
    main()
