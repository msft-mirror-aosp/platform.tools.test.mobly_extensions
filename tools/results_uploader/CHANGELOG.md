# Mobly Results Uploader release history

## 0.1

### New

* Add the `results_uploader` tool for uploading Mobly test results to the
  Resultstore service.
  * Uploads local test logs to a user-provided Google Cloud Storage location.
  * Creates a new test invocation record via Resultstore API.
  * Generates a web link to visualize results.
