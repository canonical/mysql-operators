# How to refresh a single cluster

This guide covers refresh for single cluster MySQL deployments. To refresh a multi-cluster deployment, see [](/how-to/refresh/multi-cluster/refresh-multi-cluster) first.

## Important information

**Check if your current Juju version is compatible with the new charm version**.

For information about charm versions, see [](/reference/releases).

To upgrade Juju, see [](/how-to/refresh/upgrade-juju).

**Create and test a backup of your data before running any type of refresh.** See [](/how-to/back-up-and-restore/create-a-backup).

**It is recommended to integrate your application with [Charmed MySQL Router K8s](https://charmhub.io/mysql-router-k8s).** This will ensure minimal service disruption, if any.

## Summary of the upgrade steps

1. [**Collect**](step-1-collect) all necessary pre-refresh information. It will be necessary for the rollback (if requested). Do not skip this step!
2. [**Scale-up** (optional)](step-2-scale-up-optional). The new unit will be the first one to be updated, and it will simplify the rollback procedure a lot in case of the upgrade failure.
3. [**Prepare**](step-3-prepare) the Charmed MySQL K8s application for the in-place refresh.
4. [**Configure**](step-4-configure) what would happen after each unit refresh.
5. [**Refresh**](step-5-refresh). Once started, only one unit in a cluster will be upgraded. In case of failure, the rollback is simple: remove newly added pod (via [step 2](step-2-scale-up-optional)).
6. [**Resume** refresh](step-6-resume). If the new pod is OK, the refresh can be resumed for all other units in the cluster. All units in a cluster will be executed sequentially from the largest ordinal number to the lowest. 
7. Consider a [**rollback**](step-7-rollback-optional) in case of disaster. Please inform and include us in your case scenario troubleshooting to trace the source of the issue and prevent it in the future. [Contact us](/reference/contacts)!
8. [**Scale-back** (optional)](step-8-scale-back). Remove no longer necessary K8s pod created in step 2 (if any).
9. [Post-upgrade **check**](step-9-check). Make sure all units are in a healthy state.


(step-1-collect)=
## Step 1: Collect

```{note}
This step is only valid when deploying from [Charmhub](https://charmhub.io/mysql-k8s). 

If a [local charm](https://juju.is/docs/sdk/deploy-a-charm) is deployed (revision is small, e.g. 0-10), make sure the proper/current local revision of the `.charm` file is available BEFORE going further. You might need it for a rollback.
```

The first step is to record the revision of the running application as a safety measure for a rollback action. To accomplish this, run the `juju status` command and look for the deployed Charmed MySQL K8s revision in the command output, e.g:

```shell
Model      Controller  Cloud/Region        Version  SLA          Timestamp
my-model   mkc         microk8s/localhost  3.6.13   unsupported  01:20:47Z

App        Version  Status  Scale  Charm      Channel   Rev  Address         Exposed  Message
mysql-k8s  8.4.7    active      3  mysql-k8s  8.4/edge  XXX  10.152.183.102  no       Primary

Unit          Workload  Agent  Address       Ports  Message
mysql-k8s/0*  active    idle   10.1.148.184         Primary
mysql-k8s/1   active    idle   10.1.148.138         
mysql-k8s/2   active    idle   10.1.148.143
```

For this example, the current revision is `XXX`. Store it safely to use in case of rollback!

(step-2-scale-up-optional)=
## Step 2: Scale-up (optional)

Optionally, it is recommended to scale the application up by one unit before starting the upgrade process.

The new unit will be the first one to be updated, and it will assert that the upgrade is possible. In case of failure, having the extra unit will ease a future rollback procedure without disrupting service. 

```shell
juju scale-application mysql-k8s <total number of units desired>
```

To scale up by 1 unit, `<total number of units desired>` would be the current number of units + 1 

Wait for the new unit to be ready.

(step-3-prepare)=
## Step 3: Prepare

After the application has settled, it’s necessary to run the `pre-refresh-check` action against the leader unit:

```shell
juju run mysql-k8s/leader pre-refresh-check
```

The output of the action should look like:

```yaml
unit-mysql-k8s-0:
  UnitId: mysql-k8s/0
  ...
  results: {}
  status: completed
  ...
```

The action will configure the charm to minimize the amount of primary switchover, among other preparations for a safe refresh process. After successful execution, the charm is ready to be refreshed.

(step-4-configure)=
## Step 4: Configure `pause-after-unit-refresh`

After each unit is refreshed, the charm will perform automatic health checks.
We recommend supplementing the automatic checks with manual checks.

Examples of manual checks:
* Database clients are healthy and can connect to the refreshed units
* Transactions per second and resource consumption (CPU, memory, disk) are similar on refreshed and non-refreshed units
* Leaving the application in a partially-refreshed state (only some units refreshed) for several weeks and monitoring that the new version is stable in your environment

To facilitate your manual checks, the application can be configured to pause the refresh and wait for your confirmation.

Set the `pause-after-unit-refresh` config option to:
* `all` to wait for your confirmation after each unit refreshes
* `first` (default) to wait for your confirmation once, after the first unit refreshes
* `none` to never wait for your confirmation

For example:
```shell
juju config mysql-k8s pause-after-unit-refresh=all
```

```{note}
If the charm's automatic health checks fail, the refresh will be paused (until those health checks succeed) regardless of the value of the `pause-after-unit-refresh` config option.
```

(step-5-refresh)=
## Step 5: Refresh

If you are refreshing multiple clusters, make sure to refresh the standby clusters first. See [](/how-to/refresh/multi-cluster/refresh-multi-cluster) for more information.

Use the [`juju refresh`](https://juju.is/docs/juju/juju-refresh) command to trigger the charm upgrade process.

Example with channel selection

```shell
juju refresh mysql-k8s --channel 8.4/edge --trust
```

Example with specific revision selection (do not forget the OCI resource):

```shell
juju refresh mysql-k8s --revision=YYY --resource mysql-image=...  --trust
```

The upgrade will execute only on the highest ordinal unit.

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

For the running example `mysql-k8s/2`, `juju status` would look similar to the output below:

```shell
Model      Controller  Cloud/Region        Version  SLA          Timestamp
my-model   mkc         microk8s/localhost  3.6.13   unsupported  01:20:47Z

App        Version  Status  Scale  Charm      Channel   Rev  Address         Exposed  Message
mysql-k8s  8.4.7    waiting     3  mysql-k8s  8.4/edge  YYY  10.152.183.102  no       waiting for units to settle down

Unit          Workload     Agent      Address       Ports  Message
mysql-k8s/0*  active       idle       10.1.148.184         other units upgrading first...
mysql-k8s/1   active       idle       10.1.148.138         other units upgrading first...
mysql-k8s/2   active       idle       10.1.148.143         other units upgrading first...
mysql-k8s/3   maintenance  executing  10.1.148.145         upgrading unit
```

**Please be patient during huge installations.**
Each unit should recover shortly after the refresh, but time can vary depending on the amount of data written to the cluster while the unit was not part of it. 

**Incompatible charm revisions or dependencies will halt the process.**
After a `juju refresh`, if there are any version incompatibilities in charm revisions, its dependencies, or any other unexpected failure in the refresh process, the refresh will be halted and enter a failure state.

(step-6-resume)=
## Step 6: Resume

After the unit is refreshed, the charm will set the unit refresh state as completed. 

If the unit is healthy within the cluster, the next step is to resume the refresh process by running:

```shell
juju run mysql-k8s/leader resume-refresh
```

`resume-refresh` will rollout the upgrade for the following unit, always from highest ordinal number to lowest, and for each successful upgraded unit, the process will rollout the next automatically.

```shell
Model      Controller  Cloud/Region        Version  SLA          Timestamp
my-model   mkc         microk8s/localhost  3.6.13   unsupported  01:20:47Z

App        Version  Status  Scale  Charm      Channel   Rev  Address         Exposed  Message
mysql-k8s  8.4.7    waiting     3  mysql-k8s  8.4/edge  YYY  10.152.183.102  no       waiting for units to settle down

Unit          Workload     Agent      Address       Ports  Message
mysql-k8s/0*  active       idle       10.1.148.184         other units upgrading first...
mysql-k8s/1   maintenance  executing  10.1.148.138         upgrading unit
mysql-k8s/2   active       idle       10.1.148.143         
mysql-k8s/3   active       idle       10.1.148.145 
```

(step-7-rollback-optional)=
## Step 7: Rollback (optional)

If there was an issue with the refresh, even if the underlying MySQL cluster continues to work, it’s important to roll back the charm to the previous revision. 

The update can be attempted again after a further inspection of the failure. 

See: [](/how-to/refresh/single-cluster/roll-back-single-cluster) 

(step-8-scale-back)=
## Step 8: Scale-back

If the application scale was changed for the upgrade procedure, it is now safe to scale it back to the desired unit count:

```shell
juju scale-application mysql-k8s <total number of units desired>
```

To scale down by 1 unit, `<total number of units desired>` would be the current number of units - 1 

Example:

[![asciicast](https://asciinema.org/a/7ZMAsPWU3wv7ynZI1JvgRFG31.png)](https://asciinema.org/a/7ZMAsPWU3wv7ynZI1JvgRFG31)

(step-9-check)=
## Step 9: Check

Use `juju status` to make sure the cluster [state](/reference/charm-statuses) is OK.
