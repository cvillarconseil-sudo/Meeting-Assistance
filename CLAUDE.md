# Instructions pour l'agent (Claude Code) : outil de transcription et de suivi des réunions

Projet de Carlos Villar (CVI). Outil interne, 100 % local par défaut, pour enregistrer une réunion Teams, la transcrire hors ligne et en tirer un compte rendu et un suivi des actions.

## Rôles
- Carlos : responsable produit, il décide et valide.
- Claude (conversation de pilotage) : architecte et relecteur. Il écrit les consignes dans `consignes/` et relit tes rapports.
- Toi (Claude Code) : implémenteur. Tu lis `consignes/` et `docs/ROADMAP.md`, tu travailles, tu rapportes dans `rapports/`.

## Règles absolues
1. Local d'abord : aucun envoi de données hors de la machine. Le seul accès réseau toléré est le téléchargement d'un modèle au premier lancement, et tu le signales.
2. Aucune donnée réelle dans le dépôt : pas d'audio, pas de transcription, pas de compte rendu de vraie réunion. Les tests utilisent de l'audio synthétique ou des textes inventés. Vérifie que `.gitignore` les exclut avant chaque commit.
3. Pas de secrets, mots de passe ni jetons, ni dans les fichiers ni dans les messages.
4. Une tâche = une branche = une pull request. Tu ne fusionnes pas toi-même ta pull request : tu la décris, Carlos ou la conversation de pilotage relit.
5. Tu ne t'auto-valides pas. Si un test échoue ou si tu n'es pas sûr, tu le dis dans le rapport (statut : fait / partiel / bloqué).
6. Pas de boucle sans fin : tu t'arrêtes à la fin de la tâche et tu rapportes. Maximum 3 tentatives sur un même blocage, puis rapport-question.
7. Nouvelle dépendance : vérifie sa licence (permissive : MIT, BSD, Apache). Si elle exige un compte, un jeton ou un téléchargement non standard (ex. pyannote), rapport-question avant de l'ajouter.
8. Consentement : l'outil affiche toujours un rappel de prévenir les participants avant d'enregistrer. Ne le retire pas.

## Boucle de travail
1. `git pull --rebase`, lire `consignes/` (la plus récente non traitée) et `docs/ROADMAP.md`.
2. Créer une branche `tache/<nom-court>`.
3. Implémenter, tester (`pytest`), documenter.
4. Écrire `rapports/NNN-<sujet>.md` : résultat en 5 lignes maximum, chiffres, ce qui n'est pas vérifié, question éventuelle.
5. Pousser la branche, ouvrir la pull request, attendre la relecture.

## Environnement
Windows 10/11, Python 3.10+. Les scripts existants sont dans `src/` : `record_meeting.py` (capture loopback WASAPI + micro) et `transcribe_local.py` (faster-whisper). Ils fonctionnent d'après leur auteur initial mais n'ont pas de tests : ne les suppose pas corrects.
