#!/usr/bin/env python3
import os

from aws_cdk import core
from airflow_cdk.stack import AirflowCdkStack


app = core.App()

AirflowCdkStack(app, "airflow-cdk")

app.synth()
