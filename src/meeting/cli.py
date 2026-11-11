# -*- coding: utf-8 -*-
"""Point d'entrée unique : ``meeting record``, ``recover``, ``devices``, ``transcribe``."""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="meeting", description="Réunions : enregistrement et transcription 100 % locaux.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="enregistrer le son du système + le micro dans un WAV")
    r.add_argument("--out", default="reunion.wav")
    r.add_argument("--no-mic", action="store_true", help="ne pas enregistrer le micro")
    r.add_argument("--duree", type=float, default=None, help="arrêt automatique après N secondes")
    r.add_argument("--micro", default=None, help="micro à utiliser (partie de son nom, voir meeting devices)")
    r.add_argument("--haut-parleur", default=None,
                   help="haut-parleur dont on capte le son (partie de son nom ; défaut : celui de Windows)")
    r.add_argument("--garder-pistes", action="store_true",
                   help="conserver <sortie>.pistes.wav (piste 1 = système, piste 2 = micro)")
    r.add_argument("--sans-niveau", action="store_true", help="ne pas afficher l'indicateur de niveau")

    v = sub.add_parser("recover", help="remixer les pistes d'un enregistrement interrompu")
    v.add_argument("pistes", help="fichier <sortie>.pistes.wav")
    v.add_argument("--out", default=None)

    sub.add_parser("devices", help="lister haut-parleurs et micros")

    t = sub.add_parser("transcribe", help="transcrire un WAV hors ligne (faster-whisper)")
    t.add_argument("wav")
    t.add_argument("--modele", default="large-v3", help="tiny, base, small, medium, large-v3…")
    t.add_argument("--langue", default=None, help="fr, es, ca ; omis = détection automatique")
    t.add_argument("--out", default=None)
    t.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    t.add_argument("--vocabulaire", default="ferroviaire",
                   help="« ferroviaire » (lexique fourni), chemin d'un lexique CSV, ou « aucun »")
    t.add_argument("--sans-corrections", action="store_true", help="ne pas appliquer data/corrections.csv")

    k = sub.add_parser("kb", help="base de connaissances locale (travaux ferroviaires)")
    k.add_argument("--base", default=None, help="fichier SQLite (défaut : %%LOCALAPPDATA%%/meeting-assistance)")
    ks = k.add_subparsers(dest="kb_cmd", required=True)
    ks.add_parser("stats", help="nombre de sources, passages, termes, méthodes")
    a = ks.add_parser("importer-lexique", help="importer data/lexique_ferroviaire.csv (ou un autre)")
    a.add_argument("chemin", nargs="?", default=None)
    a = ks.add_parser("importer-era", help="importer le glossaire ERA (export CSV)")
    a.add_argument("chemin")
    a = ks.add_parser("importer-transcription", help="importer une transcription horodatée")
    a.add_argument("chemin")
    a.add_argument("--titre", required=True)
    a.add_argument("--url", default=None)
    a.add_argument("--organisme", default=None)
    a.add_argument("--pays", default=None)
    a.add_argument("--langue", default=None)
    a = ks.add_parser("importer-methodes", help="importer des fiches méthodes (JSON)")
    a.add_argument("chemin")
    a = ks.add_parser("chercher", help="recherche plein texte (méthodes, termes, passages)")
    a.add_argument("requete", nargs="+")
    a.add_argument("--limite", type=int, default=8)
    a = ks.add_parser("exporter", help="exporter les fiches méthodes en Markdown")
    a.add_argument("chemin")
    return p


def kb(args) -> int:
    from meeting import connaissances as K
    con = K.ouvrir(args.base)
    c = args.kb_cmd
    if c == "stats":
        for t, n in K.statistiques(con).items():
            print(f"{t:10s} {n}")
    elif c == "importer-lexique":
        print(f"[✓] {K.importer_lexique(con, args.chemin)} termes importés")
    elif c == "importer-era":
        print(f"[✓] {K.importer_era(con, args.chemin)} termes ERA importés")
    elif c == "importer-transcription":
        n = K.importer_transcription(con, args.chemin, args.titre, args.url, args.organisme, args.pays, args.langue)
        print(f"[✓] {n} passages importés")
    elif c == "importer-methodes":
        print(f"[✓] {K.importer_methodes(con, args.chemin)} fiches méthodes importées")
    elif c == "chercher":
        r = K.chercher(con, " ".join(args.requete), args.limite)
        for m in r["methodes"]:
            print(f"[méthode] {m['nom']} ({m['pays'] or '-'}) — {m['description'] or ''}"
                  + (f"\n          source : {m['titre']} {m['url'] or ''}" if m["titre"] else ""))
        for t in r["termes"]:
            print(f"[terme]   {t['terme']} ({t['langue']}) — {(t['definition'] or t['concept'] or '')[:160]}")
        for p in r["passages"]:
            print(f"[extrait] {p['titre']} @{int(p['debut_s'] // 60):02d}:{int(p['debut_s'] % 60):02d} — {p['texte']}")
        if not any(r.values()):
            print("(aucun résultat)")
    elif c == "exporter":
        print(f"[✓] {K.exporter_markdown(con, args.chemin)} fiches -> {args.chemin}")
    con.close()
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "record":
        from meeting.record import record
        return record(out=args.out, no_mic=args.no_mic, max_seconds=args.duree, micro=args.micro,
                      haut_parleur=args.haut_parleur, garder_pistes=args.garder_pistes,
                      niveau=not args.sans_niveau)
    if args.cmd == "recover":
        from meeting.record import recover
        return recover(args.pistes, args.out)
    if args.cmd == "devices":
        from meeting.record import list_devices
        return list_devices()
    if args.cmd == "transcribe":
        from meeting.transcribe import transcribe
        transcribe(args.wav, modele=args.modele, langue=args.langue, out=args.out, device=args.device,
                   vocabulaire=None if args.vocabulaire == "aucun" else args.vocabulaire,
                   corrections=not args.sans_corrections)
        return 0
    if args.cmd == "kb":
        return kb(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
