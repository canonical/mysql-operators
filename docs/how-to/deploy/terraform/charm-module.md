---
myst:
  html_meta:
    description: "Deploy the Charmed MySQL Terraform charm module using the Juju provider: install Terraform, clone the repo, initialize, and verify deployment."
---

(charm-module)=
# Deploy charm module

The MySQL **charm** Terraform module is the smallest unit that can be deployed using Terraform, containing only the MySQL Server charm. It is designed to be deployed alongside other charms to build a more complex setup.

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

Clone the MySQL operators repository and navigate to the terraform module:

````{tab-set}
```{tab-item} VM
:sync: vm

    git clone https://github.com/canonical/mysql-operators.git
    cd machines/terraform
```

```{tab-item} K8s
:sync: k8s

    git clone https://github.com/canonical/mysql-operators.git
    cd kubernetes/terraform
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

If everything looks correct, deploy the resources (skip the approval):

```shell
terraform apply -auto-approve -var 'model=<model-uuid>'
```

## Check deployment status

Check the deployment status with 

```shell
juju status --model <cloud-provider>:my-model --watch 1s
```

Sample output on machines, where the cloud provider is LXD:

```shell
Model     Controller      Cloud/Region         Version  SLA          Timestamp
my-model  lxd-controller  localhost/localhost  3.6.14   unsupported  12:49:34Z

App    Version  Status  Scale  Charm  Channel     Rev  Exposed  Message
mysql  8.4.7    active      1  mysql  8.4/edge         no

Unit      Workload  Agent  Machine  Public address  Ports           Message
mysql/0*  active    idle   0        10.101.248.220  3306,33060/tcp  Primary

Machine  State    Address         Inst id        Base          AZ  Message
0        started  10.101.248.220  juju-c4a403-0  ubuntu@24.04      Running
```

Continue to operate the charm as usual from here or apply further Terraform changes.

## Clean up

To keep the house clean, remove the newly deployed MySQL charm by running

```shell
terraform destroy -var 'model=<model-uuid>'
```

Feel free to {ref}`contact us <contacts>` if you have any question and collaborate with us on GitHub!
