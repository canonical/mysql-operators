---
name: mysql-operators-source
description: >
  Navigates the canonical/mysql-operators charm source: monorepo layout
  (mysql = machines/, mysql-k8s = kubernetes/, shared
  lib/charms/mysql/v0/), Charmhub revision to git tag mapping, and reading
  the source of a deployed revision without checking it out. Use when the
  charm code behind a behavior, traceback, or log message is needed, or
  when comparing Charmhub revisions.
license: Apache-2.0
metadata:
  author: canonical-data-platform
  version: "0.4.0"
  upstream-repo: canonical/mysql-operators
---

# mysql-operators source navigation

## Overview

How to get from "I need to see the charm code that produced this" to the
right file, at the right revision, without wasted detours. Read this once,
then use [version-archaeology.md](references/version-archaeology.md) for
the revision/tag deep-dives. Pairs naturally with the
`charmed-mysql-log-autopsy` skill (evidence → source mapping) and the
`charmed-mysql-juju-inspect` skill (live evidence gathering).

## Monorepo layout

The monorepo `canonical/mysql-operators` builds **two charms**, not two
directories named after the charms:

- `mysql` — the VM charm: source in `machines/`, ships the snap
  `charmed-mysql`.
- `mysql-k8s` — the K8s charm: source in `kubernetes/`, ships as a ROCK
  supervised by Pebble.

Shared code lives under each charm's `lib/charms/mysql/v0/`
(`kubernetes/lib/charms/mysql/v0/` and the machines twin) — notably
`mysql.py` (InnoDB Cluster/ClusterSet control via mysqlsh), `backups.py`,
`async_replication.py`, `tls.py`. The two copies are kept byte-identical;
a fix usually must touch both. The `kubernetes/` and `machines/` charm
sources themselves may diverge freely — check the branch that matches the
deployed revision.

## Getting the source for a deployed revision

Charmhub revisions map to git tags in the monorepo. Clone only the tag you
need — shallow (seconds, ~9 MB; a full clone is minutes and ~142 MB):

```bash
git clone --quiet --depth 1 --branch mysql-k8s/rev423 \
  https://github.com/canonical/mysql-operators.git
cd mysql-operators
git show HEAD:kubernetes/src/charm.py        # read deployed source
```

Add a comparison revision to the same clone (seconds each):

```bash
git fetch --depth 1 origin tag mysql-k8s/rev426
git diff --stat mysql-k8s/rev423 mysql-k8s/rev426
```

For history-wide searches (`git log -S` pickaxe, blame across revisions),
use a blobless partial clone instead — full history, blobs on demand:

```bash
git clone --quiet --filter=blob:none --no-checkout \
  https://github.com/canonical/mysql-operators.git
git checkout mysql-k8s/rev423
```

Blobs download lazily: `git show` and point diffs are cheap; one broad
pickaxe over all history pulls many blobs (~1 min, cached afterwards).
A shallow single-tag clone has no branch tips — `git fetch --depth 1
origin <branch>` before reading `origin/<branch>:<path>`.

**Do not also download the built charm.** `juju download mysql-k8s
--revision 423` + unzip yields the same source the clone already has —
it is redundant whenever a clone is available. It is the fallback ONLY
when GitHub is unreachable (restricted egress, auth failure):

```bash
juju download mysql-k8s --revision 423
unzip -p ./mysql-k8s.charm manifest.yaml | grep -A2 architectures
unzip -p ./mysql-k8s.charm src/charm.py                  # source inside
```

`unzip` (not `tar`) — `.charm` files are zip archives. Architecture lives
only in `manifest.yaml` — the one build-level fact git cannot tell you.

## Where things live: the grep cookbook

Charm errors and statuses are raised from a small, greppable surface:

1. Grep the **exact log/error message string** in the repo → the emitting
   class and call site.
2. Grep the same string in `tests/` → the unit tests asserting the
   behavior (they document intended semantics).
3. Consult `docs/reference/charm-statuses.md` — every status setter and
   its suppression paths are documented there.

Anchor tracebacks by **line content, not line number** — numbers drift
between the deployed revision and current branches.

## Config: what juju exposes vs what mysqld gets

`kubernetes/src/config.py` defines two similarly-named classes with
very different roles — confusing them leads to `juju config` calls on
keys that do not exist:

- **`CharmConfig`** (pydantic) — the ONLY keys juju accepts, exactly the
  options in `kubernetes/config.yaml`: `cluster-name`,
  `cluster-set-name`, `profile` (testing|production),
  `profile-limit-memory`, `mysql-interface-user`/`-database`,
  `mysql-root-interface-user`/`-database`, `plugin-audit-enabled`,
  `plugin-audit-strategy`, `binlog_retention_days`, `logs_audit_policy`,
  `logs_retention_period`, `experimental-max-connections`.
- **`MySQLConfig`** — NOT juju config. An internal helper over the
  *rendered mysqld configuration*: `static_config` is the set of mysqld
  variables whose change forces a mysqld restart (`innodb_buffer_pool_size`,
  `innodb_buffer_pool_chunk_size`, `group_replication_message_cache_size`,
  `log_error`, `report_host`, `loose-audit_log_strategy`,
  `loose-audit_log_format`); `custom_config()` parses the rendered
  `[mysqld]` file for change detection on config-changed.
- mysqld variables are **derived, not settable**: charm.py's
  `_write_mysqld_configuration()` calls
  `render_mysqld_configuration(profile, ..., memory_limit,
  experimental_max_connections, ...)` — you cannot
  `juju config mysql-k8s innodb_buffer_pool_size=...`; juju answers
  `unknown option` (discovery workflow in the `juju-cli` skill). Tune
  sizing via `profile` / `profile-limit-memory` instead.
- Restart tie-in: on config-changed the charm diffs the newly rendered
  config against the file on disk; any changed key intersecting
  `static_config` triggers a mysqld restart
  (`keys_requires_restart`). This is the restart path that races with
  scale events (see issue #511 analysis).

## References

- [references/version-archaeology.md](references/version-archaeology.md) —
  revision↔tag mapping in depth: pickaxe searches, branch selection,
  consecutive-revision arch/channel pairs, ops/library version pinning,
  publish-date vs merge-date reasoning, cheap A/B revision comparisons.
