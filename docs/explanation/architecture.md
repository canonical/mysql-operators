---
myst:
  html_meta:
    description: "Understand the architecture of Charmed MySQL for VM and Kubernetes deployments, built on the charmed-mysql snap and MySQL InnoDB ClusterSet."
---

(architecture)=
# Architecture

[MySQL](https://www.mysql.com/) is the world’s most popular open source database. Charmed MySQL is a Juju-based operator to deploy and support MySQL from [day 0 to day 2](https://codilime.com/blog/day-0-day-1-day-2-the-software-lifecycle-in-the-cloud-age/). It is based on the [MySQL Community Edition](https://www.mysql.com/products/community/) using the built-in cluster functionality: [MySQL InnoDB ClusterSet](https://dev.mysql.com/doc/mysql-shell/8.4/en/innodb-clusterset.html).

## High-level design

Charmed MySQL is developed for deployment on machine clouds or Kubernetes. Although both versions are extremely similar in functionality, there are some key differences in their architecture.

(machine-charm)=
### Machine charm

[Charmed MySQL VM](https://charmhub.io/mysql) leverages the [charmed-mysql snap](https://snapcraft.io/charmed-mysql) which is deployed by Juju on the specified VM/MAAS/bare-metal machine based on Ubuntu Noble/24.04. snap allows to run MySQL service(s) in a secure and isolated environment ([strict confinement](https://snapcraft.io/blog/demystifying-snap-confinement)). 

The installed snap:

```shell
$ juju ssh mysql/0
$ snap list charmed-mysql
Name           Version  Rev  Tracking       Publisher        Notes
charmed-mysql  8.4.7          latest/stable  dataplatformbot  held
```

The snap ships the following components:

* MySQL Community Edition 
* MySQL Router
* MySQL Shell (based on Canonical [backport](https://launchpad.net/~data-platform/+archive/ubuntu/mysql-shell-8.4))
* Percona XtraBackup (based on Canonical  [backport](https://launchpad.net/~data-platform/+archive/ubuntu/percona-xtrabackup-8.4))
* Prometheus MySQLd Exporter (based on Canonical [backport](https://launchpad.net/~data-platform/+archive/ubuntu/mysqld-exporter))
* Prometheus MySQL Router Exporter (based on Canonical [backport](https://launchpad.net/~data-platform/+archive/ubuntu/mysqlrouter-exporter))
* Prometheus Grafana dashboards and Loki alert rules are part of the charm revision and missing in snap.

Versions of all the components above are carefully chosen to fit functionality of each other.

The Charmed MySQL unit consisting of a several services which are enabled/activated accordingly to the setup: 

```shell
$ snap services charmed-mysql
Service                              Startup   Current   Notes
charmed-mysql.mysqld                 enabled   active    -
charmed-mysql.mysqld-exporter        disabled  inactive  -
charmed-mysql.mysqlrouter-service    disabled  inactive  -
charmed-mysql.mysqlrouterd-exporter  disabled  inactive  -
```

The `mysqld` snap service is a main MySQL instance which is normally up and running right after the charm deployment.

The `mysql-router` snap service used in [Charmed MySQL Router](https://charmhub.io/mysql-router?channel=8.4/edge) only and should be stopped on [Charmed MySQL](https://charmhub.io/mysql?channel=8.4/edge) deployments.

All `exporter` services are activated only after relating with {ref}`COS <enable-monitoring>`.

```{caution}
* It is possible to start, stop, and restart snap services manually but it is NOT recommended to avoid a split brain with a charm state machine! Do it with a caution!!!
* All snap resources must be executed under the special user `snapd_daemon` only!
```

The snap "charmed-mysql" also ships list of tools used by charm:
* `charmed-mysql.mysql` (alias `mysql`) - mysql client to connect `mysqld`.
* `charmed-mysql.mysqlsh` - new [mysql-shell](https://dev.mysql.com/doc/mysql-shell/8.4/en/) client to configure MySQL cluster.
* `charmed-mysql.xbcloud` - a tool to download and upload full or part of xbstream archive from/to the cloud.
* `charmed-mysql.xbstream` - a tool to support simultaneous compression and streaming.
* `charmed-mysql.xtrabackup` - a tool to backup/restore MySQL DB.

The `mysql` and `mysqlsh` are well known and popular tools to manage MySQL.
The `xtrabackup (xbcloud+xbstream)` used for [MySQL Backups](/how-to/back-up-and-restore/create-a-backup) only to store backups on S3 compatible storage.

### Kubernetes charm

[Charmed MySQL K8s](https://charmhub.io/mysql-k8s) leverages the [sidecar](https://kubernetes.io/blog/2015/06/the-distributed-system-toolkit-patterns/#example-1-sidecar-containers) pattern to allow multiple containers in each pod with [Pebble](https://juju.is/docs/sdk/pebble) running as the workload container’s entrypoint.

Pebble is a lightweight, API-driven process supervisor that is responsible for configuring processes to run in a container and controlling those processes throughout the workload lifecycle.

Pebble `services` are configured through [layers](https://github.com/canonical/pebble#layer-specification), and the following containers represent each one a layer forming the effective Pebble configuration, or `pebble plan`:

1. a charm container runs Juju operator code: `juju ssh mysql-k8s/0 bash`
1. a [mysql](https://www.mysql.com/) (workload) container runs the MySQL application along with other services (like monitoring metrics exporters, etc): `juju ssh --container mysql mysql-k8s/0 bash`

As a result, if you run a `kubectl get pods` on a namespace named for the Juju model you’ve deployed the "Charmed MySQL K8s" charm into, you’ll see something like the following:

```shell
NAME           READY   STATUS    RESTARTS   AGE
mysql-k8s-0    2/2     Running   0          65m
```

This shows there are 2 containers in the pod: `charm` and `workload` mentioned above.

And if you run `kubectl describe pod mysql-k8s-0`, all the containers will have as Command `/charm/bin/pebble`. That’s because Pebble is responsible for the processes startup as explained above.

The Charmed MySQL K8s (`workload` container) based on the `mysql-image` resource defined in the [charm metadata.yaml](https://github.com/canonical/mysql-operators/blob/8.4/edge/kubernetes/metadata.yaml). It is an official Canonical "[charmed-mysql](https://github.com/canonical/charmed-mysql-rock)" [OCI/ROCK](https://documentation.ubuntu.com/server/explanation/virtualisation/about-rock-images/) image, which is recursively based on Canonical SNAP “[charmed-mysql](https://snapcraft.io/charmed-mysql)” (read more about the snap details in {ref}`machine-charm`).

[Charmcraft](https://juju.is/docs/sdk/install-charmcraft) uploads an image as a [charm resource](https://charmhub.io/mysql-k8s/resources/mysql-image) to [Charmhub](https://charmhub.io/mysql-k8s) during the [publishing](https://github.com/canonical/mysql-k8s-operator/blob/main/.github/workflows/release.yaml#L40-L53), as described in the [Juju SDK How-to guides](https://juju.is/docs/sdk/publishing).

The charm supports Juju deployment to all Kubernetes environments: [MicroK8s](https://microk8s.io/), [Charmed Kubernetes](https://ubuntu.com/kubernetes/charmed-k8s), [GKE](https://charmhub.io/mysql-k8s/docs/h-deploy-gke), [Amazon EKS](https://aws.amazon.com/eks/), ...

The OCI/ROCK ships the following components based on the [`charmed-mysql` snap](https://canonical-charmed-mysql.readthedocs-hosted.com/explanation/architecture):

* MySQL Community Edition
* MySQL Router
* MySQL Shell
* Percona XtraBackup
* Prometheus MySQLd Exporter
* Prometheus MySQL Router Exporter

**Prometheus Grafana dashboards and Loki alert rules** are part of the charm revision, but missing in the snap.

SNAP-based ROCK images guaranties the same components versions and functionality between VM and K8s charm flavors.

Pebble runs layers of all the currently enabled services, e.g. monitoring, backups, etc:

```shell
> juju ssh --container mysql mysql-k8s/0 /charm/bin/pebble plan
services:
    mysqld_exporter:
        summary: mysqld exporter
        startup: disabled                   <= COS Monitoring disabled
        override: replace
        command: /start-mysqld-exporter.sh
        environment:
            DATA_SOURCE_NAME: user:password@unix(/var/run/mysqld/mysqld.sock)/
        user: mysql
        group: mysql
    mysqld_safe:
        summary: mysqld safe
        startup: enabled                    <= MySQL is up and running
        override: replace
        command: mysqld_safe
        user: mysql
        group: mysql
        kill-delay: 24h0m0s
```

The `mysqld_safe` is a main MySQL wrapper which is normally up and running right after the charm deployment.

The `mysql-router` used in [Charmed MySQL Router K8s](https://charmhub.io/mysql-router-k8s?channel=8.4/edge) only and should be stopped on [Charmed MySQL K8s](https://charmhub.io/mysql-k8s) deployments.

All `exporter` services are activated only after relating with {ref}`COS <enable-monitoring>`.

```{caution}
* It is possible to start, stop, and restart pebble services manually but it is NOT recommended to avoid a split brain with a charm state machine! Do it with a caution!!!
* All pebble resources must be executed under the proper user (defined in user:group options of pebble layer)!
```

The ROCK "charmed-mysql" also ships list of tools used by charm:

* `mysql` - mysql client to connect `mysqld`.
* `mysqlsh` - new [mysql-shell](https://dev.mysql.com/doc/mysql-shell/8.4/en/) client to configure MySQL cluster.
* `xbcloud` - a tool to download and upload full or part of xbstream archive from/to the cloud.
* `xbstream` - a tool to support simultaneous compression and streaming.
* `xtrabackup` - a tool to backup/restore MySQL DB.

The `mysql` and `mysqlsh` are well known and popular tools to manage MySQL.

The `xtrabackup (xbcloud+xbstream)` is used only to store {ref}`backups <create-a-backup>` on S3 compatible storage.

## Integrations

### MySQL Router

[MySQL Router](https://dev.mysql.com/doc/mysql-router/8.4/en/) is part of MySQL InnoDB Cluster, and is lightweight middle-ware that provides transparent routing between your application and back-end MySQL Servers. The MySQL Router charm ([VM](https://charmhub.io/mysql-router) | [K8s](https://charmhub.io/mysql-router-k8s)) is an independent charm that can be related with MySQL.

### TLS Certificates Operator

The [TLS Certificates](https://charmhub.io/tls-certificates-operator) charm is responsible for distributing certificates through relationship. Certificates are provided by the operator through Juju configs. For playground deployments, the [self-signed operator](https://charmhub.io/self-signed-certificates) is available as well.

### S3 Integrator

[S3 Integrator](https://charmhub.io/s3-integrator) is an integrator charm for providing S3 credentials to Charmed MySQL which seek to access shared S3 data. Store the credentials centrally in the integrator charm and relate consumer charms as needed.

### Data Integrator

The [Data Integrator](https://charmhub.io/data-integrator) charm is a solution to request DB credentials for non-native Juju applications. Not all applications implement a data_interfaces relation but allow setting credentials through config options. Also, some of the applications are run outside of juju. This integrator charm allows receiving credentials which can be passed into application config directly without implementing juju-native relation.

### MySQL Test App

The charm [MySQL Test App](https://charmhub.io/mysql-test-app) is a Canonical test application to validate the charm installation / functionality and perform the basic performance tests.

### Grafana

Grafana is an open-source visualization tools that allows to query, visualize, alert on, and visualize metrics from mixed data sources in configurable dashboards for observability. This charms is shipped with its own Grafana dashboard and supports integration with the [Grafana Operator](https://charmhub.io/grafana-k8s) to simplify observability. See: {ref}`enable-monitoring`.

### Loki

Loki is an open-source fully-featured logging system. This charms is shipped with support for the [Loki Operator](https://charmhub.io/loki-k8s) to collect the generated logs. See: {ref}`enable-monitoring`.

### Prometheus

Prometheus is an open-source systems monitoring and alerting toolkit with a dimensional data model, flexible query language, efficient time series database and modern alerting approach. This charm is shipped with a Prometheus exporters, alerts and support for integrating with the [Prometheus Operator](https://charmhub.io/prometheus-k8s) to automatically scrape the targets. See: {ref}`enable-monitoring`.

## Low-level design

See the charm state machines displayed in {ref}`flowcharts`. The low-level logic is mostly common for both VM and K8s charms.

<!--- TODO: Describe all possible installations? Cross-model/controller? --->

### Juju events

Accordingly to the [Juju SDK](https://juju.is/docs/sdk/event): “an event is a data structure that encapsulates part of the execution context of a charm”.

For this charm, the following events are observed:

1. [`on_install`](https://documentation.ubuntu.com/juju/3.6/reference/hook/#install): install the snap "charmed-mysql" and perform basic preparations to bootstrap the cluster on the first leader (or join the already configured cluster). 
2. [`leader-elected`](https://documentation.ubuntu.com/juju/3.6/reference/hook/#leader-elected): generate all the secrets to bootstrap the cluster.
3. [`leader-settings-changed`](https://documentation.ubuntu.com/juju/3.6/reference/hook/#leader-settings-changed): Handle the leader settings changed event.
4. [`start`](https://documentation.ubuntu.com/juju/3.6/reference/hook/#start): Init/setting up the cluster node.
5. [`config_changed`](https://documentation.ubuntu.com/juju/3.6/reference/hook/#config-changed): usually fired in response to a configuration change using the GUI or CLI. Create and set default cluster and cluster-set names in the peer relation databag (on the leader only).
6. [`update-status`](https://documentation.ubuntu.com/juju/3.6/reference/hook/#update-status): Takes care of workload health checks.
<!--- 7. database_storage_detaching: TODO: ops? event?
8. TODO: any other events?
--->