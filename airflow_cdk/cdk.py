from aws_cdk import (
    core,
    aws_rds,
    aws_ec2,
    aws_s3,
    aws_ecs,
    aws_ecs_patterns,
    aws_elasticloadbalancingv2 as elb,
    aws_route53,
    aws_certificatemanager as certificate_manager,
)


class FargateAirflow(core.Stack):
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
        domain_name=None,
        hosted_zone=None,
        certificate=None,
        load_examples=True,
        web_container_desired_count=1,
        worker_container_desired_count=1,
        worker_cpu=2048,
        worker_memory_limit_mib=4096,
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
        rabbitmq_alb=None,
        web_service=None,
        scheduler_service=None,
        worker_service=None,
        max_worker_count=16,
        worker_target_memory_utilization=80,
        worker_target_cpu_utilization=80,
        worker_memory_scale_in_cooldown=10,
        worker_memory_scale_out_cooldown=10,
        worker_cpu_scale_in_cooldown=10,
        worker_cpu_scale_out_cooldown=10,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = vpc or aws_ec2.Vpc(self, "airflow-vpc")

        cloudmap_namespace_options = aws_ecs.CloudMapNamespaceOptions(
            name=cloudmap_namespace, vpc=vpc
        )

        bucket = bucket or aws_s3.Bucket(
            self,
            "airflow-bucket",
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        core.CfnOutput(
            self,
            "s3-log-bucket",
            value=f"https://s3.console.aws.amazon.com/s3/buckets/{bucket.bucket_name}",
            description="where worker logs are written to",
        )

        log_driver = log_driver or aws_ecs.LogDriver.aws_logs(
            stream_prefix=log_prefix
        )

        environment = {
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
            # commenting out this part, because altering the user and
            # password will affect the way workers authenticate with
            # rabbitmq
            # "RABBITMQ_DEFAULT_USER": ...,
            # "RABBITMQ_DEFAULT_PASS": ...,
        }

        environment.update(env or {})

        environment = {k: str(v) for k, v in environment.items()}

        cluster = cluster or aws_ecs.Cluster(
            self,
            "cluster",
            vpc=vpc,
            default_cloud_map_namespace=cloudmap_namespace_options,
        )

        base_image = base_image or aws_ecs.ContainerImage.from_registry(
            "knowsuchagency/airflow-cdk"
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
            instance_type=aws_ec2.InstanceType("t3.micro"),
            # TODO: turn this on when ready for prod
            deletion_protection=False,
            delete_automated_backups=True,
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        web_task = web_task or aws_ecs.FargateTaskDefinition(
            self,
            "web-task",
            cpu=1024,
            memory_limit_mib=2048,
        )

        worker_task = worker_task or aws_ecs.FargateTaskDefinition(
            self,
            "worker-task",
            cpu=worker_cpu,
            memory_limit_mib=worker_memory_limit_mib,
        )

        scheduler_task = scheduler_task or aws_ecs.FargateTaskDefinition(
            self,
            "scheduler-task",
            cpu=1024,
            memory_limit_mib=2048,
        )

        message_broker_task_pre_configured = message_broker_task is not None

        message_broker_task = (
            message_broker_task
            or aws_ecs.FargateTaskDefinition(
                self,
                "message-broker-task",
                cpu=1024,
                memory_limit_mib=2048,
            )
        )

        if not message_broker_task_pre_configured:

            rabbitmq_container = message_broker_task.add_container(
                "rabbitmq_container",
                image=aws_ecs.ContainerImage.from_registry(
                    "rabbitmq:management"
                ),
                environment=environment,
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
                self,
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

        for task in web_task, worker_task:

            bucket.grant_read_write(task.task_role.grant_principal)

        bucket.grant_delete(worker_task.task_role.grant_principal)

        postgres_hostname = rds_instance.db_instance_endpoint_address

        environment.update(
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
            environment=environment,
            logging=log_driver,
        )

        web_container.add_port_mappings(
            aws_ecs.PortMapping(container_port=airflow_webserver_port)
        )

        scheduler_container = scheduler_task.add_container(
            "scheduler-container",
            image=base_image,
            environment=environment,
            logging=log_driver,
            command=["scheduler"],
        )

        worker_container = worker_task.add_container(
            "worker-container",
            image=base_image,
            environment=environment,
            logging=log_driver,
            command=["worker"],
        )

        web_service_pre_configured = web_service is not None

        hosted_zone = hosted_zone or aws_route53.PublicHostedZone(
            self,
            "hosted-zone",
            zone_name=domain_name,
            comment="rendered from cdk",
        )

        certificate = (
            certificate
            or certificate_manager.DnsValidatedCertificate(
                self,
                "tls-cert",
                hosted_zone=hosted_zone,
                domain_name=domain_name,
            )
        )

        protocol = elb.ApplicationProtocol.HTTPS

        web_service = (
            web_service
            or aws_ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                "web-service",
                task_definition=web_task,
                cluster=cluster,
                desired_count=web_container_desired_count,
                protocol=protocol,
                domain_zone=hosted_zone,
                domain_name=domain_name,
                certificate=certificate,
            )
        )

        if not web_service_pre_configured:

            web_service.target_group.configure_health_check(
                healthy_http_codes="200-399"
            )

        scheduler_service = scheduler_service or aws_ecs.FargateService(
            self,
            "scheduler-service",
            task_definition=scheduler_task,
            cluster=cluster,
        )

        worker_service_pre_configured = worker_service is not None

        worker_service = worker_service or aws_ecs.FargateService(
            self,
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

        rabbitmq_alb_pre_configured = rabbitmq_alb is not None

        rabbitmq_alb = rabbitmq_alb or elb.ApplicationLoadBalancer(
            self,
            "rabbitmq-alb",
            vpc=vpc,
            internet_facing=True,
        )

        if not rabbitmq_alb_pre_configured:

            core.CfnOutput(
                self,
                id="rabbitmqManagement",
                value=f"http://{rabbitmq_alb.load_balancer_dns_name}",
            )

            rabbitmq_listener = rabbitmq_alb.add_listener(
                "rabbitmq-listener", port=80
            )

            # rabbitmq_listener.add_targets(
            #     message_broker_service.load_balancer_target(
            #         container_name=rabbitmq_container.container_name,
            #         # TODO: cdk bug? jsii.errors.JSIIError: Expected a string, got {"$jsii.byref":"Object@10056"}
            #         container_port=15672,
            #     )
            # )

            message_broker_service.register_load_balancer_targets(
                aws_ecs.EcsTarget(
                    container_name=rabbitmq_container.container_name,
                    container_port=15672,
                    new_target_group_id="rabbitmq-management-tg",
                    listener=aws_ecs.ListenerConfig.application_listener(
                        rabbitmq_listener,
                    ),
                )
            )

            rabbitmq_alb.connections.allow_to(
                message_broker_service.connections,
                aws_ec2.Port.tcp(15672),
                description="allow connection to rabbitmq management api",
            )
