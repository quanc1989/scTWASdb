#!/bin/bash
set -euo pipefail
[[ $# -eq 6 ]] || { echo 'Expected 6 training arguments' >&2; exit 2; }
path_input=$1
path_output=$2
chrom=$3
reference_human=$4
population_LD=$5
model_train=$6
[[ "$chrom" =~ ^chr([1-9]|1[0-9]|2[0-2])$ ]] || exit 2
[[ "$reference_human" == hg38 && "$population_LD" == EUR ]] || { echo 'Only hg38/EUR training is configured' >&2; exit 2; }
case "$model_train" in PT|lassosum|PRScs|SDPR) ;; *) exit 2 ;; esac
OTTERS_DIR=${SCTWAS_OTTERS_DIR:?Set SCTWAS_OTTERS_DIR to the installed OTTERS directory}
research_root=${SCTWAS_RESEARCH_ROOT:?Set SCTWAS_RESEARCH_ROOT to the reference resource root}
annotation=${SCTWAS_ANNOTATION:-$research_root/Homo_sapiens.GRCh38.100.gtf.h.geneANNO}
geno_root=${SCTWAS_GENOTYPE_ROOT:?Set SCTWAS_GENOTYPE_ROOT to the population PLINK root}
nthreads=${SCTWAS_THREADS:-4}
pipeline_python=${SCTWAS_PIPELINE_PYTHON:-python}
[[ -s "$path_input" && -s "$annotation" ]] || { echo 'Missing training input or annotation' >&2; exit 1; }
for suffix in bed bim fam; do
  [[ -s "$geno_root/$population_LD/$chrom.$suffix" ]] || { echo 'Missing training genotype reference' >&2; exit 1; }
done
extra_args=()
if [[ -n ${SCTWAS_RANDOM_SEED:-} ]]; then
  [[ "$SCTWAS_RANDOM_SEED" =~ ^[0-9]+$ ]] || exit 2
  extra_args+=(--seed="$SCTWAS_RANDOM_SEED")
fi
if [[ "$model_train" == SDPR ]]; then
  SDPR_DIR=${SCTWAS_SDPR_DIR:-$OTTERS_DIR/../SDPR}
  [[ -x "$SDPR_DIR/SDPR" ]] || { echo 'SDPR executable is unavailable' >&2; exit 1; }
  extra_args+=(--SDPR_dir="$SDPR_DIR")
fi
mkdir -p "$path_output"
"$pipeline_python" "$OTTERS_DIR/training.py" \
  --OTTERS_dir="$OTTERS_DIR" --anno_dir="$annotation" \
  --geno_dir="$geno_root/$population_LD/$chrom" --sst_file="$path_input" \
  --out_dir="$path_output" --chrom="${chrom#chr}" --r2=0.99 \
  --models="$model_train" --thread="$nthreads" "${extra_args[@]}"
# Keep the historical PT allele convention; its biological validation is separate.
if [[ "$model_train" == PT ]]; then
  for stem in P0.001 P0.05; do
    [[ -s "$path_output/$stem.txt" ]] || { echo 'Missing PT weight output' >&2; exit 1; }
    {
      printf 'CHROM\tPOS\tREF\tALT\tTargetID\tES\n'
      awk -F'\t' -v OFS='\t' 'NR>1{print $1,$2,$4,$3,$5,$6}' "$path_output/$stem.txt" | LC_ALL=C sort -k1,1n -k2,2n
    } | bgzip -@ "$nthreads" > "$path_output/$stem.tigar.txt.gz"
    tabix -f -s1 -b2 -e2 -S1 "$path_output/$stem.tigar.txt.gz"
  done
else
  [[ -s "$path_output/$model_train.txt" ]] || { echo 'Missing selected model weight output' >&2; exit 1; }
fi
