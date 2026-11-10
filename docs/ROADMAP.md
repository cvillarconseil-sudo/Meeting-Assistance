# Feuille de route (source de vérité des tâches)

Statut : M0 à lancer. Questions ouvertes pour Carlos en fin de document.

## M0 : base propre
- Reprendre `src/record_meeting.py` et `src/transcribe_local.py` tels quels, ajouter `pyproject.toml` (ou `requirements.txt`), un point d'entrée unique en ligne de commande (`meeting record`, `meeting transcribe`).
- Tests avec audio synthétique (sinus, silence, voix de synthèse) : le script tourne, produit un fichier, ne plante pas.
- Critère de sortie : un nouveau poste Windows installe et lance l'outil avec le README seul.

## M1 : enregistrement robuste
- Écriture progressive sur disque par morceaux (aujourd'hui tout est gardé en mémoire et perdu si le programme plante).
- Liste des périphériques et choix explicite du haut-parleur et du micro.
- Indicateur de niveau et alerte si l'un des deux flux reste silencieux.
- Contrôle de la synchronisation entre les deux flux (les deux lectures se font l'une après l'autre) et mesure de la dérive sur 30 minutes.
- Critère de sortie : une réunion simulée d'une heure sans perte, mixage vérifié.

## M2 : transcription robuste
- Détection du matériel et choix du modèle (GPU ou processeur), avec durée annoncée.
- Sorties : texte horodaté, JSON, sous-titres.
- Tester `condition_on_previous_text` (risque de répétitions et d'hallucinations sur les silences) et mesurer l'effet sur du texte de référence.
- Traitement par lot d'un dossier.
- Critère de sortie : taux d'erreur de mots mesuré sur un petit jeu de référence inventé, en français, espagnol et catalan.

## M3 : compte rendu
- Gabarit unique : contexte, points abordés, décisions, actions (pilote, échéance), prochaine réunion.
- Voie 100 % locale (Ollama). Voie Claude : seulement sur demande explicite de l'utilisateur à chaque fois, avec confirmation que le texte quitte la machine.
- Sortie structurée (JSON) puis rendu Markdown.
- Critère de sortie : sur 3 transcriptions fictives, toutes les actions sont retrouvées avec pilote et échéance quand ils sont dits.

## M4 : suivi
- Index local SQLite : réunions, actions, statuts.
- Export CSV et Markdown.
- Ensuite seulement, une petite interface (tableau de suivi) si Carlos le confirme.

## M5 : options
- Diarisation locale (qui parle). Attention : les modèles courants demandent un compte et un jeton, donc rapport-question avant.
- Gestion des réunions longues.

## Questions ouvertes pour Carlos
1. CR : 100 % local, ou passage par Claude quand tu le choisis ? Le README actuel recommande de coller la transcription dans Claude pour la qualité. Pour des réunions ADIF ou SNCF marquées « usage interne / confidentiel », vérifie d'abord ce qui est autorisé.
2. Suivi : un index et un export suffisent-ils pour démarrer, ou un tableau de suivi dès le début ?
3. Consentement : faut-il un rappel écrit à insérer en tête de chaque compte rendu ?
