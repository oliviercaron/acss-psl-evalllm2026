# ============================================================================
# fig_ambiguity_profile.R
# Reproduit la Figure 1 de l'article : « Profil d'ambiguite par base de
# connaissances » (paper/fig_ambiguity_profile.png).
#
# Donnees : comptages reels du linker (nombre de candidats retrouves par
# l'index avant desambiguisation) sur les 491 entites du jeu d'entrainement,
# issus de GeoNamesLinker._query_candidates et MeSHLinker.link. Ce sont
# exactement les valeurs affichees sur les barres de la figure ; elles sont
# reportees en dur ci-dessous, le script est donc autonome (aucune donnee du
# defi n'est requise ni redistribuee).
#
# Usage : depuis ce dossier (paper/),
#   Rscript fig_ambiguity_profile.R
# Sortie : fig_ambiguity_profile.png (PNG 600 dpi).
#
# Dependances R : tidyverse, showtext, sysfonts, ggtext (polices Roboto via
# Google Fonts -> connexion requise au premier appel de font_add_google).
# ============================================================================

library(tidyverse)
library(showtext)
library(sysfonts)
library(ggtext)

font_add_google("Roboto", "Roboto")
font_add_google("Roboto Condensed", "Roboto Condensed")
showtext_auto()
showtext_opts(dpi = 600)

pal_kb <- c(
  "GeoNames" = "#2A6B8A",
  "MeSH"     = "#D45B3A",
  "NIL"      = "#7A7A7A"
)

# Comptages reels du linker, par referentiel et par nombre de candidats.
df_amb <- tibble::tribble(
  ~kb,         ~bucket,  ~n,
  "GeoNames",  "0",       9,
  "GeoNames",  "1",      56,
  "GeoNames",  "2-5",   105,
  "GeoNames",  "6-20",   94,
  "GeoNames",  ">20",    41,
  "MeSH",      "0",       7,
  "MeSH",      "1",     158,
  "MeSH",      "2-5",     0,
  "MeSH",      "6-20",    0,
  "MeSH",      ">20",     0,
  "NIL",       "0",       9,
  "NIL",       "1",       2,
  "NIL",       "2-5",     6,
  "NIL",       "6-20",    2,
  "NIL",       ">20",     2
) %>%
  mutate(
    kb = factor(kb, levels = c("GeoNames", "MeSH", "NIL")),
    bucket = factor(bucket, levels = c("0", "1", "2-5", "6-20", ">20"))
  )

p <- ggplot(df_amb %>% filter(kb != "NIL", n > 0),
            aes(x = bucket, y = n, fill = kb)) +
  geom_col(position = position_dodge2(width = 0.7, preserve = "single"),
           width = 0.6, alpha = 0.85) +
  geom_text(
    aes(label = n),
    position = position_dodge2(width = 0.7, preserve = "single"),
    vjust = -0.4, size = 2.8, family = "Roboto Condensed", colour = "grey30"
  ) +
  scale_fill_manual(values = pal_kb, name = NULL) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.25))) +
  # accolade « Appel au LLM » au-dessus des barres a >= 2 candidats
  annotate("segment", x = 2.7, xend = 5.3, y = 170, yend = 170,
           colour = "grey50", linewidth = 0.4) +
  annotate("segment", x = 2.7, xend = 2.7, y = 166, yend = 170,
           colour = "grey50", linewidth = 0.4) +
  annotate("segment", x = 5.3, xend = 5.3, y = 166, yend = 170,
           colour = "grey50", linewidth = 0.4) +
  annotate("richtext", x = 4, y = 188,
    label = "Appel au LLM (si >= 2 candidats)",
    family = "Roboto", size = 2.4, fill = NA, label.colour = NA,
    colour = "grey40") +
  labs(
    title = "Profil d'ambiguite par base de connaissances",
    subtitle = "Distribution des entites selon l'ambiguite (donnees reelles mesurees sur le corpus d'entrainement)",
    caption = "EvalLLM 2026 - 470 entites a lier (21 NIL exclues), 40 documents",
    x = "Nombre de candidats retrouves par l'index",
    y = "Entites"
  ) +
  theme_void(base_family = "Roboto") +
  theme(
    plot.title = element_markdown(size = 9, face = "bold", margin = margin(b = 2)),
    plot.subtitle = element_text(size = 7, colour = "grey40", margin = margin(b = 6)),
    axis.text.x = element_text(size = 7, colour = "grey30", margin = margin(t = 3)),
    axis.text.y = element_text(size = 6.5, colour = "grey30", margin = margin(r = 3)),
    axis.title.x = element_text(size = 7, colour = "grey40", margin = margin(t = 4)),
    axis.title.y = element_text(size = 7, colour = "grey40", angle = 90, margin = margin(r = 4)),
    legend.position = "bottom",
    legend.text = element_text(size = 7),
    legend.key.size = unit(0.3, "cm"),
    plot.caption = element_text(
      family = "Roboto Condensed", size = 6,
      colour = "grey50", hjust = 0.5, margin = margin(t = 8)
    ),
    plot.margin = margin(8, 6, 4, 6)
  )

ggsave(
  filename = "fig_ambiguity_profile.png",
  plot = p,
  width = 5,
  height = 1.86,
  dpi = 600,
  bg = "white"
)

message("Figure exportee : fig_ambiguity_profile.png")
