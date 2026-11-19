# Input and output formats

## Summary-statistic TWAS

The existing chromosome 22 tutorial is a tab-separated gzip file with:

~~~text
CHROM  POS  REF  ALT  Zscore
~~~

Use genomic coordinates in the build selected for the reference, with alleles and the signed Z score oriented consistently. The server accepts the compressed file through the TWAS form. The wrapper passes it to TIGAR after creating the position index. The saved example uses GRCh38.

Choose the registered expression model, chromosome, reference population, statistic, nominal display threshold, gene window and absolute weight threshold. The gene window defaults to 1,000,000 base pairs, the absolute weight threshold to zero, and both method statistics are available. The display threshold does not adjust for multiple testing.

The raw output columns are:

~~~text
CHROM GeneStart GeneEnd TargetID GeneName n_snps FUSION_Z FUSION_PVAL SPred_Z SPred_PVAL
~~~

Column definitions are in examples/ukb4118/raw-result-fields.tsv. Saved-result downloads apply the selected nominal threshold and preserve method identity.

## Expression-weight construction

The provided one-gene summary-eQTL file uses:

~~~text
CHROM  POS  A1  A2  Z  TargetID  N
~~~

The seven fields carry chromosome, position, allele pair, signed summary statistic, target gene and sample-size value. Interpretation must follow the actual source study and the OTTERS input conventions. The file does not contain individual genotypes or measured expression.

The configured form supports GRCh38/EUR and PT, lassosum, PRScs or SDPR. PT output is converted to indexed CHROM/POS/REF/ALT/TargetID/ES weights using the wrapper's existing allele-column rule. That rule and a finite output do not establish predictive accuracy or source-allele correctness.

Use external, appropriately identified annotation, genotype and LD resources. The reference layout and recorded implementation file identities are documented separately.
