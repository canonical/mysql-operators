---
myst:
  html_meta:
    description: "How-to guides for Charmed MySQL covering deployment, backup and restore, monitoring, upgrades, charm development, and cluster replication."
---

(how-to)=
# How-to guides

Key processes and common tasks for deploying, configuring, and operating Charmed MySQL.

## Deployment and setup

Available deployment methods, clouds, and specialised setups:

```{toctree}
:titlesonly:
:maxdepth: 2

Deploy MySQL <deploy/index>
```

## Operations and maintenance

Essential operations to configure and manage a MySQL cluster:

```{toctree}
:titlesonly:
:maxdepth: 2

Integrate with applications <integrate-with-applications>
Scale your cluster <scale>
Manage passwords <manage-passwords>
```

Networking and encryption:

```{toctree}
:titlesonly:
:maxdepth: 2

Enable TLS <enable-tls>
External network access <external-network-access>
```

Disaster recovery:

```{toctree}
:titlesonly:
:maxdepth: 2

Primary switchover <primary-switchover>
```

```{seealso}
For more on high availability and disaster recovery, refer to

* {ref}`cluster-cluster-replication`
* {ref}`troubleshooting`
```

## Back up and restore

Configure storage providers and backup management for safety and data migration:

```{toctree}
:titlesonly:
:maxdepth: 2

Back up and restore <back-up-and-restore/index>
```

## Monitoring (COS)

Set up observability services like Grafana, Prometheus, Loki, and Tempo through the Canonical Observability Stack (COS):

```{toctree}
:titlesonly:
:maxdepth: 2

Monitoring (COS) <monitoring/index>
```

## Refresh (upgrade)

Instructions for performing an in-place refresh for one or multiple clusters:

```{toctree}
:titlesonly:
:maxdepth: 2

Refresh (upgrade) <refresh/index>
```

## Cluster-cluster replication

Walkthrough of a highly available cluster-cluster deployment and its primary operations:

```{toctree}
:titlesonly:
:maxdepth: 2

Cluster-cluster replication <cluster-cluster-replication/index>
```

## Charm development

Information about interfaces and data migration method for developers looking to support MySQL integrations with their application:

```{toctree}
:titlesonly:
:maxdepth: 2

Charm development <charm-development/index>
```

```{toctree}
:titlesonly:
:hidden:

Contribute <contribute>
```