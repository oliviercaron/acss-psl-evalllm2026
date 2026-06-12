# Runs — EvalLLM 2026 Submissions

Ce dossier décrit les **3 runs** soumis pour la phase de test EvalLLM 2026.

> Les **descriptions et empreintes des runs réellement envoyés** font foi dans
> [`RUN_DESCRIPTIONS.txt`](RUN_DESCRIPTIONS.txt) et [`CARBON_FOOTPRINT.txt`](CARBON_FOOTPRINT.txt).
> Les fichiers de prédictions (`*.json`) ne sont pas redistribués : ils contiennent le texte des
> documents de test, non partageable conformément à l'accord avec l'organisation.

## Synthèse des 3 runs soumis

| Run | Modèle (désambiguïsation) | Couverture | Liées / NIL | RANKING test | CO₂ |
|-----|---------------------------|------------|-------------|--------------|-----|
| **Run 1** | gemma-4-31b (local) | étendue | 1700 / 140 | 84,52 | ~1,15 g (mesuré) |
| **Run 2** | GPT-5.4-nano (API) | généraliste | 1654 / 186 | 82,25 | ~1,8-4,0 g (estimé) |
| **Run 3** | GPT-5.4-nano (API) | étendue | 1700 / 140 | 84,12 | ~1,8-4,0 g (estimé) |

Test : 1840 mentions. « Liées » = prédictions avec `source` GeoNames ou MeSH ; « NIL » = `source`
vide. Le run 2 est le run 3 dont on a ramené à NIL les contributions informées par le test, d'où les
**46 mentions d'écart** (1700/140 → 1654/186). Détail du run 2 : 1123 GeoNames + 531 MeSH = 1654.

## Stratégie (3 runs max autorisés)

- **Run 1** — modèle ouvert servi en local (gemma-4-31b), couverture étendue. Meilleure soumission.
- **Run 2** — configuration strictement généraliste (aucune règle informée par le test), pour une
  comparaison équitable.
- **Run 3** — API propriétaire (GPT-5.4-nano), couverture étendue.

## Note sur les `run{1,2,3}/stats.md`

Ces fichiers documentent le **développement itératif** et emploient une organisation de runs
*antérieure* (Run 1/2/3 = étapes incrémentales du pipeline, et non les trois variantes finales
ci-dessus). Pour les runs réellement soumis, se référer au tableau ci-dessus et à
`RUN_DESCRIPTIONS.txt`.
