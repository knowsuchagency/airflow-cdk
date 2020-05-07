#!/usr/bin/env python3

from pathlib import Path

from aws_cdk import aws_ec2
from aws_cdk import aws_ecs
from aws_cdk import aws_ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elb
from aws_cdk import core


def _get_env_vars():
    result = {}
    for line in Path(Path(__file__).parent, "local.env").read_text().splitlines():
        if line and not line.startswith("#"):
            k, v = line.split("=", maxsplit=1)
            result[k] = v
    return result


class AirflowCdkStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        cluster = aws_ecs.Cluster(
            self,
            "airflow-cluster",
            capacity=aws_ecs.AddCapacityOptions(
                instance_type=aws_ec2.InstanceType("t3.small")
            ),
        )

        container = aws_ecs.ContainerImage.from_asset(".",)

        airflow_task = aws_ecs.Ec2TaskDefinition(
            self,
            "airflow_task",
            # cpu=2048, memory_limit_mib=2048
        )

        rabbitmq_container = airflow_task.add_container(
            "rabbitmq_container",
            image=aws_ecs.ContainerImage.from_registry("rabbitmq:management"),
            environment=_get_env_vars(),
            hostname="rabbitmq",
            memory_limit_mib=256
        )

        rabbitmq_container.add_port_mappings(aws_ecs.PortMapping(container_port=5672))

        postgres_container = airflow_task.add_container(
            "postgres_container",
            image=aws_ecs.ContainerImage.from_registry("postgres"),
            hostname="postgres",
            memory_limit_mib=256
        )

        postgres_container.add_port_mappings(aws_ecs.PortMapping(container_port=5432))

        scheduler_container: aws_ecs.ContainerDefinition = airflow_task.add_container(
            "scheduler_container",
            image=container,
            environment=_get_env_vars(),
            hostname="scheduler",
            memory_limit_mib=512
        )

        worker_container: aws_ecs.ContainerDefinition = airflow_task.add_container(
            "worker_container",
            image=container,
            environment=_get_env_vars(),
            hostname="worker",
            memory_reservation_mib=512
        )

        web_container: aws_ecs.ContainerDefinition = airflow_task.add_container(
            "web_container",
            image=container,
            environment=_get_env_vars(),
            hostname="web",
            memory_limit_mib=512
        )

        web_container.add_port_mappings(aws_ecs.PortMapping(container_port=80))

        web_container.add_container_dependencies(
            aws_ecs.ContainerDependency(
                container=postgres_container,
                condition=aws_ecs.ContainerDependencyCondition.START,
            ),
            aws_ecs.ContainerDependency(
                container=rabbitmq_container,
                condition=aws_ecs.ContainerDependencyCondition.START,
            ),
        )

        airflow_service = aws_ecs_patterns.ApplicationLoadBalancedEc2Service(
            self,
            "airflow_service",
            task_definition=airflow_task,
            protocol=elb.ApplicationProtocol.HTTP,
            cluster=cluster,
        )


app = core.App()

AirflowCdkStack(app, "airflow-cdk")

app.synth()
