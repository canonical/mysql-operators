---
myst:
  html_meta:
    description: "Configure the s3-integrator charm to use Ceph RadosGW S3-compatible storage for Charmed MySQL backups using the MinIO client."
---

(configure-s3-radosgw)=
# Configure S3 for RadosGW

Charmed MySQL backups can be stored on any S3-compatible storage. S3 access and configurations are managed with the [S3-integrator charm](https://charmhub.io/s3-integrator?channel=2/edge).

This guide will teach you how to deploy and configure the S3-integrator charm on Ceph via [RadosGW](https://docs.ceph.com/en/quincy/man/8/radosgw/), send the configuration to a Charmed MySQL application, and update it. 

```{seealso}
{ref}`configure-s3-aws`
```

## Create the S3 bucket (optional)

Version 2 of the `s3-integrator` charm automatically creates the bucket upon configuration if it does not exist or it is not accessible. Therefore, the bucket does not need to be manually created before passing its name to the integrator charm, although this option allows for a more flexible policy specification.

## Configure the integrator

First, install the MinIO client and create a bucket:

```shell
mc config host add dest https://radosgw.mycompany.fqdn <access-key> <secret-key> --api S3v4 --lookup path
mc mb dest/backups-bucket
```

Then, deploy and run the charm:

```shell
juju deploy s3-integrator --channel=2/stable
juju add-secret s3-credentials access-key=<access-key-here> secret-key=<secret-key-here>
juju grant-secret s3-credentials s3-integrator
```

Lastly, use `juju config` to add your configuration parameters. For example:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju config s3-integrator \
        credentials=<secret-uri-from-previous-step> \
        endpoint="https://radosgw.mycompany.fqdn" \
        bucket="backups-bucket" \
        path="/mysql" \
        region="" \
        s3-api-version="" \
        s3-uri-style="path"
```

```{tab-item} K8s
:sync: k8s

    juju config s3-integrator \
        credentials=<secret-uri-from-previous-step> \
        endpoint="https://radosgw.mycompany.fqdn" \
        bucket="backups-bucket" \
        path="/mysql-k8s" \
        region="" \
        s3-api-version="" \
        s3-uri-style="path"
```
````

## Integrate with Charmed MySQL

To pass these configurations to Charmed MySQL, integrate the two applications:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju relate s3-integrator mysql
```

```{tab-item} K8s
:sync: k8s

    juju relate s3-integrator mysql-k8s
```
````

You can create, list, and restore backups now:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju run mysql/leader list-backups
    juju run mysql/leader create-backup
    juju run mysql/leader list-backups
    juju run mysql/leader restore backup-id=<backup-id>
```

```{tab-item} K8s
:sync: k8s

    juju run mysql-k8s/leader list-backups
    juju run mysql-k8s/leader create-backup
    juju run mysql-k8s/leader list-backups
    juju run mysql-k8s/leader restore backup-id=<backup-id>
```
````

You can also update your S3 configuration options after relating:

```shell
juju config s3-integrator <option>=<value>
```

The S3-integrator charm accepts many [configuration parameters](https://charmhub.io/s3-integrator/configure?channel=2/stable) for your S3 storage.
