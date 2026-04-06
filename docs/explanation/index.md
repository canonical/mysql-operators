---
myst:
  html_meta:
    description: "Conceptual documentation for Charmed MySQL covering architecture, Juju integration, users, roles, logs, security, and key interfaces."
---

(explanation)=
# Explanation

Additional context about key concepts behind the MySQL charm.

## Core concepts and design

Key concepts about the history and high-level design of Charmed MySQL, including information about the legacy InnoDB charm. 

```{toctree}
:titlesonly:
:maxdepth: 2

Architecture <architecture>
Interfaces and endpoints <interfaces-and-endpoints>
Juju <juju>
Legacy charm <legacy-charm>
```

## Operation

Clarification of standard MySQL operational concepts in the context of charms and Juju:

```{toctree}
:titlesonly:
:maxdepth: 2

Users <users>
Roles <roles>
Logs <logs/index>
```

## Security

Overview of security features in the charm and hardening guidance:

```{toctree}
:titlesonly:
:maxdepth: 2

Security <security/index>
```

## Development

Mermaid diagrams of charm events and hooks.

```{toctree}
:titlesonly:
:maxdepth: 2

Charm flowcharts <flowcharts>
```
