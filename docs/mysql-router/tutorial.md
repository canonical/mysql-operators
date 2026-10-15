(tutorial-router)=
# Tutorial

This hands-on tutorial aims to help you learn how to deploy Charmed MySQL Router on LXD or Kubernetes and become familiar with its available operations.

If you are not sure which path to take, we recommend following this tutorial on LXD by following the "VM" tabs.

## Prerequisites

While this tutorial intends to guide you as you deploy Charmed MySQL and MySQL Router for the first time, it will be most beneficial if:
- You have some experience using a Linux-based CLI
- You are familiar with MySQL concepts such as replication and users.
- Your computer fulfils the {ref}`minimum system requirements <system-requirements>`

---

## Set up the environment

First, we will set up a cloud environment using [Multipass](https://multipass.run/) with [LXD](https://documentation.ubuntu.com/lxd/latest/), [MicroK8s](https://microk8s.io/docs) and [Juju](https://documentation.ubuntu.com/juju/3.6/). This is the quickest and easiest way to get your machine ready for using Charmed MySQL.

### Create a Multipass VM

```{include} ../tutorial.md
    :start-after: "<!--start:multipass-vm-->"
    :end-before: "<!--end:multipass-vm-->"
```

### Set up Juju

```{include} ../tutorial.md
    :start-after: "<!--start:set-up-juju-->"
    :end-before: "<!--end:set-up-juju-->"
```

## Deploy Charmed MySQL and MySQL Router

To deploy the two charms, run the following commands:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju deploy mysql --channel 8.4/stable
```
```{terminal}
:user: ubuntu
:host: my-vm

juju deploy mysql-router --channel 8.4/stable
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju deploy mysql-k8s --channel 8.4/stable --trust
```
```{terminal}
:user: ubuntu
:host: my-vm

juju deploy mysql-router-k8s --channel 8.4/stable --trust
```
````
`````

Juju will now fetch the charms from [Charmhub](https://charmhub.io/) and deploy them to LXD or a MicroK8s cloud. This process can take several minutes depending on how provisioned (RAM, CPU, etc) your machine is.

You can track the progress by running:

```{terminal}
:user: ubuntu
:host: my-vm

juju status --watch 1s
```

```{tip}
You can open a separate terminal window, enter the same Multipass VM, and keep `juju status --watch 1s` permanently running in it.
```

When the application is ready, `juju status` will show something similar to the sample output below:

`````{tab-set}
````{tab-item} VM
:sync: vm

```text
Model     Controller  Cloud/Region         Version  SLA          Timestamp
tutorial  overlord    localhost/localhost  3.6.19   unsupported  22:33:45+01:00

App               Version  Status   Scale  Charm             Channel     Rev    Exposed  Message
mysql             8.4.10   active       1  mysql             8.4/stable         no
mysql-router      8.4.10   blocked      1  mysql-router      8.4/stable         no       Missing relation: backend-database

Unit              Workload  Agent  Machine  Public address  Ports           Message
mysql/0*          active    idle            10.234.188.135  3306,33060/tcp  Primary
mysql-router/0*   active    idle

```
````

````{tab-item} K8s
:sync: k8s

```text
Model     Controller  Cloud/Region        Version  SLA          Timestamp
tutorial  overlord    microk8s/localhost  3.6.19   unsupported  22:33:45+01:00

App               Version  Status   Scale  Charm             Channel     Rev  Address        Exposed  Message
mysql-k8s         8.4.10   active       1  mysql-k8s         8.4/stable       10.152.183.68  no
mysql-router-k8s  8.4.10   blocked      1  mysql-router-k8s  8.4/stable       10.152.183.52  no       Missing relation: backend-database

Unit                 Workload  Agent  Address     Ports  Message
mysql-k8s/0*         active    idle   10.1.12.36         Primary
mysql-router-k8s/0*  active    idle   10.1.12.14
```
````
`````

At this stage, MySQL Router will stay in a blocked state because it is missing an integration with MySQL.

To integrate them, run

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: user
:host: my-vm

juju integrate mysql mysql-router
```
````
````{tab-item} K8s
:sync: k8s

```{terminal}
:user: user
:host: my-vm

juju integrate mysql-k8s mysql-router-k8s
```
````
`````

Now, `juju status` will report new type of blocked state: `Missing relation: database` as it waits for a client to consume DB service.

In this tutorial, we will connect to the [data integrator charm](https://charmhub.io/data-integrator). This is a bare-bones charm that allows for central management of database users. It automatically provides credentials and endpoints that are needed to connect with a charmed database application.

Deploy `data-integrator`, associate it to a new database called `test-database`, and relate it to MySQL Router:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: user
:host: my-vm
juju deploy data-integrator --config database-name=test-database
```
```{terminal}
:user: user
:host: my-vm

juju integrate data-integrator mysql-router
```
````
````{tab-item} K8s
:sync: k8s

```{terminal}
:user: user
:host: my-vm

juju deploy data-integrator --config database-name=test-database
```
```{terminal}
:user: user
:host: my-vm

juju integrate data-integrator mysql-router-k8s
```
````
`````

In a few seconds, its status will no longer be blocked.

## Access the database

Connecting to the database requires that you know the values for `host`, `username` and `password`. To retrieve the necessary fields, run data-integrator action `get-credentials`:

```{terminal}
:user: user
:host: my-vm

juju run data-integrator/leader get-credentials
```

This should return the `username` and `password`

The `host` value is the IP address that can be found with `juju status` (the application hosting the MySQL Router application):


To access the MySQL database via MySQL Router, choose read-write (port 6446) or read-only (port 6447) endpoints:

```{terminal}
:user: user
:host: my-vm

mysql -h 10.152.183.52 -P6446 -urelation-4-6 -pNu7wK85QU7dpVX66X56lozji test-database
```

Inside the MySQL shell, list the databases available on the host with `show databases`:

```shell
mysql> show databases;
+--------------------+
| Database           |
+--------------------+
| information_schema |
| performance_schema |
| test-database      |
+--------------------+
3 rows in set (0.00 sec)

```

You can now interact with MySQL directly using any [MySQL Queries](https://dev.mysql.com/doc/refman/8.4/en/entering-queries.html). For example entering `SELECT VERSION(), CURRENT_DATE;` should output something like:

```shell
mysql> SELECT VERSION(), CURRENT_DATE;
+------------------------+--------------+
| VERSION()              | CURRENT_DATE |
+------------------------+--------------+
| 8.4.7-0ubuntu0.26.04.1 | 2026-01-22   |
+------------------------+--------------+
1 row in set (0.00 sec)
```

Feel free to test out any other MySQL queries. When you’re ready to leave the MySQL shell you can just type `exit`. Now you will be in your original shell where you first started the tutorial; here you can interact with Juju and LXD.

## Remove or reset the user

Removing the integration automatically removes the user that was created when the integration was created.

To remove the integration, run the following command:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju remove-relation data-integrator mysql
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju remove-relation data-integrator mysql-k8s
```
````
`````

If you try to connect to the same MySQL you just used in {ref}`access-the-integrated-database`, you'll get an "Access denied" error. This is expected, since the user no longer exists after removing the integration. However, note that **data remains on the server** at this stage.

To create a user again, re-integrate the applications:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju integrate data-integrator mysql-router
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju integrate data-integrator mysql-router-k8s
```
````
`````

Re-integrating generates a new user and password. You can obtain these credentials as before, with the `get-credentials` action, and connect to the database with this new credentials.

From here you will see all of your data is still present in the database.

## Scale MySQL Router units

To add two more units to your MySQL Router deployment, run

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju add-unit mysql-router -n 2
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju scale-application mysql-router-k8s 3
```
````
`````

You can now watch the scaling process in live using: `juju status --watch 1s`. It usually takes several minutes for new cluster members to be added. You’ll know that all three nodes are in sync when `juju status` reports:
- Workload is `active`.
- Agent is `idle`.

`````{tab-set}
````{tab-item} VM
:sync: vm

```shell
Model     Controller  Cloud/Region        Version  SLA          Timestamp
tutorial  overlord    microk8s/localhost  3.6.19   unsupported  22:48:57+01:00

App               Version  Status  Scale  Charm             Channel     Rev  Address         Exposed  Message
data-integrator            active      1  data-integrator   stable       13  10.152.183.142  no
mysql             8.4.10   active      1  mysql             8.4/stable       10.152.183.68   no
mysql-router      8.4.10   active      3  mysql-router      8.4/stable       10.152.183.52   no

Unit                 Workload  Agent  Address     Ports  Message
data-integrator/0*   active    idle   10.1.12.3
mysql/0*             active    idle   10.1.12.36         Primary
mysql-router/0*      active    idle   10.1.12.14
mysql-router/1       active    idle   10.1.12.32
mysql-router/2       active    idle   10.1.12.31
```
````

````{tab-item} K8s
:sync: k8s

```shell
Model     Controller  Cloud/Region        Version  SLA          Timestamp
tutorial  overlord    microk8s/localhost  3.6.19   unsupported  22:48:57+01:00

App               Version  Status  Scale  Charm             Channel     Rev  Address         Exposed  Message
data-integrator            active      1  data-integrator   stable       13  10.152.183.142  no
mysql-k8s         8.4.10   active      1  mysql-k8s         8.4/stable       10.152.183.68   no
mysql-router-k8s  8.4.10   active      3  mysql-router-k8s  8.4/stable       10.152.183.52   no

Unit                 Workload  Agent  Address     Ports  Message
data-integrator/0*   active    idle   10.1.12.3
mysql-k8s/0*         active    idle   10.1.12.36         Primary
mysql-router-k8s/0*  active    idle   10.1.12.14
mysql-router-k8s/1   active    idle   10.1.12.32
mysql-router-k8s/2   active    idle   10.1.12.31
```
````
`````

You can scale Charmed MySQL in the same way:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju add-unit mysql -n 2
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju scale-application mysql-k8s 3
```
````
`````

Make sure all units are active using `juju status`.

```{note}
The maximum number of Charmed MySQL units in a single Juju application is 9. This is a limitation of MySQL replication. 

Read more about all limitations in the [official MySQL documentation](https://dev.mysql.com/doc/refman/8.4/en/group-replication-limitations.html).
```

### Remove units

Removing a unit from the application scales the replicas down.

`````{tab-set}
````{tab-item} VM
:sync: vm

On VM, specify the unit to remove (in this example, `mysql-router/2`):

```{terminal}
:user: ubuntu
:host: my-vm

juju remove-unit mysql-router/2
```
````

````{tab-item} K8s
:sync: k8s

On K8s, specify the desired number of units:

```{terminal}
:user: ubuntu
:host: my-vm

juju scale-application mysql-router-k8s 2
```
````
`````

## Enable encryption with TLS

[Transport Layer Security (TLS)](https://en.wikipedia.org/wiki/Transport_Layer_Security) is a protocol used to encrypt data exchanged between two applications. Essentially, it secures data transmitted over a network.

Typically, enabling TLS internally within a highly available database or between a highly available database and client/server applications requires a high level of expertise. This has all been encoded into Charmed MySQL so that configuring TLS requires minimal effort on your end.

TLS is enabled by integrating Charmed MySQL with the [Self-signed certificates charm](https://charmhub.io/self-signed-certificates). This charm centralises TLS certificate management consistently and handles operations like providing, requesting, and renewing TLS certificates.

```{caution}
**[Self-signed certificates](https://en.wikipedia.org/wiki/Self-signed_certificate) are not recommended for a production environment.**

Check [this guide](https://discourse.charmhub.io/t/11664) for an overview of the TLS certificates charms available.
```

Before enabling TLS on Charmed MySQL, we must deploy the `self-signed-certificates` charm:

```{terminal}
:scroll:
:user: ubuntu
:host: my-vm

juju deploy self-signed-certificates --channel 1/stable --config ca-common-name="Tutorial CA"
```

Wait until `self-signed-certificates` is up and active, using `juju status --watch 1s` to monitor its progress:

`````{tab-set}
````{tab-item} VM
:sync: vm


```text
Model 	Controller  Cloud/Region     	Version  SLA      	Timestamp
database  lxd     	localhost/localhost  3.6.19	 unsupported  18:47:51Z

App                   	  Version  Status  Scale  Charm                 	Channel 	Rev  Exposed  Message
mysql                 	  8.4.10   active  	   1  mysql                     8.4/stable       no
mysql-router          	  8.4.10   active  	   1  mysql-router              8.4/stable       no
mysql-test-app        	  0.0.2    active  	   1  mysql-test-app            stable      36   no
self-signed-certificates           active  	   1  self-signed-certificates  stable      72   no

Unit                     	 Workload  Agent  Machine  Public address  Ports       	   Message
mysql-test-app/0*        	 active	   idle         1  10.205.193.227
  mysql-router/0*        	 active	   idle        	   10.205.193.227
mysql/0*                 	 active	   idle         0  10.205.193.171  3306,33060/tcp  Primary
self-signed-certificates/0*  active	   idle         2  10.205.193.175

Machine  State	  Address         Inst id        Base          AZ  Message
0    	 started  10.205.193.171  juju-3c2f36-0  ubuntu@26.04  	   Running
1    	 started  10.205.193.227  juju-3c2f36-1  ubuntu@26.04  	   Running
2    	 started  10.205.193.175  juju-3c2f36-2  ubuntu@26.04  	   Running
```
````

````{tab-item} K8s
:sync: k8s

```shell
Model 	  Controller  Cloud/Region    	  Version  SLA          Timestamp
database  k8s     	  microk8s/localhost  3.6.19   unsupported  12:10:33Z

App                   	Version  Status  Scale  Charm                 	 Channel 	 Rev  Address     	  Exposed  Message
mysql-k8s             	8.4.10    active  	1  mysql-k8s             	 8.4/stable       10.152.183.101  no
mysql-router-k8s      	8.4.10    active  	1  mysql-router-k8s      	 8.4/stable	      10.152.183.92   no
mysql-test-app        	0.0.2    active  	1  mysql-test-app        	 stable   	  36  10.152.183.224  no
self-signed-certificates         active  	1  self-signed-certificates  stable   	  72  10.152.183.114  no

Unit                     	 Workload  Agent  Address   	Ports  Message
mysql-k8s/0*             	 active    idle   10.1.241.252         Primary
mysql-router-k8s/0*      	 active    idle   10.1.241.253
mysql-test-app/0*        	 active    idle   10.1.241.254
self-signed-certificates/0*  active    idle   10.1.241.255
```
````
`````

To enable TLS on Charmed MySQL Router, integrate the two applications:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju integrate mysql-router self-signed-certificates
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju integrate mysql-router-k8s self-signed-certificates
```
````
`````

Use `openssl` to connect to MySQL Router and check the TLS certificate in use:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju ssh mysql-router/0 "openssl s_client -showcerts -starttls mysql -unix /var/snap/charmed-mysql/common/run/mysqlrouter/mysql.sock < /dev/null  | openssl x509 -text | grep Issuer"

...
    Issuer: C = US, CN = Tutorial CA
...
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju ssh mysql-router-k8s/0 "openssl s_client -showcerts -starttls mysql -connect 127.0.0.1:6446  < /dev/null  | openssl x509 -text | grep Issuer"

...
    Issuer: C = US, CN = Tutorial CA
...
```
````
`````

Congratulations! MySQL Router is now using a TLS certificate generated by the external application `self-signed-certificates`.

To remove the external TLS and return to the locally generated one, unrelate the applications:

`````{tab-set}
````{tab-item} VM
:sync: vm

```{terminal}
:user: ubuntu
:host: my-vm

juju remove-relation mysql-router self-signed-certificates
```
````

````{tab-item} K8s
:sync: k8s

```{terminal}
:user: ubuntu
:host: my-vm

juju remove-relation mysql-router-k8s self-signed-certificates
```
````
`````

Now, if you check the certificates again with `openssl` you'll see an output similar to:

```
Issuer: CN = MySQL_Router_Auto_Generated_CA_Certificate
```

The Charmed MySQL Router application reverted to the placeholder certificate that was created locally during the installation.

## Clean up your environment

To exit the Multipass VM, press {kbd}`Ctrl` + {kbd}`D` or type `exit`.

If you'd like to keep your MySQL environment for later, simply stop your VM with:

```{terminal}
:user: user
:host: my-pc

multipass stop my-vm
```

If you're done with testing and would like to free up resources on your machine, you can remove the VM entirely.

```{caution}
When you remove VM as shown below, you will lose all the data in MySQL and any other applications inside Multipass VM!

For more information, see the docs for [`multipass delete`](https://multipass.run/docs/delete-command).
```

**Delete your VM and its data** by running:

```{terminal}
:user: user
:host: my-pc

multipass delete --purge my-vm
```