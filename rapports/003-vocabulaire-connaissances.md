# 003 — Vocabulaire ferroviaire et base de connaissances (essai sur vidéos YouTube)

Date : 2026-11-11. Branche `tache/vocabulaire-connaissances`, partie de `tache/m1-enregistrement` (PR #2). Statut : **partiel**.
Demande de Carlos : tester sur davantage de vidéos, récupérer les dictionnaires de SNCF Réseau, d'Adif et de l'UIC, et construire une base de connaissances des méthodes de travaux.

## Résultat
- **Lexique ferroviaire** (`data/lexique_ferroviaire.csv`) : 31 concepts (voie, appareils de voie, caténaire, renouvellement, bourrage, sécurité, organisation…), 864 termes en FR, ES, IT, PT, DE, EN, CA et NL, avec une définition en français. Rédigé par l'agent, il ne recopie aucun glossaire tiers.
- **Transcription guidée** : les termes de la langue détectée sont passés à faster-whisper (`hotwords`), puis les erreurs connues sont corrigées (`data/corrections.csv`). Sur la vidéo ETF, « balaises » et « balais » deviennent « ballast », « voile » devient « voie », « voies ballastes » devient « voie ballast ». Il reste « des prêtes » au lieu de « du fret ».
- **Base de connaissances** (`meeting kb`) : SQLite et FTS5, hors du dépôt. Elle contient 13 sources, 408 passages horodatés, 8 670 termes (lexique + glossaire ERA) et 12 fiches méthodes rédigées à partir des vidéos. La recherche ignore les accents. Export Markdown.
- 31 tests passent (5 nouveaux pour la base, 6 pour le vocabulaire).

## Vidéos (14 enregistrées, 11 avec parole, transcrites avec le modèle `medium` sur CPU)
FR : ETF (RVB à Metz), Colas Rail (RER A), plus 3 vidéos sans parole (SNCF Réseau SRZD et BOA, Eiffage TCM 60). BE : Infrabel ×2. CH : FM1Today, SBB (train de travaux). IT : TTV/RFI (FCU), plus GCF sans parole. ES : Azvi (Zafra–Huelva), Adif (appareils de voie par portiques). PT : IP Beira Alta, IP Oeste.
Les langues sont toutes détectées correctement (p ≥ 0,84) quand il y a de la parole ; sans parole, la détection tombe à « en, p = 0,51 ».

## Dictionnaires demandés
| Source | Résultat |
|---|---|
| SNCF Réseau | Le DRR 2026 a été lu dans le navigateur (le téléchargement automatique est refusé, code 403). Son glossaire porte sur l'accès au réseau (sillons, redevances) ; les sigles utiles (LTV, PGF, VP/VS, KVB, TVM) sont repris dans le lexique. Aucun lexique travaux public n'a été trouvé. |
| Adif | La « Declaración sobre la Red » 2026 n'a pas pu être lue (le site refuse les scripts externes). Son glossaire porte aussi sur l'accès au réseau. Aucun diccionario ferroviario public. |
| UIC | RailLexic est **payant** (abonnement, environ 160 € par an d'après une recherche, non vérifié). Il n'a pas été contourné. C'est la seule vraie référence multilingue sur les travaux. |
| Téléchargés (gratuits) | ERA Railway Terminology Collection (CSV, 7 806 termes, en anglais), glossaire DRR d'Infrabel, brochure PIR de RFI, Directório da Rede 2023 d'IP. Ils sont stockés hors du dépôt, dans `Meeting-Assistance-data/glossaires`. |

## Défauts trouvés et corrigés
- Des mots-clés trop longs (700 caractères) faisaient planter faster-whisper (« maximum decoding length must be > 0 »). Ils sont limités à 350 caractères.
- Un enregistrement (Infrabel « Rosine ») contenait le début de la vidéo suivante, en allemand, que Whisper a **traduit** en français parce que la langue avait été fixée par le début de l'audio. Ces passages ont été retirés de la base. C'est un risque réel pour une réunion bilingue : il faut **un test de détection de langue par segment en M2**.

## Non vérifié / à traiter
- Le gain du vocabulaire est mesuré sur une seule vidéo (ETF), sans taux d'erreur de mots. C'est à faire en M2 avec un jeu de référence.
- Les mots-clés se limitent au premier terme de chaque concept (350 caractères) : les synonymes et sigles (RVB, BML, LTV…) n'y entrent pas. Il faudrait une priorité par terme ou un vocabulaire par réunion.
- Le dossier `data/` est lu depuis le dépôt (installation éditable). Il faut l'intégrer au paquet avant une installation normale.
- Les fiches méthodes ont été rédigées par l'agent à partir des transcriptions, avec des points marqués « à vérifier » (par exemple « mettre en tension »). Elles sont à relire.
- Le défaut M1 (décalage du flux système à la reprise du son) n'est pas traité ici.

## Questions
1. Faut-il acheter l'accès UIC RailLexic ? Il apporterait les termes de travaux validés dans plus de 20 langues.
2. Les fiches méthodes doivent-elles rester locales, ou aller dans le dépôt (`docs/`) ? Ce sont des résumés rédigés, sans données de réunion.
