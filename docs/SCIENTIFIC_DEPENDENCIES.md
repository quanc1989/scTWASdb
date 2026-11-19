# Scientific dependencies and resources

The wrappers use external scientific software and operator-supplied reference data. setup/external-tool-identities.json records implementation file checksums for the saved example. Repository links identify the upstream projects; use file checksums when matching an installed implementation to the saved results.

## TIGAR

The upstream repository is [yanglab-emory/TIGAR](https://github.com/yanglab-emory/TIGAR). The recorded public snapshot is c080da5b69d2746717a289bc1fbe9eb43f85ffcb. Its file URLs and checksums are in setup/tigar-public-source.json.

The wrapper calls TIGAR_TWAS.sh with summary GWAS scores, expression weights, gene annotation and SNP covariance. It uses the summary-statistic interface with --asso 2, --weight_threshold and --test_stat. Check that the installed implementation supports these arguments. For replay of the saved implementation, match the file checksums in setup/external-tool-identities.json.

## OTTERS and SDPR

The upstream OTTERS repository is [daiqile96/OTTERS](https://github.com/daiqile96/OTTERS). The weight-construction wrapper calls training.py and uses ottersutils.py, prepare.py and PRSmodels code. Its implementation file checksums are recorded in setup/external-tool-identities.json.

The upstream SDPR repository is [eldronzhou/SDPR](https://github.com/eldronzhou/SDPR). The recorded reference source identifier is c4c61fbac0b21282bbef73e75584f836b4f73fc2, and the recorded license is GPLv3. Configure SCTWAS_SDPR_DIR with the directory containing the executable when using the SDPR method.

Install scientific dependencies separately under their respective terms. The wrappers use the locations supplied through the environment variables in docs/CONFIGURATION.md.

## Reference layout

~~~text
reference-root/
  Homo_sapiens.GRCh38.100.gtf.h.geneANNO
  model/
    COLLECTION/REGISTERED_MODEL/chr22/P0.05.tigar.txt.gz
    COLLECTION/REGISTERED_MODEL/chr22/P0.05.tigar.txt.gz.tbi
  RefLD/
    EUR_hg38/CHR22_reference_cov.txt.gz
    EUR_hg38/CHR22_reference_cov.txt.gz.tbi
    EAS_hg38/CHR22_reference_cov.txt.gz
    EAS_hg38/CHR22_reference_cov.txt.gz.tbi
~~~

Select reference files with compatible coordinates, allele encoding and population context. Provide each indexed covariance matrix and its companion index at the configured path.

The recorded scientific environment uses Python 3.8.3, NumPy 1.21.4, pandas 1.2.3, SciPy 1.7.3 and pysam 0.16.0.1, with HTSlib bgzip/tabix 1.21. Weight-construction methods additionally use PLINK, R packages or SDPR. This source snapshot has been checked for syntax, static assets and read-only example startup; full scientific execution requires the configured software and reference resources.
