---
myst:
  html_meta:
    description: "Upgrade Juju for Charmed MySQL deployments, covering patch upgrades and major/minor version upgrades with model migration steps."
---

(upgrade-juju)=
# How to upgrade Juju for a new database revision

Newly released charm revisions might require a new Juju version. This is usually because the new revision requires new Juju features, e.g. [Juju secrets](https://juju.is/docs/juju/secret).

Information about Juju requirements will be clearly indicated in the charm's {ref}`release notes <release-notes>` and in the repository's `metadata.yaml` file.

When upgrading your database charm with {command}`juju refresh` Juju checks that its version is compatible with the target revision. If not, it stops the upgrade and prevents further changes to keep the installation safe. 

This guide contains instructions to perform a patch or major/minor Juju upgrade to a controller and model containing a database charm. 

## Patch version upgrade

A [PATCH](https://semver.org/#summary) Juju upgrade (e.g. Juju `3.6.0` → `3.6.1`) can be easily applied in-place.

```shell
sudo snap refresh juju 

juju upgrade-controller 
# wait until complete

juju upgrade-model 
# wait until complete
```

Once the model has finished upgrading, you can proceed with the {ref}`charm upgrade <refresh-single-cluster>`.

## Major/minor version upgrade

The easiest way to perform a [major/minor](https://semver.org/#summary) Juju version upgrade (e.g. Juju `3.5.3` → `3.6.14`),  is to update the controller and model to the new version, then [migrate](https://juju.is/docs/juju/juju-migrate) the model.

### Commands summary

The following is a summary of commands that upgrade Juju to `3.6/stable`:


````{tab-set}
```{tab-item} VM
:sync: vm

    sudo snap refresh juju --channel 3.6/stable

    juju bootstrap lxd lxd_3.6.14 # --agent-version 3.6.14

    juju migrate lxd_3.5.3:mydatabase lxd_3.6.14

    juju upgrade-model -m lxd_3.6.14:mydatabase 
    # wait until complete
```

```{tab-item} K8s
:sync: k8s

    sudo snap refresh juju --channel 3.6/stable

    juju bootstrap microk8s k8s_3.6.14 # --agent-version 3.6.14

    juju migrate k8s_3.5.3:mydatabase k8s_3.6.14

    juju upgrade-model -m k8s_3.6.14:mydatabase 
    # wait until complete
```
````

Once the model has finished upgrading, you can proceed with the {ref}`charm upgrade <refresh-single-cluster>`.

### Example

This section goes over the commands listed in the summary above with more details and sample outputs.

<details><summary>In this example scenario, we have <code>mysql</code> deployed in model <code>mydatabase</code> on the Juju controller <code>lxd_3.5.8</code>.</summary> 

```text
juju status
```
```text
Model       Controller  Cloud/Region         Version  SLA          Timestamp
mydatabase  lxd_3.5.3   localhost/localhost  3.5.3    unsupported  22:54:48+02:00

App    Version   Status  Scale  Charm  Channel     Rev  Exposed  Message
mysql  8.4.7     active      3  mysql  8.4/edge         no       

Unit      Workload  Agent  Machine  Public address  Ports           Message
mysql/0*  active    idle   0        10.217.68.104   3306,33060/tcp  Primary
mysql/1   active    idle   1        10.217.68.118   3306,33060/tcp  
mysql/2   active    idle   2        10.217.68.144   3306,33060/tcp  

Machine  State    Address        Inst id        Base          AZ  Message
0        started  10.217.68.104  juju-a4598a-0  ubuntu@26.04      Running
1        started  10.217.68.118  juju-a4598a-1  ubuntu@26.04      Running
2        started  10.217.68.144  juju-a4598a-2  ubuntu@26.04      Running
```
</details>

To upgrade Juju to `v.3.6.14`, we go through the following steps:

<details><summary>1. Update the Juju CLI</summary>

Check the current version with the command:

```text
 juju --version
```

Perform the upgrade:

```text
sudo snap refresh juju --channel 3.5/stable
```
Optionally rerun the `juju --version` command to confirm the upgrade.

</details>

<details><summary>2. Bootstrap the new controller</summary>

Use the [`juju bootstrap`](https://juju.is/docs/juju/juju-bootstrap) command to create a new controller. In this example, we specify a particular version (and name the controller accordingly):

```text
juju bootstrap lxd lxd_3.6.14 --agent-version 3.6.14
```

This will produce output describing  progress and the steps taken, similar to:

```text
Creating Juju controller "lxd_3.6.14" on lxd/localhost
Looking for packaged Juju agent version 3.6.14 for amd64
Located Juju agent version 3.6.14-ubuntu-amd64 at https://streams.canonical.com/juju/tools/agent/3.6.14/juju-3.6.14-linux-amd64.tgz
To configure your system to better support LXD containers, please see: https://documentation.ubuntu.com/lxd/en/latest/explanation/performance_tuning/
Launching controller instance(s) on localhost/localhost...
 - juju-374723-0 (arch=amd64)          
Installing Juju agent on bootstrap instance
Waiting for address
Attempting to connect to 10.217.68.44:22
Connected to 10.217.68.44
Running machine configuration script...
Bootstrap agent now started
Contacting Juju controller at 10.217.68.44 to verify accessibility...
Bootstrap complete, controller "lxd_3.6.14" is now available
Controller machines are in the "controller" model
...
```
</details>

<details><summary>3. Migrate the entire model <code>mydatabase</code> to the new controller (no database outage here)</summary>

```shell
~$ juju controllers
Controller  Model       User   Access     Cloud/Region         Models  Nodes    HA  Version
lxd_3.5.3*  mydatabase  admin  superuser  localhost/localhost       2      1  none  3.5.3  
lxd_3.6.14   -          admin  superuser  localhost/localhost       1      1  none  3.6.14

~$ juju models -c lxd_3.5.3
Controller: lxd_3.5.3
Model        Cloud/Region         Type  Status     Machines  Units  Access  Last connection
controller   localhost/localhost  lxd   available         1      1  admin   just now
mydatabase*  localhost/localhost  lxd   available         3      3  admin   36 seconds ago

~$ juju models -c lxd_3.6.14
Controller: lxd_3.6.14
Model       Cloud/Region         Type  Status     Machines  Units  Access  Last connection
controller  localhost/localhost  lxd   available         1      1  admin   just now

~$ juju migrate lxd_3.5.3:mydatabase lxd_3.6.14
Migration started with ID "5f227519-3cdb-4538-871c-1c4589a4598a:0"
```
</details>

<details><summary>4. Use <code>juju models</code> to check the migration process has started ( model status=<code>busy</code>). At the end of the process, the model is no longer available on the old controller as it has been moved to new controller</summary>

```shell
~$ juju models --controller lxd_3.5.3
...
mydatabase*  localhost/localhost  lxd   busy              3      3  admin   1 minute ago

~$ juju models --controller lxd_3.5.3
Controller: lxd_3.5.3
Model       Cloud/Region         Type  Status     Machines  Units  Access  Last connection
controller  localhost/localhost  lxd   available         1      1  admin   just now

~$ juju models --controller lxd_3.6.14
Controller: lxd_3.6.14
Model       Cloud/Region         Type  Status     Machines  Units  Access  Last connection
controller  localhost/localhost  lxd   available         1      1  admin   just now
mydatabase  localhost/localhost  lxd   available         3      3  admin   1 minute ago
```
</details>

<details><summary>5. Upgrade the model version itself (no database outage here)</summary>

```shell
> juju status -m lxd_3.6.14:mydatabase
Model       Controller  Cloud/Region         Version  SLA          Timestamp
mydatabase  lxd_3.6.14  localhost/localhost  3.5.3    unsupported  22:58:10+02:00
...

> juju upgrade-model -m lxd_3.6.14:mydatabase
best version:
    3.6.14
started upgrade to 3.6.14

> juju status -m lxd_3.6.14:mydatabase
Model       Controller  Cloud/Region         Version  SLA          Timestamp
mydatabase  lxd_3.6.14  localhost/localhost  3.6.14   unsupported  22:59:01+02:00
...
```
</details>

At this stage, the application continues running under the supervision of the new controller version and is ready to be refreshed to the new charm revision.

You can now proceed with the {ref}`charm upgrade <refresh-single-cluster>`.

## Resources
Further documentation about Juju upgrades: 
* [Juju | Upgrade a controller](https://juju.is/docs/juju/manage-controllers#upgrade-a-controller)
* [Juju | `upgrade-controller`](https://juju.is/docs/juju/juju-upgrade-controller)
* [Juju | `upgrade-model`](https://juju.is/docs/juju/juju-upgrade-model)

<!-- LINKS -->

[bootstrap]: https://juju.is/docs/juju/juju-bootstrap
