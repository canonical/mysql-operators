---
myst:
  html_meta:
    description: "Overview of in-place charm upgrades for Charmed MySQL using juju refresh, with upgrade paths for VM and K8s single and multi-cluster deployments."
---

(refresh)=
# Refresh (upgrade)

This charm supports in-place upgrades to higher versions via Juju's [`refresh`](https://documentation.ubuntu.com/juju/3.6/reference/juju-cli/list-of-juju-cli-commands/refresh/#details) command.

## Supported refreshes

`````{tab-set}
````{tab-item} VM
:sync: vm

```{eval-rst}
+------------+------------+----------+------------+
| From                    | To                    |
+------------+------------+----------+------------+
| Charm      | MySQL      | Charm    | MySQL      |
| revision   | Version    | revision | Version    |
+============+============+==========+============+
|            |            |          |            |
+------------+------------+----------+------------+
```

````

````{tab-item} K8s
:sync: k8s

```{eval-rst}
+------------+------------+----------+------------+
| From                    | To                    |
+------------+------------+----------+------------+
| Charm      | MySQL      | Charm    | MySQL      |
| revision   | Version    | revision | Version    |
+============+============+==========+============+
|            |            |          |            |
+------------+------------+----------+------------+

```
````
`````

To upgrade from MySQL 8.0, the data must be migrated manually. See: {ref}`migrate-a-cluster`.

### Juju version upgrade

Before refreshing the charm, make sure to check the {ref}`release-notes` page to see if there any requirements for the new revision, such as a Juju version upgrade.

```{toctree}
:titlesonly:
:maxdepth: 2

Upgrade Juju <upgrade-juju>
```

## Refresh guides

To refresh a **single cluster**, see:

```{toctree}
:titlesonly:
:maxdepth: 2

Single cluster <single-cluster/index>
```

To refresh a **multi-cluster** deployment, see:

```{toctree}
:titlesonly:
:maxdepth: 2

Multi-cluster <multi-cluster/index>
```