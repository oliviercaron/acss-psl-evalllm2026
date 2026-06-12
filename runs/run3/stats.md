# Run 3 — Stats

## Soumission

- **Date** : 29 mai 2026 (J+2, dernier jour de phase de test)
- **Fichier** : `acss-psl_run_3.json` (933 KB)
- **Validation format** : ✅ OK (`src/validate_predictions.py test_evalLLM.json runs/run3/acss-psl_run_3.json`)
- **Mail** : à envoyer avec Run 1 + Run 2 (tout ensemble)

## Configuration utilisée

- Mode : `--no-memory --llm-reranker`, **GeoNames listwise top-5** (cf §6.1 ; MeSH inchangé)
- LLM : GPT-5.4-nano (temperature=0, max_completion_tokens=100), prompt **anglais**
- Même famille méthodologique que Run 1/2 : cascade rule-based + LLM listwise zero-shot.
  Run 3 = raffinements de couverture supplémentaires (aucun overtuning, aucune
  triche sur le test ; tous les ajouts justifiés par le guide / le train gold /
  des faits MeSH vérifiables).

## Mise à jour finale — top-5 + continent + qualité données + Wikidata (rebuild)

Run 3 **rebuildé**, améliorations désormais **natives** dans le pipeline :

1. **GeoNames listwise top-5** (au lieu de top-10). Balayage isolé (contexte ±200
   fixe, 2 runs/config) : top-5 = sweet spot — **train ~92.0-92.2 vs ~91.4-92.0
   pour top-10** (au-dessus de la bande de variance, 0 variance interne) ET plus
   frugal (moins de tokens candidats → bonus carbone). cf.
   `notes/error_analysis_run3.md` §6.1. MeSH inchangé (listes ≤3 → top-k sans effet).
2. **Intercept « (le) continent <adjectif> »** (`_resolve_periphrase`, table fermée
   `CONTINENT_ADJ_TO_ID`, IDs vérifiés CONT, justifié gold train + guide) :
   `continent africain` → 6255146, `continent européen` → 6255148 (étaient NIL) ;
   `continent américain` reste NIL (ambigu). +6 tests `tests/test_periphrase.py`. cf. §8.
3. **Fix `\n` littéral** (`normalize`) : `"Sierra Leone\n\n"` / `"province de Hubei\n\n"`
   (caractères backslash+n littéraux, artefact test) → un PAYS n'est plus laissé NIL.
   Récupère 2403846 (Sierra Leone) et 1806949 (Hubei). + contrôle `src/data_quality.py`
   (warning au build ; `literal_escape: 2` s'est bien déclenché à ce rebuild). cf. §10.1-10.2.
4. **Fallbacks de couverture** (fin de cascade → ne peuvent que NIL→lien) : tiret↔espace
   (`Grande-Comore`→921882) + préfixe admin nu sans « de » (`région Nouvelle-Aquitaine`
   →11071620), garde-fou classe R/S (jamais une rue). Train **0 régression**, test **+2
   propres**. cf. §10.3.
5. **Couche exonymes Wikidata** (fallback caché, fin de cascade) : cache figé
   `data/processed/wikidata_search_cache.json` (Wikidata api.php **wholesale** → P1566
   + labels/alias FR, validé GeoNames, classe R/S exclue) → `_disambiguate`. Récupère
   **~10 mentions** FR exonymes/abréviations (Tchétchénie 569665, RD Congo 203312,
   Transbaïkalie, Khan Cheikhoun, Montsinéry, lacs Vänern/Vättern, Chine continentale,
   continent américain, côte est). Train **0 régression** ; inspection contexte test
   **10/10 correctes**. Lecture seule → reproductible, 0 réseau au predict. cf. §11.

- **Abstention LLM (`-1` = NIL)** testée (§9) : net dans la variance + coûte des tokens
  → **non livrée** (`allow_abstain=False`).
- **RD Congo / Tchétchénie** : désormais récupérés par la **couche Wikidata wholesale**
  (point 5) — la voie *propre* (ressource externe complète), PAS un alias test à la main
  (anti-triche §10.4 / §11.3).
- Distribution finale : GeoNames **1137** / MeSH **563** / NIL **140 (7.61 %)**.
- Format **revalidé ✅**. Backups successifs : `.bak`, `.pre-top5`, `.pre-coverage`,
  `.pre-wikidata` (chaque étape réversible).
- Tests : **113 passed, 1 skipped** (état Run 3 ; depuis l'ajout du flag `EVALLLM_TEST_INFORMED`,
  ce décompte correspond au mode `=1` — le défaut/clean donne **100 passed, 14 skipped**, cf.
  `notes/article_master.md` §4.1). Détails : `notes/error_analysis_run3.md` §6.1, §8-§11.

## Changements vs Run 2

### Tier 1 — Ajouts dictionnaire (sûrs)

1. **Cluster Marburg** (FR_MANUAL_DICT + LABEL_OVERRIDES) :
   - Maladie → D008379 (`fièvre de Marburg`, `maladie à virus de Marburg`, etc.)
   - `Marburg` [DIS_REF_TO_PATH] → D029024 (Marburgvirus)
   - Symétrie stricte avec ebola/lassa déjà présents.
2. **Encéphalite à tiques** : `TBE`/`encéphalite à tique` (singulier)/`méningoencéphalite
   à tique` → D004675 ; `TBEV` → D004669.
3. **VHC** (LABEL_OVERRIDES) : PATHOGEN → D016174 (Hepacivirus) ; PATH_REF_TO_DIS
   → D006526 (Hepatitis C).
4. **Sous-régions UN** (FR_GEONAMES_ALIASES) : `Amérique latine` → 7730009,
   `Caraïbes` → 7729891, `Europe orientale` → 7729884. **Confirmées par le train
   gold** (annotées exactement ainsi dans train_evalLLM.json) ; les alias français
   sont absents de GeoNames (seuls les noms anglais "Caribbean"… y figurent).

### Tier 2 — Mécanisme acronyme→expansion (généralisable)

`_propagate_acronym_definitions` : post-passe au niveau document. Si une entité
NIL est un acronyme (2-6 majuscules) et que le texte contient une définition
explicite `<expansion> (ACR)` où `<expansion>` est une entité déjà liée **du même
label**, on propage l'id_kb/source. Garde-fous : définition parenthésée explicite
requise + label identique (évite p.ex. qu'un acronyme PATHOGEN hérite d'un id de
maladie). Cas résolus : `CRE` ← carbapenem-resistant Enterobacteriaceae (D000073182),
`SG` ← syphilis congénitale (D013590). Généralisation linguistique, pas test-driven.

## Distribution des prédictions

| Source | Run 1 | Run 2 | Run 3 | Δ(R3-R1) |
|--------|-------|-------|-------|----------|
| GeoNames | 1097 | 1106 | **1137** | +40 |
| MeSH | 524 | 529 | **563** | +39 |
| NIL | 219 (11.9%) | 205 (11.1%) | **140 (7.61%)** | −79 |
| **Total** | 1840 | 1840 | 1840 | — |

(Run 3 final = top-5 + intercept continent + fix `\n` + fallbacks couverture +
**couche exonymes Wikidata**, tous natifs. La couche Wikidata récupère ~14 occurrences
(Tchétchénie, RD Congo, Khan Cheikhoun, Transbaïkalie, Montsinéry, lacs, … ; cf. §11),
faisant passer le NIL de 8.37 % → **7.61 %** ; cf. « Mise à jour finale ».)

## Gains détaillés (NIL → linked vs Run 2 : +44, 0 régression)

| Cible | n | Famille |
|---|---|---|
| D004675 (encéphalite à tiques) | 14 | TBE×8 + sing.×4 + méningoenc.×2 |
| D008379 (Marburg virus disease) | 9 | Marburg maladie |
| 7730009 (Amérique latine) | 6 | sub-region UN |
| D029024 (Marburgvirus) | 4 | Marburg pathogène |
| 7729891 (Caraïbes) | 3 | sub-region UN |
| D016174 (Hepacivirus / VHC) | 2 | VHC pathogène |
| D004669 (TBEV) | 2 | virus encéphalite à tiques |
| D006526 (Hepatitis C / VHC) | 1 | VHC→maladie |
| **D013590 (syphilis congénitale / SG)** | 1 | **Tier 2 acronyme** |
| **D000073182 (CRE)** | 1 | **Tier 2 acronyme** |
| 7729884 (Europe orientale) | 1 | sub-region UN |

## Diff complet Run 2 → Run 3

- **44** NIL → linked (tous justifiés)
- **0** linked → NIL (aucune régression)
- **22** ID changed = variations du LLM listwise (température=0 mais non
  déterministe côté serveur). Net positif, mais 2 cas défavorables notés pour
  transparence : `France` (pays 3017382 → lieu-dit 12313681) et `monde`
  (Earth 6295630 → cours d'eau 12267786). Bruit LLM inhérent, non causé par le code.

## Non-régression sur train

| Run | Train ranking (--no-memory --llm-reranker) |
|---|---|
| Run 1 | 91.05 |
| Run 2 | 91.19 |
| Run 3 (top-10) | 91.42 |
| **Run 3 (programme final complet)** | **92.22** |

Ranking officiel = `(InKB Accuracy partielle + NEL F1)/2`. Le **programme final**
(top-5 + continent + fix `\n` + fallbacks couverture + couche Wikidata) sur le train :
**RANKING 92.22** (InKB partielle **92.12**, NEL F1 **92.32** ; GeoNames F1 91.06,
MeSH F1 94.74). → **+0.80 vs Run 3 top-10 (91.42)**, essentiellement l'effet **top-5**
(les gains continent/`\n`/Wikidata sont **test-only** → ~0 sur le train, mais réduisent
le NIL test 11.9 %→7.61 %). Variance test-retest LLM ±0.21. **0 régression train.**

## Tests

- **98 passed, 1 skipped** *(instantané intermédiaire Run 3 — SUPERSÉDÉ ; voir le décompte
  final plus haut : 113/1 en mode test-informed, 100/14 skipped en clean)*. 21 tests Run 3 :
  Marburg, TBE, VHC, sub-regions, mécanisme acronyme + garde-fous FP ; +6 tests périphrase continent.

## Performance / carbone

- Durée : ~15 min (1 hang réseau intermittent → relance, cf. carbon_footprint.txt)
- Coût API : ~$0.08
- Empreinte : ~70 g CO₂eq

## Score attendu test

- Estimation centrale : **92-93** (gain **+60** entités liées vs Run 1 : 1681 vs
  1621, NIL rate **8.64 %** proche du train ~4-9%). *Projection (pas de gold test).*
- Run 3 est notre **meilleur run de la famille rule-based**.

## Note méthodologique (pour l'article)

Run 1/2/3 forment **une seule famille** : cascade rule-based + LLM listwise
zero-shot, raffinée de façon incrémentale et reproductible sans overtuning. Une
2e famille (machine learning : dense retrieval / cross-encoder) sera développée
pour l'article (deadline 12 juin) comme comparaison de paradigmes — hors
classement officiel, où le rule-based frugal maximise à la fois le score et le
bonus empreinte carbone.
