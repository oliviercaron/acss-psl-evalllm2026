"""Correctness audit: resolve every hardcoded ID to its KB label (MeSH English
descriptor / GeoNames name+feature) so concept mismatches (e.g. mpox -> D008538 =
'Meige Syndrome') are visible. Auto-flags ids that are missing/inactive.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from linker import (  # noqa: E402
    FR_MESH_JSON, FR_MANUAL_DICT, LABEL_OVERRIDES, AMBIGUOUS_MENTIONS,
    FR_GEONAMES_ALIASES, GENTILE_TO_COUNTRY_ID, CONTINENT_ADJ_TO_ID,
)

recs = json.load(open(FR_MESH_JSON, encoding="utf-8"))
MESH = {r["id"]: r for r in recs if isinstance(r, dict) and "id" in r}


def mesh_label(idval):
    parts = re.findall(r"[DC]\d+", idval)
    out, flag = [], ""
    for p in parts:
        r = MESH.get(p)
        if not r:
            out.append(f"{p}=??NOT-FOUND"); flag = " 🚩"
        else:
            lbl = r.get("eng") or "(no eng)"
            act = "" if r.get("active") else " (INACTIVE)"
            out.append(f"{p}={lbl}{act}")
            if not r.get("active"):
                flag = " ⚠"
    return " | ".join(out) + flag


print("=" * 70)
print("MeSH ids  (mention -> id -> English descriptor)")
print("=" * 70)
for name, items in [("FR_MANUAL_DICT", FR_MANUAL_DICT.items()),
                    ("LABEL_OVERRIDES", {k[0]: v for k, v in LABEL_OVERRIDES.items()}.items())]:
    print(f"\n### {name} ###")
    for m, i in items:
        print(f"  {m:42.42} {i:22.22} {mesh_label(i)}")

print("\n### AMBIGUOUS_MENTIONS (candidate lists) ###")
for k, ids in AMBIGUOUS_MENTIONS.items():
    print(f"  {k[0]:42.42} {','.join(ids)}")
    for i in ids:
        print(f"      -> {mesh_label(i)}")

# ---- GeoNames ----
db = sqlite3.connect(ROOT / "data" / "processed" / "geonames.db")
cur = db.cursor()
cols = [c[1] for c in cur.execute("PRAGMA table_info(locations)").fetchall()]
print("\n" + "=" * 70)
print("GeoNames ids  (geonames cols:", cols, ")")
print("=" * 70)


def geo_label(gid):
    row = cur.execute(
        "SELECT name, feature_code, feature_class, country_code FROM locations WHERE geonameid=?",
        (gid,)).fetchone()
    return f"{row[0]} [{row[2]}.{row[1]}] cc={row[3]}" if row else "??NOT-FOUND 🚩"


for name, d in [("FR_GEONAMES_ALIASES", FR_GEONAMES_ALIASES),
                ("GENTILE_TO_COUNTRY_ID", GENTILE_TO_COUNTRY_ID),
                ("CONTINENT_ADJ_TO_ID", CONTINENT_ADJ_TO_ID)]:
    print(f"\n### {name} ###")
    for m, i in d.items():
        print(f"  {m:24.24} {i:10} {geo_label(i)}")
