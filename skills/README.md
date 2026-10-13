# Charmed MySQL agent skills

A collection of Agent Skills (https://agentskills.io/specification) for
debugging and diagnosing problems with Charmed MySQL, based on
https://github.com/canonical/mysql-operators (the `mysql` VM charm and the
`mysql-k8s` Kubernetes charm). The knowledge is distilled from real
debugging case studies.

## Skills

| Skill | Use it for | Needs live access |
|---|---|---|
| `juju-cli` | Getting the Juju CLI itself right: deploy with trust, `juju ssh/exec` into the right k8s container, charm actions vs shell commands and their client-side wait timeouts, config-key discovery, destroy-model with storage, controller/model confusion, leftover background status samplers. | Yes |
| `mysql-operators-source` | Navigating the canonical/mysql-operators source: monorepo layout (`mysql` vs `mysql-k8s`), fetching the source for a deployed revision, grep cookbook for tracing errors to call sites and tests, charm config vs mysqld configuration. | No |
| `charmed-mysql-juju-inspect` | Diagnosing Charmed MySQL failures both ways. Live: interrogating a misbehaving deployment through Juju — reading `juju status` correctly (app vs unit, agent vs workload), cluster truth via actions, containers/ports/pebble topology, credentials, logs, direct SQL. Offline: static diagnosis from logs, Test Observer bundles, juju crashdumps, `db-dump.yaml`, pasted tracebacks, or issue reports — fingerprints versions, reconstructs hook timelines, maps evidence to source code, classifies the failure via a taxonomy, judges whether a reported regression is credible (git archaeology). Includes a script to parse Juju uniter operation lifecycles. | Both (live or offline) |
| `charmed-mysql-nightly-triage` | Triaging failed CI: nightly runs, PR integration failures, Test Observer executions. Classifies failures (deterministic bug / flake / infra / test-plan bug), exonerates innocent PRs, produces structured summaries. | No |
| `charmed-mysql-fault-injection` | Reproducing failures on a live deployment: the member-death / quorum-loss kill taxonomy, Group Replication guardrails, deterministic repro of race-conditional bugs, model and experiment hygiene (works on a scratch model it owns and tears down). | Yes |

Each skill directory contains a `SKILL.md` (workflow + gotchas) and
`references/` with the detailed material, loaded on demand.

## Installation

### Using the `skills` CLI (all agents)

The `skills` CLI (https://github.com/vercel-labs/skills) installs into any
supported agent — including Pi, OpenCode, Claude Code, Codex, and Cursor —
as symlinks to a canonical copy, and can update them later:

```bash
npx skills add canonical/mysql-operators -g        # global install, interactive
npx skills add canonical/mysql-operators -a pi -g --skill '*' -y   # non-interactive, Pi only
npx skills update                                  # update installed skills
```

`-g` installs globally (for Pi: `~/.agents/skills/`, which Pi reads
natively); without `-g` it installs project-locally (`.agents/skills/`).
To inspect a local checkout instead of the GitHub repo:
`npx skills add ./skills --list`.

### Manually

Clone this repository and point your agent at the `skills/` directory,
or copy the individual skill directories into the location your harness discovers.
Prefer symlinks where the harness supports them:
they track `git pull` automatically, while copied directories must be re-copied after every update.

## Which skill to reach for

- "I have a pile of logs / a crashdump / an issue report and no access to
  the system" -> `charmed-mysql-log-autopsy`
- "A nightly run / PR check failed, what happened and is it real" ->
  `charmed-mysql-nightly-triage`
- "My deployment is blocked/waiting/degraded, help me look at it" ->
  `charmed-mysql-juju-inspect`
- "Reproduce this bug / simulate quorum loss / test the recovery path" ->
  `charmed-mysql-fault-injection`
- "How do I run this juju command correctly / why did juju behave that
  way" -> `juju-cli`
- "Where is this in the charm source / what does this config option
  actually mean" -> `mysql-operators-source`

The skills are independent; combining them is common (e.g. triage a CI
failure with `charmed-mysql-nightly-triage`, then go deep with
`charmed-mysql-log-autopsy`).

## Development

Skills are validated against the Agent Skills specification with
`skills-ref` (https://github.com/agentskills/agentskills/tree/main/skills-ref):

```bash
# install: pipx install skills-ref  (or: uv tool install skills-ref)

# validate a single skill
skills-ref validate skills/charmed-mysql-log-autopsy

# validate all skills
for s in skills/*/; do skills-ref validate "$s"; done
```

Checks: frontmatter correctness, name rules (lowercase, hyphens, 64 chars
max, matches the directory), description under 1024 characters.

When editing skills, keep in mind:

- `SKILL.md` bodies should stay under 500 lines (they load fully into the
  agent context when triggered); push detail into `references/`.
- Descriptions carry the entire triggering burden; phrase them as "use
  when..." and cover both explicit and implicit phrasings of the task.
- The bundled script (`charmed-mysql-log-autopsy/scripts/parse_uniter_ops.py`)
  has no external dependencies and is smoke-tested against synthetic logs;
  run `python3 skills/charmed-mysql-log-autopsy/scripts/parse_uniter_ops.py --help`
  after changing it.
