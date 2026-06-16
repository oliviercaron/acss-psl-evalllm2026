# ACSS-PSL @ EvalLLM 2026 : liage d'entités de santé

Système de **liage d'entités** pour le défi EvalLLM 2026 (équipe ACSS-PSL, Université Paris
Dauphine - PSL). Chaque mention de santé pré-identifiée dans un texte français est reliée à un
identifiant **GeoNames** (lieux) ou **MeSH** (pathogènes, maladies, toxines), ou marquée
hors-référentiel (**NIL**).

L'approche est **frugale et sans entraînement** : une cascade de règles déterministes
(normalisation, détection NIL, génération de candidats par index local) suivie d'un **LLM** appelé
uniquement sur les cas ambigus (au moins deux candidats), en mode *listwise* (il choisit un indice
dans une liste fermée, il ne génère jamais d'identifiant).

## Résultats

- **Train** : trois modèles très différents (GPT-5.4-nano API, gemma-4-31b local,
  Qwen3.6-35B-A3B) plafonnent au même score (RANKING 92,22). Le LLM n'est donc pas le facteur
  limitant, c'est la génération de candidats qui l'est.
- **Test officiel** : meilleure soumission RANKING 84,52 (run 1, gemma local), contre une médiane
  de 74,46 sur les 19 soumissions du défi.
- **Empreinte carbone** : run local mesurée à ~1,15 g CO₂eq (Green Algorithms, grille française).

Détails dans [`docs/`](docs/) et l'article ([`paper/`](paper/)).

## Ce qui n'est pas inclus

| Élément | Raison | Comment l'obtenir |
|---|---|---|
| `data/protected/` (train/test, guides, scorer) | Données protégées du défi, non redistribuables | Auprès des organisateurs (voir [`data/README.md`](data/README.md)) |
| `data/processed/*.db`, `*.pkl` (~3 Go) | Index reconstructibles | `scripts/build_*_index.py` |
| `data/raw/` (dumps GeoNames/MeSH) | Sources publiques volumineuses | Téléchargement (voir [`data/README.md`](data/README.md)) |
| `runs/**/*.json` (prédictions) | Embarquent le texte protégé du test | Régénérables localement |

## Reproduction (Windows / PowerShell)

```powershell
# 1. Environnement (Python 3.12)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 2. Données protégées : placez les fichiers de l'organisation dans data/protected/
#    (voir data/README.md)

# 3. Sources publiques + index (voir data/README.md)
python scripts/download_public_sources.py   # télécharge GeoNames + MeSH NLM dans data/raw/
python scripts/build_geonames_index.py      # -> data/processed/geonames.db
python scripts/build_mesh_index.py           # -> data/processed/mesh_index.pkl

# 4. Configuration du LLM (copiez .env.example en .env et renseignez)
#    API : OPENAI_API_KEY + LLM_MODEL ; ou local vLLM : LLM_BASE_URL + LLM_MODEL

# 5. Prédiction (configuration de soumission)
python src/linker.py predict data/protected/test_evalLLM.json runs/local/predictions.json --no-memory --llm-reranker

# 6. Validation du format
python src/validate_predictions.py data/protected/test_evalLLM.json runs/local/predictions.json

# 7. Évaluation (scorer officiel de l'organisation, à placer dans data/protected/)
```

Tests anti-régression :

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"; python -m pytest tests -q
```

## Structure

```
src/         cascade de liage (linker.py), audit qualité, validateur
scripts/     construction des index, audits, estimation carbone
experiments/ ablations de l'article (balayage top-k, variance LLM, vote) + runlogs
tests/       tests unitaires (anti-régression)
data/        protected/ (slot), raw/ (sources publiques), processed/ (index)
runs/        métadonnées des 3 soumissions (sans les prédictions)
docs/        pipeline, empreinte carbone
paper/       article (LaTeX, figures, code R de la figure 1)
```

## Reproductibilité du LLM

L'étape LLM est exécutée à température 0, mais une variance résiduelle subsiste (routage côté API,
build/quantification côté vLLM local). Fixez le modèle, le prompt et la révision du code, et
enregistrez les empreintes de sortie. Voir [`docs/carbon_footprint.md`](docs/carbon_footprint.md)
pour le matériel et la méthode de mesure.

## Licence

Code sous licence MIT (voir [`LICENSE`](LICENSE)). Les ressources externes (GeoNames CC BY,
MeSH/NLM, traduction Inserm) conservent leurs licences respectives. Les données du défi ne sont
pas redistribuées.
