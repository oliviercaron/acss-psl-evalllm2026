# Run 1 — Stats

## Soumission

- **Date** : 27 mai 2026, ~10:00 (matin de J+0)
- **Fichier** : `acss-psl_run_1.json` (933 KB)
- **Validation format** : ✅ OK (`src/validate_predictions.py`)
- **Mail envoyé à** : julianne.flament@def.gouv.fr

## Configuration utilisée

- Code source : **commit `b18f109`** du repo GitHub
- Mode : `--no-memory --llm-reranker`
- LLM : **GPT-5.4-nano** (`temperature=0`, `max_completion_tokens=100`, `request_timeout=60s`)
- Cascade complète (cf. PIPELINE.md)

## Distribution des prédictions

| Source | Count | Proportion |
|--------|-------|-----------|
| GeoNames | 1097 | 59.6% |
| MeSH | 524 | 28.5% |
| NIL (`source==""`) | 219 | 11.9% |
| **Total** | **1840** | **100%** |

## Comparaison avec le train

| Métrique | Train (491 ent.) | Test (1840 ent.) |
|----------|------------------|-------------------|
| Proportion GeoNames | 62.1% | 59.6% |
| Proportion MeSH | 33.6% | 28.5% |
| Proportion NIL | 4.3% | **11.9%** ⚠️ |
| Nb entités/doc moyen | 12.3 | 9.2 |

## ⚠️ Observation pour Run 2/3

**Le taux de NIL prédit (11.9%) est nettement supérieur à celui du train (4.3%).**

Hypothèses :
1. Le test contient effectivement plus de mentions non-liables (lieux trop spécifiques, nouveaux pathogènes)
2. **Nos patterns NIL lexicaux pourraient être trop agressifs** sur certaines mentions du test

→ Pour Run 2, envisager d'assouplir les patterns NIL (ex : retirer `^zone\b`, `^bassins?\b`, `^fort\s+d[eu]\b`).

## Performance

- **Durée totale** : ~11 minutes (cascade locale + ~800-900 appels LLM)
- **Coût API** : ~$0.08
- **Empreinte CO₂** : ~65 g CO₂eq (voir `carbon_footprint.txt`)

## Score attendu

Estimation basée sur le score train et la similarité de distribution :
- **Borne basse** : 85 (si overfitting train confirmé)
- **Estimation centrale** : 88-91
- **Borne haute** : 92 (si le test ressemble très fortement au train)
