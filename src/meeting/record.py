# -*- coding: utf-8 -*-
"""
Enregistrement 100 % local d'une réunion (Windows).

Capte le son du système (Teams = voix des autres, via loopback WASAPI) + le micro,
les mixe et écrit un fichier WAV mono 16 kHz. Rien n'est envoyé à l'extérieur.

Repris de l'ancien ``record_meeting.py`` (M0) : même comportement, mais
- les périphériques sont injectables (tests sans carte son) ;
- ``max_seconds`` permet une durée fixe (tests, essais) ;
- le rappel de consentement est affiché au démarrage.
Limites connues, traitées en M1 : tout est gardé en mémoire jusqu'à l'arrêt,
les deux flux sont lus l'un après l'autre, normalisation par le pic.
"""
from __future__ import annotations

import sys

import numpy as np
import soundfile as sf

SR = 16000          # 16 kHz suffit pour la transcription
BLOCK = 1024        # taille de bloc (échantillons)

CONSENT = ("RAPPEL : prévenez les participants que vous enregistrez la réunion "
           "pour la prendre en notes, et vérifiez que c'est autorisé.")


def to_mono(x):
    x = np.asarray(x)
    return x if x.ndim == 1 else x.mean(axis=1)


def list_devices() -> int:
    """Affiche haut-parleurs et micros (``meeting devices``)."""
    import soundcard as sc
    print("Haut-parleurs (son capté en loopback) :")
    for s in sc.all_speakers():
        print(f"  - {s.name}{'  (défaut)' if s.name == sc.default_speaker().name else ''}")
    print("Micros :")
    for m in sc.all_microphones():
        print(f"  - {m.name}{'  (défaut)' if m.name == sc.default_microphone().name else ''}")
    return 0


def default_devices(no_mic: bool = False, micro: str | None = None):
    """Haut-parleur par défaut (en loopback) et micro (défaut, ou dont le nom contient ``micro``)."""
    import soundcard as sc  # import tardif : les tests n'en ont pas besoin
    speaker = sc.default_speaker()
    loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    if no_mic:
        mic = None
    elif micro:
        mic = sc.get_microphone(micro)   # recherche par nom partiel ; IndexError si absent
    else:
        mic = sc.default_microphone()
    return speaker.name, loopback, mic


def capture(loopback, mic, max_seconds: float | None = None, sr: int = SR, block: int = BLOCK):
    """Lit les flux jusqu'à Ctrl+C (ou ``max_seconds``) et renvoie la liste des blocs mixés."""
    max_blocks = None if max_seconds is None else int(np.ceil(max_seconds * sr / block))
    frames = []
    try:
        if mic is None:
            with loopback.recorder(samplerate=sr, blocksize=block) as rsys:
                while max_blocks is None or len(frames) < max_blocks:
                    frames.append(to_mono(rsys.record(numframes=block)))
        else:
            with loopback.recorder(samplerate=sr, blocksize=block) as rsys, \
                 mic.recorder(samplerate=sr, blocksize=block) as rmic:
                while max_blocks is None or len(frames) < max_blocks:
                    a = to_mono(rsys.record(numframes=block))
                    b = to_mono(rmic.record(numframes=block))
                    n = min(len(a), len(b))
                    frames.append(a[:n] + b[:n])   # mixage simple
    except KeyboardInterrupt:
        print("\n[i] Arrêt demandé.")
    return frames


def write_wav(frames, out: str, sr: int = SR) -> float:
    """Concatène, normalise (pic à 0,95) et écrit en PCM 16 bits. Renvoie la durée en s."""
    audio = np.concatenate(frames).astype(np.float32)
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = audio / peak * 0.95              # normalisation douce
    sf.write(out, audio, sr, subtype="PCM_16")
    return len(audio) / sr


def record(out: str = "reunion.wav", no_mic: bool = False, max_seconds: float | None = None,
           devices=None, micro: str | None = None) -> int:
    """Point d'entrée. ``devices`` = (nom, loopback, micro) pour injecter des périphériques."""
    print(f"[!] {CONSENT}")
    try:
        name, loopback, mic = devices if devices is not None else default_devices(no_mic, micro)
    except IndexError:
        print(f"[!] Aucun micro ne correspond à « {micro} ». Voir : meeting devices")
        return 2
    if no_mic:
        mic = None
    print(f"[i] Système (loopback): {name}")
    print(f"[i] Micro: {'(désactivé)' if mic is None else mic.name}")
    print(f"[i] Écriture -> {out}  | Ctrl+C pour arrêter")
    try:
        frames = capture(loopback, mic, max_seconds=max_seconds)
    except AssertionError:
        # soundcard refuse certains périphériques (format de mixage non « extensible »),
        # ex. micro de casque Dell HR024. Remplacement de la bibliothèque prévu en M1.
        print("[!] Impossible d'ouvrir un périphérique audio (format non pris en charge par soundcard).\n"
              "    Choisissez un autre micro avec --micro <nom> (liste : meeting devices),\n"
              "    ou enregistrez sans micro avec --no-mic.")
        return 3
    except Exception as e:  # périphérique débranché, occupé…
        print(f"[!] Erreur audio : {type(e).__name__}: {e}")
        return 3
    if not frames:
        print("[!] Rien enregistré.")
        return 1
    dur = write_wav(frames, out)
    print(f"[✓] {out} — {dur:.0f} s enregistrées.")
    return 0


if __name__ == "__main__":
    from meeting.cli import main
    sys.exit(main(["record", *sys.argv[1:]]))
