# scTWASdb

scTWASdb is a Django application for finding and understanding transcriptome-wide association evidence across cellular expression references. It provides searchable model, trait and source catalogues, association queries, downloadable results and interfaces for summary-statistic TWAS and expression-weight construction.

The project repository URL is [quanc1989/scTWASdb](https://github.com/quanc1989/scTWASdb). The hosted resource is available at [sctwas.omic.tech](https://sctwas.omic.tech/). This tree contains the Web implementation associated with version 20261118-01 and the separately versioned export, queue-control and scientific-worker implementation. Component identifiers are recorded in [RELEASE.json](RELEASE.json).

## Run the example

Use Python 3.12 on Linux. The Web requirements include mysqlclient, which requires a C compiler, Python headers, pkg-config and MariaDB Connector/C or MySQL client development headers.

~~~bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py init --state ./runtime
python manage.py check --state ./runtime
python manage.py run --state ./runtime --port 8000
~~~

Open http://127.0.0.1:8000/browse. The example database contains 204 model records, 829 trait definitions and 32 source records. Two source rows retain the same study identifier because they describe different registered sample contexts.

The example includes three saved RGL4 association records across three traits. Open http://127.0.0.1:8000/query?q=RGL4&key=0 to explore this subset. The complete saved 78-gene chromosome 22 result is available at:

~~~text
http://127.0.0.1:8000/detail?key=5&data=00000000000000000000000000000001&chrom=chr22&thres_twas=0.05
~~~

Example mode permits read-only browsing and saved-result downloads. Job submission is disabled. Its health endpoint reports actual database and scientific-worker readiness, so compute_ready is false when no worker is running.

## Included material

| Path | Content |
|---|---|
| sctwas/ | Django application, templates, table presentation, queues, export and scientific-worker wrappers |
| setup/ | Configuration example, empty database schemas and external-software identities |
| examples/catalogue/ | Catalogue metadata and the small RGL4 association subset |
| examples/ukb4118/ | GWAS excerpt, parameters, complete 78-gene output and field definitions |
| numerical/ | 198 captured operand groups, independent R formulas and saved comparisons |
| third-party/ | Frontend license and notice texts |
| MANIFEST.tsv, SHA256SUMS | File inventory and checksums |

Full association tables, reference weights, genotype panels and LD matrices are operator-supplied resources. Catalogue counts describe registered records. They do not count independently validated prediction models or discoveries.

See [installation](docs/INSTALLATION.md), [configuration](docs/CONFIGURATION.md), [input formats](docs/INPUT_FORMATS.md), [scientific dependencies](docs/SCIENTIFIC_DEPENDENCIES.md), [example provenance](examples/ukb4118/README.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

## License

Project-owned application and setup code is available under the [MIT License](LICENSE), Copyright (c) 2026 scTWASdb contributors. Bundled third-party components retain their own license and notice terms, listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). External scientific software and example data retain the terms of their respective sources, described in [scientific dependencies](docs/SCIENTIFIC_DEPENDENCIES.md) and [example data sources](examples/README.md).
