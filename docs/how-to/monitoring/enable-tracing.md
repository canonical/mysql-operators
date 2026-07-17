---
myst:
  html_meta:
    description: "Enable Grafana Tempo distributed tracing for Charmed MySQL (development preview) by deploying Tempo HA and integrating via cross-model offers."
---

(enable-tracing)=
# Enable tracing

This guide contains the steps to enable tracing with [Grafana Tempo](https://grafana.com/docs/tempo/latest/) for your MySQL application.

## Prerequisites

* Fully configured monitoring with COS
  * See {ref}`enable-monitoring`

---

## Deploy Tempo

First, switch to the Kubernetes controller where the COS model is deployed:

```shell
juju switch <k8s_controller_name>:<cos_model_name>
```

Then, deploy the dependencies of Tempo following [this tutorial](https://discourse.charmhub.io/t/tutorial-deploy-tempo-ha-on-top-of-cos-lite/15489). 

To summarize:
* Deploy the MinIO charm
* Deploy the s3 integrator charm
* Add a bucket in MinIO using a python script
* Configure s3 integrator with the MinIO credentials

Finally, deploy and integrate with Tempo HA in [a monolithic setup](https://discourse.charmhub.io/t/tutorial-deploy-tempo-ha-on-top-of-cos-lite/15489).

## Offer interfaces

Next, offer interfaces for cross-model integrations from the model where Charmed MySQL is deployed.

To offer the Tempo integration, run

```shell
juju offer <tempo_coordinator_k8s_application_name>:tracing
```

Then, switch to the Charmed MySQL VM model, find the offers, and integrate (relate) with them:

```shell
juju switch <mysql_controller_name>:<mysql_model_name>

juju find-offers <k8s_controller_name>:  
```
> Do not miss the "`:`" in the command above!

Below is a sample output where `k8s` is the K8s controller name and `cos` is the model where `cos-lite` and `tempo-k8s` are deployed:

```shell
Store  URL                            Access  Interfaces
k8s    admin/cos.tempo                admin   tracing:tracing
```

Next, consume this offer so that it is reachable from the current model:

```shell
juju consume k8s:admin/cos.tempo
```

## Consume interfaces

First, deploy [opentelemetry-collector](https://charmhub.io/opentelemetry-collector) / [opentelemetry-collector-k8s](https://charmhub.io/opentelemetry-collector-k8s) charm:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy opentelemetry-collector --channel 2/stable
```

```{tab-item} K8s
:sync: k8s

    juju deploy opentelemetry-collector-k8s --channel 2/stable --trust
```
````

Then, integrate OpenTelemetry Collector with Charmed MySQL:
````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate opentelemetry-collector:cos-agent mysql:cos-agent
```

```{tab-item} K8s
:sync: k8s

    juju integrate opentelemetry-collector-k8s:receive-traces mysql-k8s:tracing 
```
````

Finally, integrate OpenTelemetry Collector with the consumed interface from the previous section:
````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate opentelemetry-collector:send-traces tempo:tracing
```

```{tab-item} K8s
:sync: k8s

    juju integrate opentelemetry-collector-k8s:send-traces tempo:tracing
```
````

Wait until the model settles. The following is an example of the `juju status --relations` on the Charmed MySQL model:

````{tab-set}
```{tab-item} VM
:sync: vm

    Model     Controller  Cloud/Region         Version  SLA          Timestamp
    mysql     lxd         localhost/localhost  3.6.14   unsupported  19:15:55Z

    SAAS   Status  Store       URL
    tempo  active  k8s         admin/cos.tempo

    App                      Version  Status   Scale  Charm                    Channel      Rev  Exposed  Message
    mysql                    8.4.7    active       1  mysql                    8.4/edge          no
    opentelemetry-collector           blocked      1  opentelemetry-collector  2/stable     316  no

    Unit                          Workload  Agent  Machine  Public address  Ports           Message
    mysql/0*                      active    idle   0        10.205.193.32   3306,33060/tcp  Primary
      opentelemetry-collector/0*  blocked   idle            10.205.193.32

    Machine  State    Address        Inst id        Base          AZ  Message
    0        started  10.205.193.32  juju-4f3e50-0  ubuntu@26.04      Running

    Integration provider           Requirer                             Interface        Type         Message
    opentelemetry-collector:peers  opentelemetry-collector:peers        otelcol_replica  peer
    mysql:cos-agent                opentelemetry-collector:cos-agent    tracing          subordinate
    mysql:database-peers           mysql:database-peers                 mysql_peers      peer
    mysql:refresh-v-three          mysql:refresh-v-three                refresh          peer
    mysql:rolling-ops              mysql:rolling-ops                    rolling_op       peer
    tempo:tracing                  opentelemetry-collector:send-traces  tracing          regular
```
```{tab-item} K8s
:sync: k8s

    Model     Controller  Cloud/Region        Version  SLA          Timestamp
    mysql     k8s         microk8s/localhost  3.6.14   unsupported  16:33:26Z

    SAAS   Status  Store       URL
    tempo  active  k8s         admin/cos.tempo

    App                          Version  Status  Scale  Charm                        Channel   Rev  Address         Exposed  Message
    mysql-k8s                    8.4.7    active      1  mysql-k8s                    8.4/edge       10.152.183.135  no       Primary
    opentelemetry-collector-k8s           active      1  opentelemetry-collector-k8s  2/stable  207  10.152.183.136

    Unit                            Workload  Agent      Address       Ports  Message
    mysql-k8s/0*                    active    executing  10.1.241.253         Primary
    opentelemetry-collector-k8s/0*  active    idle       10.1.241.254

    Integration provider               Requirer                                    Interface        Type     Message
    opentelemetry-collector-k8s:peers  opentelemetry-collector-k8s:peers           otelcol_replica  peer
    mysql-k8s:tracing                  opentelemetry-collector-k8s:receive-traces  tracing          regular
    mysql-k8s:database-peers           mysql-k8s:database-peers                    mysql_peers      peer
    mysql-k8s:refresh-v-three          mysql-k8s:refresh-v-three                   refresh          peer
    mysql-k8s:rolling-ops              mysql-k8s:rolling-ops                       rolling_op       peer
    tempo:tracing                      opentelemetry-collector-k8s:send-traces     tracing          regular
```
````

```{note}
All traces are exported to Tempo using HTTP. Support for sending traces via HTTPS is an upcoming feature.
```

## View traces

The Tempo traces will be accessible from Grafana under the `Explore` section with `tempo-k8s` as the data source. You will be able to select `mysql` as the `Service Name` under the `Search` tab to view traces belonging to Charmed MySQL.

<details><summary>Screenshot
</summary>

![MySQL trace with Grafana Tempo](mysql-vm-trace.png)
</details>

Feel free to read through the [Tempo HA documentation](https://discourse.charmhub.io/t/charmed-tempo-ha/15531) at your leisure to explore its deployment and its integrations.
