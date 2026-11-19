# Captured-operand numerical comparison

This material contains 198 captured operand groups and 396 method positions for three traits and four references on chromosome 22. It compares the implemented statistics with independent base-R formulas on the same saved inputs.

matrix-index.csv maps every group to a vector table and covariance matrix in operands/. The 396 operand files contain the saved vectors and covariance matrices. Covariance files contain row-major little-endian float64 values. Each vector table determines its matrix dimension. The vectors contain weights, aligned GWAS Z and SNP standard deviations.

formula-comparison.csv records every method position. All 384 finite Z comparisons met the recorded tolerance 2e-5 + 1e-5 × abs(Z_R). Twelve positions were unavailable in both implementations and remain in the table. Saved independent results are in matrix-r.csv. Input design and recorded outcome counts are in design.json.

The original independent_pilot.R implements scalar tails, input checks and matrix formulas. Its matrix mode runs from this directory with base R 4.3.3 and a new output path:

~~~bash
Rscript --vanilla independent_pilot.R matrix matrix-index.csv new-results.csv
~~~

The script writes the computed comparison to a new output file and refuses to overwrite an existing file. It evaluates the saved operands listed in matrix-index.csv.

The saved comparison measures formula agreement on these fixed inputs using the stated tolerance. Prediction accuracy and LD population calibration require separate evaluation. Diagnostic groups retain non-finite weights, and all recorded method outcomes are included.
