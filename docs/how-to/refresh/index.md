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
| 366, 367   | ``8.0.41`` |          |            |
+------------+------------+----------+------------+
| 312, 313   | ``8.0.39`` | 366, 367 | ``8.0.41`` |
+------------+------------+----------+------------+
| 240        | ``8.0.36`` | 366, 367 | ``8.0.41`` |
|            |            +----------+------------+
|            |            | 312, 313 | ``8.0.39`` |
+------------+------------+----------+------------+
| 196        | ``8.0.34`` | None     |            |
+------------+------------+----------+------------+
| 151        | ``8.0.32`` | 240      | ``8.0.36`` |
|            |            +----------+------------+
|            |            | 196      | ``8.0.34`` |
+------------+------------+----------+------------+
```

Due to an upstream issue with MySQL Server version `8.0.35`, Charmed MySQL versions below [Revision 240](https://github.com/canonical/mysql-operator/releases/tag/rev240) **cannot** be upgraded using Juju's `refresh`.

To upgrade from older versions to Revision 240 or higher, the data must be migrated manually. See: {ref}`migrate-a-cluster`.
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
| 254, 255   | ``8.0.41`` |          |            |
+------------+------------+----------+------------+
| 240, 241   | ``8.0.41`` | 254, 255 | ``8.0.41`` |
+------------+------------+----------+------------+
| 210, 211   | ``8.0.39`` | 254, 255 | ``8.0.41`` |
|            |            +----------+------------+
|            |            | 240, 241 | ``8.0.41`` |
+------------+------------+----------+------------+
| 180, 181   | ``8.0.37`` | 254, 255 | ``8.0.41`` |
|            |            +----------+------------+
|            |            | 240, 241 | ``8.0.41`` |
|            |            +----------+------------+
|            |            | 210, 211 | ``8.0.39`` |
+------------+------------+----------+------------+
| 153        | ``8.0.36`` | 254, 255 | ``8.0.41`` |
|            |            +----------+------------+
|            |            | 240, 241 | ``8.0.41`` |
|            |            +----------+------------+
|            |            | 210, 211 | ``8.0.39`` |
|            |            +----------+------------+
|            |            | 180, 181 | ``8.0.37`` |
+------------+------------+----------+------------+
| 127        | ``8.0.35`` | None     |            |
+------------+------------+----------+------------+
| 113        | ``8.0.34`` | 127      | ``8.0.35`` |
+------------+------------+----------+------------+
| 99         | ``8.0.34`` | 127      | ``8.0.35`` |
|            |            +----------+------------+
|            |            | 113      | ``8.0.35`` |
+------------+------------+----------+------------+
| 75         | ``8.0.32`` | 127      | ``8.0.35`` |
|            |            +----------+------------+
|            |            | 113      | ``8.0.35`` |
|            |            +----------+------------+
|            |            | 99       | ``8.0.34`` |
+------------+------------+----------+------------+
```

Due to an upstream issue with MySQL Server version `8.0.35`, Charmed MySQL versions below [Revision 127](https://github.com/canonical/mysql-k8s-operator/releases/tag/rev127) **cannot** be upgraded using Juju's `refresh`.

To upgrade from older versions to Revision 153 or higher, the data must be migrated manually. See: {ref}`migrate-a-cluster`.
````
`````

### Juju version upgrade

Before refreshing the charm, make sure to check the {ref}`releases` page to see if there any requirements for the new revision, such as a Juju version upgrade.

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