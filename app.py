#!/usr/bin/env python3
import os

from aws_cdk import core, aws_ecs
from airflow_cdk import FargateAirflow


app = core.App()

FargateAirflow(
    app,
    "airflow-cdk",
    # base_image=aws_ecs.ContainerImage.from_asset(".")
)

app.synth()
