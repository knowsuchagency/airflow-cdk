from aws_cdk import (
    core,
    aws_rds,
    aws_ec2,
    aws_s3,
    aws_ecs,
    aws_ecs_patterns,
    aws_elasticloadbalancingv2 as elb,
)


class AirflowStack(core.Stack):
    """Contains all services if using a single stack."""


class NetworkStack(core.Stack):
    """Contains networks infrastructure."""


class PersistenceStack(core.Stack):
    """Contains persistence layer i.e. RDS, S3."""


class MessageBrokerStack(core.Stack):
    """Contains message broker."""


class WebStack(core.Stack):
    """Contains airflow web frontend."""


class SchedulerStack(core.Stack):
    """Contains airflow scheduler."""


class WorkerStack(core.Stack):
    """Contains airflow workers."""


class FargateAirflow(core.Construct):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        cloudmap_namespace="airflow.com",
        postgres_password="replacethiswithasecretpassword",
        airflow_webserver_port=80,
        dags_folder="/src/dags",
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
        base_image=None,
        rds_instance=None,
        web_task=None,
        worker_task=None,
        scheduler_task=None,
        message_broker_task=None,
        message_broker_service=None,
        message_broker_service_name="rabbitmq",
        web_service=None,
        scheduler_service=None,
        worker_service=None,
        max_worker_count=16,
        worker_target_memory_utilization=80,
        worker_target_cpu_utilization=80,
        worker_memory_scale_in_cooldown=30,
        worker_memory_scale_out_cooldown=30,
        worker_cpu_scale_in_cooldown=30,
        worker_cpu_scale_out_cooldown=30,
        single_stack=True,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        airflow_stack = AirflowStack(self, "airflow-stack")

        if not single_stack:

            network_stack = NetworkStack(self, "network-stack")

            persistence_stack = PersistenceStack(self, "persistence-stack")

            message_broker_stack = MessageBrokerStack(
                self, "message-broker-stack"
            )

            web_stack = WebStack(self, "web-stack")

            scheduler_stack = SchedulerStack(self, "scheduler-stack")

            worker_stack = WorkerStack(self, "worker-stack")

        vpc = vpc or aws_ec2.Vpc(
            network_stack if not single_stack else airflow_stack, "airflow-vpc"
        )

        cloudmap_namespace_options = aws_ecs.CloudMapNamespaceOptions(
            name=cloudmap_namespace, vpc=vpc
        )

        bucket = bucket or aws_s3.Bucket(
            persistence_stack if not single_stack else airflow_stack,
            "airflow-bucket",
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        core.CfnOutput(
            persistence_stack if not single_stack else airflow_stack,
            "s3-log-bucket",
            value=f"https://s3.console.aws.amazon.com/s3/buckets/{bucket.bucket_name}",
            description="where worker logs are written to",
        )

        log_driver = log_driver or aws_ecs.LogDriver.aws_logs(
            stream_prefix=log_prefix
        )

        env = env or {
            "AIRFLOW__WEBSERVER__WEB_SERVER_PORT": airflow_webserver_port,
            #
            "AIRFLOW__CORE__HOSTNAME_CALLABLE": "socket:gethostname",
            "AIRFLOW__CORE__LOAD_EXAMPLES": load_examples,
            "AIRFLOW__CORE__DAGS_FOLDER": dags_folder,
            "AIRFLOW__CORE__EXECUTOR": executor,
            #
            "AIRFLOW__CORE__REMOTE_BASE_LOG_FOLDER": f"s3://{bucket.bucket_name}/airflow/logs",
            "AIRFLOW__CORE__REMOTE_LOG_CONN_ID": "aws_default",
            "AIRFLOW__CORE__REMOTE_LOGGING": "true",
            "AIRFLOW__CORE__ENCRYPT_S3_LOGS": "false",
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
            #
            "AIRFLOW_VAR_EXAMPLE_S3_CONN": "example_s3_conn",
            "AIRFLOW_VAR_DEFAULT_S3_BUCKET": bucket.bucket_name,
        }

        env = {k: str(v) for k, v in env.items()}

        cluster = cluster or aws_ecs.Cluster(
            network_stack if not single_stack else airflow_stack,
            "cluster",
            vpc=vpc,
            default_cloud_map_namespace=cloudmap_namespace_options,
        )

        base_image = base_image or aws_ecs.ContainerImage.from_registry(
            "knowsuchagency/airflow-cdk"
        )

        rds_instance = rds_instance or aws_rds.DatabaseInstance(
            persistence_stack if not single_stack else airflow_stack,
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
            web_stack if not single_stack else airflow_stack,
            "web-task",
            cpu=1024,
            memory_limit_mib=2048,
        )

        worker_task = worker_task or aws_ecs.FargateTaskDefinition(
            worker_stack if not single_stack else airflow_stack,
            "worker-task",
            cpu=1024,
            memory_limit_mib=2048,
        )

        scheduler_task = scheduler_task or aws_ecs.FargateTaskDefinition(
            scheduler_stack if not single_stack else airflow_stack,
            "scheduler-task",
            cpu=1024,
            memory_limit_mib=2048,
        )

        message_broker_task = (
            message_broker_task
            or aws_ecs.FargateTaskDefinition(
                message_broker_stack if not single_stack else airflow_stack,
                "message-broker-task",
                cpu=1024,
                memory_limit_mib=2048,
            )
        )

        rabbitmq_container = message_broker_task.add_container(
            "rabbitmq_container",
            image=aws_ecs.ContainerImage.from_registry("rabbitmq:management"),
            environment=env,
            logging=log_driver,
            health_check=aws_ecs.HealthCheck(
                command=["CMD", "rabbitmqctl", "status"]
            ),
        )

        rabbitmq_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=5672)
        )

        rabbitmq_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=15672)
        )

        message_broker_service_pre_configured = (
            message_broker_service is not None
        )

        message_broker_service = (
            message_broker_service
            or aws_ecs.FargateService(
                message_broker_stack if not single_stack else airflow_stack,
                "message_broker_service",
                task_definition=message_broker_task,
                cluster=cluster,
            )
        )

        if not message_broker_service_pre_configured:

            message_broker_service.enable_cloud_map(
                name=message_broker_service_name
            )

            message_broker_hostname = (
                f"{message_broker_service_name}.{cloudmap_namespace}"
            )

        for task in web_task, worker_task, scheduler_task:

            bucket.grant_read_write(task.task_role.grant_principal)

        postgres_hostname = rds_instance.db_instance_endpoint_address

        env.update(
            AIRFLOW__CORE__SQL_ALCHEMY_CONN=f"postgresql+psycopg2://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
            AIRFLOW__CELERY__RESULT_BACKEND=f"db+postgresql://{postgres_user}"
            f":{postgres_password}@{postgres_hostname}"
            f":5432/{postgres_db}",
            AIRFLOW__CELERY__BROKER_URL=f"amqp://{message_broker_hostname}",
        )

        web_container = web_task.add_container(
            "web-container",
            image=base_image,
            environment=env,
            logging=log_driver,
        )

        web_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=airflow_webserver_port)
        )

        scheduler_container = scheduler_task.add_container(
            "scheduler-container",
            image=base_image,
            environment=env,
            logging=log_driver,
            command=["scheduler"],
        )

        worker_container = worker_task.add_container(
            "worker-container",
            image=base_image,
            environment=env,
            logging=log_driver,
            command=["worker"],
        )

        web_service = (
            web_service
            or aws_ecs_patterns.ApplicationLoadBalancedFargateService(
                web_stack if not single_stack else airflow_stack,
                "web-service",
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
            scheduler_stack if not single_stack else airflow_stack,
            "scheduler-service",
            task_definition=scheduler_task,
            cluster=cluster,
        )

        worker_service_pre_configured = worker_service is not None

        worker_service = worker_service or aws_ecs.FargateService(
            worker_stack if not single_stack else airflow_stack,
            "worker-service",
            task_definition=worker_task,
            cluster=cluster,
            desired_count=worker_container_desired_count,
        )

        if not worker_service_pre_configured:

            scalable_task_count = worker_service.auto_scale_task_count(
                max_capacity=max_worker_count
            )

            scalable_task_count.scale_on_memory_utilization(
                "memory-utilization-worker-scaler",
                policy_name="memory-utilization-worker-scaler",
                target_utilization_percent=worker_target_memory_utilization,
                scale_in_cooldown=core.Duration.seconds(
                    worker_memory_scale_in_cooldown
                ),
                scale_out_cooldown=core.Duration.seconds(
                    worker_memory_scale_out_cooldown
                ),
            )

            scalable_task_count.scale_on_cpu_utilization(
                "cpu-utilization-worker-scaler",
                policy_name="cpu-utilization-worker-scaler",
                target_utilization_percent=worker_target_cpu_utilization,
                scale_in_cooldown=core.Duration.seconds(
                    worker_cpu_scale_in_cooldown
                ),
                scale_out_cooldown=core.Duration.seconds(
                    worker_cpu_scale_out_cooldown
                ),
            )

        for service in (
            web_service.service,
            scheduler_service,
            worker_service,
        ):

            service.connections.allow_to(
                rds_instance,
                aws_ec2.Port.tcp(5432),
                description="allow connection to RDS",
            )

            service.connections.allow_to(
                message_broker_service.connections,
                aws_ec2.Port.tcp(5672),
                description="allow connection to rabbitmq broker",
            )

            service.connections.allow_to(
                message_broker_service.connections,
                aws_ec2.Port.tcp(15672),
                description="allow connection to rabbitmq management api",
            )
