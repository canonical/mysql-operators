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
    archive = var.storage_size
    data    = var.storage_size
    logs    = var.storage_size
    temp    = var.storage_size
  }

  config      = var.config
  constraints = var.constraints
  units       = var.units

  dynamic "expose" {
    for_each = var.expose != null ? [var.expose] : []

    content {
      endpoints = lookup(expose.value, "endpoints", null)
      spaces    = lookup(expose.value, "spaces", null)
      cidrs     = lookup(expose.value, "cidrs", null)
    }
  }
}
