#!/usr/bin/env python3
import os

from aws_cdk import core
from airflow_cdk import FargateAirflow


app = core.App()

FargateAirflow(app, "airflow-cdk")

app.synth()
