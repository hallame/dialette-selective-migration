# dialette-selective-migration

Экспериментальный стенд для ВКР: эффективность выборочной миграции данных из MariaDB в MongoDB на примере системы Dialette.

Стенд создаёт лабораторную базу, заполняет её синтетическими данными, переносит три набора данных в MongoDB (конфигурация B) и проверяет результат.

## Что переносится

| Источник в MariaDB | Коллекция в MongoDB |
|---|---|
| messages | messages |
| widget_views | widget_views |
| conversations.meta | conversation_answers |

Остальные таблицы (users, widgets, contacts, conversations) остаются в MariaDB. Миграция их не меняет.

## Требования

- Python 3.13
- MariaDB 10.4 (например, XAMPP) на localhost:3306
- MongoDB 8 на localhost:27017
- пакеты из requirements.txt (PyMySQL, pymongo, dnspython)

## Установка

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Файл `.env` нужен, только если параметры подключения отличаются от значений по умолчанию (root без пароля, localhost). В репозиторий `.env` не попадает.

Имена лабораторных баз должны оканчиваться на `_lab`. Иначе скрипты отказываются работать.

## Запуск (объём 10 000 разговоров)

Все команды выполняются из корня репозитория.

```
venv\Scripts\python.exe scripts\create_lab_schema.py
venv\Scripts\python.exe scripts\generate_data.py --volume 10000 --seed 42
venv\Scripts\python.exe scripts\verify_lab.py --out docs\verification_10000.md
venv\Scripts\python.exe scripts\migrate_selective.py --dry-run
venv\Scripts\python.exe scripts\migrate_selective.py --batch 5000
venv\Scripts\python.exe scripts\verify_migration.py --out docs\migration_verification_10000.md
```

Готовый файл `config/distributions.json` уже есть в репозитории. Скрипт `scripts\extract_distributions.py` нужен только для того, чтобы обновить его по базе Dialette. Он читает эту базу один раз, в режиме READ ONLY, и записывает только агрегаты.

## Скрипты

| Скрипт | Назначение |
|---|---|
| extract_distributions.py | агрегаты из базы Dialette без персональных данных, запись в config/distributions.json |
| create_lab_schema.py | создание базы dialette_lab по sql/lab_schema.sql |
| generate_data.py | синтетические данные, воспроизводимо (параметры `--volume`, `--seed`) |
| verify_lab.py | проверка данных: количество, сравнение с целевыми показателями, целостность связей |
| migrate_selective.py | миграция в MongoDB |
| verify_migration.py | проверка миграции (24 контроля) |

Параметры migrate_selective.py:

- `--batch` размер пакета (по умолчанию 5000)
- `--tables` какие таблицы переносить
- `--dry-run` ничего не записывать, только посчитать
- `--restart` игнорировать точку возобновления и перенести всё заново
- `--stop-after-batches K` остановиться после K пакетов (проверка возобновления)
- `--log` файл журнала (по умолчанию output/migration_N.jsonl)

Миграция идемпотентна и продолжается после остановки. Она ничего не удаляет. Если в MariaDB строки изменились или исчезли, нужен запуск с `--restart`.

## Результаты

- docs/verification_10000.md: проверка синтетических данных
- docs/migration_verification_10000.md: проверка миграции, 24 из 24
- docs/methodo.md: методика эксперимента
- docs/schema.md: схема таблиц Dialette, которые затрагивает эксперимент

## Состояние

Работает на объёме 10 000 разговоров. Объёмы 100 000 и 1 000 000, замеры производительности и вариант с индексом по widget_views.created_at планируются в следующих контрольных точках.

Распределения для генерации получены из локальной тестовой базы Dialette (40 разговоров), а не из рабочей системы.
