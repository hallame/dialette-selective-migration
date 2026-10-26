-- Schema du labo dialette_lab.
-- conversations, messages, widget_views : DDL identique a Dialette (SHOW CREATE TABLE sur la
-- base locale, sans la valeur AUTO_INCREMENT). Aucun index sur widget_views.created_at, comme
-- dans Dialette (voir docs/methodo.md pour la variante avec index).
-- users, widgets, contacts : versions MINIMALES, uniquement les colonnes utiles aux cles
-- etrangeres. Ce ne sont pas des copies de la structure de Dialette.

CREATE TABLE users (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  email varchar(255) NOT NULL,
  created_at timestamp NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY users_email_unique (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE widgets (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  user_id bigint(20) unsigned NOT NULL,
  slug varchar(255) NOT NULL,
  created_at timestamp NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY widgets_slug_unique (slug),
  KEY widgets_user_id_foreign (user_id),
  CONSTRAINT widgets_user_id_foreign FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE contacts (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  reference varchar(255) NOT NULL,
  email varchar(255) NOT NULL,
  user_id bigint(20) unsigned DEFAULT NULL,
  created_at timestamp NULL DEFAULT NULL,
  deleted_at timestamp NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY contacts_reference_unique (reference),
  UNIQUE KEY contacts_user_id_email_unique (user_id,email),
  KEY contacts_email_index (email),
  CONSTRAINT contacts_user_id_foreign FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE conversations (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  reference varchar(255) NOT NULL,
  interlocutor_type varchar(255) NOT NULL,
  interlocutor_id bigint(20) unsigned NOT NULL,
  subject varchar(255) DEFAULT NULL,
  conversable_type varchar(255) NOT NULL,
  conversable_id bigint(20) unsigned NOT NULL,
  meta longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(meta)),
  status varchar(255) NOT NULL DEFAULT 'open',
  token varchar(255) NOT NULL,
  source varchar(255) DEFAULT NULL,
  last_message_at timestamp NULL DEFAULT NULL,
  closed_at timestamp NULL DEFAULT NULL,
  user_id bigint(20) unsigned DEFAULT NULL,
  created_at timestamp NULL DEFAULT NULL,
  updated_at timestamp NULL DEFAULT NULL,
  deleted_at timestamp NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY conversations_reference_unique (reference),
  UNIQUE KEY conversations_token_unique (token),
  KEY conversations_interlocutor_type_interlocutor_id_index (interlocutor_type,interlocutor_id),
  KEY conversations_conversable_type_conversable_id_index (conversable_type,conversable_id),
  KEY conversations_user_id_foreign (user_id),
  KEY conversations_status_index (status),
  CONSTRAINT conversations_user_id_foreign FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE messages (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  conversation_id bigint(20) unsigned NOT NULL,
  sender_type varchar(255) NOT NULL,
  sender_id bigint(20) unsigned NOT NULL,
  sender_role varchar(255) DEFAULT NULL,
  content text NOT NULL,
  read_at timestamp NULL DEFAULT NULL,
  created_at timestamp NULL DEFAULT NULL,
  updated_at timestamp NULL DEFAULT NULL,
  deleted_at timestamp NULL DEFAULT NULL,
  PRIMARY KEY (id),
  KEY messages_sender_type_sender_id_index (sender_type,sender_id),
  KEY messages_conversation_id_created_at_index (conversation_id,created_at),
  CONSTRAINT messages_conversation_id_foreign FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE widget_views (
  id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  widget_id bigint(20) unsigned NOT NULL,
  created_at timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (id),
  KEY widget_views_widget_id_foreign (widget_id),
  CONSTRAINT widget_views_widget_id_foreign FOREIGN KEY (widget_id) REFERENCES widgets (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
