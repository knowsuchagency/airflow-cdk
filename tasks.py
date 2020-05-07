from pathlib import Path
import logging
import time

from invoke import task


@task
def wait(c, seconds=5):
    logging.info(f"waiting {seconds} seconds")
    time.sleep(seconds)


@task
def initdb(c):
    c.run("airflow initdb", warn=True)


@task
def add_user(c):
    from airflow import models, settings
    from airflow.contrib.auth.backends.password_auth import PasswordUser

    import sqlalchemy

    user = PasswordUser(models.User())
    user.username = c.config.auth.username
    user.email = c.config.auth.email
    user.password = c.config.auth.password

    session = settings.Session()
    session.add(user)

    try:
        session.commit()
    except sqlalchemy.exc.IntegrityError as e:
        logging.exception(e)
    finally:
        session.close()


@task
def set_airflow_variables(c):
    """Configure airflow variables from configuration."""
    for key, value in c.config.airflow.variables.items():
        c.run(f"airflow variables --set {key} {value}")


@task
def configure_aws(c):
    """Copy aws secrets file to default aws credentials location."""
    secret_path = Path("/run/secrets/aws-credentials")

    credentials_root = Path(Path.home(), ".aws")
    credentials_path = Path(credentials_root, "credentials")

    if secret_path.exists() and not credentials_path.exists():
        logging.info("aws secrets file found; writing to default path")
        credentials_root.mkdir(exist_ok=True)
        credentials_path.write_text(secret_path.read_text())

    logging.info("aws secrets file not found. skipping configuration")


@task(initdb)
def initialize(c):
    """Initialize db and anything else necessary prior to webserver, scheduler, workers etc."""


@task(initialize, wait)
def webserver(c):
    c.run(f"airflow webserver")


@task(wait)
def scheduler(c):
    c.run("airflow scheduler")


@task(wait)
def worker(c):
    c.run("airflow worker")


@task
def bootstrap(c):
    """Bootstrap AWS assets for cdk."""
    c.run("cdk bootstrap aws://$AWS_ACCOUNT/$AWS_DEFAULT_REGION")
