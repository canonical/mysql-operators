---
myst:
  html_meta:
    description: "Connect client applications to a Charmed MySQL cluster-cluster replication setup by offering and consuming database endpoints across Juju models."
---

(cluster-cluster-clients)=
# Clients

This guide assumes both `Rome` and `Lisbon` Clusters are deployed using the {ref}`cluster-cluster-deploy`.

## Offer and consume database endpoints

```shell
juju switch rome
juju offer db1:database db1-database

juju switch lisbon
juju offer db2:database db2-database

juju add-model app ; juju switch app
juju consume rome.db1-database
juju consume lisbon.db2-database
```

## Internal Juju app/clients

````{tab-set}
```{tab-item} VM
:sync: vm

    juju switch app

    juju deploy mysql-test-app
    juju deploy mysql-router --channel 8.4/edge

    juju integrate mysql-test-app mysql-router
    juju integrate mysql-router db1-database
```

```{tab-item} K8s
:sync: k8s

    juju switch app

    juju deploy mysql-test-app
    juju deploy mysql-router-k8s --trust --channel 8.4/edge

    juju integrate mysql-test-app mysql-router-k8s
    juju integrate mysql-router-k8s db1-database

```
````

## External Juju clients

````{tab-set}
```{tab-item} VM
:sync: vm
    juju switch app

    juju deploy data-integrator --config database-name=mydatabase
    juju deploy mysql-router mysql-router-external --channel 8.4/edge

    juju integrate data-integrator mysql-router-external
    juju integrate mysql-router-external db1-database

    juju run data-integrator/leader get-credentials
```

```{tab-item} K8s
:sync: k8s

    juju switch app

    juju deploy data-integrator --config database-name=mydatabase
    juju deploy mysql-router-k8s mysql-router-external --trust --channel 8.4/edge

    juju integrate data-integrator mysql-router-external
    juju integrate mysql-router-external db1-database

    juju run data-integrator/leader get-credentials
```
````