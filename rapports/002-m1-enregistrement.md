# 002 — M1 : enregistrement robuste

Date : 2026-11-10. Branche `tache/m1-enregistrement` (partie de `tache/m0-base`, PR #1 non fusionnée). Statut : **partiel** (voir « Non vérifié »).

## Résultat
- Lecture des deux flux en parallèle (un fil par périphérique) et écriture progressive dans `<sortie>.pistes.wav`, avec l'en-tête mis à jour chaque seconde. Après un plantage, `meeting recover` récupère l'enregistrement, avec une perte d'au plus 1 s.
- Choix explicite du haut-parleur (`--haut-parleur`) et du micro (`--micro`). Indicateur de niveau par flux chaque seconde, et alerte après 30 s de silence sur un flux.
- **Défaut majeur de soundcard trouvé et corrigé.** Quand un périphérique livre ses données par à-coups (ici le récepteur sans fil du casque Dell), soundcard invente des zéros, puis livre quand même les vraies données. Sur 30 min réelles, on a mesuré **22 s de faux zéros**, soit +1,1 % d'échantillons, et une désynchronisation de 7,6 s entre les flux. Après correction : 11 ms (au démarrage seulement).
- Réunion simulée d'une heure : **aucun échantillon perdu ni ajouté**, chaque piste est identique au signal émis à la quantification 16 bits près, et le mixage est vérifié. Au total, 16 tests passent.

## Mesures réelles (ce poste : son par le casque Dell HR024, micro « Microphone Array » SoundWire)
Un son de 440 Hz très faible (-54 dBFS) est joué sur le casque, comme pendant un appel Teams.

| Essai | Faux zéros | Discontinuités sys / micro | Horloge / PC, sys / micro | Dérive micro/sys |
|---|---|---|---|---|
| Avant correction, 30 min | 22 s | 160 / 91 | +11 096 / +6 869 ppm | −7,6 s |
| Après correction, 10 min | 0,011 s | 14 / 4 | −139 / −68 ppm | +43 ms (+128 ms/30 min) |
| **Après correction, 30 min** | **0,011 s** | **0 / 2** | **−2 / −12 ppm** | **−17 ms** |

Sans aucun son joué (10 min, avant correction) : le flux système est bien zéro, et l'alerte de silence se déclenche à 30 s comme prévu.

## Changements
- `src/meeting/record.py` a été réécrit : fils de lecture, écriture progressive, mixage final par morceaux de 30 s (rien n'est gardé en mémoire), bilan à l'arrêt (échantillons reçus, discontinuités, dérive en ppm).
- `corriger_silence_soundcard` : le silence n'est compté qu'après 1 s sans données, au lieu de 40 ms, et le tampon WASAPI passe de 64 ms à 0,5 s. Ce code est adapté de soundcard (BSD-3) et remplace une méthode interne, d'où la contrainte `soundcard>=0.4.6,<0.5`.
- CLI : `--haut-parleur`, `--garder-pistes`, `--sans-niveau` et la commande `meeting recover`. README mis à jour.

## Non vérifié / à traiter
- **Discontinuités restantes** : 14 et 4 lors de l'essai de 10 min, mais 0 et 2 sur 30 min. Ces pertes sont donc rares et irrégulières, et leur durée n'est pas mesurable. Le bilan d'horloge (−2 et −12 ppm sur 30 min) montre que la perte totale reste inférieure à environ 20 ms. La cause n'est pas identifiée (radio du casque, charge du PC). Il faut la mesurer avec un vrai Teams.
- **Dérive non corrigée** : elle vaut −17 ms sur 30 min sur ce poste (+43 ms lors de l'essai de 10 min), sans effet sur la transcription. Je propose de ne pas la corriger. Il faudra la mesurer sur d'autres périphériques.
- L'alignement acoustique réel (même son entendu dans les deux flux) n'a pas été mesuré : le micro n'entend pas un son joué dans le casque.
- Le micro du casque Dell est toujours refusé par soundcard (message clair + `--micro`). Changer de bibliothèque n'est plus nécessaire pour la synchronisation.
- Pas encore testé avec une vraie réunion Teams.
- **Défaut introduit par le correctif (vu lors de l'essai YouTube, 7 vidéos)** : quand aucune application ne joue de son, le loopback ne livre rien. Au moment où le son reprend, la période de silence en cours (jusqu'à 1 s) n'est pas comptée, ce qui avance le flux système d'au plus 1 s à chaque reprise. On a mesuré −3 248 ppm, soit environ 0,6 s, sur une vidéo de 3 min lancée 2,5 s après le début de l'enregistrement. C'est sans effet sans micro. Avec micro, le décalage peut se cumuler si le son du système s'arrête et reprend souvent. Pendant un appel Teams, le flux reste a priori ouvert, mais ce n'est pas vérifié. Piste de correction : à la reprise, comparer le nombre d'images en attente (`GetCurrentPadding`) au temps écoulé, pour distinguer un retard de livraison d'un vrai silence. **Il faut le corriger avant de fusionner, ou en tâche M1b.**

## Question
- Faut-il corriger la dérive (moins de 0,1 s par 30 min mesuré ici), ou la laisser telle quelle ? Je recommande de la laisser.
