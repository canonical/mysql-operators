(enable-tracing)=
# How to enable tracing

This guide contains the steps to enable tracing with [Grafana Tempo](https://grafana.com/docs/tempo/latest/) for your MySQL Router application.

## Prerequisites

* Fully configured monitoring with COS
  * See {ref}`enable-monitoring`

---

## Deploy Tempo

First, switch to the Kubernetes controller where the COS model is deployed:

```shell
juju switch <k8s_controller_name>:<cos_model_name>
```

````{tab-set}
```{tab-item} VM
:sync: vm

Deploy the [`tempo-k8s`](https://charmhub.io/tempo-k8s) charm:

    juju deploy -n 1 tempo-k8s --channel latest/edge

Integrate `tempo-k8s` with the COS charms as follows:

    juju integrate tempo-k8s:grafana-dashboard grafana:grafana-dashboard
    juju integrate tempo-k8s:grafana-source grafana:grafana-source
    juju integrate tempo-k8s:ingress traefik:traefik-route
    juju integrate tempo-k8s:metrics-endpoint prometheus:metrics-endpoint
    juju integrate tempo-k8s:logging loki:logging

If you would like to instrument traces from the COS charms as well, create the following integrations:

    juju integrate tempo-k8s:tracing alertmanager:tracing
    juju integrate tempo-k8s:tracing catalogue:tracing
    juju integrate tempo-k8s:tracing grafana:tracing
    juju integrate tempo-k8s:tracing loki:tracing
    juju integrate tempo-k8s:tracing prometheus:tracing
    juju integrate tempo-k8s:tracing traefik:tracing
```
```{tab-item} K8s
:sync: k8s

Deploy the dependencies of Tempo following [this tutorial](https://discourse.charmhub.io/t/tutorial-deploy-tempo-ha-on-top-of-cos-lite/15489).

In particular, we would want to:
- Deploy the minio charm
- Deploy the s3 integrator charm
- Add a bucket in minio using a python script
- Configure s3 integrator with the minio credentials

Finally, deploy and integrate with Tempo HA in a monolithic setup by following the "Monolithic deployment mode for testing and dev" section of the [Tempo tutorial](https://discourse.charmhub.io/t/tutorial-deploy-tempo-ha-on-top-of-cos-lite/15489).
```
````

## Offer interfaces

Next, offer interfaces for cross-model integrations from the model where Charmed MySQL Router is deployed.

````{tab-set}
```{tab-item} VM
:sync: vm

To offer the Tempo integration, run

    juju offer tempo-k8s:tracing

Then, switch to the Charmed MySQL Router model, find the offers, and integrate (relate) with them:

    juju switch <machine_controller_name>:<mysql_router_model_name>
    juju find-offers <k8s_controller_name>:

Do not miss the "`:`" in the command above!

Below is a sample output where `k8s` is the K8s controller name and `cos` is the model where `cos-lite` and `tempo-k8s` are deployed:

    Store  URL                  Access  Interfaces
    k8s    admin/cos.tempo-k8s  admin   tracing:tracing

Next, consume this offer so that it is reachable from the current model:

    juju consume k8s:admin/cos.tempo-k8s

Relate Charmed MySQL Router with the above consumed interface:

    juju integrate mysql-router:tracing tempo-k8s:tracing

Wait until the model settles. The following is an example of the `juju status --relations` on the Charmed MySQL Router model:

    Model     Controller  Cloud/Region         Version  SLA          Timestamp
    database  lxd         localhost/localhost  3.6.19   unsupported  12:48:46Z

    SAAS       Status  Store  URL
    tempo-k8s  active  uk8s   admin/cos.tempo-k8s

    App             Version  Status  Scale  Charm           Channel      Rev  Exposed  Message
    mysql           8.4.10   active      1  mysql           8.4/stable        no
    mysql-router    8.4.10   active      1  mysql-router    8.4/stable        no
    mysql-test-app  0.0.2    active      1  mysql-test-app  latest/edge   46  no       Last written value=54713

    Unit               Workload  Agent  Machine  Public address  Ports           Message
    mysql-test-app/0*  active    idle   1        10.205.193.43                   Last written value=54713
      mysql-router/0*  active    idle            10.205.193.43
    mysql/0*           active    idle   0        10.205.193.72   3306,33060/tcp  Primary

    Machine  State    Address        Inst id        Base          AZ  Message
    0        started  10.205.193.72  juju-7f1fdf-0  ubuntu@26.04      Running
    1        started  10.205.193.43  juju-7f1fdf-1  ubuntu@26.04      Running

    Integration provider              Requirer                          Interface          Type         Message
    mysql-router:cos                  mysql-router:cos                  cos                peer
    mysql-router:database             mysql-test-app:database           mysql_client       subordinate
    mysql-router:tls                  mysql-router:tls                  tls                peer
    mysql-router:refresh-v-three      mysql-router:refresh-v-three      refresh            peer
    mysql-test-app:application-peers  mysql-test-app:application-peers  application-peers  peer
    mysql:database                    mysql-router:backend-database     mysql_client       regular
    mysql:database-peers              mysql:database-peers              mysql_peers        peer
    mysql:rolling_ops                 mysql:rolling_ops                 rolling_op         peer
    mysql:refresh-v-three             mysql:refresh-v-three             refresh            peer
    tempo-k8s:tracing                 mysql-router:tracing              tracing            regular
```
```{tab-item} K8
:sync: k8

To offer the Tempo integration, run

    juju offer <tempo_coordinator_k8s_application_name>:tracing

Then, switch to the Charmed MySQL Router K8s model, find the offers, and integrate (relate) with them:

    juju switch <k8s_controller_name>:<mysql_router_k8s_model_name>
    juju find-offers <k8s_controller_name>:

Do not miss the "`:`" in the command above.

Below is a sample output where `k8s` is the K8s controller name and `cos` is the model where `cos-lite` and `tempo-k8s` are deployed:

    Store  URL                            Access  Interfaces
    k8s    admin/cos.tempo                admin   tracing:tracing

Next, consume this offer so that it is reachable from the current model:

    juju consume k8s:admin/cos.tempo

## Consume interfaces with OpenTelemetry Collector

<!--TODO: clarify whether this is K8s only -->

First, deploy the [OpenTelemetry Collector K8s](https://charmhub.io/opentelemetry-collector-k8s) charm:

    juju deploy opentelemetry-collector-k8s --channel=2/stable

Then, integrate OpenTelemetry Collector k8s with the consumed interface from the previous section:

    juju integrate opentelemetry-collector-k8s:tracing tempo:tracing

Finally, integrate Charmed MySQL Router K8s with OpenTelemetry Collector K8s:

    juju integrate opentelemetry-collector-k8s:tracing-provider mysql-router-k8s:tracing

Wait until the model settles. The following is an example of the `juju status --relations` on the Charmed MySQL Router K8s model:

    Model     Controller  Cloud/Region        Version  SLA          Timestamp
    database  k8s         microk8s/localhost  3.6.19   unsupported  18:32:28Z

    SAAS   Status  Store       URL
    tempo  active  k8s         admin/cos.tempo

    App                          Version  Status  Scale  Charm                        Channel        Rev  Address         Exposed  Message
    mysql-k8s                    8.4.10   active      1  mysql-k8s                    8.4/stable          10.152.183.58   no
    mysql-router-k8s             8.4.10   active      1  mysql-router-k8s             8.4/stable          10.152.183.50   no
    mysql-test-app               0.0.2    active      1  mysql-test-app               latest/stable   51  10.152.183.162  no
    opentelemetry-collector-k8s           active      1  opentelemetry-collector-k8s  2/stable       207  10.152.183.164  no

    Unit                            Workload  Agent  Address       Ports  Message
    mysql-k8s/0*                    active    idle   10.1.241.213         Primary
    mysql-router-k8s/0*             active    idle   10.1.241.218
    mysql-test-app/0*               active    idle   10.1.241.222
    opentelemetry-collector-k8s/0*  active    idle   10.1.241.224

    Integration provider                 Requirer                                    Interface           Type     Message
    opentelemetry-collector-k8s:peers    opentelemetry-collector-k8s:peers           otelcol_replica     peer
    mysql-router-k8s:tracing             opentelemetry-collector-k8s:receive-traces  tracing             regular
    mysql-k8s:database                   mysql-router-k8s:backend-database           mysql_client        regular
    mysql-k8s:database-peers             mysql-k8s:database-peers                    mysql_peers         peer
    mysql-k8s:refresh-v-three            mysql-k8s:refresh-v-three                   refresh             peer
    mysql-k8s:rolling_ops                mysql-k8s:rolling_ops                       rolling_op          peer
    mysql-router-k8s:cos                 mysql-router-k8s:cos                        cos                 peer
    mysql-router-k8s:database            mysql-test-app:database                     mysql_client        regular
    mysql-router-k8s:mysql-router-peers  mysql-router-k8s:mysql-router-peers         mysql_router_peers  peer
    mysql-router-k8s:refresh-v-three     mysql-router-k8s:refresh-v-three            refresh             peer
    mysql-test-app:application-peers     mysql-test-app:application-peers            application-peers   peer
    tempo:tracing                        opentelemetry-collector-k8s:send-traces     tracing             regular
```
````

```{note}
All traces are exported to Tempo using HTTP. Support for sending traces via HTTPS is an upcoming feature.
```

## View traces

After this is complete, the Tempo traces will be accessible from Grafana under the `Explore` section with `tempo-k8s` as the data source. You will be able to select `mysql-router` or `mysql-router-k8s` as the `Service Name` under the `Search` tab to view traces belonging to Charmed MySQL Router.

<!--TODO Below is a screenshot demonstrating a Charmed MySQL Router trace:
![Example MySQL Router trace with Grafana Tempo|690x382](upload://iXdGsc3ACrhMal43QwNU5q5OCJ7.jpeg) -->

Feel free to read through the [Tempo documentation](https://discourse.charmhub.io/t/tempo-k8s-docs-index/14005) at your leisure to explore its deployment and its integrations.