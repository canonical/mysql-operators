# Version archaeology — pinning artifacts to code

Reference for `charmed-mysql-log-autopsy` step 6. Every "which code was
running?" question is answerable from git + Charmhub metadata without
building anything.

## Charmhub revisions ↔ git tags

The monorepo tags every published revision: `mysql-k8s/revNNN`,
`mysql/revNNN`, `mysql-router-k8s/revNNN`, ...

```bash
git tag | grep "mysql-k8s/rev"            # list
git diff --stat mysql-k8s/rev422..mysql-k8s/rev423   # what changed between revs
git merge-base --is-ancestor <commit> <tag>          # is this fix in that rev?
git tag --contains <commit>              # first rev carrying a commit
git show mysql-k8s/rev423:kubernetes/src/charm.py   # read deployed source
```

- **Consecutive revision numbers are frequently the same code promoted
  per-architecture** (e.g. 747=arm64, 748=amd64), or adjacent
  arch/channel pairs — not necessarily feature revisions. Check
  `manifest.yaml` inside the `.charm` (arch lives only there):
  `juju download <charm> --revision NNN` then
  `unzip -p <file>.charm manifest.yaml | grep -A2 architectures`.
- **Revision publish dates vs commit merge dates** answer "is this fix in
  my deployment?" — find the rev's date on Charmhub, compare with
  `git log --format="%h %ci %s"`.
- Charm **libs** may be git-tracked (identical tags ⇒ identical libs) or
  `charmcraft fetch-lib`-ed at build time (identical history can still
  yield different built charms). When in doubt, diff the built artifacts:
  download both revs, unzip, diff `lib/`.

## Reading the right branch

- The 8.0 and 8.4 lines diverge: lib files were refactored, databag keys
  renamed (e.g. `endpoint`→`instance-address`, `node-label`→`instance-label`,
  `mysql-version`→`cluster-version`, readiness flag moved between databags).
  **Grep/read `git show origin/<branch>:<path>` for the branch matching the
  deployed revision**, not your checkout.
- Shared libs (`lib/charms/mysql/v0/*.py`, and the router's `common/`)
  exist as byte-identical copies under `kubernetes/` and `machines/`.
  `diff` them before/after editing; a fix or analysis must cover both.
- `git log -S '<literal>' --all` (pickaxe) over **both old and new paths**:
  package/dir moves (e.g. `src/relations/...` → `common/common/relations/...`
  → monorepo split) silently hide half the history from single-path
  searches. Add `-- <path>` variants for each historical location, or omit
  the path filter when unsure.

## Locating deployed code from a traceback

- Deployed tracebacks reference the **deployed** source; line numbers drift
  from your checkout. Correlate by **line content** (the statement text),
  then find its current/branch location.
- Verify fix-presence by reading the branch, e.g.:

```bash
git show origin/8.4/edge:kubernetes/lib/charms/mysql/v0/mysql.py | sed -n '600,625p'
```

- Check what changed around an area with commit messages — canonical
  `[DPE-xxxx]` messages are descriptive; `git log --oneline <branch> -- <path>`
  gives a readable history of the file.

## Pinning the ops version from a revision

When only the charm revision is known (no logs with the version line):

```bash
git log --format="%h %ci %s" origin/<branch> -- kubernetes/poetry.lock | head
# last lock update before the revision's build date:
git show <commit>:kubernetes/poetry.lock | grep -A2 'name = "ops"'
```

Then verify claimed ops behavior against that exact tag (e.g. in an ops
checkout: `git show 2.23.1:ops/model.py | grep -n "__delitem__" -A3`).
In logs, the runtime marker is `ops <version> up and running.` (one line
per hook process).

## Searching dependency code

Charm ERROR strings may originate in dependency packages, not the repo:

- `mysql_shell` library (vendored under the charm's venv as
  site-packages) logs e.g. `Failed to fetch cluster status` from
  `mysql_shell/clients/cluster.py`.
- `charms.data_platform_libs.v0.data_interfaces` (bundled under `lib/`)
  implements the diff-snapshot mechanics that drive `database_requested`
  re-emission.
- Search order when a log line has no repo hit: repo → bundled `lib/` →
  venv/site-packages of the matching charm revision (or its
  `requirements.txt`/lock file for versions).

## Issue-report premise checks (cheap before expensive)

1. **"Regression in rev X"** → `git diff --stat <revA>..<revB>` on the
   relevant files; if bit-identical, the premise is dead. Deploy-published
   revisions A/B (~4 min each) refutes whole bisect plans without building.
2. **"Wasn't this fixed by PR N?"** → read the **diff**, not the title
   (`gh pr diff N --repo canonical/mysql-operators`); titles routinely
   describe adjacent work.
3. **"Only affects new versions"** → check `git log -S` for when the
   *sender* started writing a field vs when the *receiver* started
   rejecting it — for relation incompatibilities, the bug window is the
   intersection of the two answers, and either search alone misleads.
4. **Latent-surfacing attribution**: when a bug surfaces alongside a test
   -plan or promotion change, the trigger may live in a *different* repo
   (e.g. `canonical/charm-integration-testing`) — check its history too
   before blaming the charm.
