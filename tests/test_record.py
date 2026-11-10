import shutil
import time

import numpy as np
import pytest
import soundfile as sf

from meeting import record as R
from meeting.cli import main


def signal(freq, amp, debut, n):
    t = (debut + np.arange(n)) / R.SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class FakeRecorder:
    """Enregistreur simulé : sinus (ou silence), stéréo.

    ``stop_after`` : Ctrl+C après N blocs ; ``erreur_apres`` : panne (RuntimeError) après N blocs ;
    ``accel`` : cadence en temps réel accéléré (sinon aussi vite que possible) ;
    ``crochet(n)`` : appelé avant chaque bloc (tests d'écriture progressive).
    """

    def __init__(self, freq, amp, stop_after=None, channels=2, erreur_apres=None, accel=None, crochet=None):
        self.freq, self.amp, self.stop_after, self.channels = freq, amp, stop_after, channels
        self.erreur_apres, self.accel, self.crochet = erreur_apres, accel, crochet
        self.n = 0
        self.t0 = 0

    def __enter__(self):
        self.debut = time.perf_counter()
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        if self.stop_after is not None and self.n >= self.stop_after:
            raise KeyboardInterrupt
        if self.erreur_apres is not None and self.n >= self.erreur_apres:
            raise RuntimeError("périphérique débranché")
        if self.crochet:
            self.crochet(self.n)
        if self.accel and self.n % 64 == 0:
            cible = self.debut + self.t0 / R.SR / self.accel
            attente = cible - time.perf_counter()
            if attente > 0:
                time.sleep(attente)
        x = signal(self.freq, self.amp, self.t0, numframes)
        self.t0 += numframes; self.n += 1
        return np.repeat(x[:, None], self.channels, axis=1)


class FakeDevice:
    def __init__(self, name, **kw):
        self.name, self.kw = name, kw
        self.rec = None

    def recorder(self, samplerate, blocksize):
        assert samplerate == R.SR and blocksize == R.TAMPON
        self.rec = FakeRecorder(**self.kw)
        return self.rec


def devices(mic=True, stop_after=None, sys_amp=0.2, mic_amp=0.1, **kw_mic):
    lb = FakeDevice("haut-parleur test", freq=440, amp=sys_amp, stop_after=stop_after)
    m = FakeDevice("micro test", freq=1000, amp=mic_amp, stop_after=stop_after, **kw_mic) if mic else None
    return ("haut-parleur test", lb, m)


def pics(a, sr=R.SR, k=2):
    spec = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
    return sorted(f[np.argsort(spec)[-k:]])


def test_duree_fixe_mixage(tmp_path, capsys):
    out = tmp_path / "t.wav"
    assert R.record(str(out), max_seconds=2.0, devices=devices()) == 0
    a, sr = sf.read(out)
    assert sr == 16000 and a.ndim == 1
    assert len(a) == 2 * sr                                 # durée exacte
    assert abs(np.max(np.abs(a)) - 0.95) < 1e-3            # normalisation
    p = pics(a)
    assert abs(p[0] - 440) < 2 and abs(p[1] - 1000) < 2   # les deux flux sont mixés
    sortie = capsys.readouterr().out
    assert "RAPPEL" in sortie                               # consentement affiché
    assert "dB" in sortie                                   # indicateur de niveau
    assert not (tmp_path / "t.pistes.wav").exists()         # pistes supprimées par défaut


def test_pistes_separees_conservees(tmp_path):
    out = tmp_path / "t.wav"
    assert R.record(str(out), max_seconds=1.0, devices=devices(), garder_pistes=True) == 0
    p, sr = sf.read(tmp_path / "t.pistes.wav")
    assert p.shape == (sr, 2)
    assert abs(pics(p[:, 0], k=1)[0] - 440) < 2            # piste 1 = système
    assert abs(pics(p[:, 1], k=1)[0] - 1000) < 2           # piste 2 = micro


def test_sans_micro(tmp_path):
    out = tmp_path / "t.wav"
    assert R.record(str(out), no_mic=True, max_seconds=1.0, devices=devices()) == 0
    a, sr = sf.read(out)
    spec = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
    assert abs(f[np.argmax(spec)] - 440) < 2
    assert spec[np.argmin(np.abs(f - 1000))] < 0.01 * spec.max()   # pas de micro


def test_ctrl_c_ecrit_le_fichier(tmp_path):
    out = tmp_path / "t.wav"
    assert R.record(str(out), devices=devices(stop_after=20)) == 0
    a, sr = sf.read(out)
    assert len(a) == 20 * R.BLOCK


def test_rien_enregistre(tmp_path):
    out = tmp_path / "t.wav"
    assert R.record(str(out), devices=devices(stop_after=0)) == 1
    assert not out.exists() and not (tmp_path / "t.pistes.wav").exists()


def test_peripherique_refuse_message_clair(tmp_path, capsys):
    class Refus(FakeDevice):
        def recorder(self, samplerate, blocksize):
            raise AssertionError   # comportement de soundcard sur un format non extensible
    d = ("hp", FakeDevice("hp", freq=440, amp=0.2), Refus("micro casque"))
    out = tmp_path / "t.wav"
    assert R.record(str(out), max_seconds=1.0, devices=d) == 3
    assert "--micro" in capsys.readouterr().out and not out.exists()


def test_silence_ne_plante_pas(tmp_path):
    out = tmp_path / "t.wav"
    assert R.record(str(out), max_seconds=0.5, devices=devices(sys_amp=0.0, mic_amp=0.0)) == 0
    a, _ = sf.read(out)
    assert np.all(a == 0)


def test_alerte_flux_silencieux(tmp_path, capsys):
    out = tmp_path / "t.wav"
    assert R.record(str(out), max_seconds=R.SILENCE_ALERTE_S + 5, devices=devices(mic_amp=0.0), niveau=False) == 0
    sortie = capsys.readouterr().out
    assert "ALERTE : flux micro silencieux" in sortie
    assert "flux système" not in sortie


def test_panne_en_cours_garde_les_pistes_et_recover(tmp_path, capsys):
    out = tmp_path / "t.wav"
    assert R.record(str(out), devices=devices(erreur_apres=50)) == 3
    pistes = tmp_path / "t.pistes.wav"
    assert "meeting recover" in capsys.readouterr().out
    n = sf.info(str(pistes)).frames
    assert n == 50 * R.BLOCK                                # tout ce qui a été livré avant la panne est écrit
    assert main(["recover", str(pistes)]) == 0
    a, _ = sf.read(out)
    assert len(a) == n


def test_fichier_lisible_pendant_l_enregistrement(tmp_path):
    """Simule un plantage : copie du fichier de pistes en cours d'écriture, qui doit être lisible."""
    pistes = tmp_path / "t.pistes.wav"
    copie = tmp_path / "copie.wav"

    def crochet(n):
        if n == 100:
            time.sleep(1.3)          # laisse passer une mise à jour d'en-tête (chaque seconde)
        if n == 101:
            shutil.copy(pistes, copie)

    assert R.record(str(tmp_path / "t.wav"), max_seconds=10, devices=devices(crochet=crochet), niveau=False) == 0
    a, _ = sf.read(copie)
    assert len(a) >= 99 * R.BLOCK


def test_recover_fichier_absent(tmp_path):
    assert main(["recover", str(tmp_path / "absent.pistes.wav")]) == 2


def test_choix_peripherique_par_nom():
    class D:
        def __init__(self, name): self.name = name
    liste = [D("Casque Dell HR024"), D("Microphone Array on SoundWire")]
    assert R._choisir(liste, "array", "micro").name.startswith("Microphone")
    with pytest.raises(LookupError):
        R._choisir(liste, "brio", "micro")


@pytest.mark.slow
def test_reunion_simulee_une_heure_sans_perte(tmp_path):
    """Critère de sortie M1 : 1 h simulée (cadence accélérée x400), aucune perte, mixage vérifié."""
    duree = 3600
    out = tmp_path / "t.wav"
    lb = FakeDevice("hp", freq=440, amp=0.3, accel=400)
    mic = FakeDevice("mic", freq=1000, amp=0.2, accel=400)
    assert R.record(str(out), max_seconds=duree, devices=("hp", lb, mic), garder_pistes=True, niveau=False) == 0
    pistes = tmp_path / "t.pistes.wav"
    assert sf.info(str(pistes)).frames == duree * R.SR     # aucun échantillon perdu ni ajouté
    assert sf.info(str(out)).frames == duree * R.SR
    # chaque piste est exactement le signal émis (à la quantification 16 bits près), sur toute la durée
    q = 1.5 / 32768
    debut = 0
    for bloc in sf.blocks(str(pistes), blocksize=R.SR * 60, always_2d=True):
        n = len(bloc)
        assert np.max(np.abs(bloc[:, 0] - signal(440, 0.3, debut, n))) < q
        assert np.max(np.abs(bloc[:, 1] - signal(1000, 0.2, debut, n))) < q
        debut += n
    # le mixage final = somme des pistes, normalisée
    a, _ = sf.read(out, frames=R.SR * 10, start=duree * R.SR - R.SR * 10)
    attendu = signal(440, 0.3, duree * R.SR - R.SR * 10, R.SR * 10) + signal(1000, 0.2, duree * R.SR - R.SR * 10, R.SR * 10)
    attendu *= 0.95 / 0.5
    assert np.max(np.abs(a - attendu)) < 0.01
