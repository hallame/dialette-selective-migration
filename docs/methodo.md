# Méthodologie de l'expérience

Document de travail, complété au fil de l'avancement.

## Cadre

L'expérience se déroule dans un environnement isolé, avec des données synthétiques calibrées sur les distributions de Dialette, aux volumes 10k, 100k et 1M, selon deux configurations : A (tout relationnel) et B (hybride).

Base MariaDB du labo : `dialette_lab`. La base de l'application n'est jamais écrite. Elle n'est lue qu'une fois, par `scripts/extract_distributions.py`, en transaction READ ONLY, pour produire des agrégats.

## Définition du volume N

N est le nombre de conversations. Les autres volumes en découlent par les ratios de `config/distributions.json` :
- messages : tirés conversation par conversation selon l'histogramme observé (moyenne cible 4,025 par conversation) ;
- vues de widget : N multiplié par `views_per_conversation` (11,4) ;
- contacts : N multiplié par `contacts_per_conversation` (0,75).

Les tables de dimension `users` (11) et `widgets` (9) ne grandissent pas avec N.

## Limites connues des distributions actuelles

- L'échantillon est une base de développement et de test : 40 conversations, 161 messages, 456 vues. Les quantiles de longueur de message et d'écart entre messages reposent sur très peu de points. Les distributions sont conçues pour être remplacées par des agrégats de production (relancer `scripts/extract_distributions.py` sur la source voulue).
- Le nombre de messages par conversation est tiré indépendamment du type de conversation, alors que dans les données observées les conversations de type question et de type projet n'ont probablement pas la même forme (non vérifié).
- Les identifiants cibles des clés polymorphes `conversable_id` de type `lead` ne correspondent à aucune table du labo (pas de table `leads`). L'intégrité de ces clés n'est pas assurée par le SGBD, comme dans Dialette.
- Le fenêtrage temporel (365 jours par défaut) concentre N conversations sur une durée bien plus courte que dans la réalité, donc la densité par jour n'est pas celle de Dialette. Seuls les ratios et la dispersion quotidienne des vues sont calibrés.

## Variante à mesurer plus tard : index sur widget_views.created_at

Dialette n'a pas d'index sur `widget_views.created_at`. Le labo reproduit donc ce DDL à l'identique pour la configuration de référence.

Une agrégation par jour ou par période sur `widget_views` balaie la table en l'absence d'index. Comparer MariaDB sans index à MongoDB, où un index sur la date est facile à créer, favoriserait MongoDB pour une raison étrangère au modèle de données. Pour une comparaison équitable, mesurer aussi une variante "avec index" :

- configuration A, variante A+i : MariaDB avec `CREATE INDEX widget_views_created_at_index ON widget_views (created_at)`, et éventuellement un index composite `(widget_id, created_at)` ;
- configuration B : index équivalent sur `created_at` dans la collection MongoDB.

Cette variante n'est pas créée à ce stade. Les résultats devront indiquer pour chaque mesure si la variante avec index est utilisée.

## Configuration B : mapping relationnel vers documents

Base MongoDB `dialette_lab`. Le noyau transactionnel (users, widgets, contacts, conversations) reste dans MariaDB et n'est pas modifié par la migration. Trois jeux de données sont copiés.

Règle générale : un champ par colonne, même nom, sans renommage ni imbrication, et `_id` = identifiant d'origine. Ce choix rend la migration idempotente (écriture par `_id`), rend la vérification ligne à ligne possible, et évite d'introduire un gain ou une perte de performance dû au remodelage plutôt qu'au changement de moteur. Les dates sont des dates BSON en UTC.

### messages (collection `messages`)

| Colonne MariaDB | Champ MongoDB | Remarque |
|---|---|---|
| id | `_id` | entier d'origine |
| conversation_id | `conversation_id` | référence applicative, plus de clé étrangère |
| sender_type, sender_id, sender_role | mêmes noms | relation polymorphe conservée telle quelle |
| content | `content` | |
| read_at, created_at, updated_at, deleted_at | mêmes noms | `null` conservé pour les valeurs NULL |

Choix écarté : imbriquer les messages dans un document par conversation. Cela favoriserait la lecture d'une conversation entière mais changerait la forme des écritures (réécriture du document à chaque message) et celle des agrégations, ce qui fausserait la comparaison avec A. À reconsidérer comme variante de modélisation, pas dans la comparaison de base.

### widget_views (collection `widget_views`)

| Colonne MariaDB | Champ MongoDB |
|---|---|
| id | `_id` |
| widget_id | `widget_id` |
| created_at | `created_at` |

### conversation_answers (contenu de conversations.meta)

| Source | Champ MongoDB | Remarque |
|---|---|---|
| conversations.id | `_id` | une clé par conversation |
| conversations.meta (JSON) | `answers` | objet imbriqué, ordre des clés et types JSON conservés |

Les réponses sont sous `answers` plutôt qu'aplaties à la racine : les clés de `meta` sont librement choisies par les utilisateurs de Dialette (questions personnalisées), un nom de clé pourrait entrer en collision avec `_id`. Une conversation dont `meta` est NULL n'a pas de document (l'absence vaut NULL). La colonne `conversations.meta` n'est pas supprimée de MariaDB par la migration : la bascule (suppression de la colonne et des tables sources en configuration B) n'est pas faite à ce stade.

### Index

| MariaDB | MongoDB |
|---|---|
| messages (conversation_id, created_at) | idem, nom `messages_conversation_id_created_at_index` |
| messages (sender_type, sender_id) | idem, nom `messages_sender_type_sender_id_index` |
| widget_views (widget_id), créé par la clé étrangère | `widget_views_widget_id_foreign` |
| widget_views : aucun index sur created_at | aucun index sur created_at |
| conversations (clé primaire) | `_id` |

Écart avec la liste donnée pour la mission : j'ai aussi créé l'index `(sender_type, sender_id)` sur `messages`, car il existe dans MariaDB et l'omettre rendrait les écritures MongoDB moins coûteuses que celles de MariaDB. Il se retire en supprimant une ligne de `INDEXES` dans `scripts/migrate_selective.py`.

## Module de migration sélective

`scripts/migrate_selective.py`. Options : `--batch` (taille des lots, 5000 par défaut), `--tables`, `--dry-run`, `--restart`, `--log`, et `--stop-after-batches K` qui simule une interruption pour tester la reprise.

- **Lots** : pagination par clé (`id > dernier id ORDER BY id LIMIT lot`), coût constant par lot.
- **Idempotence** : `ReplaceOne({_id}, document, upsert=True)`. Relancer ne crée aucun doublon. Le prix est une lecture-écriture par document même quand rien n'a changé.
- **Reprise** : le dernier id écrit est enregistré dans la collection `_migration_state` après chaque lot. Après une interruption, la relance repart de là. Un crash entre l'écriture du lot et l'enregistrement rejoue au plus un lot, sans effet grâce à l'idempotence. Limite : les lignes modifiées ou supprimées dans MariaDB sous le point de reprise ne sont pas détectées ; `--restart` rejoue tout.
- **Dry-run** : lit, convertit, compte ce qui serait inséré ou remplacé, n'écrit rien (ni document, ni index, ni point de reprise).
- **Journal** : `output/migration_<N>.jsonl` (ignoré par git), une ligne par lot et un résumé par table avec durée et débit.

Tests réalisés à N = 10 000 : dry-run (aucune collection créée, 40 079 + 114 000 + 7 591 documents annoncés), interruption après 2 lots de messages puis reprise depuis l'id 10 000 (30 079 insérés, total 40 079), relance simple (0 ligne lue), relance avec `--restart` (tout inchangé, aucun doublon).

Les débits du journal (quelques milliers de lignes par seconde) sont des ordres de grandeur d'un seul passage sur une machine de développement, pas des mesures de benchmark.

## Suppression en cascade en configuration B

Dans MariaDB, `messages` et `widget_views` portent `ON DELETE CASCADE` : supprimer une conversation ou un widget supprime ses lignes filles. Cette garantie disparaît pour les données déplacées dans MongoDB, qui n'a pas de clé étrangère. Traitement retenu pour l'expérience :

1. Les suppressions applicatives doivent être faites dans les deux systèmes, côté application, dans cet ordre : d'abord MongoDB (`delete_many` sur `conversation_id` ou `widget_id`, et `delete_one` dans `conversation_answers`), puis la ligne parente dans MariaDB. En cas de panne entre les deux, on obtient une ligne parente sans enfants, qui se re-supprime sans dommage, plutôt que des enfants orphelins invisibles. Il n'y a pas de transaction commune : l'opération n'est pas atomique.
2. La vérification (`scripts/verify_migration.py`) compte les orphelins MongoDB (messages, vues et réponses dont le parent n'existe plus dans MariaDB), attendu 0. C'est le filet de réconciliation.
3. La migration elle-même ne supprime rien : un document dont la ligne source a disparu reste dans MongoDB. Le test de sensibilité ci-dessous l'a confirmé. Un nettoyage des orphelins n'est pas implémenté ; il reste à faire si la configuration B doit être utilisée avec des suppressions.

Les suppressions logiques (`deleted_at`) sont simplement copiées comme des champs.

Le coût de cette gestion applicative (code supplémentaire, atomicité perdue) fait partie de la mesure de complexité du modèle.

## Test de sensibilité de la vérification

Pour vérifier que les contrôles détectent un défaut, j'ai altéré MongoDB à la main (contenu d'un message, une valeur de `answers`, un message orphelin ajouté). La vérification a signalé les trois défauts (13 contrôles réussis sur 24). `migrate_selective.py --restart` a réparé l'altération du message (1 remplacé) et celle de `answers` (1 remplacé), mais pas l'orphelin, supprimé à la main ensuite. La vérification finale réussit (24 sur 24).

## Reproduire le labo (volume 10 000)

Depuis la racine du dépôt, avec le venv Python 3.13 et un `.env` copié de `.env.example` (optionnel : les valeurs par défaut visent le XAMPP local, utilisateur root sans mot de passe) :

```
venv\Scripts\python.exe scripts\extract_distributions.py      # lit Dialette en READ ONLY, écrit config/distributions.json
venv\Scripts\python.exe scripts\create_lab_schema.py          # recrée dialette_lab depuis sql/lab_schema.sql
venv\Scripts\python.exe scripts\generate_data.py --volume 10000 --seed 42
venv\Scripts\python.exe scripts\verify_lab.py --out docs\verification_10000.md
```

Migration vers la configuration B et vérification (MongoDB doit tourner sur localhost:27017) :

```
venv\Scripts\python.exe scripts\migrate_selective.py --dry-run
venv\Scripts\python.exe scripts\migrate_selective.py --batch 5000
venv\Scripts\python.exe scripts\verify_migration.py --out docs\migration_verification_10000.md
```

Reproductibilité vérifiée : deux générations avec la même graine donnent les mêmes CHECKSUM TABLE sur les six tables ; une autre graine donne des sommes différentes.