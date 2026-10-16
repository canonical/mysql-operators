(deploy-router)=
# How to deploy

For more thorough, guided instructions on setting up your environment and deploying MySQL Router, see the {ref}`tutorial`.

## Set up a cloud

To deploy via the **Juju CLI**, you need to first [bootstrap](https://juju.is/docs/juju/juju-bootstrap) a cloud controller and create a [model](https://canonical-juju.readthedocs-hosted.com/en/latest/user/reference/model/):

```shell
juju bootstrap <cloud name> <controller name>
juju add-model <model name>
```

## Deploy

Deploy MySQL and MySQL Router, and integrate them:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --channel 8.4/stable
    juju deploy mysql-router --channel 8.4/stable
    juju integrate mysql mysql-router
```
```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --channel 8.4/stable --trust
    juju deploy mysql-router-k8s --channel 8.4/stable --trust
    juju integrate mysql-k8s mysql-router-k8s
```
````

Deploy and integrate your client application with MySQL Router.

```{note}
If your client application is not a charm, you'll need to use `data-integrator`. See:

* {ref}`integrate-router`
* {ref}`external-access-router`
```

````{tab-set}
```{tab-item} VM
:sync: vm

For this example, we'll use the `mysql-test-app` charm:

    juju deploy mysql-test-app
    juju integrate mysql-router mysql-test-app:database

Example output of `juju status --watch 1s` with a deployment in a local LXD cloud:

    Model         Controller  Cloud/Region         Version  SLA          Timestamp
    sample-model  lxd         localhost/localhost  3.6.19   unsupported  11:57:33+02:00

    App             Version  Status  Scale  Charm           Channel     Rev  Exposed  Message
    mysql           8.4.10   active      1  mysql           8.4/stable  196  no
    mysql-router    8.4.10   active      1  mysql-router    8.4/stable  119  no
    mysql-test-app  0.0.2    active      1  mysql-test-app  stable       26  no

    Unit               Workload  Agent  Machine  Public address  Ports           Message
    mysql-test-app/0*  active    idle   1        10.3.217.209
    mysql-router/0*    active    idle            10.3.217.209
    mysql/0*           active    idle   0        10.3.217.119    3306,33060/tcp  Primary

    Machine  State    Address       Inst id        Base          AZ  Message
    0        started  10.3.217.119  juju-d458a0-0  ubuntu@26.04      Running
    1        started  10.3.217.209  juju-d458a0-1  ubuntu@26.04      Running
```
```{tab-item} K8s
:sync: k8s

For this example, we'll use the `wordpress-k8s` charm:

    juju deploy wordpress-k8s
    juju integrate mysql-router wordpress-k8s:database

Example output of `juju status --watch 1s` with a deployment in a local MicroK8s cloud:

    Model           Controller  Cloud/Region        Version  SLA          Timestamp
    sample-model    microk8s    microk8s/localhost  3.6.19   unsupported  14:39:27+02:00

    App               Version  Status   Scale  Charm             Channel       Rev  Address         Exposed  Message
    mysql-k8s         8.4.10   active       1  mysql-k8s         8.4/stable     99  10.152.183.189  no
    mysql-router-k8s  8.4.10   active       1  mysql-router-k8s  8.4/stable     69  10.152.183.81   no
    wordpress-k8s              active       1  wordpress-k8s     latest/stable

    Unit                 Workload  Agent  Address     Ports  Message
    mysql-k8s/0*         active    idle   10.1.12.61         Primary
    mysql-router-k8s/0*  active    idle   10.1.12.16
    wordpress-k8s/0*     active    idle
```
````