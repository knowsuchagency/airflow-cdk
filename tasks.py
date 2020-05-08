import logging
import time

from invoke import task


### local automation tasks ###

@task
def bootstrap(c):
    """Bootstrap AWS account for use with cdk."""
    c.run("cdk bootstrap aws://$AWS_ACCOUNT/$AWS_DEFAULT_REGION")

### tasks to be run in a container ###

@task
def wait(c, seconds=5):
    logging.info(f"waiting {seconds} seconds")
    time.sleep(seconds)


@task
def initdb(c):

    c.run("airflow initdb", warn=True)


@task(initdb, wait)
def initialize(c):
    """Initialize db and anything else necessary prior to webserver, scheduler, workers etc."""


@task(initialize)
def webserver(c):

    c.run(f"airflow webserver")


@task(wait)
def scheduler(c):
    c.run("airflow scheduler")


@task(wait)
def worker(c):
    c.run("airflow worker")

