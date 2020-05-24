# airflow-cdk

This project makes it simple to deploy airflow via ECS fargate using the aws cdk in Python.

## Usage

**There are two main ways that this package can be used.**

### Standalone Package

For those already familiar with the aws cdk, add this project
as a dependency i.e. to `requirement.txt` and use the `FargateAirflow`
construct like so.

```python3
from aws_cdk import core
from airflow_cdk import FargateAirflow


app = core.App()

FargateAirflow(
    app,
    "airflow-cdk",
    postgres_password="replacethiswithasecretpassword")

app.synth()
```

`cdk deploy`

That's it.

### Cloning

You can also clone this repository and alter the `FargateAirflow` construct
to your heart's content.

That also provides you an added benefit of utilizing the `tasks.py` tasks
with [invoke](http://www.pyinvoke.org) to do things like create new dags easily
i.e. `inv new-dag`

You would then also easily be able to use the existing docker-compose for local development
with some minor modifications for your setup.

The easiest way to get started would be just a one-line change to the `app.py` example above
and to the `docker-compose.yml` file.

```python3
from aws_cdk import core
from airflow_cdk import FargateAirflow


app = core.App()

FargateAirflow(
    app,
    "airflow-cdk",
    postgres_password="replacethiswithasecretpassword"),
    # now the image deployed to ECS will match the one
    # built with your local Dockerfile
    base_image=aws_ecs.ContainerImage.from_asset(".")

app.synth()
```

Now in the `docker-compose.yml` file, simply delete, comment out, or change the image name
for the `image: knowsuchagency/airflow-cdk` line in `x-airflow`.

Now, the same image that is built when you run `docker-compose build` that runs
on your local machine when you run `docker-compose up` is what will
be deployed to ECS for your web, worker, and scheduler images.


## Components

The following aws resources will be deployed as ecs tasks within the same cluster and vpc by default:

* an airflow webserver task
  * and an internet-facing application load-balancer
* an airflow scheduler task
* an airflow worker task
  * (note) it will auto-scale based on cpu and memory usage up to a total of 16 instances at a time by default starting from 1
* a rabbitmq broker
  * an application load balancer that will allow you to log in to
    the rabbitmq management console with the default user/pw guest/guest
* an rds instance
* an s3 bucket for logs

## Why is this awesome?

Apart from the fact that we're able to describe our infrastructure using the same
codebase language and codebase we use to author our dags?

One of the great things about this pattern is that since we're using cloudformation under-the-hood,
whenever we change a part of our code or infrastructure, only that changeset which cloudformation calculates for
us gets deployed.

Meaning, if all we do is alter the code we want to run on our deployment, we simply re-build and publish our docker
container (which is done for us if we use the `aws_ecs.ContainerImage.from_asset(".")` pattern) and `cdk deploy`!

Existing users of airflow will know how tricky it can be to manage deployments when you want to distinguish between
pushing changes to your codebase i.e. dags and actual infrastructure deployments. Now they're basically identical!
We just have to be careful not to deploy whilewe have some long-running worker task we don't want to interrupt since 
fargate will replace those worker instances with new ones running our updated code.

## TODOs

* create a custom component to deploy airflow to an ec2 cluster
* improve documentation
* (possibly) subsume the [airflow stable helm chart](https://hub.helm.sh/charts/stable/airflow) as a cdk8s chart

## Contributions Welcome!