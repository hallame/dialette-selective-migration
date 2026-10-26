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



## Reproduire le labo (volume 10 000)

Depuis la racine du dépôt, avec le venv Python 3.13 et un `.env` copié de `.env.example` (optionnel : les valeurs par défaut visent le XAMPP local, utilisateur root sans mot de passe) :

```
venv\Scripts\python.exe scripts\extract_distributions.py      # lit Dialette en READ ONLY, écrit config/distributions.json
venv\Scripts\python.exe scripts\create_lab_schema.py          # recrée dialette_lab depuis sql/lab_schema.sql
venv\Scripts\python.exe scripts\generate_data.py --volume 10000 --seed 42
venv\Scripts\python.exe scripts\verify_lab.py --out docs\verification_10000.md
```

Reproductibilité vérifiée : deux générations avec la même graine donnent les mêmes CHECKSUM TABLE sur les six tables ; une autre graine donne des sommes différentes.