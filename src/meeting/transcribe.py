# -*- coding: utf-8 -*-
"""
Transcription 100 % locale d'un WAV (faster-whisper).

Le modèle se télécharge une seule fois (Hugging Face) au premier lancement,
puis tout est hors ligne. Repris de l'ancien ``transcribe_local.py`` (M0) :
mêmes réglages, modèle injectable pour les tests, choix ``--device``.
"""
from __future__ import annotations

import os
import sys


def hms(s: float) -> str:
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def load_model(modele: str, device: str = "auto", compute_type: str = "auto"):
    from faster_whisper import WhisperModel  # import tardif
    return WhisperModel(modele, device=device, compute_type=compute_type)


def transcribe(wav: str, modele: str = "large-v3", langue: str | None = None,
               out: str | None = None, device: str = "auto", model=None) -> str:
    """Transcrit ``wav`` et écrit un texte horodaté. Renvoie le chemin de sortie."""
    out = out or os.path.splitext(wav)[0] + ".txt"
    if model is None:
        print(f"[i] Chargement du modèle « {modele} » ({device}) "
              "(1er lancement = téléchargement depuis Hugging Face)…")
        model = load_model(modele, device=device)
    print("[i] Transcription en cours…")
    segments, info = model.transcribe(
        wav, language=langue, vad_filter=True,
        beam_size=5, condition_on_previous_text=True,
    )
    print(f"[i] Langue détectée : {info.language} (p={info.language_probability:.2f})")
    with open(out, "w", encoding="utf-8") as f:
        for seg in segments:
            line = f"[{hms(seg.start)} → {hms(seg.end)}] {seg.text.strip()}"
            print(line); f.write(line + "\n")
    print(f"[✓] Transcript -> {out}")
    return out


if __name__ == "__main__":
    from meeting.cli import main
    sys.exit(main(["transcribe", *sys.argv[1:]]))
