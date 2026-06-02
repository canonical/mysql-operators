# mysql-operators artifact patterns

## Integration workflow artifacts

From `.github/workflows/integration_test.yaml`:

- `allure-default-results-integration-test-<path>`
- `allure-results-integration-test-<path>-<name_in_artifact>`
- `logs-integration-test-<path>-<name_in_artifact>`

`<path>` is usually `kubernetes` or `machines`.

`<name_in_artifact>` comes from the spread job and is built from:
- test file name
- spread variant
- architecture

Example shape:
- `test_storage.py-juju36-amd64`

## What the log bundle usually contains

The uploaded logs directory may include:
- `juju-status.txt`
- `juju-debug-log.txt`
- `juju-debug-log-controller.txt`
- `jhack-tail.txt`

Use the artifact names to map a failing integration check back to its uploaded diagnostics.
