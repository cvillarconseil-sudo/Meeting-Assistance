from types import SimpleNamespace as NS

from meeting import transcribe as T
from meeting import vocabulaire as V


def test_lexique_fourni_complet():
    lex = V.charger_lexique()
    assert len(lex) >= 30
    ids = {c.id for c in lex}
    assert {"ballast", "traverse", "catenaire", "appareil_de_voie", "suite_rapide"} <= {i.replace("é", "e") for i in ids}
    for c in lex:
        assert c.definition, c.id
        for lg in ("fr", "es", "it", "pt", "de", "en"):
            assert c.termes[lg], (c.id, lg)          # chaque concept traduit dans les 6 langues principales


def test_hotwords_langue_et_longueur():
    lex = V.charger_lexique()
    fr, es = V.hotwords("fr", lex), V.hotwords("es", lex)
    assert "ballast" in fr and "traverse" in fr and "caténaire" in fr
    assert "balasto" in es and "traviesa" in es and "ballast" not in es.split(", ")
    assert len(fr) <= V.MAX_HOTWORDS_CAR and len(es) <= V.MAX_HOTWORDS_CAR
    # le premier terme de chaque concept passe avant les synonymes
    premiers = [c.termes["fr"][0] for c in lex]
    choisis = fr.split(", ")
    assert choisis == premiers[: len(choisis)]


def test_hotwords_langue_inconnue():
    assert V.hotwords("xx", V.charger_lexique()) == ""


def test_corrections(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("langue;erreur;correction;origine\nfr;balaises;ballast;t\n*;RFF;SNCF Réseau;t\npt;taludos;taludes;t\n",
                 encoding="utf-8")
    r = V.charger_corrections(str(p))
    assert V.corriger("Les Balaises et les taludos, RFF.", "fr", r) == ("Les ballast et les taludos, SNCF Réseau.", 2)
    assert V.corriger("balaisesX", "fr", r) == ("balaisesX", 0)      # mot entier seulement
    assert V.corriger("taludos", "pt", r) == ("taludes", 1)


class FakeModel:
    def __init__(self, langue="fr"):
        self.kw, self.langue = None, langue

    def detect_language(self, audio, **kw):
        return self.langue, 0.99, []

    def transcribe(self, wav, **kw):
        self.kw = kw
        return iter([NS(start=0.0, end=2.0, text=" On remet du balaises neuf. ")]), NS(language=self.langue,
                                                                                    language_probability=0.99)


def test_transcription_avec_vocabulaire_et_corrections(tmp_path, monkeypatch):
    import numpy as np
    import faster_whisper
    monkeypatch.setattr(faster_whisper, "decode_audio", lambda wav: np.zeros(16000, np.float32))
    wav = tmp_path / "r.wav"; wav.write_bytes(b"")
    m = FakeModel("fr")
    out = T.transcribe(str(wav), model=m)                 # langue détectée, puis hotwords en français
    assert "ballast" in m.kw["hotwords"] and "traverse" in m.kw["hotwords"]
    assert open(out, encoding="utf-8").read().strip() == "[00:00:00 → 00:00:02] On remet du ballast neuf."


def test_transcription_sans_vocabulaire(tmp_path):
    wav = tmp_path / "r.wav"; wav.write_bytes(b"")
    m = FakeModel("fr")
    out = T.transcribe(str(wav), langue="fr", model=m, vocabulaire=None, corrections=False)
    assert m.kw["hotwords"] is None
    assert "balaises" in open(out, encoding="utf-8").read()
