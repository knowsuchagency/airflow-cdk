#!/usr/bin/env python3

from aws_cdk import core

from airflow_cdk.airflow_cdk_stack import AirflowCdkStack


app = core.App()
AirflowCdkStack(app, "airflow-cdk")

app.synth()
