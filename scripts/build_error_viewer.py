"""Build a standalone HTML viewer of all Run 3 errors on the train set.

For every mistake (WRONG_ID / MISSED / SPURIOUS) it shows the FULL document text
with the offending mention highlighted, the gold vs predicted link (clickable
GeoNames / MeSH), and — for GeoNames LOCATION errors — the candidate pool that
was actually generated (so you can see whether the gold was even available, and
at which rank). Self-contained: open reports/error_viewer.html in any browser.

Usage: python experiments/build_error_viewer.py
"""
import html
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
TRAIN = ROOT / "train_evalLLM.json"
# Predictions file (sys.argv[1] overrides) — point at a current-program run to
# refresh the viewer for the latest code.
PREDS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "experiments" / "train_preds_llm.json"
GEO_DB = ROOT / "data" / "processed" / "geonames.db"
OUT = ROOT / "reports" / "error_viewer.html"


def geo_meta(cur, gid):
    r = list(cur.execute(
        "SELECT name, country_code, feature_code, population FROM locations "
        "WHERE geonameid=?", (gid,)))
    if not r:
        return None
    return {"name": r[0][0], "cc": r[0][1], "fcode": r[0][2], "pop": r[0][3]}


def link_html(source, idkb):
    if not source or not idkb:
        return '<span class="nil">NIL</span>'
    if source == "GeoNames":
        url = f"https://www.geonames.org/{idkb}"
        return f'<a href="{url}" target="_blank">GeoNames/{html.escape(idkb)}</a>'
    if source == "MeSH":
        parts = []
        for tok in str(idkb).replace("&", " ").replace(":", " ").split():
            tok = tok.strip()
            if not tok:
                continue
            url = f"https://meshb.nlm.nih.gov/record/ui?ui={tok}"
            parts.append(f'<a href="{url}" target="_blank">{html.escape(tok)}</a>')
        return f'MeSH/{" & ".join(parts)}' if parts else html.escape(str(idkb))
    return html.escape(f"{source}/{idkb}")


def highlight(text, spans):
    """Return HTML of `text` with the [start,end) char spans wrapped in <mark>."""
    cuts = sorted(set([0, len(text)] + [s for s, _ in spans] + [e for _, e in spans]))
    span_set = {(s, e) for s, e in spans}
    out = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        chunk = html.escape(text[a:b])
        inside = any(s <= a and b <= e for s, e in span_set)
        out.append(f'<mark>{chunk}</mark>' if inside else chunk)
    return "".join(out)


def main():
    conn = sqlite3.connect(GEO_DB)
    cur = conn.cursor()

    from linker import (GeoNamesLinker, normalize, strip_prefix,
                        remove_accents, LLMRerankerConfig)
    geo = GeoNamesLinker(llm_config=LLMRerankerConfig(enabled=False))

    def pool_for(mention):
        norm = normalize(mention)
        for key in (norm, strip_prefix(norm), remove_accents(norm),
                    remove_accents(strip_prefix(norm))):
            c = geo._query_candidates(key)
            if c:
                return c
        words = norm.split()
        if len(words) >= 3:
            for i in range(len(words) - 1, 0, -1):
                c = geo._query_candidates(" ".join(words[i:]))
                if c:
                    return c
        return []

    gold = json.load(open(TRAIN, encoding="utf-8"))
    preds = json.load(open(PREDS, encoding="utf-8"))

    errors = []
    for di, (gdoc, pdoc) in enumerate(zip(gold, preds)):
        text = gdoc.get("text", "")
        for ge, pe in zip(gdoc["entities"], pdoc["entities"]):
            g_src, g_id = ge.get("source", ""), ge.get("id_kb", "")
            p_src, p_id = pe.get("source", ""), pe.get("id_kb", "")
            if (g_src, g_id) == (p_src, p_id):
                continue
            if g_src and p_src and g_id != p_id:
                cat = "WRONG_ID"
            elif g_src and not p_src:
                cat = "MISSED"
            elif not g_src and p_src:
                cat = "SPURIOUS"
            else:
                cat = "OTHER"
            kb = g_src or p_src or "NIL"
            label = ge["label"]
            starts = ge["start"] if isinstance(ge["start"], list) else [ge["start"]]
            ends = ge["end"] if isinstance(ge["end"], list) else [ge["end"]]
            spans = list(zip(starts, ends))

            # GeoNames candidate pool (LOCATION only) with gold/pred flags + rank
            pool_rows = []
            if kb == "GeoNames" or label == "LOCATION":
                pool = pool_for(ge["text"])
                for rank, c in enumerate(pool[:25], 1):
                    flag = ""
                    if g_id and c["id"] == g_id:
                        flag = "gold"
                    elif p_id and c["id"] == p_id:
                        flag = "pred"
                    pool_rows.append({
                        "rank": rank, "id": c["id"], "name": c["name"],
                        "cc": c["cc"], "fcode": c["fcode"], "pop": c["pop"],
                        "flag": flag})
                if g_id and not any(r["id"] == g_id for r in pool_rows) and g_src == "GeoNames":
                    # gold beyond rank 25 or absent: note it
                    full_ids = [c["id"] for c in pool]
                    note = (f"rank {full_ids.index(g_id)+1}/{len(full_ids)}"
                            if g_id in full_ids else "ABSENT from pool")
                    pool_rows.append({"rank": "", "id": g_id, "name": "(gold)",
                                      "cc": "", "fcode": "", "pop": note, "flag": "gold"})

            gmeta = geo_meta(cur, g_id) if g_src == "GeoNames" and g_id else None
            pmeta = geo_meta(cur, p_id) if p_src == "GeoNames" and p_id else None
            errors.append({
                "doc": di, "cat": cat, "kb": kb, "label": label,
                "mention": ge["text"],
                "g_src": g_src, "g_id": g_id, "p_src": p_src, "p_id": p_id,
                "g_link": link_html(g_src, g_id), "p_link": link_html(p_src, p_id),
                "g_meta": gmeta, "p_meta": pmeta,
                "text_html": highlight(text, spans),
                "pool": pool_rows,
            })

    # Build HTML
    counts = {}
    for e in errors:
        counts[e["cat"]] = counts.get(e["cat"], 0) + 1
    cards = []
    for idx, e in enumerate(errors):
        meta_g = (f' <span class="meta">[{e["g_meta"]["fcode"]}, {e["g_meta"]["cc"]}, '
                  f'pop {e["g_meta"]["pop"]:,}]</span>' if e["g_meta"] else "")
        meta_p = (f' <span class="meta">[{e["p_meta"]["fcode"]}, {e["p_meta"]["cc"]}, '
                  f'pop {e["p_meta"]["pop"]:,}]</span>' if e["p_meta"] else "")
        pool_html = ""
        if e["pool"]:
            rows = []
            for r in e["pool"]:
                cls = r["flag"]
                pop = f'{r["pop"]:,}' if isinstance(r["pop"], int) else r["pop"]
                tag = (' <b>← GOLD</b>' if r["flag"] == "gold"
                       else ' <b>← PRED</b>' if r["flag"] == "pred" else "")
                rows.append(
                    f'<tr class="{cls}"><td>{r["rank"]}</td>'
                    f'<td><a href="https://www.geonames.org/{r["id"]}" target="_blank">{r["id"]}</a></td>'
                    f'<td>{html.escape(str(r["name"]))}</td><td>{html.escape(str(r["cc"]))}</td>'
                    f'<td>{html.escape(str(r["fcode"]))}</td><td>{pop}{tag}</td></tr>')
            pool_html = (
                '<details><summary>Candidats GeoNames générés '
                f'({len([r for r in e["pool"] if r["rank"]])})</summary>'
                '<table class="pool"><tr><th>#</th><th>id</th><th>nom</th>'
                '<th>pays</th><th>fcode</th><th>population</th></tr>'
                + "".join(rows) + "</table></details>")
        cards.append(f'''
<div class="card" data-cat="{e['cat']}" data-kb="{e['kb']}" data-label="{e['label']}"
     data-search="{html.escape((e['mention'] + ' ' + e['cat'] + ' ' + e['label'] + ' ' + str(e['g_id']) + ' ' + str(e['p_id'])).lower())}">
  <div class="hd">
    <span class="badge {e['cat']}">{e['cat']}</span>
    <span class="badge kb">{e['kb']}</span>
    <span class="badge lbl">{e['label']}</span>
    <span class="mention">{html.escape(e['mention'])}</span>
    <span class="docid">doc #{e['doc']}</span>
  </div>
  <div class="links">
    <div>gold&nbsp;: {e['g_link']}{meta_g}</div>
    <div>pred&nbsp;: {e['p_link']}{meta_p}</div>
  </div>
  {pool_html}
  <div class="txt">{e['text_html']}</div>
</div>''')

    summary = " &nbsp;·&nbsp; ".join(
        f"{k}: <b>{v}</b>" for k, v in sorted(counts.items(), key=lambda x: -x[1]))

    page = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Run 3 — erreurs (train)</title>
<style>
 body{{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f5f6f8;color:#1a1a1a}}
 header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 20px;z-index:10}}
 h1{{font-size:18px;margin:0 0 6px}}
 .summary{{color:#555;font-size:14px;margin-bottom:8px}}
 .filters{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
 .filters button{{border:1px solid #ccc;background:#fff;border-radius:14px;padding:3px 12px;cursor:pointer;font-size:13px}}
 .filters button.on{{background:#1a73e8;color:#fff;border-color:#1a73e8}}
 .filters input{{border:1px solid #ccc;border-radius:6px;padding:4px 10px;font-size:13px;min-width:200px}}
 main{{padding:16px 20px;max-width:1000px;margin:0 auto}}
 .card{{background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:14px 16px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
 .hd{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}}
 .badge{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:4px;letter-spacing:.3px}}
 .badge.WRONG_ID{{background:#fde0d0;color:#b23a00}} .badge.MISSED{{background:#fff3c4;color:#8a6d00}}
 .badge.SPURIOUS{{background:#e0d7fb;color:#5b21b6}} .badge.OTHER{{background:#eee;color:#555}}
 .badge.kb{{background:#d6ebff;color:#0b57d0}} .badge.lbl{{background:#e6f4ea;color:#137333}}
 .mention{{font-weight:700;font-size:16px}} .docid{{margin-left:auto;color:#999;font-size:12px}}
 .links{{font-size:13px;margin-bottom:8px}} .links a{{color:#1a73e8}}
 .links .nil{{color:#999;font-style:italic}} .meta{{color:#777;font-size:12px}}
 details{{margin:6px 0}} summary{{cursor:pointer;color:#0b57d0;font-size:13px}}
 table.pool{{border-collapse:collapse;font-size:12px;margin:6px 0;width:100%}}
 table.pool th,table.pool td{{border:1px solid #eee;padding:2px 6px;text-align:left}}
 table.pool tr.gold{{background:#e6f4ea}} table.pool tr.pred{{background:#fde0d0}}
 .txt{{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;border-radius:6px;padding:10px 12px;font-size:14px;margin-top:6px}}
 mark{{background:#ffe066;padding:0 2px;border-radius:2px;font-weight:600;box-shadow:0 0 0 1px #f0c000}}
 .hidden{{display:none}}
</style></head><body>
<header>
 <h1>Run 3 — erreurs sur le train ({len(errors)} erreurs)</h1>
 <div class="summary">{summary}</div>
 <div class="filters">
  <button data-f="cat" data-v="ALL" class="on">Toutes</button>
  <button data-f="cat" data-v="WRONG_ID">WRONG_ID</button>
  <button data-f="cat" data-v="MISSED">MISSED</button>
  <button data-f="cat" data-v="SPURIOUS">SPURIOUS</button>
  <span style="width:10px"></span>
  <button data-f="kb" data-v="GeoNames">GeoNames</button>
  <button data-f="kb" data-v="MeSH">MeSH</button>
  <span style="width:10px"></span>
  <input id="q" placeholder="recherche (mention, id, label…)">
 </div>
</header>
<main>{"".join(cards)}</main>
<script>
 const state={{cat:"ALL",kb:"ALL",q:""}};
 function apply(){{
   document.querySelectorAll('.card').forEach(c=>{{
     const okCat=state.cat==="ALL"||c.dataset.cat===state.cat;
     const okKb=state.kb==="ALL"||c.dataset.kb===state.kb;
     const okQ=!state.q||c.dataset.search.includes(state.q);
     c.classList.toggle('hidden',!(okCat&&okKb&&okQ));
   }});
 }}
 document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{{
   const f=b.dataset.f,v=b.dataset.v;
   if(state[f]===v&&f==="kb"){{state[f]="ALL";}} else {{state[f]=v;}}
   document.querySelectorAll(`.filters button[data-f=${{f}}]`).forEach(x=>x.classList.remove('on'));
   document.querySelectorAll(`.filters button[data-f=${{f}}][data-v=${{state[f]}}]`).forEach(x=>x.classList.add('on'));
   apply();
 }});
 document.getElementById('q').oninput=e=>{{state.q=e.target.value.toLowerCase();apply();}};
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {len(errors)} errors -> {OUT}")
    print("Counts:", counts)


if __name__ == "__main__":
    main()
