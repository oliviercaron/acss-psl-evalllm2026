# Données

Ce dépôt ne redistribue **ni** les données protégées du défi EvalLLM 2026, **ni** les
index volumineux reconstructibles. Les emplacements ci-dessous sont des slots vides à
remplir localement.

## 1. Fichiers protégés de l'organisation (non inclus)

À obtenir auprès des organisateurs d'EvalLLM 2026, sous l'accord du défi, puis à placer dans
`data/protected/` :

- `data/protected/train_evalLLM.json`
- `data/protected/test_evalLLM.json`
- `data/protected/eval_linking.py` (script d'évaluation officiel)
- `data/protected/Guide_alignement_lexical_Geonames.docx`
- `data/protected/Guide_alignement_lexical_MeSH.docx`
- `data/protected/CHALLENGE.md`

Ces fichiers sont exclus du dépôt (`.gitignore`).

## 2. Sources publiques brutes (non incluses)

Téléchargement automatique (GeoNames + MeSH NLM) :

```powershell
python scripts/download_public_sources.py
```

Fichiers attendus dans `data/raw/` et liens :

| Fichier | Source | Lien |
|---|---|---|
| `geonames/allCountries.zip` | GeoNames (CC BY) | <https://download.geonames.org/export/dump/allCountries.zip> |
| `geonames/alternateNamesV2.zip` | GeoNames (CC BY) | <https://download.geonames.org/export/dump/alternateNamesV2.zip> |
| `mesh/desc2026.xml` | NLM | <https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml> |
| `mesh/supp2026.xml` | NLM | <https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/supp2026.xml> |
| `mesh/2026_js_elastic_mesh_bilingue.json` | Inserm (MeSH bilingue FR/EN) | <https://mesh.inserm.fr/telecharger-le-fichier-mesh/> (formulaire requis) |

GeoNames et le MeSH NLM sont en accès direct (récupérés par `download_public_sources.py`). La
traduction bilingue FR/EN de l'Inserm (<https://mesh.inserm.fr/telecharger-le-fichier-mesh/>)
nécessite de remplir un formulaire ; elle n'est donc pas couverte par le script automatique et est
à télécharger manuellement, puis à placer dans `data/raw/mesh/`.

## 3. Index reconstruits localement (non inclus)

Générés depuis les sources brutes :

- `data/processed/geonames.db` (~2,8 Go)
- `data/processed/mesh_index.pkl` (~143 Mo)
- `data/processed/wikidata_search_cache.json` (seulement pour reproduire les runs informés
  par le test, mode `EVALLLM_TEST_INFORMED=1`)

Reconstruction :

```powershell
python scripts/build_geonames_index.py   # -> data/processed/geonames.db
python scripts/build_mesh_index.py        # -> data/processed/mesh_index.pkl
python scripts/build_wikidata_cache.py    # -> data/processed/wikidata_search_cache.json (optionnel)
```

## Versions utilisées

- **GeoNames** : dump complet téléchargé le 13 mai 2026 (le dump GeoNames est glissant, sans
  numéro de version officiel — la date conditionne la reproductibilité exacte).
- **MeSH** : édition 2026 (NLM, `desc2026.xml` + `supp2026.xml`) et traduction bilingue FR/EN
  Inserm 2026.
