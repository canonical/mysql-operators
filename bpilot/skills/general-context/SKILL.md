---
name: general-context
description: Shared repo context read by multiple bpilot tasks — lifecycle hooks, upgrade paths, files of interest, known branch divergences. Loaded alongside each task-specific skill.
---
## Lifecycle Hooks
<!-- e.g. install → start → config-changed; start calls workload_initialise. -->

## Upgrade Path
<!-- e.g. machine charm upgrades defer start; new "enable X by default" changes must also be added to _on_upgrade_granted. -->

## Known Divergences Between Branches
<!-- e.g. 8.4 workload_initialise has an is_data_dir_initialised() shortcut; 8.0 does not. -->

## Files of Interest
<!-- e.g. machines/src/charm.py — main charm logic. -->
