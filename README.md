# Transcripteur de réunion — 100 % local (Windows)

Chaîne hors-ligne pour prendre une réunion Teams en notes **sans bot et sans envoi externe** :
**capture audio → transcription locale → (option) rédaction du CR**.

> ⚠️ **Consentement** : prévenez les participants en début de réunion que vous prenez la
> réunion en notes avec un outil de transcription. En contexte ADIF / SNCF (mentions
> « usage interne / confidentiel »), vérifiez que c'est autorisé.

## 1. Installation (une fois)
- Installez **Python 3.10+** (cochez « Add Python to PATH »). Vérifiez avec `py -0` ; si plusieurs
  versions sont installées, utilisez `py -3.12` (ou la plus récente) ci-dessous.
- Dans un terminal, depuis le dossier du projet :
  ```
  py -3.12 -m venv .venv
  .venv\Scripts\activate
  pip install -e .
  ```
  La commande `meeting` est alors disponible tant que l'environnement est activé.
- GPU NVIDIA (optionnel) : accélère la transcription. Sinon, le CPU suffit (plus lent que le direct,
  mais parfait pour transcrire **après** la réunion).

## 2. Enregistrer la réunion
```
meeting devices
meeting record --out reunion.wav
```
- Capte le **son de Teams** (les autres participants) **+ votre micro**, mixés.
- Laissez tourner pendant la réunion ; **Ctrl+C** pour arrêter → `reunion.wav`.
- Pendant l'enregistrement, une ligne affiche chaque seconde le niveau des deux flux
  (`système -32.0 dB | micro -41.5 dB`). Une **ALERTE** s'affiche si l'un des deux reste
  silencieux 30 s (micro coupé, mauvais haut-parleur…).
- `meeting devices` liste les haut-parleurs et micros. Choix explicite (une partie du nom suffit) :
  `--haut-parleur "Casque"` (son à capter) et `--micro "Microphone Array"`, ou `--no-mic`.
  Si le micro par défaut est refusé (message « format non pris en charge », vu sur un casque
  Dell HR024), choisissez-en un autre avec `--micro`.
- `--duree 60` : arrêt automatique après 60 s (pour un essai).
- **Écriture au fil de l'eau** : l'audio est écrit sur le disque chaque seconde dans
  `reunion.pistes.wav` (piste 1 = système, piste 2 = micro). Si le programme ou le PC plante,
  rien n'est perdu sauf la dernière seconde : `meeting recover reunion.pistes.wav` produit `reunion.wav`.
  Ce fichier est supprimé après un arrêt normal, sauf avec `--garder-pistes`.
- À l'arrêt, un bilan indique les échantillons reçus par flux et la dérive d'horloge mesurée.
- Astuce : montez un peu le volume Teams ; parlez normalement.

## 3. Transcrire (hors-ligne)
```
meeting transcribe reunion.wav --modele large-v3 --langue ca
```
- `--langue` : `fr`, `es`, `ca` (catalan) — ou omettez pour détection automatique.
- `--modele` : `medium` (rapide) ou `large-v3` (meilleure qualité) ; `tiny` pour un essai rapide.
- `--device` : `auto` (défaut), `cpu` ou `cuda`.
- Le modèle se télécharge **au 1er lancement** (Hugging Face), puis tout est **hors-ligne**.
- Sortie : `reunion.txt` (horodaté).

## Tests (développement)
```
pip install -e ".[test]"
pytest
```
Le test réel (voix de synthèse Windows transcrite par le modèle `tiny`, téléchargé au 1er lancement)
est désactivé par défaut : `set MEETING_IT=1` puis `pytest -m integration`.
La réunion simulée d'une heure (environ 45 s) se saute avec `pytest -m "not slow"`.

## 4. Rédiger le compte-rendu
Deux options :
- **Via Claude (recommandé pour la qualité)** : collez `reunion.txt` dans la conversation et je
  produis le CR au **format SNCF Réseau**. (Le texte passe alors par Claude.)
- **Tout en local (confidentialité maximale)** : installez **Ollama** (https://ollama.com),
  puis :
  ```
  ollama run llama3.1
  ```
  et donnez-lui ce prompt, suivi du contenu de `reunion.txt` :
  > « Rédige un compte-rendu de réunion clair et synthétique en français à partir de cette
  >   transcription. Structure : Contexte, Points abordés, Décisions, Actions (avec pilote et
  >   échéance), Prochaine réunion. Transcription : … »

## Limites & conseils
- La capture ne prend que l'audio qui passe par votre PC (Teams **application** ou **web**).
- Le mixage ne distingue pas automatiquement « qui parle » (pas de diarisation). Pour des noms,
  annotez à la volée ou dites-le-moi : on peut ajouter une diarisation locale (pyannote) plus tard.
- Le catalan est géré par Whisper (`large-v3` conseillé pour une meilleure précision).
- Pour une qualité maximale, un casque réduit l'écho ; évitez le haut-parleur ouvert.
