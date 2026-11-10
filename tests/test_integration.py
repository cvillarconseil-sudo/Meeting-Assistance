"""Test réel, hors ligne après le 1er lancement : voix de synthèse Windows -> faster-whisper ``tiny``.

Désactivé par défaut (télécharge le modèle tiny, ~75 Mo, depuis Hugging Face au 1er lancement).
Lancer avec : ``set MEETING_IT=1`` puis ``pytest -m integration``.
"""
import os
import subprocess
import sys

import pytest

from meeting.transcribe import transcribe

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(os.environ.get("MEETING_IT") != "1" or sys.platform != "win32",
                                 reason="MEETING_IT=1 et Windows requis")]

TEXTE = "Hello everyone. The next meeting is on Friday at ten o'clock."


def voix_windows(path):
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SetOutputToWaveFile('{path}'); $s.Speak(\"{TEXTE}\"); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=60)


def test_voix_synthese_tiny(tmp_path):
    wav = tmp_path / "voix.wav"
    voix_windows(str(wav))
    out = transcribe(str(wav), modele="tiny", langue="en", device="cpu")
    txt = open(out, encoding="utf-8").read().lower()
    for mot in ("meeting", "friday"):
        assert mot in txt, txt
