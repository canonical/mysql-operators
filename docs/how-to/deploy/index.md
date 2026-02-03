(deploy)=
# How to deploy MySQL

The basic requirements for deploying a charm are the [Juju client](https://documentation.ubuntu.com/juju/3.6/) and a [cloud](https://documentation.ubuntu.com/juju/3.6/reference/cloud/) .

If you are not sure where to start, or would like a more guided walkthrough for setting up your environment, see the {ref}`tutorial`.

## Quickstart

Charmed MySQL can be deployed using the Juju CLI directly, or via Terraform.

To deploy via the **Juju CLI**, you need to first [boostrap](https://juju.is/docs/juju/juju-bootstrap) a cloud controller and create a [model](https://canonical-juju.readthedocs-hosted.com/en/latest/user/reference/model/):

```shell
juju bootstrap <cloud name> <controller name>
juju add-model <model name>
```

Then, use the [`juju deploy`](https://canonical-juju.readthedocs-hosted.com/en/latest/user/reference/juju-cli/list-of-juju-cli-commands/deploy/) command:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju deploy mysql --channel 8.0/stable
```

```{tab-item} K8s
:sync: k8s

    juju deploy mysql-k8s --channel 8.0/stable --trust
```
````

To deploy via **Terraform**, see the {ref}`Terraform guide <terraform>`.

## Clouds

Charmed MySQL can be deployed on several machine and Kubernetes cloud services.

```{toctree}
:titlesonly:

Machine clouds <vm-clouds/index>
K8s clouds <k8s-clouds/index>
```

## Additional deployment scenarios

```{toctree}
:titlesonly:

Terraform <terraform/index>
Airgapped <airgapped>
Multi-AZ <multi-az/index>
Juju spaces <juju-spaces>
```
