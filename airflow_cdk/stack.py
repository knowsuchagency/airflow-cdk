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
        postgres_password="replacethiswithasecretpassword",
        dags_folder="/src/airflow_cdk/dags",
        airflow_webserver_port=80,
        executor="CeleryExecutor",
        postgres_user="airflow",
        airflow_home="/airflow",
        aws_region="us-west-2",
        postgres_db="airflow",
        log_prefix="airflow",
        load_examples=True,
        web_container_desired_count=1,
        worker_container_desired_count=1,
        vpc=None,
        bucket=None,
        log_driver=None,
        env=None,
        cluster=None,
        base_container=None,
        rds_instance=None,
        web_task=None,
        worker_task=None,
        scheduler_task=None,
        rabbitmq_task=None,
        rabbitmq_service=None,
        web_service=None,
        scheduler_service=None,
        worker_service=None,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = vpc or aws_ec2.Vpc(self, "airflow-vpc")

        bucket = bucket or aws_s3.Bucket(
            self, "airflow-bucket", removal_policy=core.RemovalPolicy.DESTROY,
        )

        log_driver = log_driver or aws_ecs.LogDriver.aws_logs(
            stream_prefix=log_prefix
        )

        env = env or {
            "AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER": f"s3://{bucket.bucket_name}",
            "AIRFLOW__WEBSERVER__WEB_SERVER_PORT": airflow_webserver_port,
            "AIRFLOW__CORE__HOSTNAME_CALLABLE": "socket:gethostname",
            "AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID": "aws_default",
            "AIRFLOW__CORE__LOAD_EXAMPLES": load_examples,
            "AIRFLOW__LOGGING__REMOTE_LOGGING": "true",
            "AIRFLOW__CORE__DAGS_FOLDER": dags_folder,
            "AIRFLOW__CORE__EXECUTOR": executor,
            #
            "GUNICORN_CMD_ARGS": "--log-level WARNING",
            "C_FORCE_ROOT": "true",
            "INVOKE_RUN_ECHO": 1,
            #
            "POSTGRES_PASSWORD": postgres_password,
            "POSTGRES_USER": postgres_user,
            "POSTGRES_DB": postgres_db,
            #
            "AWS_DEFAULT_REGION": aws_region,
            "AIRFLOW_HOME": airflow_home,
        }

        env = {k: str(v) for k, v in env.items()}

        cluster = cluster or aws_ecs.Cluster(self, "cluster", vpc=vpc)

        base_container = base_container or aws_ecs.ContainerImage.from_asset(
            ".",
        )

        rds_instance = rds_instance or aws_rds.DatabaseInstance(
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

        web_task = web_task or aws_ecs.FargateTaskDefinition(
            self, "web_task", cpu=1024, memory_limit_mib=2048,
        )

        worker_task = worker_task or aws_ecs.FargateTaskDefinition(
            self, "worker_task", cpu=1024, memory_limit_mib=2048
        )

        scheduler_task = scheduler_task or aws_ecs.FargateTaskDefinition(
            self, "scheduler_task", cpu=1024, memory_limit_mib=2048
        )

        rabbitmq_task = rabbitmq_task or aws_ecs.FargateTaskDefinition(
            self, "rabbitmq_task", cpu=1024, memory_limit_mib=2048
        )

        rabbitmq_container = rabbitmq_task.add_container(
            "rabbitmq_container",
            image=aws_ecs.ContainerImage.from_registry("rabbitmq:management"),
            environment=env,
            logging=log_driver,
            health_check=aws_ecs.HealthCheck(
                command=["CMD", "nc", "-z", "localhost", "5672"]
            ),
        )

        rabbitmq_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=5672)
        )

        rabbitmq_service = (
            rabbitmq_service
            or aws_ecs_patterns.NetworkLoadBalancedFargateService(
                self,
                "rabbitmq_service",
                task_definition=rabbitmq_task,
                public_load_balancer=False,
                listener_port=5672,
                cluster=cluster,
            )
        )

        bucket.grant_read_write(web_task.task_role.grant_principal)

        bucket.grant_read_write(worker_task.task_role.grant_principal)

        postgres_hostname = rds_instance.db_instance_endpoint_address

        env.update(
            AIRFLOW__CORE__SQL_ALCHEMY_CONN=f"postgresql+psycopg2://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
            AIRFLOW__CELERY__RESULT_BACKEND=f"db+postgresql://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
            AIRFLOW__CELERY__BROKER_URL=f"amqp://{rabbitmq_service.load_balancer.load_balancer_dns_name}",
        )

        web_container = web_task.add_container(
            "web_container",
            image=base_container,
            environment=env,
            logging=log_driver,
            essential=True,
        )

        web_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=airflow_webserver_port)
        )

        scheduler_container = scheduler_task.add_container(
            "scheduler_container",
            image=base_container,
            environment=env,
            logging=log_driver,
            command=["scheduler"],
        )

        worker_container = worker_task.add_container(
            "worker_container",
            image=base_container,
            environment=env,
            logging=log_driver,
            command=["worker"],
        )

        web_service = (
            web_service
            or aws_ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                "web_service",
                task_definition=web_task,
                protocol=elb.ApplicationProtocol.HTTP,
                cluster=cluster,
                desired_count=web_container_desired_count,
            )
        )

        web_service.target_group.configure_health_check(
            healthy_http_codes="200-399"
        )

        scheduler_service = scheduler_service or aws_ecs.FargateService(
            self,
            "scheduler_service",
            task_definition=scheduler_task,
            cluster=cluster,
        )

        worker_service = worker_service or aws_ecs.FargateService(
            self,
            "worker_service",
            task_definition=worker_task,
            cluster=cluster,
            desired_count=worker_container_desired_count,
        )

        web_service.service.connections.allow_to(
            rds_instance,
            aws_ec2.Port.tcp(5432),
            description="allow connection to RDS",
        )

        web_service.service.connections.allow_to(
            rabbitmq_service.service.connections,
            aws_ec2.Port.tcp(5672),
            description="allow connection to rabbitmq broker",
        )

        for service in scheduler_service, worker_service:

            service.connections.allow_to(
                rds_instance,
                aws_ec2.Port.tcp(5432),
                description="allow connection to RDS",
            )

            service.connections.allow_to(
                rabbitmq_service.service.connections,
                aws_ec2.Port.tcp(5672),
                description="allow connection to rabbitmq broker",
            )
