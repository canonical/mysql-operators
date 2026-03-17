---
myst:
  html_meta:
    description: "Connect to Charmed MySQL from outside the local network using MySQL Router with virtual IPs or cross-controller Juju relations."
---

(external-network-access)=
# How to connect to your database outside the local network

This page summarises resources for setting up deployments where an external application must connect to a MySQL database from outside the local area network.

## External application (non-Juju)

**Use case**: the client application is a non-Juju application outside of Juju, Kubernetes, or the local area network the database is connected to.

The available options are heavily depend on the cloud/hardware/virtualization in use. One of the possible options is to use [virtual IP addresses (VIP)](https://en.wikipedia.org/wiki/Virtual_IP_address) which the MySQL Router charm provides with assist of the charm/interface `hacluster`. 

Please follow the MySQL Router documentation:
* [MySQL Router for machines](https://charmhub.io/mysql-router/docs/h-external-access?channel=dpe/candidate)
* [MySQL Router for Kubernetes](https://charmhub.io/mysql-router-k8s/docs/h-external-access)

## External relation (Juju)

**Use case**: the client application is a Juju application outside of the database deployment (e.g. hybrid Juju deployment with different VM clouds/controllers, or mixed K8s and VM applications).

In this case, a cross-controllers relation is necessary. Please {ref}`contact <contacts>` the Data team to discuss the possible option for your use case.

