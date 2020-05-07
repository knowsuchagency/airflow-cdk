from pathlib import Path
import logging
import time

from invoke import task
import os
import threading


@task
def wait(c, seconds=5):
    logging.info(f"waiting {seconds} seconds")
    time.sleep(seconds)


@task
def initdb(c):

    c.run("airflow initdb", warn=True)


@task
def set_airflow_variables(c):
    """Configure airflow variables from configuration."""
    for key, value in c.config.airflow.variables.items():
        c.run(f"airflow variables --set {key} {value}")


@task(initdb)
def initialize(c):
    """Initialize db and anything else necessary prior to webserver, scheduler, workers etc."""


@task(initialize, wait)
def webserver(c, run_scheduler_in_bg_thread=True):
    if run_scheduler_in_bg_thread:
        threading.Thread(target=scheduler, args=(c,), daemon=True).start()

    c.run(f"airflow webserver")


@task(wait)
def scheduler(c):
    c.run("airflow scheduler")


@task(wait)
def worker(c):
    c.run("airflow worker")


@task
def bootstrap(c):
    """Bootstrap AWS account for use with cdk."""
    c.run("cdk bootstrap aws://$AWS_ACCOUNT/$AWS_DEFAULT_REGION")
