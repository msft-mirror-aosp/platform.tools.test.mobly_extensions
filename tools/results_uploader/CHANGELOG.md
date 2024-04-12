# Mobly Results Uploader release history

## 0.3 (2024-04-10)

### Fixes
* Fall back to manual GCS upload (via web page) if the automated upload fails.
* Clean up console output.


## 0.2 (2024-03-28)

### Fixes
* Properly URL-encode the target resource name.
* Report targets with all skipped test cases as `skipped`.
* Update Resultstore UI link from source.cloud to BTX.
* Suppress warnings from imported modules.


## 0.1 (2024-01-05)

### New

* Add the `results_uploader` tool for uploading Mobly test results to the
  Resultstore service.
  * Uploads local test logs to a user-provided Google Cloud Storage location.
  * Creates a new test invocation record via Resultstore API.
  * Generates a web link to visualize results.
