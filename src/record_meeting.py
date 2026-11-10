# -*- coding: utf-8 -*-
"""
record_meeting.py — Enregistrement 100% local d'une réunion (Windows).
Capte le son du système (Teams = voix des autres, via loopback WASAPI) + votre micro,
les mixe et écrit un fichier WAV mono 16 kHz. Rien n'est envoyé à l'extérieur.

Prérequis : Windows 10/11, Python 3.10+
    pip install soundcard soundfile numpy
Usage :
    python record_meeting.py --out reunion.wav
    (Arrêt : Ctrl+C)
IMPORTANT : prévenez les participants que vous prenez la réunion en notes.
"""
import argparse, sys, time
import numpy as np
import soundfile as sf
import soundcard as sc

SR = 16000          # 16 kHz suffit pour la transcription
BLOCK = 1024        # taille de bloc

def to_mono(x):
    return x if x.ndim == 1 else x.mean(axis=1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reunion.wav")
    ap.add_argument("--no-mic", action="store_true", help="ne pas enregistrer le micro")
    args = ap.parse_args()

    speaker = sc.default_speaker()
    loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    mic = None if args.no_mic else sc.default_microphone()
    print(f"[i] Système (loopback): {speaker.name}")
    print(f"[i] Micro: {'(désactivé)' if mic is None else mic.name}")
    print(f"[i] Écriture -> {args.out}  | Ctrl+C pour arrêter")

    frames = []
    try:
        if mic is None:
            with loopback.recorder(samplerate=SR, blocksize=BLOCK) as rsys:
                while True:
                    frames.append(to_mono(rsys.record(numframes=BLOCK)))
        else:
            with loopback.recorder(samplerate=SR, blocksize=BLOCK) as rsys, \
                 mic.recorder(samplerate=SR, blocksize=BLOCK) as rmic:
                while True:
                    a = to_mono(rsys.record(numframes=BLOCK))
                    b = to_mono(rmic.record(numframes=BLOCK))
                    n = min(len(a), len(b))
                    frames.append(a[:n] + b[:n])   # mixage simple
    except KeyboardInterrupt:
        print("\n[i] Arrêt demandé.")
    if not frames:
        print("[!] Rien enregistré."); sys.exit(1)
    audio = np.concatenate(frames).astype(np.float32)
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = (audio / peak * 0.95)              # normalisation douce
    sf.write(args.out, audio, SR, subtype="PCM_16")
    print(f"[✓] {args.out} — {len(audio)/SR:.0f} s enregistrées.")

if __name__ == "__main__":
    main()
