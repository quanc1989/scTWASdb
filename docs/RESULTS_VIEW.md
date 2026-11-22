# Saved-task regional association view

## Open the saved example

Initialize and run the read-only example using the commands in the main README, then open:

~~~text
http://127.0.0.1:8000/detail?key=5&data=00000000000000000000000000000001&chrom=chr22&thres_twas=0.05
~~~

The included result has 78 gene records and 156 method positions. At nominal P ≤ 0.05, each method has 78 valid genes and five hits; the threshold-selected table and TSV contain ten gene–method rows. With thres_twas=1e-5, each method retains 78 plotted background genes, the selected table/download has zero rows, and the all-valid-results download retains 156 rows. The example is a replay of the saved file, not a new analysis.

## Read and interact

The x-axis uses the midpoint of each recorded gene interval in Mb. The genome build and reference model come from the saved task parameters. The y-axis is −log10 of the stored nominal P value. Both coordinate ranges use the complete valid task output and stay fixed when switching method or threshold.

Grey open points are valid background genes; method-coloured filled points meet the selected nominal threshold. One gene with the lowest P is labelled. A threshold outside the y range is labelled at the plot edge without expanding the axis. A stored P of zero is retained as zero and shown with an upper-edge triangle rather than an invented finite probability.

Select or keyboard-activate a point to read its interval, Z, nominal P and SNP count. A hit offers **View table row**, which locates its method-specific row and changes page when necessary. Background selection leaves the threshold-filtered table unchanged.

**Download threshold-selected TSV** and **Download all valid results TSV** have different scopes. Both retain the saved statistics' text precision. **Export SVG** includes the displayed range, method, model and genome context. These operations read the existing result; they do not submit a job.

The compact view supports narrow screens and keyboard navigation. Nominal-threshold markers are not multiple-testing-adjusted discoveries or evidence of cell-specific causality.

## Component scope

| Included component | Source version |
|---|---|
| Saved-task handler, template and regional-view controller | 20261121-01 / 0f6201fec7f0d40d80f0de16223794bdbe059bf4 |
| Shared SVG renderer and stylesheet/bundle files | Same 20261121-01 source snapshot |
| Base catalogue, Explore and precomputed-association interfaces | Parent Web 20261118-01 / 232c8f241a2fe0765a4db230a2a6ceea953d22bd |
| Association-export queue, RPC and scientific wrappers | Parent component 20260918-02 / cf434e42c111098a1e6a75fe851a482e640c8cf5 |
| Standalone settings, read-only middleware and explicit resource configuration | Retained public-parent portability adapters |

The seven result-view/shared files listed in RELEASE.json reproduce the corresponding production source bytes. The regional renderer uses the retained ScEvidence.finite and ScEvidence.pState helpers; these functions match the production versions. The shared module also contains paired-rendering helpers. The existing Explore workflow remains the parent paged workflow; the hosted site's complete-gene paired Explore workflow and its extra server endpoints are outside this source update.

The examples/ and numerical/ trees, scientific scripts, requirements and third-party license texts are unchanged from public parent fb0948a49a0843b99ba8b785d90e5b926b522124. Full association databases, model weights and LD resources remain operator-supplied as described in the installation and scientific-dependency documents.
