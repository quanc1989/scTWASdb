#!/bin/bash
set -euo pipefail
[[ $# -eq 11 ]] || { echo 'Expected 11 TWAS arguments' >&2; exit 2; }
path_input=$1
path_output=$2
chrom=$3
celltypeID=$4
collectionID=$5
# Filter views/exports by this threshold; retain the full raw statistics.
thres_twas=$6
eqtl_window=$7
eqtl_weight=$8
reference_human=$9
reference_population=${10}
method_ztest=${11}
[[ "$chrom" =~ ^chr([1-9]|1[0-9]|2[0-2])$ ]] || exit 2
[[ "$reference_human" == hg38 ]] || { echo 'Only hg38 annotation is configured' >&2; exit 2; }
[[ "$reference_population" == EUR || "$reference_population" == EAS ]] || exit 2
[[ "$celltypeID" != */* && "$collectionID" != */* && "$celltypeID" != .. && "$collectionID" != .. ]] || exit 2
nThreads=${SCTWAS_THREADS:-4}
TIGAR_dir=${SCTWAS_TIGAR_DIR:?Set SCTWAS_TIGAR_DIR to the installed TIGAR directory}
research_root=${SCTWAS_RESEARCH_ROOT:?Set SCTWAS_RESEARCH_ROOT to the reference resource root}
annotation=${SCTWAS_ANNOTATION:-$research_root/Homo_sapiens.GRCh38.100.gtf.h.geneANNO}
ES_dir=$research_root/model/$collectionID/$celltypeID/$chrom/P0.05.tigar.txt.gz
LD_dir=$research_root/RefLD/${reference_population}_${reference_human}
num_chrom=${chrom#chr}
for required in "$path_input" "$ES_dir" "$annotation" "$LD_dir/CHR${num_chrom}_reference_cov.txt.gz"; do
  [[ -s "$required" ]] || { echo 'A required TWAS input is missing or empty' >&2; exit 1; }
done
mkdir -p "$path_output"
tabix -f -s1 -S1 -b2 -e2 "$path_input"
bash -e "$TIGAR_dir/TIGAR_TWAS.sh" \
  --asso 2 --gene_anno "$annotation" --chr "$num_chrom" \
  --weight "$ES_dir" --Zscore "$path_input" \
  --LD "$LD_dir/CHR${num_chrom}_reference_cov.txt.gz" \
  --thread "$nThreads" --out_dir "$path_output" --TIGAR_dir "$TIGAR_dir" \
  --window "$eqtl_window" --weight_threshold "$eqtl_weight" --test_stat "$method_ztest"
