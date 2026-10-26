# Verification de la migration, N = 10000

Source : MariaDB `dialette_lab`. Cible : MongoDB `dialette_lab` (serveur 8.3.2).

Resultat global : **TOUS LES CONTROLES REUSSIS** (24 sur 24).


## Comptes

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| messages | 40079 | 40079 | OK |
| widget_views | 114000 | 114000 | OK |
| conversations.meta non NULL / conversation_answers | 7591 | 7591 | OK |

## Messages par conversation

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| conversations avec message (MariaDB / MongoDB) | 10000 | 10000 | OK |
| conversations dont le nombre de messages differe (attendu 0) | 0 | 0 | OK |
| total des messages | 40079 | 40079 | OK |

## Messages (hash)

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| messages compares | 40079 | 40079 | OK |
| lignes dont un champ differe (attendu 0) | 0 | 0 | OK |
| messages dont le contenu differe (attendu 0) | 0 | 0 | OK |
| SHA-256 du contenu, ordre par id | `ebc2f4bdf2c67c2e...` | `ebc2f4bdf2c67c2e...` | OK |
| SHA-256 des lignes completes, ordre par id | `f992270ea0d5f03b...` | `f992270ea0d5f03b...` | OK |

## Widget views (hash)

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| SHA-256 des lignes (id, widget_id, created_at), ordre par id | `43f8c0446688d5c7...` | `43f8c0446688d5c7...` | OK |

## Meta (JSON)

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| meta absents ou mal apparies cote MongoDB (attendu 0) | 0 | 0 | OK |
| JSON egal au document migre (valeurs) | 7591 | 7591 | OK |
| meme ordre des cles | 7591 | 7591 | OK |
| valeurs dont le type JSON differe (attendu 0) | 0 | 0 | OK |
| conversations a meta NULL sans document (attendu : toutes) | 2409 | 2409 | OK |

## Orphelins MongoDB

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| messages sans conversation dans MariaDB (attendu 0) | 0 | 0 | OK |
| widget_views sans widget dans MariaDB (attendu 0) | 0 | 0 | OK |
| conversation_answers sans conversation dans MariaDB (attendu 0) | 0 | 0 | OK |

## Index MongoDB

| Controle | Attendu (MariaDB) | Obtenu (MongoDB) | Resultat |
|---|---|---|---|
| messages : index hors _id | ['messages_conversation_id_created_at_index', 'messages_sender_type_sender_id_index'] | ['messages_conversation_id_created_at_index', 'messages_sender_type_sender_id_index'] | OK |
| widget_views : index hors _id | ['widget_views_widget_id_foreign'] | ['widget_views_widget_id_foreign'] | OK |
| conversation_answers : index hors _id | [] | [] | OK |
| widget_views : index sur created_at (attendu aucun) | False | False | OK |
