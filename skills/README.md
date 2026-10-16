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
| `mysql-charms-source` | Navigating the canonical/mysql-operators source: monorepo layout (`mysql` vs `mysql-k8s`), fetching the source for a deployed revision, grep cookbook for tracing errors to call sites and tests, charm config vs mysqld configuration. | No |

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

- "How do I run this juju command correctly / why did juju behave that
  way" -> `juju-cli`
- "Where is this in the charm source / what does this config option
  actually mean" -> `mysql-charms-source`

## Development

Skills are validated against the Agent Skills specification with
`skills-ref` (https://github.com/agentskills/agentskills/tree/main/skills-ref):

```bash
# install: pipx install skills-ref  (or: uv tool install skills-ref)

# validate a single skill
skills-ref validate skills/mysql-charms-source

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
