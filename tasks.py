import json
import os

import toml
from invoke import task


@task
def bootstrap(c):
    """Bootstrap AWS account for use with cdk."""
    c.run("cdk bootstrap aws://$AWS_ACCOUNT/$AWS_DEFAULT_REGION")


@task(aliases=["format"])
def black(c):
    """Format modules using black."""
    c.run("black airflow-cdk/ tests/ tasks.py")


@task(aliases=["check-black"])
def check_formatting(c):
    """Check that files conform to black standards."""
    c.run("black --check airflow-cdk/ tests/ tasks.py")


@task(check_formatting)
def publish(c, username=None, password=None):
    """Publish to pypi."""

    username = username or os.getenv("PYPI_USERNAME")

    password = password or os.getenv("PYPI_PASSWORD")

    *_, latest_release = json.loads(
        c.run("qypi releases airflow-cdk", hide=True).stdout
    )["airflow-cdk"]

    latest_release_version = latest_release["version"]

    local_version = toml.load("pyproject.toml")["tool"]["poetry"]["version"]

    if local_version == latest_release_version:
        print("local and release version are identical -- skipping publish")
    else:
        print(f"publishing airflow-cdk v{local_version}")
        c.run(
            f"poetry publish -u {username} -p '{password}' --build",
            pty=True,
            hide=True,
        )
