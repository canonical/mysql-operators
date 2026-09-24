# Test Observer API — invocation patterns and endpoints

Reference for `charmed-mysql-nightly-triage` steps 1–2.

## Hosts and auth (the red herrings first)

- **API base**: `https://test-observer-api.canonical.com` — bearer token in
  `$TO_TOKEN`.
- The frontend host `test-observer.canonical.com` 503s for API paths and
  `/api/v1/...` on either host returns the Flutter HTML shell — both are
  red herrings. The real API paths are `/v1/...` on the `-api` host.
- The OpenAPI spec has **no servers** defined, so every specli invocation
  needs `--server` explicitly.
- Occasional intermittent 503s: retry, or use plain `curl` with the same
  bearer token — fine for GETs.

## specli invocation pattern

```bash
SPEC=~/Projects/Canonical/test_observer/backend/schemata/openapi.json
export PATH="$HOME/.local/share/nvm/v24.13.0/bin:$PATH"   # npx needs nvm

npx specli exec $SPEC __schema                                  # resource list
npx specli exec $SPEC <resource> --help                         # CLI action names (NOT operationIds)
npx specli exec $SPEC --bearer-token "$TO_TOKEN" \
  --server https://test-observer-api.canonical.com \
  artefacts get-v1-artefact-id-get <artefact-id>
npx specli exec $SPEC ... test-executions get-v1-id-get <exec-id>
npx specli exec $SPEC ... test-executions get-test-results-v1-id-test-results-get <exec-id>
```

Gotcha: operationIds like `get_test_execution_v1_test_executions__id__get`
are **not** the CLI commands — use the derived names from
`<resource> --help` (e.g. `get-v1-id-get`).

## curl fallback (GETs)

```bash
curl -sSL -H "Authorization: Bearer $TO_TOKEN" \
  https://test-observer-api.canonical.com/v1/test-executions/<exec-id> | jq .
```

## What each endpoint gives you

### `get_test_execution` (execution details)

- `ci_link` — the GitHub Actions run.
- `relevant_links[]` — `url` points at the logs bundle index
  (`https://charm.logs.test-observer.canonical.com/production/<exec-id>/index.html`),
  a file listing with `junit.xml` and a `juju-controller-*.tar.gz`
  juju-crashdump; download siblings directly, e.g.:

```bash
curl -sSL -O .../production/<exec-id>/juju-controller-*.tar.gz
tar -xzf juju-controller-*.tar.gz -C to-<exec-id>
```

- `execution_metadata` — flat map including:
  - `charm_qa:failure:charm:<app>:status` — the failing unit/app status;
    often names the failing hook before any log is opened.
  - `charm_qa:juju:version` (e.g. `3.6.20-genericlinux-amd64`).
  - Environment name encoding channel + base
    (`juju:3/stable ubuntu:22.04 kubernetes`).
  Check these before attributing behavior differences to code.

### Test results

- `io_log` — captured pytest output (the failure signal when you don't
  want the full bundle).
- `previous_results` — cross-revision history: which revisions passed or
  failed before. A failure at exactly one revision with clean neighbors is
  a regression candidate; the same signature across many revisions is
  structural or environmental.
- Result-level metadata (test name, duration, outcome).

## From issue links to IDs

A frontend URL like
`https://test-observer.canonical.com/artefact/<id>/execution/<exec-id>`
maps directly to artefact ID and execution ID for the API. The execution
ID is also the logs-bundle path segment on
`charm.logs.test-observer.canonical.com/production/<exec-id>/`.

## Environment fingerprinting checklist

Before comparing runs or attributing a failure to a revision, record:

- Charm name + revision(s) + channel (from execution metadata and bundle's
  `juju-status.txt`).
- Juju version (`charm_qa:juju:version`), k8s client/server versions
  (`kubernetes-version.txt` in the bundle), MySQL version (embedded in
  `get-cluster-status` payloads or workload logs).
- Base/architecture from the execution environment name.
- Whether the model may contain *mixed* revisions (leftover deployments
  from prior experiments) — verify per app in `juju-status.txt`.
