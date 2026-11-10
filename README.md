# Transcripteur de réunion — 100 % local (Windows)

Chaîne hors-ligne pour prendre une réunion Teams en notes **sans bot et sans envoi externe** :
**capture audio → transcription locale → (option) rédaction du CR**.

> ⚠️ **Consentement** : prévenez les participants en début de réunion que vous prenez la
> réunion en notes avec un outil de transcription. En contexte ADIF / SNCF (mentions
> « usage interne / confidentiel »), vérifiez que c'est autorisé.

## 1. Installation (une fois)
- Installez **Python 3.10+** (cochez « Add Python to PATH »).
- Dans un terminal :
  ```
  pip install soundcard soundfile numpy faster-whisper
  ```
- GPU NVIDIA (optionnel) : accélère la transcription. Sinon, le CPU suffit (plus lent que le direct,
  mais parfait pour transcrire **après** la réunion).

## 2. Enregistrer la réunion
```
python record_meeting.py --out reunion.wav
```
- Capte le **son de Teams** (les autres participants) **+ votre micro**, mixés.
- Laissez tourner pendant la réunion ; **Ctrl+C** pour arrêter → `reunion.wav`.
- Astuce : montez un peu le volume Teams ; parlez normalement.

## 3. Transcrire (hors-ligne)
```
python transcribe_local.py reunion.wav --modele large-v3 --langue ca
```
- `--langue` : `fr`, `es`, `ca` (catalan) — ou omettez pour détection automatique.
- `--modele` : `medium` (rapide) ou `large-v3` (meilleure qualité).
- Le modèle se télécharge **au 1er lancement**, puis tout est **hors-ligne**.
- Sortie : `reunion.txt` (horodaté).

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
