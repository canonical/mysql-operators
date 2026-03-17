---
myst:
  html_meta:
    description: "Overview of Charmed MySQL cluster-to-cluster async replication (ClusterSet) for disaster recovery, with links to deploy, failover, and recovery guides."
---

(cluster-cluster-replication)=
# Cluster-cluster replication

```{admonition} This feature requires Juju 3
:class: warning

The feature described in this section is **not** available on Juju 2.9.
```

Cluster-cluster asynchronous replication focuses on disaster recovery by distributing data across different servers.

For increased safety, it is recommended to deploy each cluster in a different geographical region.

## Substrate dependencies

The following table shows the source and target controller/model combinations that are currently supported:

|       |     AWS    |     GCP    |    Azure   |
|-------|------------|:----------:|:----------:|
| AWS   | ![ check ] |            |            |
| GCP   |            | ![ check ] |            |
| Azure |            |            | ![ check ] |

## Guides

```{toctree}
:titlesonly:
:maxdepth: 2

Deploy <deploy>
Clients <clients>
Switchover/failover <switchover-failover>
Recovery <recovery>
Removal <removal>
```

[check]: https://img.shields.io/badge/%E2%9C%93-brightgreen