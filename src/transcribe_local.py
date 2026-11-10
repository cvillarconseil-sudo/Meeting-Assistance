# -*- coding: utf-8 -*-
"""
transcribe_local.py — Transcription 100% locale d'un WAV (faster-whisper).
Le modèle se télécharge une seule fois (Hugging Face) puis tout est hors-ligne.

Prérequis :
    pip install faster-whisper
    (GPU NVIDIA optionnel : installe CUDA pour accélérer ; sinon CPU, plus lent que le temps réel)
Usage :
    python transcribe_local.py reunion.wav --modele large-v3 --langue ca
    # --langue : fr / es / ca  (ou omettre pour détection auto)
    # --modele : medium (rapide) ou large-v3 (meilleure qualité, + lourd)
Sortie : reunion.txt (horodaté)
"""
import argparse, os, sys
from faster_whisper import WhisperModel

def hms(s):
    h=int(s//3600); m=int((s%3600)//60); sec=int(s%60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--modele", default="large-v3")      # medium | large-v3
    ap.add_argument("--langue", default=None)            # fr | es | ca | None(auto)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or os.path.splitext(args.wav)[0] + ".txt"

    print(f"[i] Chargement du modèle « {args.modele} » (1er lancement = téléchargement)…")
    # device/compute auto : utilise le GPU si dispo, sinon CPU
    model = WhisperModel(args.modele, device="auto", compute_type="auto")

    print("[i] Transcription en cours…")
    segments, info = model.transcribe(
        args.wav, language=args.langue, vad_filter=True,
        beam_size=5, condition_on_previous_text=True,
    )
    print(f"[i] Langue détectée : {info.language} (p={info.language_probability:.2f})")
    with open(out, "w", encoding="utf-8") as f:
        for seg in segments:
            line = f"[{hms(seg.start)} → {hms(seg.end)}] {seg.text.strip()}"
            print(line); f.write(line + "\n")
    print(f"[✓] Transcript -> {out}")

if __name__ == "__main__":
    main()
