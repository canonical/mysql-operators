# mysql-operators failure signals

## Lint and unit jobs

These usually fail with direct command output from:
- `tox run -e lint`
- `tox run -e lint-terraform`
- `tox run -e unit`

Treat these as code or test failures unless the log clearly shows package installation or runner issues.

## Build jobs

Build jobs use the reusable workflow `build_charm.yaml`.

Typical signals:
- charmcraft or packaging errors
- missing files
- build environment setup errors

## Integration jobs

Integration jobs come from `.github/workflows/integration_test.yaml`.

Key shared setup steps:
- free disk space
- install mysql client, charmcraft, and go
- download packed charms
- download the test database
- run spread

Shared failure indicators:
- package or snap install failures
- disk exhaustion
- spread setup failures before tests start
- Juju or LXD environment issues

When spread runs and later diagnostics execute, inspect:
- `juju status`
- `juju debug-log`
- `juju debug-log controller`
- `jhack tail`

If many matrix jobs fail in the same run with similar early-step errors, treat it as an infrastructure or workflow issue first.
