# Source changes

## 20261121.1

- Add the saved-task regional association view from hosted Web release 20261121-01: all valid genes, method selection, nominal-threshold markers, point details and navigation to the corresponding filtered table row.
- Share coordinate ranges across methods and thresholds; mark an off-scale threshold at the plot edge and retain stored zero P values as upper-edge markers.
- Add SVG export with model and genome-build context, and a separate all-valid-results TSV alongside the threshold-selected download.
- Include the matching shared SVG module and styles. The existing catalogue and Explore workflow, association-export queue and scientific wrappers retain their parent component versions.
- Retain the standalone configuration, read-only example initializer, input examples, saved numerical material, MIT license and third-party notices.

Component identifiers and file scope are listed in RELEASE.json and docs/RESULTS_VIEW.md. This update changes presentation and saved-file access; it does not regenerate association statistics or prediction models.
