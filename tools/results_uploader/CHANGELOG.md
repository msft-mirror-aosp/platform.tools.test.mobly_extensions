# Mobly Results Uploader release history

## 0.2

### Fixes
* Properly URL-encode the target resource name.
* Report targets with all skipped test cases as `skipped`.
* Update Resultstore UI link from source.cloud to BTX.
* Suppress warnings from imported modules.


## 0.1

### New

* Add the `results_uploader` tool for uploading Mobly test results to the
  Resultstore service.
  * Uploads local test logs to a user-provided Google Cloud Storage location.
  * Creates a new test invocation record via Resultstore API.
  * Generates a web link to visualize results.
