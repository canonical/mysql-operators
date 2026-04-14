# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import os
import uuid

import jubilant
import pytest

from . import architecture

logging.getLogger("jubilant.wait").setLevel(logging.WARNING)


def pytest_configure(config):
    """Configure pytest logging format with timestamps."""
    config.option.log_cli_format = (
        "%(asctime)s %(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s"
    )
    config.option.log_cli_date_format = "%b %d %H:%M:%S"
    config.option.log_format = (
        "%(asctime)s %(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s"
    )
    config.option.log_date_format = "%b %d %H:%M:%S"


def pytest_addoption(parser):
    """Adds command line parameter ``--model`` (see help for details)."""
    parser.addoption(
        "--model",
        action="store",
        default="testing",
        help="model name or ':auto:' for temporary model, default to 'testing'",
        required=False,
    )


@pytest.fixture(scope="session")
def charm():
    # Return str instead of pathlib.Path since python-libjuju's model.deploy(), juju deploy, and
    # juju bundle files expect local charms to begin with `./` or `/` to distinguish them from
    # Charmhub charms.
    return f"./mysql-k8s_ubuntu@24.04-{architecture.architecture}.charm"


@pytest.fixture(scope="session")
def cloud_configs_aws() -> tuple[dict[str, str], dict[str, str]]:
    configs = {
        "endpoint": os.getenv("AWS_ENDPOINT_URL", "https://s3.amazonaws.com"),
        "bucket": "data-charms-testing",
        "path": f"mysql-k8s/{uuid.uuid4()}",
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
        "path": f"mysql-k8s/{uuid.uuid4()}",
        "region": "us-east-1",
    }
    credentials = {
        "access-key": os.environ["GCP_ACCESS_KEY"],
        "secret-key": os.environ["GCP_SECRET_KEY"],
    }
    return configs, credentials


@pytest.fixture(scope="module")
def juju(request: pytest.FixtureRequest):
    """Pytest fixture that yields a new :meth:`jubilant.Juju` object."""
    model = request.config.getoption("--model")

    if model == ":auto:":
        with jubilant.temp_model() as juju:
            yield juju
    else:
        yield jubilant.Juju(model=model)
