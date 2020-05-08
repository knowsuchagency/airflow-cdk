#!/usr/bin/env python3
import os

from aws_cdk import (
    core,
    aws_rds,
    aws_ec2,
    aws_s3,
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
        aws_region="us-west-2",
        log_prefix="airflow",
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        bucket = aws_s3.Bucket(
            self, "airflow-bucket", removal_policy=core.RemovalPolicy.DESTROY,
        )

        env = {
            # https://github.com/puckel/docker-airflow/issues/233
            'AIRFLOW__WEBSERVER__WORKERS': (airflow_task_cpu // 1000) + 1,
            'AIRFLOW__WEBSERVER__WORKER_REFRESH_INTERVAL': 1800,
            'AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_TIMEOUT': 300,
            'GUNICORN_CMD_ARGS': '--log-level WARNING',
            "AIRFLOW__CORE__HOSTNAME_CALLABLE": "socket:gethostname",
            "AIRFLOW__CELERY__BROKER_URL": celery_broker_url,
            "INVOKE_RUN_ECHO": 1,
            "C_FORCE_ROOT": "true",
            "POSTGRES_USER": postgres_user,
            # TODO: make this more secure i.e. SSM/Secrets Manager
            "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD")
            or postgres_password,
            "POSTGRES_DB": postgres_db,
            "AIRFLOW__CORE__DAGS_FOLDER": dags_folder,
            "AIRFLOW__CORE__LOAD_EXAMPLES": load_examples,
            "AIRFLOW__CORE__EXECUTOR": executor,
            "AIRFLOW__WEBSERVER__WEB_SERVER_PORT": airflow_webserver_port,
            "AIRFLOW_HOME": airflow_home,
            "AWS_DEFAULT_REGION": aws_region,
            "AIRFLOW__LOGGING__REMOTE_LOGGING": "true",
            "AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID": "aws_default",
            "AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER": f"s3://{bucket.bucket_name}",
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

        bucket.grant_read_write(airflow_task.task_role.grant_principal)

        postgres_hostname = airflow_rds_instance.db_instance_endpoint_address

        env.update(
            AIRFLOW__CORE__SQL_ALCHEMY_CONN=f"postgresql+psycopg2://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
            AIRFLOW__CELERY__RESULT_BACKEND=f"db+postgresql://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
        )

        env = {k: str(v) for k, v in env.items()}

        log_driver = aws_ecs.LogDriver.aws_logs(stream_prefix=log_prefix)

        web_container = airflow_task.add_container(
            "web_container",
            image=base_airflow_container,
            environment=env,
            logging=log_driver,
            essential=True,

        )

        web_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=airflow_webserver_port)
        )

        rabbitmq_container = airflow_task.add_container(
            "rabbitmq_container",
            image=aws_ecs.ContainerImage.from_registry("rabbitmq:management"),
            environment=env,
            logging=log_driver,
            essential=False,
        )

        scheduler_container = airflow_task.add_container(
            "scheduler_container",
            image=base_airflow_container,
            environment=env,
            logging=log_driver,
            command=["scheduler"],
            essential=False,

        )

        worker_container = airflow_task.add_container(
            "worker_container",
            image=base_airflow_container,
            environment=env,
            logging=log_driver,
            command=["worker"],
            essential=True,
            cpu=2048,
            memory_reservation_mib=4096,
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
