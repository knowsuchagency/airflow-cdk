#!/usr/bin/env python3

from pathlib import Path

from aws_cdk import (
    core,
    aws_rds,
    aws_ec2,
    aws_ecs,
    aws_ecs_patterns,
    aws_elasticloadbalancingv2 as elb,
)


def _get_env_vars():
    result = {}
    for line in Path(Path(__file__).parent, "fargate.env").read_text().splitlines():
        if line and not line.startswith("#"):
            k, v = line.split("=", maxsplit=1)
            result[k] = v
    return result


class AirflowCdkStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # TODO: parametrize this for real

        environment = _get_env_vars()

        airflow_vpc = aws_ec2.Vpc(self, "airflow-vpc")

        airflow_cluster = aws_ecs.Cluster(self, "airflow_cluster", vpc=airflow_vpc)

        base_airflow_container = aws_ecs.ContainerImage.from_asset(".",)

        postgres_user = environment.get("POSTGRES_USER")
        postgres_database = environment.get("POSTGRES_DB")
        postgres_password = environment.get("POSTGRES_PASSWORD")

        airflow_rds_instance = aws_rds.DatabaseInstance(
            self,
            "airflow-rds-instance",
            master_username=postgres_user,
            engine=aws_rds.DatabaseInstanceEngine.POSTGRES,
            allocated_storage=20,
            database_name=postgres_database,
            master_user_password=core.SecretValue.plain_text(postgres_password),
            vpc=airflow_vpc,
            instance_class=aws_ec2.InstanceType("t3.micro"),
            # TODO: turn this on when ready for prod
            deletion_protection=False,
            delete_automated_backups=True,
            removal_policy=core.RemovalPolicy.DESTROY
        )

        airflow_task = aws_ecs.FargateTaskDefinition(
            self, "airflow_task", cpu=1024, memory_limit_mib=2048
        )

        postgres_hostname = airflow_rds_instance.db_instance_endpoint_address

        airflow_container = airflow_task.add_container(
            "airflow_container",
            image=base_airflow_container,
            environment={
                **environment,
                "AIRFLOW__CORE__SQL_ALCHEMY_CONN": f"postgresql+psycopg2://{postgres_user}"
                f":{postgres_password}@{postgres_hostname}"
                f":5432/{postgres_database}",
            },
            logging=aws_ecs.LogDriver.aws_logs(stream_prefix="airflow"),
        )

        airflow_container.add_port_mappings(aws_ecs.PortMapping(container_port=80))

        airflow_service = aws_ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "airflow_service",
            task_definition=airflow_task,
            protocol=elb.ApplicationProtocol.HTTP,
            cluster=airflow_cluster,
        )

        airflow_service.service.connections.allow_to(
            airflow_rds_instance,
            aws_ec2.Port.tcp(5432),
            description="allow connection to RDS",
        )


app = core.App()

AirflowCdkStack(app, "airflow-cdk")

app.synth()
