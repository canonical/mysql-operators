---
name: version-control
description: Repo-specific branch and commit-message conventions for backports. Used by bpilot to name backport branches and to validate commit message style when porting.
---
## Branch Conventions

- Active development branch: `8.4/edge`
- Release branches: `8.4/edge`, `8.0/edge`, `edge`
- Backport branch naming convention: `<short-hash>-to-<target-branch>` (e.g. `29c7f0fdd-to-8.0-edge`, `e1f560051-to-8.0-edge`)
- Feature/fix branch naming convention: `feat/<description>`, `fix/<description>`, `misc/<description>` (optionally prefixed with a user or tool name, e.g. `juanlu/8.4/fix/...`, `copilot/...`, `dependabot/...`, `renovate/...`)

## Commit Conventions

- Commit messages use a bracketed prefix followed by a description, e.g. `[MISC] Single kernel fixes (III) (#584)`
- Ticket prefix uses the `DPE-<number>` JIRA project code, e.g. `[DPE-9811] Single-kernel VM (#544)`
- Other known prefixes: `[MISC]` for miscellaneous changes, `[DOC]` for documentation changes
- Pull-request references are appended in parentheses at the end of the subject, e.g. `(#549)`
- Some commits (e.g. dependency updates) omit the bracketed prefix and use a free-form description with a PR reference
- No sign-off requirement is evident from the commit subjects
- Body/footer conventions: <!-- human to fill in if there are required trailers -->
