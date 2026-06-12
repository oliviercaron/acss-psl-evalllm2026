# Pipeline architectural — EvalLLM 2026 Entity Linking

Représentation ASCII du pipeline complet pour publication scientifique.
Source : `src/linker.py` (~1170 lignes après cleanup). Score : 91.05 ± 0.12.

---

## Vue 1 — Orchestrateur global (`EntityLinker.link_entity`)

```
                Input: (mention, label, context)
                              |
                              v
                  +-------------------------+
                  |    TrainingMemory       |       (1)
                  |  (mention, label)       |
                  |       -> id_kb          |     enabled?
                  +-------------------------+ ----------+
                              |                        |
                  hit (mémoire) -----> return (id_kb, source)  [mode --memory]
                              |
                              v miss / mode --no-memory
                  +-------------------------+
                  |     _is_likely_nil      |       (2)
                  |  (lexical NIL patterns) |
                  +-------------------------+
                              |
                  match -----> return ("", "")   [NIL: fort/quartier/zone/...]
                              |
                              v no match
              +---------------+---------------+
              |                               |
       label == LOCATION              label in MESH_LABELS
              |                               |
              v                               v
       +-------------+              +-------------------+
       | GeoNamesLink|              |    MeSHLinker     |
       |    (Vue 2)  |              |     (Vue 3)       |
       +-------------+              +-------------------+
              |                               |
              v                               v
        id -> (id,"GeoNames")          id -> (id,"MeSH")
        None -> ("","")                None -> ("","")

       Autres labels  ----------------------->  ("", "")  [silencieux]
```

---

## Vue 2 — Branche GeoNames (`GeoNamesLinker.link`)

```
                       Input: (mention, context)
                                  |
                                  v
            +---------------------------------------------+
            |   Cascade de lookups (5 tentatives + NIL)   |
            |                                             |
            |  1. exact match                             |
            |  2. strip_prefix(mention)                   |
            |  3. remove_accents(mention)                 |
            |  4. strip_prefix + remove_accents           |
            |  5. tail-match (si mention >= 3 mots)       |
            |  -> aucune ne matche : return None  ---> NIL|
            +---------------------------------------------+
                                  |
                                  v match (>=1 candidat)
            +----------------------------------+
            |    _query_candidates (SQL)       |
            |  pool prioritaire = _KEEP_FCODES |
            |  + pool secondaire LIMIT 50      |
            |  dédup, ordre population DESC    |
            +----------------------------------+
                                  |
                                  v
                       +----------------------+
                       |    _disambiguate     |
                       +----------------------+
                                  |
                  +---------------+---------------+
                  |                               |
              1 candidat                   >= 2 candidats
                  |                               |
                  v                               v
                return                +-------------------------+
                                      | _heuristic_disambiguate |
                                      | -> heuristic_id         |
                                      +-------------------------+
                                                  |
                                       LLM enabled & cands >=2 ?
                                                  |
                                +-----------------+-----------------+
                                | yes                               | no
                                v                                   |
                       +------------------+                          |
                       |  _get_llm_client |                          |
                       +------------------+                          |
                                |                                    |
                       client available ?                             |
                                |                                    |
                       yes -----+----- no (key/openai missing,        |
                                |        runtime-disables enabled)    |
                                v                                    |
                       +------------------+                          |
                       |   _llm_rerank    |                          |
                       | (GPT-5.4-nano,   |                          |
                       |  temperature=0,  |                          |
                       |  candidates[:10],|                          |
                       |  context[:500])  |                          |
                       +------------------+                          |
                                |                                    |
                       re.match(r"\d+",                               |
                       content) hit ?                                 |
                                |                                    |
                       +--------+----------+                          |
                       | yes               | no (timeout, exception, |
                       |                   |   non-int response)     |
                       v                   v                          |
                    llm_id             None -> heuristic_id           |
                       \                       \                      /
                        \                       \                    /
                         v                       v                  v
                       +-------------------------+
                       |   _postprocess_fcode    |
                       | (GPS reconciliation)    |
                       +-------------------------+
                                  |
                                  v
                               final_id


Détail _heuristic_disambiguate :
    if PCLI/PCLD/PCLF (pays)    -> max(pop)
    elif wants_admin (mention)  -> _ADMIN_FCODES -> max(pop)
    elif pop > 0                -> exclude ADM3 -> max(pop)
    else                        -> candidates[0]

Détail _postprocess_fcode :
    same_place = candidats à <5 km du chosen (haversine).
                 GPS fallback (lat/lon manquants) : même country_code
                 ET même nom avant virgule (name.split(",")[0]).
    if len(same_place) <= 1     -> return chosen
    if wants_admin              -> max(pop) parmi ADMx
    elif PPLC/PPLA/PPLA2 in same_place -> max(pop) parmi ces "major"
    elif chosen=PPL & ADM4 in same_place :
         ratio = min(pop_PPL, pop_ADM4) / max(pop_PPL, pop_ADM4, 1)
         if ratio > 0.80         -> swap vers ADM4 (commune française)
```

---

## Vue 3 — Branche MeSH (`MeSHLinker.link`)

```
                  Input: (mention, label, context)
                              |
                              v
                  +-----------------------+
                  | LLM enabled ?         |  --- no -----+
                  +-----------------------+              |
                              | yes                      |
                              v                          |
                  +--------------------------+           |
                  |  AMBIGUOUS_MENTIONS      |           |
                  |  (mention,label)->[ids]  |           |
                  +--------------------------+           |
                              |                          |
                       hit ? -+----> yes ----> _llm_rerank_mesh  |
                              |                            |    |
                              |                  not None -+    |
                              |                            |    |
                              |                            v    |
                              |                          return |
                              |                            |    |
                              |       None (failure)<------+    |
                              |       (LLM unavail / parse fail)|
                              |       |                         |
                              v <-----+                         |
                  +--------------------------+ <----------------+
                  |  _resolve_from_manual_dict           |
                  |  (LABEL_OVERRIDES, then              |
                  |   FR_MANUAL_DICT, with no-accents    |
                  |   variants)                          |
                  +--------------------------+
                              |
                       hit ? -+----> yes -> return id
                              |
                              v no
                  +--------------------------+
                  |  _get_fr_mesh_candidates  |
                  |  (Inserm FR dict,         |
                  |   no-accents fallback)    |
                  +--------------------------+
                              |
              +---------------+---------------+
              |               |               |
         0 cand          1 cand          >= 2 cand
              |               |               |
              v               v               v
   +-----------------+   return   +-------------------------+
   | _resolve_from_  |            |  _resolve_from_fr_mesh  |
   |    _index       |            |  (cat-label compat via  |
   | (English MeSH,  |            |   _CAT_LABEL_COMPAT)    |
   |  no-accents     |            |  -> det_result          |
   |  fallback :     |            +-------------------------+
   |  desc > pref >  |                      |
   |  supp >         |          LLM enabled ?
   |  "DUI : SUI")   |                      |
   +-----------------+    +-----------------+-----------------+
              |           | yes                               | no
              v           v                                   v
           id or None  +--------------------+            return det_result
                       | _llm_rerank_mesh   |            (or fr_candidates[0]
                       +--------------------+             if det_result None)
                                |
                         not None ?
                                |
                       +--------+--------+
                       | yes             | no (LLM fail/timeout)
                       v                 v
                  return llm_id      return det_result (or fr_candidates[0])
                              |
                              v
                  +---------------------+
                  | _resolve_strain_    |
                  | override (regex     |
                  | _STRAIN_MARKERS +   |
                  | candidate blob      |
                  | matches o104/o157/  |
                  | ehec/stec)          |
                  +---------------------+
                              |
                  hit ? --+--> yes --> return strain candidate
                          | no
                          v
                  +----------------------+
                  | LLM API call         |
                  | (GPT-5.4-nano,       |
                  |  prompt = mention +  |
                  |  context + cands +   |
                  |  strain/anatomy/     |
                  |  generic rules)      |
                  +----------------------+
                              |
                  parse int -> cands[i]   ou   None -> fallback (det. result / cands[0])


Détail _resolve_from_fr_mesh (désambiguïsation déterministe) :
    for did in candidates:
        for cat in _fr_mesh_cats[did]:
            if label in _CAT_LABEL_COMPAT[cat]:
                return did
    return candidates[0]

_CAT_LABEL_COMPAT :
    c -> {INF_DISEASE, NON_INF_DISEASE, DIS_REF_TO_PATH, PATH_REF_TO_DIS}
    b -> {PATHOGEN, PATH_REF_TO_DIS, DIS_REF_TO_PATH}
    d -> {BIO_TOXIN, PATHOGEN}
```

---

## Légende des composants

### Cascades et orchestrateurs

- **EntityLinker.link_entity** — orchestrateur principal. Cascade : memory → NIL lexical → branche KB selon label.
- **GeoNamesLinker.link** — résolution LOCATION via SQLite (13M lieux). Cascade de 6 tentatives de lookup avec stripping de préfixes et accents.
- **MeSHLinker.link** — résolution MeSH (31K descripteurs FR + 323K supplementary EN). Cascade : ambiguïté → dict manuel → Inserm FR → fallback EN.

### Filtres préliminaires

- **TrainingMemory** — lookup `(mention, label) → id_kb` majoritaire depuis le train. Désactivé en mode officiel `--no-memory`.
- **_is_likely_nil** — détection lexicale NIL (6 patterns regex validés : `fort/quartier/zone/bassins/ceinture` LOCATION et `venom/venin` BIO_TOXIN).

### Helpers de normalisation et constantes

- **strip_prefix** — supprime itérativement 16 préfixes géographiques FR (`la/le/les/l'`, `région d(e|u|')`, `département d(e|u|')`, `ville d(e|u|')`, etc.) jusqu'à stabilité.
- **remove_accents** — normalisation NFKD + suppression des combining characters.
- **_KEEP_FCODES** — 10 feature codes garantis dans le pool SQL (pays/admin/chefs-lieux) pour qu'ils ne soient pas filtrés par LIMIT 50.
- **_ADMIN_PREFIXES** — 14 tokens linguistiques (`région/province/département/commune/sous-préfecture/...`) déclenchant la préférence ADM dans la désambiguïsation et le postprocesseur.
- **_CAT_LABEL_COMPAT** — mapping catégorie MeSH (b/c/d) → labels d'entité compatibles, utilisé par `_resolve_from_fr_mesh` pour départager.

### Dictionnaires manuels

- **AMBIGUOUS_MENTIONS** — 5 entrées (mention, label) → liste de candidats pour forcer l'appel LLM sur cas ambigus.
- **LABEL_OVERRIDES** — 14 entrées (mention, label) → id_kb pour cas où le label change le mapping.
- **FR_MANUAL_DICT** — 157 entrées mention → id_kb pour termes FR courants/colloquiaux.

### Désambiguation GeoNames

- **_query_candidates** — requête SQL paramétrique : pool prioritaire `_KEEP_FCODES` (pays, capitales, ADM1-2, chefs-lieux) puis pool secondaire LIMIT 50, dédup, tri population DESC.
- **_heuristic_disambiguate** — règle déterministe : pays > admin (wants_admin) > exclusion ADM3 > max population.
- **_llm_rerank** — appel GPT-5.4-nano listwise avec prompt enrichi (country match, PPLC/PPLA > ADM, ADM4 pour communes FR).
- **_postprocess_fcode** — réconciliation feature code via GPS (haversine <5 km) : préfère ADM, major, ou swap PPL→ADM4 si ratio pop > 0.80.

### Désambiguation MeSH

- **_resolve_from_manual_dict** — consultation LABEL_OVERRIDES puis FR_MANUAL_DICT (avec variante no-accents).
- **_get_fr_mesh_candidates** — lookup dans l'index Inserm bilingue (~313 K termes).
- **_resolve_from_fr_mesh** — désambiguïsation par compatibilité catégorie MeSH ↔ label entité (`_CAT_LABEL_COMPAT`).
- **_resolve_from_index** — fallback sur l'index MeSH anglais : descriptor préféré > descriptor premier > supplementary "DUI : SUI".
- **_resolve_strain_override** — règle Python pré-LLM : si contexte contient marqueur de souche ET candidat contient `o104/o157/ehec/stec` → force ce candidat.
- **_llm_rerank_mesh** — appel GPT-5.4-nano avec prompt enrichi (strain rule, anatomy rule, generic default).

### Configuration LLM

- **LLMRerankerConfig** — `model=gpt-5.4-nano`, `temperature=0`, `max_completion_tokens=100`, `max_candidates=10`, `context_chars=500`, `request_timeout=60s`.

---

## Note critique — heuristiques implicites non représentées dans le diagramme

1. **Population comme tiebreaker universel** : tous les `max(...)` dans le diagramme utilisent `c.get("pop") or 0` comme clé. En cas d'égalité, c'est l'ordre Python qui décide (généralement l'ordre SQL = population DESC, mais non garanti).
2. **`return candidates[0]` comme dernier recours** : aux trois endroits non visibles dans le diagramme (heuristique sans pop, FR MeSH sans match catégorie, MeSH cascade épuisée), on retourne le premier candidat sans tiebreaker explicite.
3. **Parsing LLM** : seul un entier en début de réponse est accepté (`re.match(r"\d+", content)`) ; tout autre format → fallback déterministe (heuristic_id côté Geo, det_result côté MeSH).
4. **Labels inconnus → NIL silencieux** : tout label hors `GEONAMES_LABELS ∪ MESH_LABELS` court-circuite la cascade et retourne `("", "")` sans avertissement.
5. **Ratio 0.80 du postprocessor GPS** : magic number calibré empiriquement (les communes françaises où PPL et ADM4 sont la même entité ont typiquement un ratio de population > 0.90, à l'inverse les paires PPL/ADM4 représentant des scopes différents tombent en dessous de 0.80). C'est le seuil le plus fragile pour la généralisation au test.
