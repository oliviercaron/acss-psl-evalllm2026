"""Anti-cheating audit: classify every hardcoded mention->ID entry by whether it is
justified by the TRAIN gold, appears only in the TEST set (to scrutinize), or in
neither (a general/unused dictionary entry).

A hardcoded entry whose mention is in TEST but NOT in TRAIN is the cheating-risk
set: it must be justifiable as a *general* fact (a term any medical/geographic
lexicon would contain), otherwise it looks test-peeked.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from linker import (  # noqa: E402
    normalize, FR_MANUAL_DICT, LABEL_OVERRIDES, AMBIGUOUS_MENTIONS,
    FR_GEONAMES_ALIASES, GENTILE_TO_COUNTRY_ID, CONTINENT_ADJ_TO_ID,
)


def load(path):
    docs = json.load(open(path, encoding="utf-8"))
    gold, ments = {}, set()
    for d in docs:
        for e in d.get("entities", []):
            t = normalize(e["text"])
            ments.add(t)
            if e.get("id_kb"):
                gold.setdefault(t, set()).add(e["id_kb"])
    return gold, ments


train_gold, train_ments = load(ROOT / "data" / "protected" / "train_evalLLM.json")
_, test_ments = load(ROOT / "data" / "protected" / "test_evalLLM.json")
print(f"train mentions={len(train_ments)} (gold keys={len(train_gold)}) | test mentions={len(test_ments)}\n")


def audit(name, items):
    """items: list of (mention, id_or_None)."""
    buckets = {"TRAIN-JUSTIFIED": [], "TRAIN-other-id": [], "TEST-ONLY": [], "neither": []}
    for mention, idval in items:
        m = normalize(mention)
        in_tr, in_te = m in train_gold, m in test_ments
        if in_tr and (idval is None or idval in train_gold[m]):
            buckets["TRAIN-JUSTIFIED"].append(m)
        elif in_tr:
            buckets["TRAIN-other-id"].append(f"{m} (dict={idval}, gold={sorted(train_gold[m])})")
        elif in_te:
            buckets["TEST-ONLY"].append(f"{m} -> {idval}")
        else:
            buckets["neither"].append(m)
    print(f"### {name}: {len(items)} entries | "
          f"train-justified={len(buckets['TRAIN-JUSTIFIED'])} "
          f"train-other-id={len(buckets['TRAIN-other-id'])} "
          f"TEST-ONLY={len(buckets['TEST-ONLY'])} "
          f"neither={len(buckets['neither'])}")
    if buckets["TRAIN-other-id"]:
        print("  ⚠ TRAIN-other-id:")
        for x in buckets["TRAIN-other-id"]:
            print("     ", x)
    if buckets["TEST-ONLY"]:
        print("  🚩 TEST-ONLY (in test, NOT in train — scrutinize):")
        for x in buckets["TEST-ONLY"]:
            print("     ", x)
    print()


audit("FR_MANUAL_DICT", list(FR_MANUAL_DICT.items()))
audit("FR_GEONAMES_ALIASES", list(FR_GEONAMES_ALIASES.items()))
audit("GENTILE_TO_COUNTRY_ID", list(GENTILE_TO_COUNTRY_ID.items()))
audit("CONTINENT_ADJ_TO_ID", list(CONTINENT_ADJ_TO_ID.items()))
audit("LABEL_OVERRIDES", [(k[0], v) for k, v in LABEL_OVERRIDES.items()])
audit("AMBIGUOUS_MENTIONS", [(k[0], None) for k in AMBIGUOUS_MENTIONS])

# Wikidata cache (if present)
wk = ROOT / "data" / "processed" / "wikidata_search_cache.json"
if wk.exists():
    cache = json.load(open(wk, encoding="utf-8"))
    audit("wikidata_search_cache", [(k, (v[0] if isinstance(v, list) and v else None)) for k, v in cache.items()])
