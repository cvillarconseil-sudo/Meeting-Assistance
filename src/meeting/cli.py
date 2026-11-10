# -*- coding: utf-8 -*-
"""Point d'entrée unique : ``meeting record`` et ``meeting transcribe``."""
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

    sub.add_parser("devices", help="lister haut-parleurs et micros")

    t = sub.add_parser("transcribe", help="transcrire un WAV hors ligne (faster-whisper)")
    t.add_argument("wav")
    t.add_argument("--modele", default="large-v3", help="tiny, base, small, medium, large-v3…")
    t.add_argument("--langue", default=None, help="fr, es, ca ; omis = détection automatique")
    t.add_argument("--out", default=None)
    t.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "record":
        from meeting.record import record
        return record(out=args.out, no_mic=args.no_mic, max_seconds=args.duree, micro=args.micro)
    if args.cmd == "devices":
        from meeting.record import list_devices
        return list_devices()
    if args.cmd == "transcribe":
        from meeting.transcribe import transcribe
        transcribe(args.wav, modele=args.modele, langue=args.langue, out=args.out, device=args.device)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
