# Saved UK Biobank chromosome 22 example

This example uses 4,500 variants for PheCode 411.8, the DICE naïve CD4 reference CD4+_T_cells_Schmiedel_2018_naive (SCM-4575da5cbc8dfa56), GRCh38 coordinates and the recorded EUR LD resource. The gene window is 1 Mb on each side, the weight threshold is zero, and both implemented statistics are retained.

The [original fastGWA statistics](https://yanglab.westlake.edu.cn/resources/fastgwa_data/UKBbin/411.8_PheCode.v1.0.fastGWA.gz) used GRCh37 coordinates. The existing excerpt was mapped to GRCh38 with a dbSNP154-derived mapping. input.txt.gz preserves its recorded gzip bytes.

| File | Content |
|---|---|
| input.txt.gz | 4,500-variant tutorial input |
| saved-parameters.json | Parameters, saved outcome counts and output checksum |
| scTWASdb_Table_S2_source.tsv | Complete saved 78-gene output and 156 method statistics |
| raw-result-fields.tsv | Ten raw column definitions |
| reference-assets.json | Logical reference names and existing identities |

The nominal threshold P ≤ 0.05 selects ten method records involving five genes. These are unadjusted statistics. A fresh scientific run requires the external implementation and large reference inputs described in docs/SCIENTIFIC_DEPENDENCIES.md.

The expression-weight example is sctwas/static/sctwas/examples/D11_Stegle_2021_FPP.iPSCs.chr22.one-gene.tsv. Its catalogue source is Jerber et al. (2021), [Population-scale single-cell RNA-seq profiling across dopaminergic neuron differentiation](https://doi.org/10.1038/s41588-021-00801-6). It contains summary association fields, not individual-level genotype or measured expression data.
