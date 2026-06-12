"""Estimation EcoLogits de l'empreinte des runs API (GPT-5.4-nano) — EvalLLM 2026, acss-psl.

POURQUOI. Green Algorithms suppose un matériel connu (notre H100 local => énergie MESURÉE
via nvidia-smi). Pour une API propriétaire (OpenAI), le GPU et le datacenter sont inconnus :
on ne peut donc PAS appliquer Green Algorithms proprement. L'outil standard pour estimer
l'impact d'un LLM appelé via API est EcoLogits (https://ecologits.ai), utilisé par d'autres
équipes du challenge (p. ex. O_FT@EvalLLM).

MÉTHODO EcoLogits. L'impact est estimé à partir (a) du MODÈLE (nombre de paramètres
actifs/totaux, depuis la base interne d'EcoLogits — gpt-5.4-nano y figure) et (b) du nombre
de tokens de SORTIE. Le GWP renvoyé combine :
  - usage    : énergie d'inférence x intensité carbone de la grille ;
  - embodied : fabrication/amortissement du matériel.
Zone électrique par défaut = "WOR" (moyenne monde). On donne aussi "FRA" à titre indicatif.

LIMITE IMPORTANTE. EcoLogits ne facture que les tokens de SORTIE. Notre tâche de reranking
est « input-heavy » (~310 tokens d'entrée / ~50 de sortie par appel) : le prefill de
l'entrée n'est pas modélisé, donc cette estimation est plutôt une BORNE BASSE de l'énergie.

HYPOTHÈSES DU RUN (cf. runs/run3/carbon_footprint.txt) :
  - ~880 appels LLM par run (mentions à >= 2 candidats) ;
  - ~50 tokens de sortie par appel ;
  - ~0,5 s de latence par appel.

REPRO : pip install ecologits ; python experiments/ecologits_api_estimate.py
(EcoLogits 0.10.1 utilisé. Aucune clé API requise : estimation hors-ligne depuis la base.)
"""
import warnings
warnings.filterwarnings("ignore")
from ecologits.tracers.utils import llm_impacts

MODEL = "gpt-5.4-nano"   # modèle réellement utilisé (présent dans EcoLogits >= 0.10)
CALLS = 880              # appels LLM par run
OUT_TOKENS = 50          # tokens de sortie par appel
LATENCY = 0.5            # secondes par appel

# Repère mesuré (run local Gemma), pour comparaison (GPU 1,05 g mesuré + CPU Ryzen ~0,10 g)
GEMMA_MEASURED_WH = 11.2
GEMMA_MEASURED_G = 1.15


def _lohi(impact):
    """Retourne (min, max) d'un impact EcoLogits (gère les RangeValue)."""
    v = impact.value
    return (v.min, v.max) if hasattr(v, "min") else (v, v)


def per_run(zone=None):
    """Impact estimé d'UN run nano. Retourne ((Wh_min, Wh_max), (g_min, g_max))."""
    o = llm_impacts("openai", MODEL, OUT_TOKENS, LATENCY, zone)
    elo, ehi = _lohi(o.energy)   # kWh / appel
    glo, ghi = _lohi(o.gwp)      # kgCO2e / appel
    return (elo * CALLS * 1000, ehi * CALLS * 1000), (glo * CALLS * 1000, ghi * CALLS * 1000)


if __name__ == "__main__":
    print(f"EcoLogits — {MODEL} — {CALLS} appels x {OUT_TOKENS} tok sortie, latence {LATENCY}s/appel\n")
    print(f"{'zone':12s} {'energie/run (Wh)':22s} {'GWP/run (gCO2e)':20s}")
    print("-" * 56)
    for zone, label in [(None, "WOR (monde)"), ("FRA", "France")]:
        (ewl, ewh), (ggl, ggh) = per_run(zone)
        print(f"{label:12s} {ewl:6.2f} - {ewh:6.2f}        {ggl:5.2f} - {ggh:5.2f}")
    print("\nNB : EcoLogits ne compte que les tokens de SORTIE => borne basse (tache input-heavy).")
    print(f"Repere MESURE (run local Gemma) : GPU {GEMMA_MEASURED_WH} Wh mesures -> 1.05 g ; total avec CPU Ryzen ~{GEMMA_MEASURED_G} g (grille FR).")
