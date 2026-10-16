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

## Deploy and integrate OpenTelemetry Collector

````{tab-set}
```{tab-item} VM
:sync: vm

First, deploy [opentelemetry-collector](https://charmhub.io/opentelemetry-collector), and integrate it with the principal application for the subordinate MySQL Router app `<client_application>`:

    juju deploy opentelemetry-collector --channel=2/stable
    juju integrate opentelemetry-collector <client_application>

Then, integrate `opentelemetry-collector` with the COS interfaces:

    juju integrate opentelemetry-collector mysql-router:cos-agent
    juju integrate opentelemetry-collector grafana
    juju integrate opentelemetry-collector loki
    juju integrate opentelemetry-collector prometheus

After this is complete, Grafana will show the new dashboards `MySQLRouter Exporter` and allows access for Charmed MySQL Router logs on Loki.

Example of `juju status` on the MySQL Router VM model:

    Model     Controller  Cloud/Region         Version  SLA          Timestamp
    database  lxd         localhost/localhost  3.6.19   unsupported  12:34:26Z

    SAAS        Status  Store  URL
    grafana     active  k8s    admin/cos.grafana
    loki        active  k8s    admin/cos.loki
    prometheus  active  k8s    admin/cos.prometheus

    App                      Version  Status  Scale  Charm                    Channel     Rev  Exposed  Message
    mysql                    8.4.10   active      1  mysql                    8.4/stable       no
    mysql-router             8.4.10   active      1  mysql-router             8.4/stable       no
    mysql-test-app           0.0.2    active      1  mysql-test-app           stable       36  no
    opentelemetry-collector           active      1  opentelemetry-collector  2/stable    316  no

    Unit                          Workload  Agent  Machine  Public address  Ports           Message
    mysql-test-app/0*             active    idle         1  10.205.193.82
      mysql-router/0*             active    idle            10.205.193.82
      opentelemetry-collector/0*  active    idle            10.205.193.82
    mysql/0*                      active    idle         0  10.205.193.13   3306,33060/tcp  Primary

    Machine  State    Address        Inst id        Base          AZ  Message
    0        started  10.205.193.13  juju-65afbd-0  ubuntu@26.04      Running
    1        started  10.205.193.82  juju-65afbd-1  ubuntu@26.04      Running

Example of `juju status` on the COS K8s model:

    Model  Controller  Cloud/Region        Version  SLA          Timestamp
    cos    k8s         microk8s/localhost  3.6.19   unsupported  20:29:12Z

    App             Version  Status  Scale  Charm             Channel  Rev  Address         Exposed  Message
    alertmanager    0.27.0   active      1  alertmanager-k8s  stable   106  10.152.183.197  no
    catalogue                active      1  catalogue-k8s     stable    33  10.152.183.38   no
    grafana         9.5.3    active      1  grafana-k8s       stable   106  10.152.183.238  no
    loki            2.9.4    active      1  loki-k8s          stable   124  10.152.183.84   no
    prometheus      2.49.1   active      1  prometheus-k8s    stable   171  10.152.183.182  no
```
```{tab-item} K8s
:sync: k8s

First, deploy [opentelemetry-collector-k8s](https://charmhub.io/opentelemetry-collector-k8s):

    juju deploy opentelemetry-collector-k8s --channel=2/stable --trust

Then, integrate `opentelemetry-collector-k8s` with Charmed MySQL Router K8s:

    juju integrate opentelemetry-collector-k8s grafana
    juju integrate opentelemetry-collector-k8s loki
    juju integrate opentelemetry-collector-k8s prometheus

Finally, integrate `opentelemetry-collector-k8s` with the consumed COS offers:

    juju integrate opentelemetry-collector-k8s mysql-router-k8s:grafana-dashboard
    juju integrate opentelemetry-collector-k8s mysql-router-k8s:logging
    juju integrate opentelemetry-collector-k8s mysql-router-k8s:metrics-endpoint

After this is complete, Grafana will show the new dashboards `MySQLRouter Exporter` and allows access for Charmed MySQL Router K8s logs on Loki.

An example of `juju status` on Charmed MySQL Router K8s model:

    Model 	  Controller  Cloud/Region    	  Version  SLA          Timestamp
    database  k8s     	  microk8s/localhost  3.6.19   unsupported  13:27:08Z

    SAAS    	Status  Store  URL
    grafana 	active  k8s	   admin/cos.grafana
    loki    	active  k8s	   admin/cos.loki
    prometheus  active  k8s	   admin/cos.prometheus

    App            	            Version  Status  Scale  Charm           	         Channel 	 Rev  Address     	  Exposed  Message
    mysql-k8s      	             8.4.10  active      1  mysql-k8s      	             8.4/stable       10.152.183.105  no
    mysql-router-k8s             8.4.10  active      1  mysql-router-k8s             8.4/stable	      10.152.183.92   no
    mysql-test-app 	             0.0.2   active      1  mysql-test-app 	             stable   	  36  10.152.183.35   no
    opentelemetry-collector-k8s          active      1  opentelemetry-collector-k8s  2/stable     64  10.152.183.141  no

    Unit              	            Workload  Agent  Address   	   Ports  Message
    mysql-k8s/0*      	            active	  idle   10.1.241.239         Primary
    mysql-router-k8s/0*             active	  idle   10.1.241.240
    mysql-test-app/0* 	            active	  idle   10.1.241.241
    opentelemetry-collector-k8s/0*  active	  idle   10.1.241.243


An example of `juju status` on the COS K8s model:

    Model  Controller  Cloud/Region        Version  SLA          Timestamp
    cos	   k8s     	   microk8s/localhost  3.6.19   unsupported  13:28:02Z

    App       	  Version  Status  Scale  Charm          Channel  Rev  Address     	   Exposed  Message
    alertmanager  0.27.0   active  	1  alertmanager-k8s  stable   106  10.152.183.197  no
    catalogue              active  	1  catalogue-k8s 	 stable	   33  10.152.183.38   no
    grafana       9.5.3	   active  	1  grafana-k8s   	 stable   106  10.152.183.238  no
    loki      	  2.9.4	   active  	1  loki-k8s      	 stable   124  10.152.183.84   no
    prometheus	  2.49.1   active  	1  prometheus-k8s	 stable   171  10.152.183.182  no
    traefik   	  2.10.5   active  	1  traefik-k8s   	 stable   174  10.0.0.44   	   no

    Unit         	 Workload  Agent  Address   	Ports  Message
    alertmanager/0*  active	   idle   10.1.241.222
    catalogue/0* 	 active	   idle   10.1.241.225
    grafana/0*   	 active	   idle   10.1.241.228
    loki/0*          active	   idle   10.1.241.226
    prometheus/0*	 active	   idle   10.1.241.227
    traefik/0*   	 active	   idle   10.1.241.221

    Offer   	Application  Charm       	 Rev  Connected  Endpoint          	   Interface                Role
    grafana 	grafana  	 grafana-k8s 	 106  2/2    	 grafana-dashboard 	   grafana_dashboard        requirer
    loki    	loki     	 loki-k8s    	 124  2/2    	 logging           	   loki_push_api            provider
    prometheus  prometheus   prometheus-k8s  171  2/2    	 receive-remote-write  prometheus_remote_write  provider

```
````

## Connect to Grafana web interface

To connect the Grafana web interface, follow the [Browse dashboards](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s)" section of the COS MicroK8s tutorial:

```shell
juju run grafana/leader get-admin-password --model <cos_k8s_controller>:<cos_model_name>
```