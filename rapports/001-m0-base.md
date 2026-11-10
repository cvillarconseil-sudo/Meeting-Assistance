# 001 — M0 : base propre

Date : 2026-11-10. Branche `tache/m0-base`. Statut : **partiel** (installation par le README seul pas testée sur un autre poste).

## Résultat
- Paquet `meeting` installable (`pip install -e .`, `pyproject.toml`) avec une commande unique : `meeting record`, `meeting transcribe`, `meeting devices`.
- Tests : **9 passent** (audio synthétique : sinus, silence, mixage vérifié par FFT, Ctrl+C, périphérique refusé), en 0,4 s. Le **test réel passe** (voix de synthèse Windows, modèle `tiny` sur CPU, environ 12 s) ; il est désactivé par défaut (`MEETING_IT=1`).
- **2 défauts réels trouvés et corrigés** : (1) faster-whisper 1.2.1 plante avec PyAV 19 (`TypeError: metadata_errors`), donc PyAV est borné à `<16` ; (2) le micro du casque Dell HR024 (micro par défaut de ce poste) fait planter soundcard à l'ouverture. L'ancien script ne pouvait donc rien enregistrer sur ce PC. Il y a maintenant un message clair et une option `--micro <nom>`.
- Capture réelle de 3 s vérifiée sur ce poste : son du système + micro intégré, et son du système seul. Les fichiers de test ont été supprimés.

## Changements
- `src/record_meeting.py` est devenu `src/meeting/record.py`, et `src/transcribe_local.py` est devenu `src/meeting/transcribe.py`. Le comportement est inchangé. Les périphériques et le modèle sont injectables pour les tests. Ajouts : `--duree`, `--micro`, `--device`. Le rappel de consentement est affiché au démarrage de chaque enregistrement.
- `.gitignore` : ajout de `*.txt` (sortie des transcriptions, qui n'était pas exclue), sauf `requirements*.txt`.
- README : installation en environnement virtuel, nouvelles commandes, tests.

## Non vérifié / à traiter
- **Critère de sortie M0** (nouveau poste installé avec le README seul) : non testé sur un autre poste. Ici, `python` pointe sur Python 3.8, et c'est pourquoi le README indique `py -3.12`.
- **Pour M1** : soundcard émet « data discontinuity in recording » en capture réelle. Les deux flux sont lus l'un après l'autre et des échantillons sont sans doute perdus ; il faut le mesurer. Le refus du casque Dell plaide pour une autre bibliothèque de capture (à évaluer en M1 : PyAudioWPatch ou sounddevice, licences à vérifier).
- Le GPU (RTX 4060, `--device cuda`) n'a pas été testé, car les DLL CUDA ou cuDNN nécessaires à faster-whisper ne sont pas vérifiées. Ce point relève de M2.
- Le téléchargement du modèle `tiny` (Hugging Face, environ 75 Mo) a eu lieu pendant le test réel, comme prévu par la règle 1.

## Question
- Aucune bloquante pour M1. Les 3 questions ouvertes de `docs/ROADMAP.md` restent en attente.
