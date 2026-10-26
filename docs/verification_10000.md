# Verification de dialette_lab, N = 10000

Distributions : `config/distributions.json` (extraites le 2026-10-26, echantillon : 40 conversations, 161 messages, 456 vues ; base de test, pas de production).

Generation : graine 42, fenetre 365 jours jusqu'au 2026-09-10, duree 8.5 s.

Anomalies d'integrite : **0**.


## Comptes

| Indicateur | Cible | Obtenu | Ecart relatif |
|---|---|---|---|
| contacts (N x ratio) | 7500 | 7500 | +0.0 % |
| widget_views (N x ratio) | 114000 | 114000 | +0.0 % |
| messages (N x moyenne) | 40250 | 40079 | -0.4 % |
| users | 11 | 11 | +0.0 % |
| widgets | 9 | 9 | +0.0 % |

## Messages

| Indicateur | Cible | Obtenu | Ecart relatif |
|---|---|---|---|
| messages par conversation (moyenne) | 4.025 | 4.008 | -0.4 % |
| conversations sans message | 0 | 0 |  |
| part des conversations a 1 message(s) | 0.05 | 0.0473 | -5.4 % |
| part des conversations a 3 message(s) | 0.5 | 0.5063 | +1.3 % |
| part des conversations a 4 message(s) | 0.175 | 0.1803 | +3.0 % |
| part des conversations a 5 message(s) | 0.075 | 0.071 | -5.3 % |
| part des conversations a 6 message(s) | 0.075 | 0.0729 | -2.8 % |
| part des conversations a 7 message(s) | 0.075 | 0.0735 | -2.0 % |
| part des conversations a 8 message(s) | 0.025 | 0.0247 | -1.2 % |
| part des conversations a 9 message(s) | 0.025 | 0.024 | -4.0 % |
| longueur moyenne, tous roles | 54.76 | 55.03 | +0.5 % |
| longueur moyenne, role user:system | 55.43 | 54.78 | -1.2 % |
| longueur moyenne, role contact:client | 40.07 | 40.02 | -0.1 % |
| longueur moyenne, role user:admin | 72.36 | 72.95 | +0.8 % |
| part lue, role user:system | 0.9 | 0.8938 | -0.7 % |
| part lue, role contact:client | 0.8611 | 0.8658 | +0.5 % |
| part lue, role user:admin | 0.08475 | 0.0841 | -0.8 % |
| part des conversations commencant par user:system | 0.75 | 0.7507 | +0.1 % |
| part des conversations commencant par contact:client | 0.25 | 0.2493 | -0.3 % |
| sender_type en nom de classe (convention ancienne, attendu 0) | 0 | 0 |  |

## Vues

| Indicateur | Cible | Obtenu | Ecart relatif |
|---|---|---|---|
| vues par conversation | 11.4 | 11.4 | +0.0 % |
| vues par jour (moyenne sur 365 j) | 312.3 | 312.3 | +0.0 % |
| coefficient de variation quotidien | 1.443 | 1.588 | +10.0 % |
| part des jours actifs |  | 1 |  |
| part du widget de rang 1 | 0.4079 | 0.4067 | -0.3 % |
| part du widget de rang 2 | 0.3136 | 0.3111 | -0.8 % |
| part du widget de rang 3 | 0.1382 | 0.1404 | +1.6 % |
| part du widget de rang 4 | 0.05482 | 0.05623 | +2.6 % |
| part du widget de rang 5 | 0.03728 | 0.03663 | -1.7 % |
| part du widget de rang 6 | 0.0329 | 0.03289 | -0.0 % |
| part du widget de rang 7 | 0.01535 | 0.01611 | +4.9 % |

## Conversations

| Indicateur | Cible | Obtenu | Ecart relatif |
|---|---|---|---|
| part status|source = open| | 0.525 | 0.5211 | -0.7 % |
| part status|source = closed| | 0.225 | 0.2341 | +4.0 % |
| part status|source = closed|widget | 0.15 | 0.1506 | +0.4 % |
| part status|source = open|widget | 0.1 | 0.0942 | -5.8 % |
| part types contact|lead | 0.775 | 0.7761 | +0.1 % |
| part types contact|contact | 0.225 | 0.2239 | -0.5 % |
| types en nom de classe (attendu 0) | 0 | 0 |  |
| fermees avec closed_at | 0.8667 | 0.8617 | -0.6 % |

## Meta

| Indicateur | Cible | Obtenu | Ecart relatif |
|---|---|---|---|
| part de meta NULL | 0.25 | 0.2409 | -3.6 % |
| meta non valides en JSON (attendu 0) | 0 | 0 |  |
| part du motif de cles type,project_type,budget,timeline,done | 0.4667 | 0.4681 | +0.3 % |
| part du motif de cles type,question_message,done | 0.2667 | 0.2599 | -2.5 % |
| part du motif de cles type,profession,goal,timeline,done | 0.1667 | 0.1726 | +3.5 % |
| part du motif de cles budget,project_type,type,done | 0.03333 | 0.03122 | -6.3 % |
| part du motif de cles company,type,question_message,done | 0.03333 | 0.03425 | +2.8 % |
| part du motif de cles phone,company,type,timeline,project_type,budget,done | 0.03333 | 0.03399 | +2.0 % |
| motifs de cles inattendus (attendu 0) | 0 | 0 |  |
| done est un booleen true | 1 | 1 | +0.0 % |
| valeurs non chaines hors done (attendu 0) | 0 | 0 |  |
| type = projet | 0.7 | 0.7054 | +0.8 % |
| type = question | 0.3 | 0.2946 | -1.8 % |
| timeline = Dès que possible | 0.3 | 0.2912 | -2.9 % |
| timeline = Maintenant | 0.2 | 0.2052 | +2.6 % |
| timeline = autre (saisie libre) | 0.15 | 0.1511 | +0.8 % |
| timeline = Dans 1 à 3 mois | 0.15 | 0.1504 | +0.2 % |
| timeline = 1 à 3 mois | 0.1 | 0.1006 | +0.6 % |
| timeline = Dans 1 mois | 0.1 | 0.1015 | +1.5 % |
| budget = 1000 - 3000€ | 0.375 | 0.3752 | +0.1 % |
| budget = autre (saisie libre) | 0.1875 | 0.1808 | -3.6 % |
| budget = 500 - 1500€ | 0.1875 | 0.1863 | -0.7 % |
| budget = 3000 - 8000€ | 0.125 | 0.1262 | +1.0 % |
| budget = < 500€ | 0.125 | 0.1314 | +5.1 % |
| project_type = autre (saisie libre) | 0.4375 | 0.4306 | -1.6 % |
| project_type = SaaS | 0.25 | 0.2601 | +4.1 % |
| project_type = Site vitrine ou institutionnel | 0.1875 | 0.1803 | -3.8 % |
| project_type = Coaching individuel | 0.125 | 0.129 | +3.2 % |
| taille moyenne de meta en octets (reference Dialette 113,8) | 113.8 | 112.5 | -1.2 % |

## Integrite

| Indicateur | Cible | Obtenu | Ecart relatif |
|---|---|---|---|
| messages sans conversation (attendu 0) | 0 | 0 |  |
| widget_views sans widget (attendu 0) | 0 | 0 |  |
| widgets sans user (attendu 0) | 0 | 0 |  |
| conversations avec user_id inexistant (attendu 0) | 0 | 0 |  |
| contacts avec user_id inexistant (attendu 0) | 0 | 0 |  |
| interlocutor_id sans contact (attendu 0) | 0 | 0 |  |
| conversable contact sans contact (attendu 0) | 0 | 0 |  |
| expediteur contact sans contact (attendu 0) | 0 | 0 |  |
| expediteur user sans user (attendu 0) | 0 | 0 |  |
| last_message_at different du dernier message (attendu 0) | 0 | 0 |  |
| lignes polymorphes de type inconnu (attendu 0) | 0 | 0 |  |
| references ou jetons dupliques (attendu 0) | 0 | 0 |  |
| index sur widget_views.created_at (attendu 0, comme Dialette) | 0 | 0 |  |
