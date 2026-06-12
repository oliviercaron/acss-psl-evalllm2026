# Empreinte carbone — EvalLLM 2026 Entity Linking (équipe acss-psl)

Empreinte des 3 runs soumis, conformément à la demande des organisateurs.
**Méthodologie selon le matériel :**
- **Matériel connu** (GPU H100 local, CPU du PC fixe) : [Green Algorithms](http://calculator.green-algorithms.org/), avec l'énergie GPU **mesurée** par nvidia-smi.
- **LLM via API** (GPT-5.4-nano) : estimation **[EcoLogits](https://ecologits.ai)**, le matériel d'OpenAI n'étant pas observable.

Approche **frugale par conception** : aucun entraînement ni fine-tuning, retrieval déterministe local (index GeoNames/MeSH), petit LLM non-raisonnant appelé uniquement sur les mentions ambiguës (≥ 2 candidats). **Chaque run ≈ 1–4 g CO₂eq.**

Constantes : intensité carbone France = **56 g CO₂eq/kWh** ; PUE serveur = **1,67** ; PUE PC perso = **1** ; grille EcoLogits par défaut = **« WOR »** (moyenne monde).

---

## 1. Pourquoi deux outils

Green Algorithms estime l'énergie à partir d'un **matériel connu** (cœurs, TDP, runtime, PUE) : adapté à notre **H100** et au **CPU de notre PC fixe**, mais **pas** à une API dont on ignore le GPU et le datacenter. EcoLogits est conçu pour estimer l'impact des LLM appelés par API (OpenAI, Anthropic, Mistral…) à partir du **modèle** et des **tokens de sortie** ; son GWP combine l'**usage** (énergie × grille) et l'**embodied** (fabrication du matériel).

---

## 2. run_1 — Gemma-4-31B en local — **MESURÉ**

**Matériel :** GPU **NVIDIA H100** (serveur de calcul, France) pour le LLM ; CPU **AMD Ryzen 5 5600X** (notre PC fixe, France) pour la cascade de règles et les I/O. Aucun autre GPU utilisé (la RTX 3070 locale est restée inactive).

Énergie GPU mesurée par nvidia-smi (puissance 1 Hz intégrée sur la fenêtre d'inférence du run test complet : 200 docs / 1840 entités) :

| Composant | Matériel | Mesure / calcul | CO₂eq |
|---|---|---|---|
| LLM (GPU) | NVIDIA H100, datacenter, PUE 1,67 | **11,2 Wh mesurés** (242 W moy. × 167 s) | ~1,05 g |
| Règles + I/O (CPU) | AMD Ryzen 5 5600X, PC fixe, ~40 W × 167 s, PUE 1 | ~1,9 Wh | ~0,10 g |
| **TOTAL run_1** | | | **≈ 1,15 g CO₂eq** |

Débit : 779 appels LLM, 4,7 req/s, ~1800 tokens d'entrée/s.
Repro Green Algorithms : GPU 0,046 h, 1× H100 (TDP 400 W, **usage mesuré 0,60** → 11,1 Wh) ; CPU 0,046 h, Ryzen 5 5600X (6 cœurs, ~40 W en charge légère, le TDP plein de 65 W donnant une borne haute à ~0,17 g) ; mémoire négligeable ; France.

> Le PUE 1,67 ne vaut que pour le GPU (serveur) ; le CPU tourne sur un PC perso hors datacenter, donc PUE 1.

---

## 3. run_2 / run_3 — GPT-5.4-nano via API — **ESTIMÉ (EcoLogits)**

**Matériel :** **aucun GPU local**. Le LLM tourne sur le matériel d'OpenAI (non observable) ; la cascade de règles tourne sur le même CPU **AMD Ryzen 5 5600X** (notre PC fixe). Green Algorithms ne s'applique donc qu'au CPU local, et EcoLogits estime le LLM.

| Hypothèses du run | Valeur |
|---|---|
| Appels LLM / run | ~880 (mentions à ≥ 2 candidats) |
| Tokens de sortie / appel | ~50 |
| Latence / appel | ~0,5 s |

| Poste | Matériel | Estimation |
|---|---|---|
| LLM (API) | OpenAI (inconnu), EcoLogits, grille monde | énergie **~3–8 Wh** → **~1,2–3,4 g** |
| *(indicatif, sur grille française)* | | *~0,2–0,5 g* |
| Règles + I/O (CPU) | AMD Ryzen 5 5600X, PC fixe, ~40 W × ~15 min ≈ 10 Wh, France | ~0,5–0,6 g |
| **TOTAL par run** | | **≈ 1,8–4,0 g CO₂eq** |

> **Fourchette du LLM** : EcoLogits ignore la taille exacte de gpt-5.4-nano (non publiée) et suppose **15 à 58 milliards de paramètres** ; l'énergie étant ~proportionnelle à la taille, d'où le facteur ~3.
> **Limite** : EcoLogits ne facture que les tokens de **sortie** ; notre tâche est *input-heavy* (~310 entrée / ~50 sortie), donc cette estimation est plutôt une **borne basse**.

Script reproductible : [`experiments/ecologits_api_estimate.py`](experiments/ecologits_api_estimate.py).

---

## 4. Bilan

| Run | Matériel LLM | CO₂eq / run | Nature |
|---|---|---|---|
| run_1 | Gemma-4-31B sur H100 (local, France) + CPU Ryzen 5 5600X | **≈ 1,15 g** | **mesuré** (GPU) |
| run_2 | GPT-5.4-nano (API OpenAI) + CPU Ryzen 5 5600X | ≈ 1,8–4,0 g | estimé (EcoLogits) |
| run_3 | GPT-5.4-nano (API OpenAI) + CPU Ryzen 5 5600X | ≈ 1,8–4,0 g | estimé (EcoLogits) |
| **Total 3 runs** | | **≈ 4,8–9 g CO₂eq** | |

**Lecture honnête.** L'approche est **uniformément frugale** (~1–4 g/run). Le run local a un avantage carbone **modéré (~1,5–3×)**, dû **surtout à la grille française décarbonée** : en énergie d'inférence, le petit nano (3–8 Wh) consomme en réalité **moins** que Gemma-4-31B (11,2 Wh). Nous ne revendiquons donc **pas** un facteur élevé local vs API, seulement une approche très sobre dont le run local est **entièrement mesuré**.

Coût API nano ≈ 0,08 $/run (tarif gpt-5.4-nano : 0,20 $/M tokens entrée, 1,25 $/M sortie).

---

## 5. Limites

- **Local** : l'énergie GPU est mesurée ; la conversion en CO₂ utilise des facteurs standards (France 56 g/kWh, PUE 1,67 serveur / 1 PC perso). Le CPU est estimé à la Green Algorithms (Ryzen 5 5600X, ~40 W en charge légère I/O-bound).
- **API** : l'énergie n'est pas mesurable (fournisseur fermé) ; EcoLogits fournit une **fourchette** (architecture du modèle non publiée) et ne modélise que les **tokens de sortie**.

---

*Méthodologie : Green Algorithms (calculator.green-algorithms.org) pour le matériel connu + EcoLogits (ecologits.ai) pour le LLM via API. Document révisé le 2026-05-30.*
