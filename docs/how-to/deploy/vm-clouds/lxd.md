---
myst:
  html_meta:
    description: "Deploy Charmed MySQL on LXD with an existing Juju and LXD environment. See the tutorial for a complete step-by-step walkthrough."
---

(lxd)=
# Deploy on LXD

This guide assumes you have a running Juju and LXD environment. 

For a detailed walkthrough of setting up an environment and deploying the charm on LXD, refer to the {ref}`tutorial`.

---

[Bootstrap](https://juju.is/docs/juju/juju-bootstrap) a juju controller and create a [model](https://juju.is/docs/juju/juju-add-model) if you haven't already:
```shell
juju bootstrap localhost <controller name>
juju add-model <model name>
```
Deploy MySQL
```shell
juju deploy mysql --channel 8.4/edge
```
> See the [`juju deploy` documentation](https://juju.is/docs/juju/juju-deploy) for all available options at deploy time.
> 
> See the [Configurations tab](https://charmhub.io/mysql/configurations) for specific MySQL parameters.

Sample output of `juju status --watch 1s`:
```shell
Model   Controller  Cloud/Region         Version  SLA          Timestamp
mysql   overlord    localhost/localhost  3.1.6    unsupported  00:52:59+02:00

App    Version          Status  Scale  Charm  Channel     Rev  Exposed  Message
mysql  8.4.7            active      1  mysql  8.4/edge         no       Primary

Unit      Workload  Agent  Machine  Public address  Ports           Message
mysql/0*  active    idle   1        10.234.188.135  3306,33060/tcp  Primary

Machine  State    Address         Inst id        Base          AZ  Message
1        started  10.234.188.135  juju-ff9064-0  ubuntu@24.04      Running
```

