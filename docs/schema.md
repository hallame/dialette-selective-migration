# Schéma relationnel de Dialette (tables concernées par l'expérience)

Sources : migrations Laravel de Dialette (lecture seule), puis `SHOW CREATE TABLE` sur la base locale pour confirmer. Les deux concordent. Moteur InnoDB, jeu de caractères utf8mb4, collation utf8mb4_unicode_ci. SGBD de l'application : MariaDB 10.4.32.

Migrations sources :
- `2026_03_26_094246_create_conversations_table.php`
- `2026_03_26_094335_create_messages_table.php`
- `2026_06_14_000001_create_widget_views_table.php`

## Relations

```
users 1 --- n conversations (user_id, ON DELETE SET NULL)
conversations 1 --- n messages (conversation_id, ON DELETE CASCADE)
widgets 1 --- n widget_views (widget_id, ON DELETE CASCADE)
conversations n --- 1 conversable (polymorphe : lead, project, contact)
conversations n --- 1 interlocutor (polymorphe : contact, user)
messages n --- 1 sender (polymorphe : user, contact, system)
```

Les clés polymorphes (`*_type`, `*_id`) n'ont pas de contrainte de clé étrangère : l'intégrité est applicative.

## Table conversations

| Colonne | Type MariaDB | Null | Défaut | Remarque |
|---|---|---|---|---|
| id | bigint unsigned AUTO_INCREMENT | non | | clé primaire |
| reference | varchar(255) | non | | générée côté modèle (`CONV` + année sur 2 chiffres + 6 caractères aléatoires) |
| interlocutor_type | varchar(255) | non | | morphs, nom de classe ou alias |
| interlocutor_id | bigint unsigned | non | | morphs |
| subject | varchar(255) | oui | NULL | |
| conversable_type | varchar(255) | non | | morphs, lead, project ou contact |
| conversable_id | bigint unsigned | non | | morphs |
| meta | longtext, collation utf8mb4_bin, CHECK json_valid(meta) | oui | NULL | JSON (voir plus bas) |
| status | varchar(255) | non | 'open' | open, closed, archived |
| token | varchar(255) | non | | 64 caractères hexadécimaux, généré côté modèle |
| source | varchar(255) | oui | NULL | commentaire de la migration : form, chat, whatsapp, email |
| last_message_at | timestamp | oui | NULL | |
| closed_at | timestamp | oui | NULL | |
| user_id | bigint unsigned | oui | NULL | FK vers users(id), ON DELETE SET NULL |
| created_at | timestamp | oui | NULL | |
| updated_at | timestamp | oui | NULL | |
| deleted_at | timestamp | oui | NULL | suppression logique (SoftDeletes) |

Index :

| Nom | Colonnes | Type |
|---|---|---|
| PRIMARY | id | clé primaire |
| conversations_reference_unique | reference | unique |
| conversations_token_unique | token | unique |
| conversations_interlocutor_type_interlocutor_id_index | interlocutor_type, interlocutor_id | non unique |
| conversations_conversable_type_conversable_id_index | conversable_type, conversable_id | non unique |
| conversations_user_id_foreign | user_id | non unique (créé par la FK) |
| conversations_status_index | status | non unique |

### Colonne meta (réponses de qualification)

Déclarée `$table->json('meta')->nullable()`. MariaDB 10.4 n'a pas de type JSON natif : la colonne est un `longtext` avec contrainte `json_valid`. Le modèle la caste en tableau (`'meta' => 'array'`).

Écriture : `ChatApiController` (autour des lignes 138 à 158) ajoute une paire clé/valeur à chaque réponse du visiteur (`$meta[$data['key']] = $data['value']`), puis met à jour la conversation. La clé `done` déclenche la création du lead (ou du message de question). Il n'y a pas de schéma fixe : les clés système connues dans le code sont `type`, `done`, `question_message`, `project_type`, `budget`, `timeline`, `phone`, `company`. Toute autre clé correspond à une question personnalisée du widget (`custom_questions` du widget), dont la clé est choisie par l'utilisateur de Dialette.

Remarque : `phone` et `company` sont aussi recopiés dans la table contacts. Dans `meta` ils sont donc redondants.

## Table messages

| Colonne | Type MariaDB | Null | Défaut | Remarque |
|---|---|---|---|---|
| id | bigint unsigned AUTO_INCREMENT | non | | clé primaire |
| conversation_id | bigint unsigned | non | | FK vers conversations(id), ON DELETE CASCADE |
| sender_type | varchar(255) | non | | morphs |
| sender_id | bigint unsigned | non | | morphs |
| sender_role | varchar(255) | oui | NULL | admin, client, system |
| content | text | non | | |
| read_at | timestamp | oui | NULL | |
| created_at | timestamp | oui | NULL | |
| updated_at | timestamp | oui | NULL | |
| deleted_at | timestamp | oui | NULL | suppression logique |

Index :

| Nom | Colonnes | Type |
|---|---|---|
| PRIMARY | id | clé primaire |
| messages_sender_type_sender_id_index | sender_type, sender_id | non unique |
| messages_conversation_id_created_at_index | conversation_id, created_at | non unique (sert aussi la FK) |

## Table widget_views

| Colonne | Type MariaDB | Null | Défaut | Remarque |
|---|---|---|---|---|
| id | bigint unsigned AUTO_INCREMENT | non | | clé primaire |
| widget_id | bigint unsigned | non | | FK vers widgets(id), ON DELETE CASCADE |
| created_at | timestamp | non | current_timestamp() | seule colonne temporelle, pas de updated_at |

Index :

| Nom | Colonnes | Type |
|---|---|---|
| PRIMARY | id | clé primaire |
| widget_views_widget_id_foreign | widget_id | non unique (créé par la FK) |

Il n'existe pas d'index sur `created_at` ni composite (widget_id, created_at). Toute agrégation par jour ou par période balaie donc l'index sur widget_id puis filtre, ou balaie la table.

## Points à garder en tête pour la migration

1. Convention des types polymorphes (`interlocutor_type`, `conversable_type`, `sender_type`). Vérifiée dans le code actuel de Dialette :
   - **Convention actuelle : alias.** `AppServiceProvider::boot()` appelle `Relation::enforceMorphMap` avec les alias `user`, `contact`, `lead`, `project`, `message`, `subscription`, `payment`. `getMorphClass()` renvoie donc l'alias, et `ConversationService` et `ChatApiController` écrivent des alias (`'contact'`, `'lead'`, `'user'`, `'project'`).
   - **Ancienne convention : nom de classe complet** (`App\Models\Contact`, `App\Models\Lead`, `App\Models\User`). Elle subsiste dans 25 % des conversations de la base locale (10 sur 40) et dans 30 messages sur 161. Le morph map date pourtant du premier commit de Dialette (2026-05-28) d'après `git log -S`, donc l'origine de ces lignes est inconnue : je ne l'ai pas établie.
   - Le générateur de l'expérience n'écrit que des alias. Les lignes à nom de classe ne sont pas reproduites (part consignée dans `config/distributions.json`, clé `share_legacy_class_name_rows`).
   - Point d'attention dans le code de Dialette : `Contact.php` (lignes 95 et 118) filtre `conversable_type` avec `Lead::class`, ce qui ne correspond qu'aux anciennes lignes à nom de classe. Je note le fait sans porter de jugement sur son effet.
2. `meta` est sans schéma fixe et son contenu varie d'une conversation à l'autre : c'est le candidat naturel à un document MongoDB.
3. La suppression en cascade (messages et widget_views) est portée par le SGBD. En configuration hybride, elle devra être reproduite par l'application ou un script.
4. Les colonnes `locale` ajoutées par `2026_09_11_000001_add_locale_columns.php` concernent users et widgets, pas les trois tables ci-dessus.
