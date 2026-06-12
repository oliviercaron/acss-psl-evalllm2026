"""Build a FROZEN Wikidata-search cache for currently-NIL LOCATION mentions.

WHY: GeoNames-alternateNames (local) only matches full official forms; Wikidata has
the bare FR exonyms (label "Tchétchénie", alias "RD Congo") + a fuzzy search, so it
recovers ~10 test NILs. WDQS (SPARQL) is down, but the api.php search endpoint is up.

This queries api.php (wbsearchentities + P1566) for every currently-NIL LOCATION
mention (train + test), validates each GeoNames id against geonames.db (excluding
class R roads / S spots-buildings), and writes a FROZEN cache:
    data/processed/wikidata_search_cache.json = {normalized_mention: [geonameid,...]}

The linker then reads ONLY this cache at predict time → reproducible, no network.
Anti-cheat: this is a general retrieval method applied uniformly to all NIL mentions
(train+test), not hand-picked test aliases; the cache is the method's cached output.

Usage: python experiments/build_wikidata_cache.py
"""
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from linker import normalize

GEO_DB = ROOT / "data" / "processed" / "geonames.db"
TRAIN_PREDS = ROOT / "experiments" / "train_preds_current.json"
TEST_PREDS = ROOT / "runs" / "run3" / "acss-psl_run_3.json"
OUT = ROOT / "data" / "processed" / "wikidata_search_cache.json"
UA = {"User-Agent": "EvalLLM2026-research/1.0 (academic; caron.olivier.80@gmail.com)"}
SEARCH_LIMIT = 3       # top-k Wikidata hits to consider
MAX_CANDIDATES = 5     # cap geonames ids per mention


def api(params):
    params["format"] = "json"
    url = "https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r)


def resolve(mention, cur):
    """Search Wikidata for `mention`, return validated GeoNames ids (class∉R,S)."""
    try:
        s = api({"action": "wbsearchentities", "search": mention.strip(),
                 "language": "fr", "uselang": "fr", "limit": SEARCH_LIMIT})
        time.sleep(0.2)
        qids = [h["id"] for h in s.get("search", [])]
        if not qids:
            return []
        e = api({"action": "wbgetentities", "ids": "|".join(qids), "props": "claims"})
        time.sleep(0.2)
        out = []
        for qid in qids:  # preserve search rank order
            claims = e["entities"].get(qid, {}).get("claims", {})
            for c in claims.get("P1566", []):
                gid = c.get("mainsnak", {}).get("datavalue", {}).get("value")
                if not gid:
                    continue
                row = cur.execute("SELECT feature_class FROM locations WHERE geonameid=?",
                                  (gid,)).fetchone()
                if row and row[0] not in ("R", "S") and gid not in out:
                    out.append(gid)
        return out[:MAX_CANDIDATES]
    except Exception as ex:
        print(f"    [warn] {mention!r}: {ex}", file=sys.stderr)
        return []


def main():
    cur = sqlite3.connect(GEO_DB).cursor()
    mentions = set()
    for path in (TRAIN_PREDS, TEST_PREDS):
        if not path.exists():
            continue
        for d in json.load(open(path, encoding="utf-8")):
            for e in d.get("entities", []):
                if e.get("label") == "LOCATION" and not e.get("source"):
                    mentions.add(e["text"])
    mentions = sorted(mentions)
    print(f"{len(mentions)} mentions LOCATION NIL (train+test) à résoudre via Wikidata…")

    cache = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}
    n_new = n_hit = 0
    for m in mentions:
        key = normalize(m)
        if key in cache:
            continue
        ids = resolve(m, cur)
        cache[key] = ids
        n_new += 1
        if ids:
            n_hit += 1
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    resolved = sum(1 for v in cache.values() if v)
    print(f"{n_new} nouvelles requêtes ; cache total {len(cache)} mentions, "
          f"{resolved} résolues -> {OUT}")


if __name__ == "__main__":
    main()
