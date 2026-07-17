---
myst:
  html_meta:
    description: "Integrate Charmed MySQL with COS Lite (Grafana, Prometheus, Loki) for observability via cross-model offers and Juju integrations."
---

(enable-monitoring)=
# How to enable monitoring (COS)

This guide will show you how to deploy and configure the [COS Lite bundle](https://charmhub.io/cos-lite) to monitor your deployment with Grafana.

## Prerequisites

* The `cos-lite` bundle deployed in a Kubernetes environment
  * See: [COS Microk8s tutorial](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s)

---

## Offer interfaces via the COS controller

First, switch to COS K8s environment and offer COS interfaces to be cross-model integrated with the model hosting Charmed MySQL.

To switch to the Kubernetes controller for the COS model, run

```shell
juju switch <cos_k8s_controller>:<cos_model_name>
```

To offer the COS interfaces, run

```shell
juju offer grafana:grafana-dashboard
juju offer loki:logging
juju offer prometheus:receive-remote-write
```

## Consume offers via the MySQL model

Next, we will switch to Charmed MySQL model, find offers and integrate (relate) with them.

We are on the Kubernetes controller for the COS model. To switch to the MySQL model, run

```shell
juju switch <mysql_controller_name>:<mysql_model_name>
```

To find offers, run the following command (make sure not to miss the colon `:` at the end!):

```shell
juju find-offers <cos_k8s_controller>:
```

A similar output should appear, where `k8s` is the k8s controller name and `cos` the model where `cos-lite` has been deployed:

```shell
Store  URL                    Access  Interfaces
k8s    admin/cos.grafana      admin   grafana:grafana-dashboard
k8s    admin/cos.loki         admin   loki:logging
k8s    admin/cos.prometheus   admin   prometheus:receive-remote-write
...
```

Consume offers to be reachable in the current model:

```shell
juju consume k8s:admin/cos.grafana
juju consume k8s:admin/cos.loki
juju consume k8s:admin/cos.prometheus
```

## Deploy and integrate OpenTelemetry Collector

First, deploy the [opentelemetry-collector](https://charmhub.io/opentelemetry-collector) / [opentelemetry-collector-k8s](https://charmhub.io/opentelemetry-collector-k8s) charm:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy opentelemetry-collector --channel=2/stable
```

```{tab-item} K8s
:sync: k8s

    juju deploy opentelemetry-collector-k8s --channel=2/stable --trust
```
````

Then, integrate it with Charmed MySQL

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate opentelemetry-collector mysql:cos-agent
```

```{tab-item} K8s
:sync: k8s

    juju integrate opentelemetry-collector-k8s mysql-k8s:grafana-dashboard
    juju integrate opentelemetry-collector-k8s mysql-k8s:logging
    juju integrate opentelemetry-collector-k8s mysql-k8s:metrics-endpoint
```
````

Finally, integrate OpenTelemetry Collector with consumed COS offers:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate opentelemetry-collector grafana
    juju integrate opentelemetry-collector loki
    juju integrate opentelemetry-collector prometheus
```

```{tab-item} K8s
:sync: k8s

    juju integrate opentelemetry-collector-k8s grafana
    juju integrate opentelemetry-collector-k8s loki
    juju integrate opentelemetry-collector-k8s prometheus
```
````

After this is complete, Grafana will show the new dashboards: `MySQL Exporter` and allows access for Charmed MySQL logs on Loki.

### Example `juju status` outputs

`````{dropdown} Charmed MySQL model
````{tab-set}
```{tab-item} VM
:sync: vm

    ubuntu@localhost:~$ juju status
    Model      Controller  Cloud/Region         Version  SLA          Timestamp
    mysql      local       localhost/localhost  3.6.14   unsupported  00:12:18+02:00

    SAAS         Status  Store    URL
    grafana      active  k8s      admin/cos.grafana
    loki         active  k8s      admin/cos.loki
    prometheus   active  k8s      admin/cos.prometheus

    App                      Version  Status  Scale  Charm                    Channel   Rev  Exposed  Message
    mysql                    8.4.7    active      1  mysql                    8.4/edge       no       Primary
    opentelemetry-collector           active      1  opentelemetry-collector  2/stable  316  no

    Unit                          Workload  Agent  Machine  Public address  Ports               Message
    mysql/0*                      active    idle   4        10.85.186.140   3306/tcp,33060/tcp  Primary
      opentelemetry-collector/0*  active    idle            10.85.186.140

    Machine  State    Address        Inst id        Series  AZ    Message
    4        started  10.85.186.140  juju-fcde9e-4  ubuntu@26.04  Running
```
```{tab-item} K8s
:sync: k8s
    Model  Controller   Cloud/Region        Version  SLA          Timestamp
    mysql  charmed-dev  microk8s/localhost  3.6.14   unsupported  02:20:09+02:00

    SAAS        Status  Store        URL
    grafana     active  charmed-dev  admin/cos.grafana
    loki        active  charmed-dev  admin/cos.loki
    prometheus  active  charmed-dev  admin/cos.prometheus

    App                          Version  Status  Scale  Charm                        Channel   Rev  Address         Exposed  Message
    mysql-k8s                    8.4.7    active      1  mysql-k8s                    8.4/edge       10.152.183.115  no       Primary
    opentelemetry-collector-k8s           active      1  opentelemetry-collector-k8s  2/stable  207  10.152.183.116

    Unit                            Workload  Agent  Address      Ports  Message
    mysql-k8s/0*                    active    idle   10.1.84.117         Primary
    opentelemetry-collector-k8s/0*  active    idle   10.1.84.118         Primary
```
````
`````

````{dropdown} COS K8s model

```shell
ubuntu@localhost:~$ juju status
Model  Controller   Cloud/Region        Version  SLA          Timestamp
cos    k8s          microk8s/localhost  3.6.14   unsupported  00:15:31+02:00

App           Version  Status  Scale  Charm             Channel  Rev  Address         Exposed  Message
alertmanager  0.23.0   active      1  alertmanager-k8s  stable    47  10.152.183.206  no
catalogue              active      1  catalogue-k8s     stable    13  10.152.183.183  no
grafana       9.2.1    active      1  grafana-k8s       stable    64  10.152.183.140  no
loki          2.4.1    active      1  loki-k8s          stable    60  10.152.183.241  no
prometheus    2.33.5   active      1  prometheus-k8s    stable   103  10.152.183.240  no
traefik       2.9.6    active      1  traefik-k8s       stable   110  10.76.203.178   no

Unit             Workload  Agent  Address      Ports  Message
alertmanager/0*  active    idle   10.1.84.125
catalogue/0*     active    idle   10.1.84.127
grafana/0*       active    idle   10.1.84.83
loki/0*          active    idle   10.1.84.79
prometheus/0*    active    idle   10.1.84.96
traefik/0*       active    idle   10.1.84.119

Offer        Application  Charm           Rev  Connected  Endpoint              Interface                Role
grafana      grafana      grafana-k8s     64   1/1        grafana-dashboard     grafana_dashboard        requirer
loki         loki         loki-k8s        60   1/1        logging               loki_push_api            provider
prometheus   prometheus   prometheus-k8s  103  1/1        receive-remote-write  prometheus_remote_write  provider
```

````

## Connect Grafana web interface

To connect the Grafana web interface, follow the [Browse dashboards](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s)" section of the COS MicroK8s tutorial:

```shell
juju run grafana/leader get-admin-password --model <cos_k8s_controller>:<cos_model_name>
```


## Full example of COS integration (MySQL K8s)

[![asciicast](https://asciinema.org/a/580608.svg)](https://asciinema.org/a/580608)
