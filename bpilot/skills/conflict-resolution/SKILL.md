---
name: conflict-resolution
description: Known branch divergences and project-specific rules for resolving cherry-pick conflicts. Used by bpilot's resolver when a port produces a conflict.
---
## Skip Files
<!-- Glob patterns to skip during conflict resolution (target version taken instead). -->
- poetry.lock
- *.lock
- package-lock.json
- Cargo.lock
- go.sum

## Merge Conflict Resolution Rules
<!-- Project-specific guidance the LLM should follow when resolving conflicts. -->
