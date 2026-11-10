from types import SimpleNamespace as NS

from meeting import transcribe as T
from meeting.cli import build_parser


class FakeModel:
    def __init__(self):
        self.kw = None

    def transcribe(self, wav, **kw):
        self.kw = kw
        segs = [NS(start=0.0, end=2.5, text=" Bonjour à tous. "),
                NS(start=3661.2, end=3663.9, text="Action pour Marie, vendredi.")]
        return iter(segs), NS(language="fr", language_probability=0.98)


def test_hms():
    assert T.hms(0) == "00:00:00"
    assert T.hms(59.9) == "00:00:59"
    assert T.hms(3661.2) == "01:01:01"


def test_sortie_horodatee(tmp_path):
    wav = tmp_path / "r.wav"; wav.write_bytes(b"")
    m = FakeModel()
    out = T.transcribe(str(wav), langue="fr", model=m)
    assert out == str(tmp_path / "r.txt")
    lignes = open(out, encoding="utf-8").read().splitlines()
    assert lignes == ["[00:00:00 → 00:00:02] Bonjour à tous.",
                      "[01:01:01 → 01:01:03] Action pour Marie, vendredi."]
    assert m.kw["language"] == "fr" and m.kw["vad_filter"] is True


def test_cli():
    a = build_parser().parse_args(["transcribe", "x.wav", "--modele", "tiny", "--langue", "ca", "--device", "cpu"])
    assert (a.cmd, a.wav, a.modele, a.langue, a.device) == ("transcribe", "x.wav", "tiny", "ca", "cpu")
    a = build_parser().parse_args(["record", "--out", "a.wav", "--no-mic", "--duree", "5"])
    assert (a.cmd, a.out, a.no_mic, a.duree) == ("record", "a.wav", True, 5.0)
