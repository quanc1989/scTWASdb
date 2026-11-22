# Configuration and entry points

## Web settings

SCTWAS_RUNTIME_CONFIG selects the owner-only JSON file. Use absolute paths in deployment configurations.

| Key | Purpose |
|---|---|
| SECRET_KEY | Random site secret |
| DATABASE | Django connection dictionary |
| ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS | Site host names and HTTPS origins |
| HTTPS | Secure session and CSRF cookies |
| READ_ONLY_DEMO | Read-only local example mode |
| STATIC_ROOT, STATIC_URL | Collected assets and URL prefix |
| SCTWAS_RELEASE, SCTWAS_DATA_VERSION | Web and data version labels |
| SCTWAS_TASK_ROOT | Private job inputs, manifests and results |
| SCTWAS_EXPORT_ROOT | Prepared downloads and export queue |
| SCTWAS_QUERY_CACHE_ROOT | Explore cache |
| SCTWAS_EXPLORE_INDEX, SCTWAS_EXPLORE_INDEX_SHA256 | Optional query projection and checksum |
| MAIL | Django backend and optional SMTP settings |

An absent, stale or damaged Explore index falls back to database queries.

## Scientific environment

| Variable | Meaning |
|---|---|
| SCTWAS_TIGAR_DIR | Installed TIGAR directory |
| SCTWAS_OTTERS_DIR | Installed OTTERS directory |
| SCTWAS_RESEARCH_ROOT | Model archive and LD resource root |
| SCTWAS_ANNOTATION | Annotation path; defaults to the named GRCh38 file under the resource root |
| SCTWAS_GENOTYPE_ROOT | Population-specific PLINK root |
| SCTWAS_PIPELINE_PYTHON | Scientific interpreter; defaults to python |
| SCTWAS_SDPR_DIR | Optional SDPR executable directory |
| SCTWAS_THREADS | Scientific thread count; defaults to 4 |
| SCTWAS_RANDOM_SEED | Optional nonnegative seed for weight construction |

The TWAS wrapper accepts eleven positional arguments:

~~~text
input output chromosome registered_model collection display_p_threshold
gene_window_bp weight_threshold reference_build LD_population statistic
~~~

It supports chr1 through chr22, hg38, EUR or EAS, and FUSION, SPrediXcan or both. The display threshold filters views and downloads. The raw output retains the complete method statistics.

The weight-construction wrapper accepts six positional arguments:

~~~text
input output chromosome reference_build LD_population method
~~~

Its configured scope is hg38/EUR, with PT, lassosum, PRScs or SDPR. It calls OTTERS on summary-eQTL input and external genotypes.

## Background services

Supervise the export worker separately:

~~~bash
export DJANGO_SETTINGS_MODULE=sctwas.deployment.settings
export SCTWAS_RUNTIME_CONFIG=/absolute/path/to/config.json
python -m sctwas.export_worker --settings-path .
~~~

The scientific worker communicates with a queue host over SSH/SCP:

~~~bash
python -m sctwas.research.spool_worker \
  --host queue-host \
  --remote-release /absolute/path/to/source \
  --remote-project /absolute/path/to/source \
  --remote-python /absolute/path/to/web-venv/bin/python \
  --remote-settings sctwas.deployment.settings \
  --remote-config /absolute/path/to/config.json \
  --remote-root /absolute/path/to/private-tasks \
  --work-root /absolute/path/to/scientific-work \
  --worker scientific-worker
~~~

The --timeout limit defaults to 21600 seconds per job. The --once option claims at most one queued job. Both modes execute science when a job is present. The RPC module sctwas.research.spool_control receives JSON over SSH standard input. It is not an HTTP endpoint.

RELEASE.json records the base Web, saved-task result view, shared assets, association-export/RPC and scientific-worker components separately. The local example reports the source-package label source-20261121.1. Saved-task file downloads read an existing result artifact; they do not use the precomputed-association export queue.
