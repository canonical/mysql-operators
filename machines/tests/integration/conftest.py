# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import subprocess
import uuid

import jubilant
import pytest

from . import architecture

logging.getLogger("jubilant.wait").setLevel(logging.WARNING)


@pytest.fixture(scope="session")
def charm():
    # Return str instead of pathlib.Path since python-libjuju's model.deploy(), juju deploy, and
    # juju bundle files expect local charms to begin with `./` or `/` to distinguish them from
    # Charmhub charms.
    return f"./mysql_ubuntu@22.04-{architecture.architecture}.charm"


@pytest.fixture(scope="session")
def cloud_configs_aws() -> tuple[dict[str, str], dict[str, str]]:
    configs = {
        "endpoint": os.getenv("AWS_ENDPOINT_URL", "https://s3.amazonaws.com"),
        "bucket": "data-charms-testing",
        "path": f"mysql/{uuid.uuid4()}",
        "region": "us-east-1",
    }
    credentials = {
        "access-key": os.environ["AWS_ACCESS_KEY"],
        "secret-key": os.environ["AWS_SECRET_KEY"],
    }
    return configs, credentials


@pytest.fixture(scope="session")
def cloud_configs_gcp() -> tuple[dict[str, str], dict[str, str]]:
    configs = {
        "endpoint": "https://storage.googleapis.com",
        "bucket": "data-charms-testing",
        "path": f"mysql/{uuid.uuid4()}",
        "region": "us-east-1",
    }
    credentials = {
        "access-key": os.environ["GCP_ACCESS_KEY"],
        "secret-key": os.environ["GCP_SECRET_KEY"],
    }
    return configs, credentials


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Pytest fixture that wraps :meth:`jubilant.with_model`.

    This adds command line parameter ``--keep-models`` (see help for details).
    """
    model = request.config.getoption("--model")
    keep_models = bool(request.config.getoption("--keep-models"))

    if model:
        juju = jubilant.Juju(model=model)  # type: ignore
        yield juju
        log = juju.debug_log(limit=1000)
    else:
        with jubilant.temp_model(keep=keep_models) as juju:
            yield juju
            log = juju.debug_log(limit=1000)

    if request.session.testsfailed:
        print(log, end="")
        # Capture controller debug logs
        try:
            controller_log = subprocess.check_output(
                ["juju", "debug-log", "-m", "controller", "--replay", "--no-tail", "--limit", "1000"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
            )
            print("\n=== Controller Debug Logs ===\n")
            print(controller_log, end="")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"\n=== Failed to retrieve controller logs: {e} ===\n")
