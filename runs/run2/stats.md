# Run 2 — Stats

## Soumission

- **Date** : 28 mai 2026, ~matin (J+1)
- **Fichier** : `acss-psl_run_2.json` (933 KB)
- **Validation format** : ✅ OK (`src/validate_predictions.py test_evalLLM.json runs/run2/acss-psl_run_2.json`)
- **Mail envoyé à** : julianne.flament@def.gouv.fr

## Configuration utilisée

- Code source : commit `6b51ce8` + diff Run 2 (à committer après soumission)
- Mode : `--no-memory --llm-reranker` (identique à Run 1)
- LLM : **GPT-5.4-nano** (`temperature=0`, `max_completion_tokens=100`, `request_timeout=60s`)
- Prompt LLM : **anglais** (validation A/B empirique : FR perd −1.07 pt ranking train ; cohérent avec littérature 8 papiers)

## Changements vs Run 1

Trois ajouts ciblés, tous **justifiés par le guide d'alignement officiel** (pas d'overtuning test-driven) :

1. **Normalisation Greek → Latin** (`α → alpha`, `β → beta`, etc., + homoglyph µ U+00B5)
   - Fallback dans `_resolve_from_index`, `_resolve_from_fr_mesh`, `_get_fr_mesh_candidates`
   - 14 nouveaux tests unitaires + non-régression 70/71 (1 skip légitime)

2. **Périphrases géographiques** (`_resolve_periphrase` dans `GeoNamesLinker`)
   - `Hexagone` → France (3017382) — guide cite littéralement
   - Regex `^territoire <gentilé>$` + dico 16 gentilés (chinois→Chine 1814991, etc.)
   - Garde-fou : « territoire européen » → None (concept géo, conforme guide)
   - 13 nouveaux tests unitaires (dont garde-fou « territoire de Krasnoyarsk » qui doit passer dans la cascade standard)

3. **Retrait pattern NIL `^fort\s+d[eu]\b`** (cosmétique : 0 mention test, mais bloquait Fort-de-France à tort)
   - Test transformé en négatif : vérifie que Fort-de-France n'est plus bloqué
   - Lower bound train NIL : 9 → 7 (les 2 `fort de Corbas` restent NIL via cascade naturelle)

## Distribution des prédictions

| Source | Run 1 | Run 2 | Delta |
|--------|-------|-------|-------|
| GeoNames | 1097 (59.6%) | **1106 (60.1%)** | **+9** |
| MeSH | 524 (28.5%) | **529 (28.8%)** | **+5** |
| NIL (`source==""`) | 219 (11.9%) | **205 (11.14%)** | **−14** |
| **Total** | **1840** | **1840** | — |

## Gains détaillés (NIL → linked, +14 net)

| Mention | Catégorie | Run 1 | Run 2 | Source du fix |
|---|---|---|---|---|
| `α-amanitine` × 5 (doc#189) | BIO_TOXIN | NIL | MeSH D053959 | Greek normalize |
| `Hexagone` × 5 (docs 96, 121, 143, 148) | LOCATION | NIL | GeoNames 3017382 (France) | `_resolve_periphrase` (cité guide) |
| `territoire chinois` × 2 (docs 11, 57) | LOCATION | NIL | GeoNames 1814991 (Chine) | `_resolve_periphrase` (exemple guide) |
| `territoire français` (doc#85) | LOCATION | NIL | GeoNames 3017382 (France) | `_resolve_periphrase` |
| `territoire camerounais` (doc#74) | LOCATION | NIL | GeoNames 2233387 (Cameroun) | `_resolve_periphrase` |

## Diff complet Run 1 vs Run 2

- **14** NIL → linked (tous prédits/justifiés)
- **0** linked → NIL (aucune régression)
- **7** ID changed (variations LLM listwise, température=0 mais non déterministe à 100%)
  - 2 améliorations probables : `France` → 3017382 PCLI (correct), `monde` → 6295630 (Earth)
  - 5 variations marginales sur des homonymes proches

## Non-régression validée sur train

| Métrique | Run 1 train | Run 2 train | Delta |
|---|---|---|---|
| Entity accuracy | ~90.65 | 90.85 | +0.20 |
| F1 global | ~91.4 | 91.53 | +0.13 |
| GeoNames F1 | ~89.5 | 89.84 | +0.34 |
| MeSH F1 | ~94.7 | 94.74 | ≈0 |
| **RANKING** | **91.05** | **91.19** | **+0.14** ✅ |

## Tests

- **70/71 passed** (1 skip légitime : μ-conotoxine GIIIA absent du dump MeSH)
- Couverture : 14 Greek + 18 NIL detection (avec test négatif `fort_de`) + 13 periphrase + 9 strain override + 17 validator

## Expérience secondaire : prompt LLM FR vs EN

A/B test conduit sur train (config identique sauf `--llm-lang fr`) :

| Métrique | EN | FR | Delta |
|---|---|---|---|
| RANKING train | **91.19** | 90.12 | **−1.07** |
| GeoNames F1 | 89.84 | 88.20 | −1.64 |
| MeSH F1 | 94.74 | 94.74 | 0.00 |

**Verdict : EN conservé**. Confirmation empirique de la littérature (Zaghir et al. 2024, Matsuo et al. 2024, Wendler et al. 2024) : sur tâches structurées avec modèles English-centric (GPT-5.4-nano), les instructions EN s'alignent mieux avec le pivot latent du modèle.

Insight intéressant : MeSH listwise est robuste à la langue d'instruction (candidats déjà bilingues dans le prompt), tandis que GeoNames listwise dépend de l'EN pour ses feature_codes culturellement anglo-saxons (PCLI, PPLC, ADM4).

## Performance

- **Durée totale** : ~17 minutes (vs ~11 min Run 1 — légère hausse car +14 entités → +14 chemins linker complets)
- **Coût API** : ~$0.08 (identique à Run 1)
- **Empreinte CO₂** : ~65 g CO₂eq (voir `carbon_footprint.txt`)

## Score attendu

Estimation basée sur train + ratio entités test/train :

- **Borne basse** : 89 (si test diverge plus que prévu du train)
- **Estimation centrale** : **91-92** (gain +1 pt vs Run 1 si extrapolation linéaire des +14 entités)
- **Borne haute** : 93 (si tous les fixes sont au pic d'utilité)

## Notes pour Run 3 (J+2)

Découvertes des 3 sous-agents analytiques (synthèse) :
- Cluster Marburg (`maladie à virus de Marburg`, etc.) : +10-13 entités attendues (symétrie Ebola/Lassa)
- Sub-regions UN (`Amérique latine` 7730009, `Caraïbes` 7729891, `Europe orientale` 7729884) : +10-11 (gold train direct)
- Acronymes (TBE→D004675, TBEV, VHC, BTX=brévétoxines C053342) : +20-25
- Toxines pluriel + diacritiques (`brévétoxines`, `palytoxine`, `microcystine`) : +10-15
- Mécanisme acronyme→forme plein dans même document : +25 NIL potentiel
- Normalisation pluriel/singulier composites : +10

Gain Run 3 attendu : **+60-90 entités vs Run 1**.
