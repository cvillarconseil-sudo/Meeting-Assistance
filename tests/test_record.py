import numpy as np
import soundfile as sf

from meeting import record as R


class FakeRecorder:
    """Enregistreur simulé : sinus (ou silence), stéréo, puis Ctrl+C après ``stop_after`` blocs."""

    def __init__(self, freq, amp, stop_after=None, channels=2):
        self.freq, self.amp, self.stop_after, self.channels = freq, amp, stop_after, channels
        self.n = 0
        self.t0 = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        if self.stop_after is not None and self.n >= self.stop_after:
            raise KeyboardInterrupt
        t = (self.t0 + np.arange(numframes)) / R.SR
        self.t0 += numframes; self.n += 1
        x = self.amp * np.sin(2 * np.pi * self.freq * t)
        return np.repeat(x[:, None], self.channels, axis=1)


class FakeDevice:
    def __init__(self, name, **kw):
        self.name, self.kw = name, kw
        self.rec = None

    def recorder(self, samplerate, blocksize):
        assert samplerate == R.SR and blocksize == R.BLOCK
        self.rec = FakeRecorder(**self.kw)
        return self.rec


def devices(mic=True, stop_after=None, sys_amp=0.2, mic_amp=0.1):
    lb = FakeDevice("haut-parleur test", freq=440, amp=sys_amp, stop_after=stop_after)
    m = FakeDevice("micro test", freq=1000, amp=mic_amp, stop_after=stop_after) if mic else None
    return ("haut-parleur test", lb, m)


def test_duree_fixe_mixage(tmp_path, capsys):
    out = tmp_path / "t.wav"
    assert R.record(str(out), max_seconds=2.0, devices=devices()) == 0
    a, sr = sf.read(out)
    assert sr == 16000 and a.ndim == 1
    assert abs(len(a) / sr - 2.0) < R.BLOCK / sr          # arrondi au bloc
    assert abs(np.max(np.abs(a)) - 0.95) < 1e-3           # normalisation
    spec = np.abs(np.fft.rfft(a)); f = np.fft.rfftfreq(len(a), 1 / sr)
    pics = sorted(f[np.argsort(spec)[-2:]])
    assert abs(pics[0] - 440) < 2 and abs(pics[1] - 1000) < 2   # les deux flux sont mixés
    assert "RAPPEL" in capsys.readouterr().out             # consentement affiché


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
    assert not out.exists()


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
