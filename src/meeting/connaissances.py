# -*- coding: utf-8 -*-
"""
Base de connaissances locale (SQLite) sur les travaux ferroviaires.

Contenu : sources (vidéos, documents, glossaires), passages de transcription horodatés,
termes (lexique métier, glossaire ERA…) et fiches « méthodes » (renouvellement, bourrage…).
Recherche plein texte (FTS5) sur passages, termes et méthodes.

La base est hors du dépôt (données dérivées de sources tierces) : ``%LOCALAPPDATA%/meeting-assistance``,
ou le dossier donné par la variable ``MEETING_DATA``, ou ``--base``.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,              -- video | document | glossaire | lexique
    titre TEXT NOT NULL,
    url TEXT UNIQUE,
    organisme TEXT, pays TEXT, langue TEXT,
    fichier_local TEXT, ajoute_le TEXT
);
CREATE TABLE IF NOT EXISTS passages (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    debut_s REAL, fin_s REAL, texte TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS termes (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    concept TEXT, categorie TEXT, langue TEXT, terme TEXT NOT NULL, definition TEXT
);
CREATE TABLE IF NOT EXISTS methodes (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    nom TEXT NOT NULL, categorie TEXT, pays TEXT,
    description TEXT, etapes TEXT, engins TEXT, rendement TEXT, contraintes TEXT,
    termes TEXT, horodatage TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(texte, content='passages', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE IF NOT EXISTS termes_fts USING fts5(terme, definition, content='termes', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE IF NOT EXISTS methodes_fts USING fts5(nom, description, etapes, engins, rendement, contraintes,
    termes, content='methodes', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS passages_ai AFTER INSERT ON passages BEGIN
  INSERT INTO passages_fts(rowid, texte) VALUES (new.id, new.texte); END;
CREATE TRIGGER IF NOT EXISTS passages_ad AFTER DELETE ON passages BEGIN
  INSERT INTO passages_fts(passages_fts, rowid, texte) VALUES ('delete', old.id, old.texte); END;
CREATE TRIGGER IF NOT EXISTS termes_ai AFTER INSERT ON termes BEGIN
  INSERT INTO termes_fts(rowid, terme, definition) VALUES (new.id, new.terme, new.definition); END;
CREATE TRIGGER IF NOT EXISTS termes_ad AFTER DELETE ON termes BEGIN
  INSERT INTO termes_fts(termes_fts, rowid, terme, definition) VALUES ('delete', old.id, old.terme, old.definition); END;
CREATE TRIGGER IF NOT EXISTS methodes_ai AFTER INSERT ON methodes BEGIN
  INSERT INTO methodes_fts(rowid, nom, description, etapes, engins, rendement, contraintes, termes)
  VALUES (new.id, new.nom, new.description, new.etapes, new.engins, new.rendement, new.contraintes, new.termes); END;
CREATE TRIGGER IF NOT EXISTS methodes_ad AFTER DELETE ON methodes BEGIN
  INSERT INTO methodes_fts(methodes_fts, rowid, nom, description, etapes, engins, rendement, contraintes, termes)
  VALUES ('delete', old.id, old.nom, old.description, old.etapes, old.engins, old.rendement, old.contraintes, old.termes); END;
"""

LIGNE_TRANSCRIPTION = re.compile(r"^\[(\d\d):(\d\d):(\d\d) → (\d\d):(\d\d):(\d\d)\] (.*)$")


def dossier_donnees() -> str:
    d = os.environ.get("MEETING_DATA") or os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "meeting-assistance")
    os.makedirs(d, exist_ok=True)
    return d


def base_par_defaut() -> str:
    return os.path.join(dossier_donnees(), "connaissances.sqlite")


def ouvrir(chemin: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(chemin or base_par_defaut())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def ajouter_source(con, type_: str, titre: str, url: str | None = None, organisme=None, pays=None,
                   langue=None, fichier_local=None) -> int:
    """Crée la source, ou remplace son contenu si l'URL existe déjà (réimport idempotent)."""
    if url:
        old = con.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
        if old:
            con.execute("DELETE FROM sources WHERE id = ?", (old["id"],))
    cur = con.execute(
        "INSERT INTO sources(type, titre, url, organisme, pays, langue, fichier_local, ajoute_le) VALUES (?,?,?,?,?,?,?,?)",
        (type_, titre, url, organisme, pays, langue, fichier_local, date.today().isoformat()))
    return cur.lastrowid


def importer_lexique(con, chemin: str | None = None) -> int:
    from meeting.vocabulaire import LANGUES, LEXIQUE_DEFAUT, charger_lexique
    chemin = chemin or LEXIQUE_DEFAUT
    sid = ajouter_source(con, "lexique", "Lexique ferroviaire Meeting-Assistance", url="lexique:" + os.path.basename(chemin),
                         fichier_local=chemin)
    n = 0
    for c in charger_lexique(chemin):
        for lg in LANGUES:
            for t in c.termes.get(lg, []):
                con.execute("INSERT INTO termes(source_id, concept, categorie, langue, terme, definition) VALUES (?,?,?,?,?,?)",
                            (sid, c.id, c.categorie, lg, t, c.definition if lg == "fr" else None))
                n += 1
    con.commit()
    return n


def importer_era(con, chemin: str) -> int:
    """Glossaire de l'Agence de l'UE pour les chemins de fer (export CSV, en anglais)."""
    csv.field_size_limit(10 ** 8)
    sid = ajouter_source(con, "glossaire", "ERA Railway Terminology Collection",
                         url="https://www.era.europa.eu/era-railway-terminology-collection",
                         organisme="ERA", pays="UE", langue="en", fichier_local=chemin)
    n = 0
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            terme = (r.get("Term") or "").strip()
            if not terme:
                continue
            doc = (r.get("Document") or "").strip()
            definition = (r.get("Definition") or "").strip() + (f" [{doc}]" if doc else "")
            con.execute("INSERT INTO termes(source_id, concept, categorie, langue, terme, definition) VALUES (?,?,?,?,?,?)",
                        (sid, None, "ERA", "en", terme, definition))
            n += 1
    con.commit()
    return n


def lire_transcription(chemin: str):
    """Lignes « [hh:mm:ss → hh:mm:ss] texte » -> (debut_s, fin_s, texte)."""
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            m = LIGNE_TRANSCRIPTION.match(ligne.strip())
            if m:
                h1, m1, s1, h2, m2, s2 = (int(x) for x in m.groups()[:6])
                yield h1 * 3600 + m1 * 60 + s1, h2 * 3600 + m2 * 60 + s2, m.group(7)


def importer_transcription(con, chemin: str, titre: str, url: str | None = None, organisme=None,
                           pays=None, langue=None, type_: str = "video") -> int:
    sid = ajouter_source(con, type_, titre, url, organisme, pays, langue, fichier_local=chemin)
    n = 0
    for debut, fin, texte in lire_transcription(chemin):
        con.execute("INSERT INTO passages(source_id, debut_s, fin_s, texte) VALUES (?,?,?,?)", (sid, debut, fin, texte))
        n += 1
    con.commit()
    return n


def importer_methodes(con, chemin: str) -> int:
    """Fiches méthodes (JSON : liste d'objets nom, categorie, pays, description, etapes, engins, rendement,
    contraintes, termes, source_url, horodatage). La source est retrouvée par son URL si elle est déjà en base."""
    with open(chemin, encoding="utf-8") as f:
        fiches = json.load(f)
    n = 0
    for m in fiches:
        src = con.execute("SELECT id FROM sources WHERE url = ?", (m.get("source_url"),)).fetchone()
        con.execute("DELETE FROM methodes WHERE nom = ? AND IFNULL(source_id, -1) = IFNULL(?, -1)",
                    (m["nom"], src["id"] if src else None))

        def txt(k):
            v = m.get(k)
            return "\n".join(v) if isinstance(v, list) else v

        con.execute("INSERT INTO methodes(source_id, nom, categorie, pays, description, etapes, engins, rendement, "
                    "contraintes, termes, horodatage) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (src["id"] if src else None, m["nom"], m.get("categorie"), m.get("pays"), txt("description"),
                     txt("etapes"), txt("engins"), txt("rendement"), txt("contraintes"), txt("termes"),
                     m.get("horodatage")))
        n += 1
    con.commit()
    return n


def _fts(requete: str) -> str:
    """Requête simple -> syntaxe FTS5 (chaque mot doit apparaître, préfixe autorisé)."""
    mots = re.findall(r"\w+", requete, flags=re.UNICODE)
    return " ".join(f'"{m}"*' for m in mots)


def chercher(con, requete: str, limite: int = 10) -> dict:
    q = _fts(requete)
    if not q:
        return {"methodes": [], "termes": [], "passages": []}
    methodes = con.execute(
        "SELECT m.nom, m.pays, m.categorie, m.description, s.titre, s.url, m.horodatage FROM methodes_fts f "
        "JOIN methodes m ON m.id = f.rowid LEFT JOIN sources s ON s.id = m.source_id "
        "WHERE methodes_fts MATCH ? ORDER BY rank LIMIT ?", (q, limite)).fetchall()
    termes = con.execute(
        "SELECT t.terme, t.langue, t.concept, t.definition, s.titre FROM termes_fts f JOIN termes t ON t.id = f.rowid "
        "LEFT JOIN sources s ON s.id = t.source_id WHERE termes_fts MATCH ? ORDER BY rank LIMIT ?", (q, limite)).fetchall()
    passages = con.execute(
        "SELECT p.texte, p.debut_s, s.titre, s.url, s.pays FROM passages_fts f JOIN passages p ON p.id = f.rowid "
        "JOIN sources s ON s.id = p.source_id WHERE passages_fts MATCH ? ORDER BY rank LIMIT ?", (q, limite)).fetchall()
    return {"methodes": [dict(r) for r in methodes], "termes": [dict(r) for r in termes],
            "passages": [dict(r) for r in passages]}


def statistiques(con) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("sources", "passages", "termes", "methodes")}


def exporter_markdown(con, chemin: str) -> int:
    """Fiches méthodes, groupées par catégorie, avec leurs sources : un document lisible et partageable."""
    lignes = ["# Méthodes de travaux ferroviaires", "",
              "Fiches tirées des sources de la base de connaissances (vidéos publiques, documents).", ""]
    rows = con.execute("SELECT m.*, s.titre AS s_titre, s.url AS s_url, s.organisme AS s_org FROM methodes m "
                       "LEFT JOIN sources s ON s.id = m.source_id ORDER BY m.categorie, m.nom").fetchall()
    cat = None
    for r in rows:
        if r["categorie"] != cat:
            cat = r["categorie"]
            lignes += [f"## {cat or 'Divers'}", ""]
        lignes.append(f"### {r['nom']}" + (f" ({r['pays']})" if r["pays"] else ""))
        for cle, titre in (("description", None), ("etapes", "Étapes"), ("engins", "Engins"),
                           ("rendement", "Rendement"), ("contraintes", "Contraintes"), ("termes", "Termes")):
            v = r[cle]
            if not v:
                continue
            if titre:
                lignes.append(f"**{titre}** :")
            lignes += [f"- {x}" for x in v.split("\n")] if "\n" in v else [v]
            lignes.append("")
        if r["s_titre"]:
            h = f" (à {r['horodatage']})" if r["horodatage"] else ""
            lignes += [f"Source : [{r['s_titre']}]({r['s_url']}){h}", ""]
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    return len(rows)
