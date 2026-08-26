---
myst:
  html_meta:
    description: "Configure the s3-integrator charm for AWS S3 to enable Charmed MySQL backups, including credentials, bucket setup, and application integration."
---

(configure-s3-aws)=
# Configure S3 for AWS

Charmed MySQL backups can be stored on any S3 compatible storage. S3 access and configurations are managed with the [S3-integrator charm](https://charmhub.io/s3-integrator?channel=2/stable).

This guide will teach you how to deploy and configure the S3-integrator charm for [AWS S3](https://aws.amazon.com/s3/), send the configuration to a Charmed MySQL application, and update it.

```{seealso}
{ref}`configure-s3-radosgw`
```

## Create the S3 bucket (optional)

Version 2 of the `s3-integrator` charm automatically creates the bucket upon configuration if it does not exist or it is not accessible. Therefore, the bucket does not need to be manually created before passing its name to the integrator charm, although this option allows for a more flexible policy specification.

## Configure the integrator

Deploy and configure the `s3-integrator` charm for AWS S3:

```shell
juju deploy s3-integrator --channel=2/stable

juju add-secret s3-credentials access-key=<access-key-here> secret-key=<secret-key-here>
juju grant-secret s3-credentials s3-integrator

juju config s3-integrator \
    credentials=<secret-uri-from-previous-step> \
    endpoint="https://s3.amazonaws.com" \
    bucket="mysql-test-bucket-1" \
    path="/mysql-test" \
    region="us-west-2"
```

```{note} 
The Amazon S3 endpoint must be specified as `s3.<region>.amazonaws.com ` within the first 24 hours of creating the bucket. For older buckets, the endpoint `s3.amazonaws.com` can be used.

See [this post](https://repost.aws/knowledge-center/s3-http-307-response) for more information. 
```

## Integrate with Charmed MySQL

To pass these configurations to Charmed MySQL, relate the two applications:

````{tab-set}
```{tab-item} VM
:sync: vm

    juju integrate s3-integrator mysql
```

```{tab-item} K8s
:sync: k8s

    juju integrate s3-integrator mysql-k8s
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

The S3-integrator charm accepts many [configuration parameters](https://charmhub.io/s3-integrator/configurations?channel=2/stable) for your S3 storage.
