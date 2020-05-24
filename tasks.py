import datetime as dt
import json
import logging
import os
from pathlib import Path

from invoke import task
from jinja2 import Template
from klaxon.invoke import klaxonify


@task
def bootstrap(c):
    """Bootstrap AWS account for use with cdk."""
    c.run("cdk bootstrap aws://$AWS_ACCOUNT/$AWS_DEFAULT_REGION")


@task(aliases=["format"])
def black(c):
    """Format modules using black."""
    c.run("black airflow_cdk/ setup.py app.py tasks.py")


@task(aliases=["check-black"])
def check_formatting(c):
    """Check that files conform to black standards."""
    c.run("black --check airflow_cdk/ setup.py app.py tasks.py")


@task(black)
def build(c, password=None, username=None):
    """Build package."""
    username = username or os.getenv("PYPI_USERNAME")
    password = password or os.getenv("PYPI_PASSWORD")
    c.run("rm -rf build/* dist/*")
    c.run("python setup.py sdist bdist_wheel")
    c.run("twine check dist/*")
    return password, username


@task(aliases=["bump"])
def bump_version(c, version="patch"):
    """Bump package version."""

    version_choices = ["major", "minor", "patch"]

    if version not in version_choices:
        raise SystemExit(f"semver must be one of {version_choices}")

    version_file = Path("VERSION")

    major, minor, patch = [
        int(s) for s in version_file.read_text().strip().split(".")
    ]

    if version == "major":
        major += 1
    elif version == "minor":
        minor += 1
    elif version == "patch":
        patch += 1

    version_file.write_text(".".join(map(str, [major, minor, patch])))


@task(pre=[check_formatting], aliases=["publish"])
def publish_package(c, username=None, password=None):
    *_, latest_release = json.loads(
        c.run("qypi releases airflow-cdk", hide=True).stdout
    )["airflow-cdk"]

    latest_release_version = latest_release["version"]
    """Publish package to pypi."""

    local_version = Path("VERSION").read_text()

    if local_version <= latest_release_version:
        logging.warning("published version is equal to or greater than local")
        logging.warning("skipping publish")

        return

    password, username = build(c, password, username)

    c.run(
        f"twine upload -u {username} -p {password} "
        f"--repository-url https://test.pypi.org/legacy/ dist/*"
    )

    c.run(f"twine upload -u {username} -p {password} dist/*")


@task
def new_dag(
    c,
    dag_id=None,
    owner=None,
    email=None,
    start_date=None,
    schedule_interval=None,
    force=False,
):
    """
    Render a new dag and put it in the dags folder.
    Args:
        c: invoke context
        dag_id: i.e. my_dag_v1_p3 (dag_name, version, priority[1-high, 2-med, 3-low])
        owner: you
        email: your email
        start_date: date in iso format
        schedule_interval: cron expression
        force: overwrite dag module if it exists
    """

    yesterday = dt.date.today() - dt.timedelta(days=1)

    defaults = {
        "dag_id": "example_dag",
        "owner": "Stephan Fitzpatrick",
        "email": "knowsuchagency@gmail.com",
        "start_date": yesterday.isoformat(),
        "schedule_interval": "0 7 * * *",
    }

    template_text = Path("airflow_cdk/templates/example_dag.py").read_text()

    template = Template(template_text)

    args = {}

    locals_ = locals()

    print(
        "rendering your new dag. please enter the following values:",
        end=os.linesep * 2,
    )

    for key, default_value in defaults.items():

        explicit_value = locals_[key]

        if explicit_value:
            args[key] = explicit_value
        else:
            value = input(f"{key} (default: {default_value}) -> ").strip()

            args[key] = value or defaults[key]

    rendered_text = template.render(**args)

    print()

    filename = args["dag_id"] + ".py"

    dag_path = Path("airflow_cdk", "dags", filename)

    if dag_path.exists() and not force:
        raise SystemExit(f"{filename} already exists. aborting")

    print(f"writing dag to: {dag_path}")

    dag_path.write_text(rendered_text + os.linesep)


@task(aliases=["push"])
def push_to_dockerhub(c):
    c.run("docker-compose build")
    c.run("docker-compose push", warn=True)


@task(push_to_dockerhub)
@klaxonify
def deploy(c, force=False, publish=False):
    """Deploy to AWS."""

    c.run("cdk diff")

    c.run("cdk deploy" + "--require-approval never" if force else "")

    if publish:
        publish_package(c)
