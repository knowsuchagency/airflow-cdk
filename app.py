#!/usr/bin/env python3

from aws_cdk import core

from airflow_cdk import FargateAirflow

app = core.App()

airflow = FargateAirflow(app, "airflow-cdk",)


app.synth()
