# airflow-cdk

This project makes it simple to deploy airflow via ECS fargate using the aws cdk in Python.

It is meant for rapid prototyping, you will need to do some work to make it production-ready.

## Usage

```python3
from aws_cdk import core
from airflow_cdk.stack import FargateAirflow


app = core.App()

FargateAirflow(
    app,
    "airflow-cdk",
    postgres_password="replacethiswithasecretpassword")

app.synth()
```

...

`cdk deploy`

That's it.

## Components

The following aws resources will be deployed as ecs tasks within the same cluster and vpc by default:

* an airflow webserver task
  * and an internet-facing application load-balancer
* an airflow scheduler task
* an airflow worker task
  * (note) it will auto-scale based on cpu and memory usage up to a total of 16 instances at a time by default starting from 1
* a rabbitmq broker
* an rds instance
* an s3 bucket for logs

## TODOs

* create a custom component to deploy airflow to an ec2 cluster as opposed to fargate
* improve documentation
* (possibly) subsume the [airflow stable helm chart](https://hub.helm.sh/charts/stable/airflow) as a cdk8s chart

## Contributions Welcome!