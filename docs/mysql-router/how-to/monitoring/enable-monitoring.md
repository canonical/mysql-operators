(enable-monitoring-router)=
# Enable monitoring

This guide goes over the steps to integrate your MySQL Router deployment with COS to enable monitoring in Grafana.

## Prerequisites

* The `cos-lite` bundle deployed in a Kubernetes environment
  * See: [COS Microk8s tutorial](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s)

---


## Offer interfaces via the COS controller

First, switch to COS K8s environment and offer COS interfaces to be cross-model integrated with the model hosting Charmed MySQL Router.

To switch to the Kubernetes controller for the COS model, run

```shell
juju switch <k8s_controller>:<cos_model_name>
```

To offer the COS interfaces, run

```shell
juju offer grafana:grafana-dashboard
juju offer loki:logging
juju offer prometheus:receive-remote-write
```

## Consume offers via the MySQL Router model

Next, we will switch to the Charmed MySQL Router model, find offers, and consume them.

We are currently on the Kubernetes controller for the COS model. To switch to the MySQL Router model, run:

```shell
juju switch <mysql_controller_name>:<mysql_model_name>
```

To find offers, run the following command (make sure not to miss the colon `:` at the end!):

```shell
juju find-offers <cos_k8s_controller>:
```

A similar output should appear, where `k8s` is the k8s controller name and `cos` the model where `cos-lite` has been deployed:

```shell
Store  URL                   Access     Interfaces
k8s       admin/cos.grafana     admin   grafana_dashboard:grafana-dashboard
k8s       admin/cos.loki        admin   loki_push_api:logging
k8s       admin/cos.prometheus  admin   prometheus_remote_write:receive-remote-write
```
<!--TODO: are the interface names correct?-->

Consume offers to be reachable in the current model:

```shell
juju consume k8s:admin/cos.grafana
juju consume k8s:admin/cos.loki
juju consume k8s:admin/cos.prometheus
```

## Deploy and integrate Grafana

First, deploy [grafana-agent](https://charmhub.io/grafana-agent) and integrate it:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy grafana-agent
    juju integrate <client_application> grafana-agent
```
```{tab-item} K8s
:sync: k8s

    juju deploy grafana-agent-k8s --trust
    juju integrate grafana-agent-k8s grafana
    juju integrate grafana-agent-k8s loki
    juju integrate grafana-agent-k8s prometheus
```
````

Then integrate the Grafana agent with the COS interfaces:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate grafana-agent mysql-router:cos-agent
    juju integrate grafana-agent grafana
    juju integrate grafana-agent loki
    juju integrate grafana-agent prometheus
```
```{tab-item} K8s
:sync: k8s

    juju integrate grafana-agent-k8s mysql-router-k8s:grafana-dashboard
    juju integrate grafana-agent-k8s mysql-router-k8s:logging
    juju integrate grafana-agent-k8s mysql-router-k8s:metrics-endpoint
```
````

After this is complete, Grafana will show the new dashboards `MySQLRouter Exporter` and allows access for Charmed MySQL Router logs on Loki.

## Connect to Grafana web interface

To connect the Grafana web interface, follow the [Browse dashboards](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s)" section of the COS MicroK8s tutorial:

```shell
juju run grafana/leader get-admin-password --model <cos_k8s_controller>:<cos_model_name>
```
