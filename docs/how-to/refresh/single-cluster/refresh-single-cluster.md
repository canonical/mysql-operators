(refresh-single-cluster)=
# How to refresh a single cluster

This guide covers refresh for single cluster MySQL deployments. To refresh a multi-cluster deployment, see {ref}`refresh-multi-cluster` first.

## Important information

**Check if your current Juju version is compatible with the new charm version**.

For information about charm versions, see {ref}`release-notes`.

To upgrade Juju, see {ref}`upgrade-juju`

**Create and test a backup of your data before running any type of refresh.** See {ref}`create-a-backup`.

**It is recommended to integrate your application with [Charmed MySQL Router](https://charmhub.io/mysql-router).** This will ensure minimal service disruption, if any.

## Step 1: Record revision information

```{note}
This step is only valid when deploying from [Charmhub](https://charmhub.io/mysql). 

If a [local charm](https://juju.is/docs/sdk/deploy-a-charm) is deployed (revision is small, e.g. 0-10), make sure the proper/current local revision of the `.charm` file is available BEFORE going further. You might need it for a rollback.
```

The first step is to record the revision of the running application as a safety measure for a rollback action. To accomplish this, run the `juju status` command and look for the deployed Charmed MySQL revision in the command output.

Example output for Charmed MySQL on a machine controller:

```shell
Model    Controller  Cloud/Region         Version  SLA          Timestamp
example  lxd         localhost/localhost  3.5.2    unsupported  17:58:37Z

App    Version          Status  Scale  Charm  Channel  Rev  Exposed  Message
mysql  8.0.39-0ubun...  active      3  mysql           182  no       

Unit       Workload  Agent  Machine  Public address  Ports               Message
mysql/9    active    idle   13       10.169.158.70   3306/tcp,33060/tcp  
mysql/10*  active    idle   11       10.169.158.14   3306/tcp,33060/tcp  Primary
mysql/11   active    idle   12       10.169.158.217  3306/tcp,33060/tcp  

Machine  State    Address         Inst id         Series  AZ  Message
11       started  10.169.158.14   juju-b72e25-11  jammy       Running
12       started  10.169.158.217  juju-b72e25-12  jammy       Running
13       started  10.169.158.70   juju-b72e25-13  jammy       Running
```

For this example, the current revision is `182`. Store it safely to use in case of rollback!

## Step 2: Scale up (optional)

With Charmed MySQL for Kubernetes, it is recommended to scale the application up by one unit before starting the upgrade process.

The new unit will be the first one to be updated, and it will assert that the upgrade is possible. In case of failure, having the extra unit will ease a future rollback procedure without disrupting service. 

```shell
juju scale-application mysql-k8s <total number of units desired>
```

To scale up by 1 unit, `<total number of units desired>` would be the current number of units + 1 

Wait for the new unit to be ready.

## Step 3: Pre-upgrade check

Before refreshing, it is necessary to run the `pre-upgrade-check` action against the {ref}`leader unit <primary-vs-leader-unit>`:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader pre-upgrade-check

The output of the action should look like:

    unit-mysql-10:
      ...
      results: {}
      status: completed
      ...
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader pre-upgrade-check

The output of the action should look like:

    unit-mysql-k8s-0:
      UnitId: mysql-k8s/0
      ...
      results: {}
      status: completed
      ...
```
````

```{admonition} Juju 2.9 users
:class: tip

Remember that `juju run <action name>` becomes `juju run-action <action name> --wait`.

See also: {ref}`breaking-changes-juju`
```

The action will configure the charm to minimize the amount of primary switchover, among other preparations for a safe refresh process. After successful execution, the charm is ready to be refreshed.

## Step 4: Refresh

If you are refreshing multiple clusters, make sure to refresh the standby clusters first. See {ref}`refresh-multi-cluster for more information.

Use the [`juju refresh`](https://juju.is/docs/juju/juju-refresh) command to trigger the charm refresh process. 

````{tab-set}
```{tab-item} VM
:sync: vm

Example with channel selection:

    juju refresh mysql --channel 8.0/stable


Example with specific revision selection:

    juju refresh mysql --revision=366


Example with a local charm file:

    juju refresh mysql --path ./mysql_ubuntu-22.04-amd64.charm
```

```{tab-item} K8s
:sync: k8s

Example with channel selection:

    juju refresh mysql-k8s --channel 8.0/edge --trust


Example with specific revision selection( do not forget the OCI resource):

    juju refresh mysql-k8s --revision=89 --resource mysql-image=...  --trust
```
````

```{admonition} During an ongoing refresh
:class: warning

**Do NOT perform any other extraordinary operations on the cluster**, such as:

* Adding or removing units
* Creating or destroying new relations
* Changes in workload configuration
* Refreshing other connected/related/integrated applications simultaneously

Concurrency with other operations is not supported, and it can lead the cluster into inconsistent states.

**Do NOT trigger a rollback**. Status changes during the process are expected (e.g. `waiting`, `maintenance`, `active`) 

Make sure the refresh has failed/stopped and cannot be continued before triggering a rollback.
```

Once the `refresh` command is executed, all units will receive new charm content. The refresh will run on one unit at a time. 

````{tab-set}
```{tab-item} VM
:sync: vm

After each unit completes the refresh, the message `refresh completed` is displayed, and the next unit follows.

Example `juju status` during an refresh:


    Model    Controller  Cloud/Region         Version  SLA          Timestamp
    example  lxd         localhost/localhost  3.5.2    unsupported  18:11:21Z

    App    Version          Status  Scale  Charm  Channel  Rev  Exposed  Message
    mysql  8.0.39-0ubun...  active      3  mysql             7  no       

    Unit       Workload     Agent      Machine  Public address  Ports               Message
    mysql/9    maintenance  executing  13       10.169.158.70   3306/tcp,33060/tcp  upgrading snap...
    mysql/10*  waiting      idle       11       10.169.158.14   3306/tcp,33060/tcp  other units upgrading first...
    mysql/11   maintenance  idle       12       10.169.158.217  3306/tcp,33060/tcp  upgrade completed

    Machine  State    Address         Inst id         Series  AZ  Message
    11       started  10.169.158.14   juju-b72e25-11  jammy       Running
    12       started  10.169.158.217  juju-b72e25-12  jammy       Running
    13       started  10.169.158.70   juju-b72e25-13  jammy       Running
```

```{tab-item} K8s
:sync: k8s

After the unit is upgraded, the charm will set the unit upgrade state as completed. 

If the unit is healthy within the cluster, the next step is to resume the upgrade process by running:

    juju run mysql-k8s/leader resume-upgrade

`resume-upgrade` will rollout the upgrade for the following unit, always from highest ordinal number to lowest, and for each successful upgraded unit, the process will rollout the next automatically.

    Model      Controller  Cloud/Region        Version  SLA          Timestamp
    example    k8s         microk8s/localhost  3.5.2    unsupported  01:20:47Z

    App        Version                  Status  Scale  Charm      Channel  Rev  Address         Exposed  Message
    mysql-k8s  8.0.32-0ubuntu0.22.04.2  waiting     3  mysql-k8s  8.0/edge  89  10.152.183.102  no       waiting for units to settle down

    Unit          Workload     Agent      Address       Ports  Message
    mysql-k8s/0*  active       idle       10.1.148.184         other units upgrading first...
    mysql-k8s/1   maintenance  executing  10.1.148.138         upgrading unit
    mysql-k8s/2   active       idle       10.1.148.143         
    mysql-k8s/3   active       idle       10.1.148.145 
```
````

**Please be patient during huge installations.**
Each unit should recover shortly after the refresh, but time can vary depending on the amount of data written to the cluster while the unit was not part of it. 

**Incompatible charm revisions or dependencies will halt the process.**
After a `juju refresh`, if there are any version incompatibilities in charm revisions, its dependencies, or any other unexpected failure in the refresh process, the refresh will be halted and enter a failure state.

## Step 5: Roll back

If there was an issue with the refresh, even if the underlying MySQL cluster continues to work, it’s important to roll back the charm to the previous revision. 

The update can be attempted again after a further inspection of the failure. 

See: {ref}`roll-back-single-cluster` 

## Step 6: Check cluster health

Use `juju status` to make sure the cluster {ref}`state <charm-statuses>` is OK.
