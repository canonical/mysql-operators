# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "mysql_server" {
  model_uuid = var.model
  name       = var.app_name
  trust      = true

  charm {
    name     = "mysql-k8s"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }

  storage_directives = {
    archive = lookup(var.storage_sizes, "archive", "10G")
    data    = lookup(var.storage_sizes, "data", "10G")
    logs    = lookup(var.storage_sizes, "logs", "10G")
    temp    = lookup(var.storage_sizes, "temp", "10G")
  }

  config      = var.config
  constraints = var.constraints
  units       = var.units

  dynamic "expose" {
    for_each = length(var.expose) > 0 ? [var.expose] : []

    content {
      endpoints = lookup(expose.value, "endpoints", null)
      spaces    = lookup(expose.value, "spaces", null)
      cidrs     = lookup(expose.value, "cidrs", null)
    }
  }
}
