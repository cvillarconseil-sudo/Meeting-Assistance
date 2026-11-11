# -*- coding: utf-8 -*-
"""
Vocabulaire métier (ferroviaire) pour guider la transcription et corriger les erreurs connues.

- ``data/lexique_ferroviaire.csv`` : un concept par ligne, termes par langue séparés par « | »
  (fr, es, it, pt, de, en, ca, nl), catégorie et définition courte en français.
- ``data/corrections.csv`` : erreurs de reconnaissance constatées -> forme correcte, par langue.

Le lexique sert à construire les « hotwords » de faster-whisper (mots que le modèle doit
privilégier), dans la langue de l'enregistrement. Tout reste local.
"""
from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from importlib import resources

LANGUES = ("fr", "es", "it", "pt", "de", "en", "ca", "nl")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
LEXIQUE_DEFAUT = os.path.join(DATA, "lexique_ferroviaire.csv")
CORRECTIONS_DEFAUT = os.path.join(DATA, "corrections.csv")
# Whisper décode au plus 448 jetons, dont jusqu'à 223 pour le texte précédent : au-delà d'environ
# 200 jetons de mots-clés, faster-whisper échoue (« maximum decoding length must be > 0 », vu avec
# 700 caractères en français). 350 caractères ≈ 110 à 130 jetons.
MAX_HOTWORDS_CAR = 350


@dataclass
class Concept:
    id: str
    categorie: str
    definition: str
    termes: dict = field(default_factory=dict)   # langue -> [termes]


def charger_lexique(chemin: str | None = None) -> list[Concept]:
    chemin = chemin or LEXIQUE_DEFAUT
    concepts = []
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            termes = {lg: [t.strip() for t in (ligne.get(lg) or "").split("|") if t.strip()] for lg in LANGUES}
            concepts.append(Concept(ligne["concept"].strip(), ligne["categorie"].strip(),
                                    ligne["definition"].strip(), termes))
    return concepts


def hotwords(langue: str, concepts: list[Concept], max_car: int = MAX_HOTWORDS_CAR) -> str:
    """Termes de la langue, les plus importants d'abord (1er terme de chaque concept, puis les suivants)."""
    listes = [c.termes.get(langue, []) for c in concepts]
    choisis, vus, rang = [], set(), 0
    while any(rang < len(l) for l in listes):
        for l in listes:
            if rang < len(l):
                t = l[rang]
                if t.lower() not in vus:
                    vus.add(t.lower())
                    choisis.append(t)
        rang += 1
    texte = ""
    for t in choisis:
        suivant = f"{texte}, {t}" if texte else t
        if len(suivant) > max_car:
            break
        texte = suivant
    return texte


def charger_corrections(chemin: str | None = None) -> list[tuple[str, re.Pattern, str]]:
    chemin = chemin or CORRECTIONS_DEFAUT
    if not os.path.exists(chemin):
        return []
    regles = []
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            erreur = ligne["erreur"].strip()
            motif = re.compile(r"(?<!\w)" + re.escape(erreur) + r"(?!\w)", re.IGNORECASE)
            regles.append((ligne["langue"].strip(), motif, ligne["correction"].strip()))
    return regles


def corriger(texte: str, langue: str | None, regles) -> tuple[str, int]:
    """Applique les corrections de la langue (et celles marquées « * »). Renvoie (texte, nb de remplacements)."""
    n_total = 0
    for lg, motif, correction in regles:
        if lg in ("*", langue):
            texte, n = motif.subn(correction, texte)
            n_total += n
    return texte, n_total
