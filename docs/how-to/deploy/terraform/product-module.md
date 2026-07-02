---
myst:
  html_meta:
    description: "Deploy the Charmed MySQL Terraform product module for a recommended stack including optional TLS and COS monitoring integrations."
---

(product-module)=
# Deploy product module

```{admonition} This feature requires Juju 3
:class: warning

The feature described in this page is **not** available on Juju 2.9.
```

The MySQL **product** Terraform module is the set of recommended charms to be deployed using Terraform, containing only Data Platform-owned charms by default. It could be extended with the addition of TLS and COS (Canonical Observability Stack) charms to build more complex setups.

## Install Terraform tooling

This guide assumes Juju is installed, and you have a cloud controller already bootstrapped - such as {ref}`LXD <lxd>` or {ref}`MicroK8s <microk8s>`. For more information, check the {ref}`deployment guides <deploy>`.

Let's install the Terraform and YQ snaps:

```shell
sudo snap install terraform --classic
sudo snap install yq
```

Switch to the cloud controller and create a new model:

```shell
juju switch <cloud-provider>
juju add-model my-model
juju show-model my-model | yq '."my-model"."model-uuid"'
```

Clone the MySQL bundle repository and navigate to the terraform module:

````{tab-set}
```{tab-item} VM
:sync: vm
    git clone https://github.com/canonical/mysql-bundle.git
    cd terraform
```

```{tab-item} K8s
:sync: k8s
    git clone https://github.com/canonical/mysql-k8s-bundle.git
    cd terraform
```
````

Initialise the Juju Terraform Provider:

```shell
terraform init
```

## Verify the deployment

Open the `main.tf` file to see the brief contents of the Terraform module, and run `terraform plan` to get a preview of the changes that will be made:

```shell
terraform plan -var 'model=<model-uuid>'
```

## Apply the deployment

### Default charms

The default MySQL product module deploys MySQL Server, MySQL Router and S3 Integrator charms.
In order to deploy those resources:

```shell
terraform apply -auto-approve \
    -var 'model=<model-uuid>'
```

### Extended charms

The extended MySQL product module deploys [self-signed-certificates](https://charmhub.io/self-signed-certificates) and [opentelemetry-collector](https://charmhub.io/opentelemetry-collector) charms on top.
In order to deploy all resources:

```shell
terraform apply -auto-approve \
    -var 'model=<model-uuid>' \
    -var 'tls_offer=certificates' \
    -var 'cos_offers={"dashboard"="cos-agent"}'
```

It is possible to substitute both of these charms by overwriting some of the module variables.

For instance, the `self-signed-certificates` charm is used to provide the TLS certificates,
but it is not a _production-ready_ charm. It must be changed before deploying on a real environment.
As an alternative, the [manual-tls-certificates](https://charmhub.io/manual-tls-certificates) could be used.

```shell
terraform apply -auto-approve \
    -var 'model=<model-uuid>' \
    -var 'tls_offer=certificates' \
    -var 'certificates={"app_name"="manual-tls-certificates","base"="ubuntu@22.04","channel"="latest/stable"}'
```

## Configure the deployment

The S3 Integrator charm needs to be configured for it to work properly.
Wait until it reaches `blocked` status and run:

```shell
juju run s3-integrator/leader sync-s3-credentials \
    access-key=<access-key> \
    secret-key=<secret-key>
```

```{seealso}
{ref}`configure-s3-aws`
```

## Check deployment status

Check the deployment status with 

```shell
juju status --model <cloud-provider>:my-model --watch 1s
```

Sample output on machines, where the cloud provider is LXD:

```shell
Model     Controller      Cloud/Region         Version  SLA          Timestamp
my-model  lxd-controller  localhost/localhost  3.5.3    unsupported  12:49:34Z

App            Version          Status  Scale  Charm          Channel        Rev  Exposed  Message                                
mysql          8.0.41-0ubun...  active      3  mysql          8.0/stable     366  no
mysql-router                    unknown     0  mysql-router   dpe/candidate  355  no
s3-integrator                   active      1  s3-integrator  1/stable       241  no

Unit              Workload  Agent  Machine  Public address  Ports           Message
mysql/0*          active    idle   0        10.101.248.220  3306,33060/tcp  Primary
mysql/1           active    idle   1        10.101.248.221                  Primary
mysql/2           active    idle   2        10.101.248.222                  Primary
s3-integrator/0*  active    idle   3        10.101.248.223

Machine  State    Address         Inst id        Base          AZ  Message
0        started  10.101.248.220  juju-c4a403-0  ubuntu@22.04      Running
1        started  10.101.248.221  juju-c4a403-1  ubuntu@22.04      Running
2        started  10.101.248.222  juju-c4a403-2  ubuntu@22.04      Running
3        started  10.101.248.223  juju-c4a403-3  ubuntu@22.04      Running
```

Continue to operate the charm as usual from here or apply further Terraform changes.

## Clean up

To keep the house clean, remove the newly deployed MySQL charm by running

```shell
terraform destroy -var 'model=<model-uuid>'
```

Feel free to {ref}`contact us <contacts>` if you have any question and collaborate with us on GitHub!

