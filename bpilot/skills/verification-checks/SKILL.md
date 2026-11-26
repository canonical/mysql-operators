---
name: verification-checks
description: Format, lint, and unit-test commands to run after a backport. Used by bpilot to verify a ported change and to drive the LLM repair loop on failure.
---
## Format Commands
- `cd kubernetes && tox run -e format`
- `cd machines && tox run -e format`

## Verification Checks
- Lint: `cd kubernetes && tox run -e lint`
- Lint: `cd machines && tox run -e lint`
- Tests: `cd kubernetes && tox run -e unit`
- Tests: `cd machines && tox run -e unit`

## Test Commands
- `cd kubernetes && tox run -e unit`
- `cd machines && tox run -e unit`
