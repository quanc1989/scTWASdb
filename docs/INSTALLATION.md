# Installation and database setup

## Web environment

Install requirements.txt in a new Python 3.12 virtual environment. System packages must supply the compiler and MariaDB/MySQL client development files required by mysqlclient. The recorded Web environment uses Python 3.12.14, Django 5.2.17 and MariaDB 10.11.19.

The manage.py init command creates a new state directory. It initializes an empty SQLite database with setup/schema.sqlite.sql, imports the included example rows, generates a random secret in an owner-only configuration file, and installs the saved example result. It refuses an existing state directory. It does not execute a scientific job.

The local server binds 127.0.0.1 and serves the shipped static assets. Stop it with Ctrl+C. Use a WSGI server and reverse proxy for a network-facing installation.

## Empty application database

The application models are unmanaged. Django migrations do not create their scientific tables. Use setup/schema.mariadb.sql for a fresh MariaDB database or setup/schema.sqlite.sql for a fresh SQLite database. These scripts derive from the recorded application columns and indexes.

After creating an empty database and a database account with suitable privileges:

~~~bash
mariadb --host=127.0.0.1 --user=sctwas --password sctwas < setup/schema.mariadb.sql
~~~

The scripts preserve non-unique scientific and metadata keys. In particular, studyID is not unique, and repeated ensemblID or rsID values occur across associations and references. Only the recorded primary keys are enforced. Imports must retain record multiplicity. Use a fresh database to initialize the schema.

The example initializer loads SQLite fixtures. A full MariaDB resource needs its own data import procedure and database snapshot. Numerical TWAS output files do not supply the full precomputed database.

## Configuration

Copy setup/config.example.json to a runtime directory outside the tracked source tree. Generate a random site secret, save it in the private configuration, set the database, runtime paths, public host names and HTTPS origins, then apply owner-only permissions:

~~~bash
chmod 600 /absolute/path/to/config.json
export SCTWAS_RUNTIME_CONFIG=/absolute/path/to/config.json
export DJANGO_SETTINGS_MODULE=sctwas.deployment.settings
python -m django check
python -m django collectstatic --noinput
gunicorn --bind 127.0.0.1:8000 --workers 2 sctwas.deployment.wsgi:application
~~~

Serve STATIC_ROOT through the reverse proxy at STATIC_URL. Keep task and export directories outside static storage. Configure ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS and HTTPS for the deployment.

READ_ONLY_DEMO defaults to true. Set it to false in a configured deployment with the required reference data and a supervised scientific worker. The Web process persists submissions to a private queue. The export and scientific workers are separate services.

## Assets

Verify the checked-in bundles without network access:

~~~bash
python -m sctwas.research.build_assets --check
~~~

After editing bundle inputs, regenerate with python -m sctwas.research.build_assets. Retain the component notices with both original assets and generated bundles.
