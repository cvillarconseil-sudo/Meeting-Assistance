# -*- coding: utf-8 -*-
"""
Enregistrement 100 % local d'une réunion (Windows), version robuste (M1).

Capte le son du système (Teams = voix des autres, via loopback WASAPI) et le micro.
Rien n'est envoyé à l'extérieur.

Fonctionnement :
- un fil de lecture par flux : chaque périphérique est vidé en continu, sans attendre l'autre
  (avant M1, les deux lectures se faisaient l'une après l'autre et soundcard signalait
  des « data discontinuity », c'est-à-dire des échantillons perdus) ;
- écriture progressive : les pistes (0 = système, 1 = micro) sont écrites au fil de l'eau
  dans ``<sortie>.pistes.wav``, en-tête mis à jour chaque seconde. Si le programme ou le PC
  plante, ce fichier reste lisible (perte d'au plus ~1 s) : ``meeting recover`` le remixe ;
- à l'arrêt : mixage mono normalisé dans ``<sortie>``, par morceaux (pas de tout-en-mémoire) ;
- indicateur de niveau chaque seconde, alerte si un flux reste silencieux ;
- mesure de la dérive : nombre d'échantillons reçus par flux comparé à l'horloge du PC.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import warnings
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf

SR = 16000          # 16 kHz suffit pour la transcription
BLOCK = 1024        # taille de bloc (échantillons)
SILENCE_DBFS = -60.0    # en dessous : flux considéré silencieux
SILENCE_ALERTE_S = 30   # alerte après N secondes de silence continu
MIX_CHUNK = SR * 30     # mixage final par morceaux de 30 s
TAMPON = SR // 2        # tampon WASAPI : 0,5 s (64 ms débordait avec un casque sans fil)
SEUIL_SILENCE_S = 1.0   # absence de données au-delà de laquelle on compte du silence

CONSENT = ("RAPPEL : prévenez les participants que vous enregistrez la réunion "
           "pour la prendre en notes, et vérifiez que c'est autorisé.")

NOMS = ("système", "micro")


def to_mono(x):
    x = np.asarray(x, dtype=np.float32)
    return x if x.ndim == 1 else x.mean(axis=1)


def dbfs(x) -> float:
    if len(x) == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    return 20 * np.log10(rms) if rms > 1e-6 else -120.0


def pistes_path(out: str) -> str:
    base, _ = os.path.splitext(out)
    return base + ".pistes.wav"


# --------------------------------------------------------------------------- périphériques

def list_devices() -> int:
    """Affiche haut-parleurs et micros (``meeting devices``)."""
    import soundcard as sc
    print("Haut-parleurs (son capté en loopback, option --haut-parleur) :")
    for s in sc.all_speakers():
        print(f"  - {s.name}{'  (défaut)' if s.name == sc.default_speaker().name else ''}")
    print("Micros (option --micro) :")
    for m in sc.all_microphones():
        print(f"  - {m.name}{'  (défaut)' if m.name == sc.default_microphone().name else ''}")
    return 0


def _choisir(liste, nom, quoi):
    """Premier périphérique dont le nom contient ``nom`` (insensible à la casse)."""
    trouves = [d for d in liste if nom.lower() in d.name.lower()]
    if not trouves:
        raise LookupError(f"Aucun {quoi} ne correspond à « {nom} ». Voir : meeting devices")
    return trouves[0]


def default_devices(no_mic: bool = False, micro: str | None = None, haut_parleur: str | None = None):
    """Haut-parleur (défaut ou choisi) en loopback, et micro (défaut, choisi, ou aucun)."""
    import soundcard as sc  # import tardif : les tests n'en ont pas besoin
    speaker = _choisir(sc.all_speakers(), haut_parleur, "haut-parleur") if haut_parleur else sc.default_speaker()
    loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    if no_mic:
        mic = None
    elif micro:
        mic = _choisir(sc.all_microphones(), micro, "micro")
    else:
        mic = sc.default_microphone()
    return speaker.name, loopback, mic


# --------------------------------------------------------------------------- lecture

@dataclass
class Flux:
    """Un périphérique lu en continu par son propre fil."""
    nom: str
    device: object
    sr: int = SR
    block: int = BLOCK
    q: queue.Queue = field(default_factory=queue.Queue)
    recus: int = 0                 # échantillons reçus
    discontinuites: int = 0        # avertissements « data discontinuity » de soundcard
    erreur: BaseException | None = None
    t0: float | None = None        # horloge PC au premier bloc reçu
    t_dernier: float | None = None
    pret: threading.Event = field(default_factory=threading.Event)
    fin: threading.Event = field(default_factory=threading.Event)

    def run(self, stop: threading.Event):
        try:
            with self.device.recorder(samplerate=self.sr, blocksize=TAMPON) as rec:
                corriger_silence_soundcard(rec)
                self.pret.set()
                while not stop.is_set():
                    x = to_mono(rec.record(numframes=self.block))
                    now = time.perf_counter()
                    if self.t0 is None:
                        self.t0 = now - len(x) / self.sr
                    self.t_dernier = now
                    self.recus += len(x)
                    self.q.put(x)
        except KeyboardInterrupt:
            pass
        except BaseException as e:   # périphérique refusé, débranché…
            self.erreur = e
        finally:
            self.pret.set()
            self.fin.set()


def corriger_silence_soundcard(rec, seuil_s: float = SEUIL_SILENCE_S) -> bool:
    """Remplace l'heuristique de silence de soundcard (0.4.x) sur l'enregistreur ``rec``.

    Quand WASAPI ne livre aucune donnée pendant plus de 4 périodes (~40 ms), soundcard suppose
    que le périphérique est silencieux et renvoie des zéros pour la durée écoulée. Or un
    périphérique qui livre par à-coups (casque sans fil, micro SoundWire) livre ensuite quand même
    les données en retard : le flux reçoit des zéros en trop et se décale. Mesuré sur 30 min :
    22 s de faux zéros (rapport 002). On ne garde l'heuristique que pour un vrai silence de
    plus de ``seuil_s`` (loopback quand rien n'est joué). Code adapté de soundcard
    (``_Recorder._record_chunk``, licence BSD-3). Renvoie False si ``rec`` n'est pas un
    enregistreur soundcard reconnu (faux périphérique de test, autre version).
    """
    if not all(hasattr(rec, a) for a in ("_capture_available_frames", "_capture_buffer",
                                          "_capture_release", "_idle_start_time", "_is_first_frame")):
        return False
    from soundcard.mediafoundation import _ffi, _ole32, SoundcardRuntimeWarning

    _, periode_min = rec.deviceperiod
    nb_canaux = len(set(rec.channelmap))

    def _record_chunk():
        while rec._capture_available_frames() == 0:
            if rec._idle_start_time is None:
                rec._idle_start_time = time.perf_counter_ns()
            time.sleep(periode_min / 4)
            ecoule_ns = time.perf_counter_ns() - rec._idle_start_time
            if ecoule_ns / 1e9 > seuil_s:
                n = int(rec.samplerate * ecoule_ns / 1e9)
                rec._idle_start_time += ecoule_ns
                return np.zeros([n * nb_canaux], dtype="float32")
        rec._idle_start_time = None
        ptr, nframes, flags = rec._capture_buffer()
        if ptr == _ffi.NULL:
            raise RuntimeError("Could not create capture buffer")
        chunk = np.frombuffer(_ffi.buffer(ptr, nframes * 4 * nb_canaux), dtype="float32").copy()
        if flags & _ole32.AUDCLNT_BUFFERFLAGS_SILENT:
            chunk[:] = 0
        if rec._is_first_frame:
            flags &= ~_ole32.AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY
            rec._is_first_frame = False
        if flags & _ole32.AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY:
            warnings.warn("data discontinuity in recording", SoundcardRuntimeWarning)
        if nframes > 0:
            rec._capture_release(nframes)
            return chunk
        return np.zeros([0], dtype="float32")

    rec._record_chunk = _record_chunk
    return True


_compteur_lock = threading.Lock()


def _installer_compteur_discontinuites(flux_par_fil: dict):
    """Compte les avertissements soundcard par fil, au lieu de les afficher en vrac."""
    ancien = warnings.showwarning

    def show(message, category, filename, lineno, file=None, line=None):
        f = flux_par_fil.get(threading.get_ident())
        if f is not None and "discontinuity" in str(message):
            with _compteur_lock:
                f.discontinuites += 1
            return
        ancien(message, category, filename, lineno, file, line)

    warnings.showwarning = show
    warnings.simplefilter("always")   # sinon un seul avertissement par emplacement
    return ancien


# --------------------------------------------------------------------------- enregistrement

@dataclass
class Bilan:
    secondes: float = 0.0
    recus: tuple = (0, 0)
    discontinuites: tuple = (0, 0)
    derive_ppm: tuple = (None, None)   # écart d'horloge de chaque flux par rapport au PC
    alertes: list = field(default_factory=list)


def capture(loopback, mic, pistes: str, max_seconds: float | None = None, sr: int = SR,
            block: int = BLOCK, afficher=print, niveau=True) -> Bilan:
    """Lit les flux en parallèle et écrit les pistes au fil de l'eau jusqu'à Ctrl+C ou ``max_seconds``."""
    devices = [loopback] + ([mic] if mic is not None else [])
    flux = [Flux(NOMS[i], d, sr, block) for i, d in enumerate(devices)]
    stop = threading.Event()
    fils = [threading.Thread(target=f.run, args=(stop,), daemon=True, name=f"lecture-{f.nom}") for f in flux]
    par_fil: dict = {}
    filtres = warnings.filters[:]
    ancien_show = _installer_compteur_discontinuites(par_fil)
    max_frames = None if max_seconds is None else int(round(max_seconds * sr))
    bilan = Bilan()
    ecrits = 0
    tampons = [np.zeros(0, np.float32) for _ in flux]
    silence = [0.0 for _ in flux]
    alerte_active = [False for _ in flux]
    niveau_acc = [[] for _ in flux]
    prochain_niveau = sr
    try:
        for t, f in zip(fils, flux):
            t.start()
            par_fil[t.ident] = f
        for f in flux:
            f.pret.wait()
        for f in flux:
            if f.erreur is not None:
                raise f.erreur
        with sf.SoundFile(pistes, "w", sr, len(flux), "PCM_16") as wav:
            dernier_flush = time.monotonic()
            while True:
                # 1. vider les files
                for i, f in enumerate(flux):
                    morceaux = [tampons[i]]
                    try:
                        if len(tampons[i]) < block:
                            morceaux.append(f.q.get(timeout=0.05))
                        while True:
                            morceaux.append(f.q.get_nowait())
                    except queue.Empty:
                        pass
                    if len(morceaux) > 1:
                        tampons[i] = np.concatenate(morceaux)
                # 2. écrire ce qui est disponible sur toutes les pistes
                n = min(len(b) for b in tampons)
                if max_frames is not None:
                    n = min(n, max_frames - ecrits)
                if n > 0:
                    trame = np.stack([b[:n] for b in tampons], axis=1)
                    tampons = [b[n:] for b in tampons]
                    wav.write(np.clip(trame, -1.0, 1.0))
                    ecrits += n
                    for i in range(len(flux)):
                        niveau_acc[i].append(trame[:, i])
                # 3. niveau et silence, chaque seconde d'audio
                while ecrits >= prochain_niveau:
                    lignes = []
                    for i, f in enumerate(flux):
                        x = np.concatenate(niveau_acc[i]) if niveau_acc[i] else np.zeros(0, np.float32)
                        niveau_acc[i] = []
                        d = dbfs(x)
                        lignes.append(f"{f.nom} {d:6.1f} dB")
                        if d < SILENCE_DBFS:
                            silence[i] += len(x) / sr
                            if silence[i] >= SILENCE_ALERTE_S and not alerte_active[i]:
                                alerte_active[i] = True
                                msg = (f"ALERTE : flux {f.nom} silencieux depuis {silence[i]:.0f} s "
                                       f"(à {ecrits / sr:.0f} s). Vérifiez le périphérique.")
                                bilan.alertes.append(msg)
                                afficher(f"\n[!] {msg}")
                        else:
                            silence[i] = 0.0
                            alerte_active[i] = False
                    if niveau:
                        s = ecrits // sr
                        print(f"\r[{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}] " + " | ".join(lignes),
                              end="", flush=True)
                    prochain_niveau += sr
                # 4. en-tête à jour chaque seconde (fichier lisible même après un plantage)
                if time.monotonic() - dernier_flush >= 1.0:
                    wav.flush()
                    dernier_flush = time.monotonic()
                if max_frames is not None and ecrits >= max_frames:
                    break
                # panne d'un périphérique : on écrit d'abord tout ce qu'il a livré avant de s'arrêter
                tous_finis = all(g.fin.is_set() and g.q.empty() for g in flux)
                for i, f in enumerate(flux):
                    if f.erreur is not None and f.fin.is_set() and f.q.empty() \
                            and (len(tampons[i]) == 0 or tous_finis):
                        raise f.erreur
                # 5. un flux s'est arrêté (Ctrl+C reçu par son fil) et tout est écrit
                if any(f.fin.is_set() and f.q.empty() and len(tampons[i]) == 0 for i, f in enumerate(flux)):
                    break
    except KeyboardInterrupt:
        afficher("\n[i] Arrêt demandé.")
    finally:
        stop.set()
        for t in fils:
            t.join(timeout=2)
        warnings.showwarning = ancien_show
        warnings.filters[:] = filtres
    if niveau:
        print()
    bilan.secondes = ecrits / sr
    bilan.recus = tuple(f.recus for f in flux)
    bilan.discontinuites = tuple(f.discontinuites for f in flux)
    derives = []
    for f in flux:
        if f.t0 is not None and f.t_dernier is not None and f.t_dernier - f.t0 > 10:
            attendu = (f.t_dernier - f.t0) * sr
            derives.append((f.recus - attendu) / attendu * 1e6)
        else:
            derives.append(None)
    bilan.derive_ppm = tuple(derives)
    return bilan


def mixdown(pistes: str, out: str) -> float:
    """Mixe les pistes en mono, normalise au pic (0,95), écrit ``out`` en PCM 16 bits. Par morceaux.

    Renvoie la durée en secondes (0 si le fichier de pistes est vide).
    """
    info = sf.info(pistes)
    if info.frames == 0:
        return 0.0
    pic = 0.0
    for bloc in sf.blocks(pistes, blocksize=MIX_CHUNK, dtype="float32", always_2d=True):
        pic = max(pic, float(np.max(np.abs(bloc.sum(axis=1)))))
    gain = 0.95 / pic if pic > 0 else 1.0
    with sf.SoundFile(out, "w", info.samplerate, 1, "PCM_16") as o:
        for bloc in sf.blocks(pistes, blocksize=MIX_CHUNK, dtype="float32", always_2d=True):
            o.write(bloc.sum(axis=1) * gain)
    return info.frames / info.samplerate


def recover(pistes: str, out: str | None = None) -> int:
    """``meeting recover`` : remixe un fichier de pistes laissé par un enregistrement interrompu."""
    if not os.path.exists(pistes):
        print(f"[!] Fichier introuvable : {pistes}")
        return 2
    if out is None:
        out = pistes[: -len(".pistes.wav")] + ".wav" if pistes.endswith(".pistes.wav") else pistes + ".mix.wav"
    try:
        dur = mixdown(pistes, out)
    except Exception as e:
        print(f"[!] Fichier de pistes illisible : {type(e).__name__}: {e}")
        return 3
    if dur == 0:
        print("[!] Fichier de pistes vide.")
        return 1
    print(f"[✓] {out} — {dur:.0f} s récupérées.")
    return 0


def rapport(b: Bilan, afficher=print):
    afficher(f"[i] Durée : {b.secondes:.1f} s")
    for i, nom in enumerate(NOMS[: len(b.recus)]):
        d = b.derive_ppm[i]
        txt_d = "non mesurée (< 10 s)" if d is None else f"{d:+.0f} ppm"
        afficher(f"[i] {nom} : {b.recus[i]} échantillons reçus, {b.discontinuites[i]} discontinuité(s), "
                 f"horloge / PC {txt_d}")
    if len(b.recus) == 2 and None not in b.derive_ppm:
        rel = b.derive_ppm[1] - b.derive_ppm[0]
        txt = f"[i] Dérive micro / système : {rel:+.0f} ppm, soit {rel * 1e-6 * b.secondes * 1000:+.0f} ms sur l'enregistrement"
        if b.secondes >= 300:
            txt += f" ({rel * 1e-6 * 1800 * 1000:+.0f} ms par 30 min)"
        else:
            txt += " (peu fiable sous 5 min)"
        afficher(txt)


def record(out: str = "reunion.wav", no_mic: bool = False, max_seconds: float | None = None,
           devices=None, micro: str | None = None, haut_parleur: str | None = None,
           garder_pistes: bool = False, niveau: bool = True) -> int:
    """Point d'entrée. ``devices`` = (nom, loopback, micro) pour injecter des périphériques."""
    print(f"[!] {CONSENT}")
    try:
        name, loopback, mic = devices if devices is not None else default_devices(no_mic, micro, haut_parleur)
    except LookupError as e:
        print(f"[!] {e}")
        return 2
    if no_mic:
        mic = None
    pistes = pistes_path(out)
    print(f"[i] Système (loopback): {name}")
    print(f"[i] Micro: {'(désactivé)' if mic is None else mic.name}")
    print(f"[i] Écriture progressive -> {pistes}  | Ctrl+C pour arrêter")
    try:
        bilan = capture(loopback, mic, pistes, max_seconds=max_seconds, niveau=niveau)
    except AssertionError:
        # soundcard refuse certains périphériques (format de mixage non « extensible »),
        # ex. micro de casque Dell HR024.
        print("\n[!] Impossible d'ouvrir un périphérique audio (format non pris en charge par soundcard).\n"
              "    Choisissez un autre micro avec --micro <nom> (liste : meeting devices),\n"
              "    ou enregistrez sans micro avec --no-mic.")
        _nettoyer_vide(pistes)
        return 3
    except Exception as e:  # périphérique débranché, occupé…
        print(f"\n[!] Erreur audio : {type(e).__name__}: {e}")
        if not _nettoyer_vide(pistes):
            print(f"[i] Ce qui a été enregistré est conservé : meeting recover \"{pistes}\"")
        return 3
    rapport(bilan)
    if bilan.secondes == 0:
        _nettoyer_vide(pistes)
        print("[!] Rien enregistré.")
        return 1
    dur = mixdown(pistes, out)
    if not garder_pistes:
        os.remove(pistes)
    print(f"[✓] {out} — {dur:.0f} s enregistrées.")
    return 0


def _nettoyer_vide(pistes: str) -> bool:
    """Supprime le fichier de pistes s'il est vide. Renvoie True s'il n'en reste rien."""
    try:
        if os.path.exists(pistes) and sf.info(pistes).frames == 0:
            os.remove(pistes)
    except Exception:
        pass
    return not os.path.exists(pistes)


if __name__ == "__main__":
    from meeting.cli import main
    sys.exit(main(["record", *sys.argv[1:]]))
