#!/usr/bin/env python3
import os
from pathlib import Path

from aws_cdk import (
    core,
    aws_rds,
    aws_ec2,
    aws_ecs,
    aws_ecs_patterns,
    aws_elasticloadbalancingv2 as elb,
)



class AirflowCdkStack(core.Stack):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        postgres_user="airflow",
        postgres_password="replacethiswithasecretpassword",
        postgres_db="airflow",
        dags_folder="/src/airflow_cdk/dags",
        load_examples=True,
        executor="CeleryExecutor",
        celery_broker_url="amqp://127.0.0.1",
        airflow_webserver_port=80,
        airflow_home="/airflow",
        airflow_task_memory_limit=8192,
        airflow_task_cpu=4096,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        env = {
            "AIRFLOW__CELERY__BROKER_URL": celery_broker_url,
            "INVOKE_RUN_ECHO": 1,
            "C_FORCE_ROOT": "true",
            "POSTGRES_USER": postgres_user,
            "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD")
            or postgres_password,
            "POSTGRES_DB": postgres_db,
            "AIRFLOW__CORE__DAGS_FOLDER": dags_folder,
            "AIRFLOW__CORE__LOAD_EXAMPLES": load_examples,
            "AIRFLOW__CORE__EXECUTOR": executor,
            "AIRFLOW__WEBSERVER__WEB_SERVER_PORT": airflow_webserver_port,
            "AIRFLOW_HOME": airflow_home,
        }

        vpc = aws_ec2.Vpc(self, "airflow-vpc")

        cluster = aws_ecs.Cluster(self, "cluster", vpc=vpc)

        base_airflow_container = aws_ecs.ContainerImage.from_asset(".",)

        airflow_rds_instance = aws_rds.DatabaseInstance(
            self,
            "airflow-rds-instance",
            master_username=postgres_user,
            engine=aws_rds.DatabaseInstanceEngine.POSTGRES,
            allocated_storage=10,
            database_name=postgres_db,
            master_user_password=core.SecretValue.plain_text(
                postgres_password
            ),
            vpc=vpc,
            instance_class=aws_ec2.InstanceType("t3.micro"),
            # TODO: turn this on when ready for prod
            deletion_protection=False,
            delete_automated_backups=True,
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        airflow_task = aws_ecs.FargateTaskDefinition(
            self,
            "airflow_task",
            cpu=airflow_task_cpu,
            memory_limit_mib=airflow_task_memory_limit,
        )

        postgres_hostname = airflow_rds_instance.db_instance_endpoint_address

        env.update(
            AIRFLOW__CORE__SQL_ALCHEMY_CONN=f"postgresql+psycopg2://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
            AIRFLOW__CELERY__RESULT_BACKEND=f"db+postgresql://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
        )

        web_container = airflow_task.add_container(
            "web_container",
            image=base_airflow_container,
            environment=env,
            logging=aws_ecs.LogDriver.aws_logs(stream_prefix="airflow-web"),
            essential=True,
        )

        web_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=airflow_webserver_port)
        )

        rabbitmq_container = airflow_task.add_container(
            "rabbitmq_container",
            image=aws_ecs.ContainerImage.from_registry("rabbitmq:management"),
            environment=env,
            logging=aws_ecs.LogDriver.aws_logs(
                stream_prefix="airflow-rabbitmq"
            ),
            essential=False,
        )

        scheduler_container = airflow_task.add_container(
            "scheduler_container",
            image=base_airflow_container,
            environment=env,
            logging=aws_ecs.LogDriver.aws_logs(
                stream_prefix="airflow-scheduler"
            ),
            command=["scheduler"],
            essential=False,
        )

        worker_container = airflow_task.add_container(
            "worker_container",
            image=base_airflow_container,
            environment=env,
            logging=aws_ecs.LogDriver.aws_logs(stream_prefix="airflow-worker"),
            command=["worker"],
            essential=False,
        )

        web_service = aws_ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "web_service",
            task_definition=airflow_task,
            protocol=elb.ApplicationProtocol.HTTP,
            cluster=cluster,
        )

        web_service.service.connections.allow_to(
            airflow_rds_instance,
            aws_ec2.Port.tcp(5432),
            description="allow connection to RDS",
        )


app = core.App()

AirflowCdkStack(app, "airflow-cdk")

app.synth()
