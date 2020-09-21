"""
Do things.
"""
import datetime as dt
import os
import typing as T
from dataclasses import dataclass
from functools import partial
from pprint import pprint

from airflow.hooks.S3_hook import S3Hook
from airflow.models import DAG, Variable
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import PythonOperator

dag = DAG(
    dag_id="{{ dag_id }}",
    default_args={
        "owner": "{{ owner }}",
        "email": "{{  email }}",
        "start_date": dt.datetime(*map(int, "{{ start_date }}".split("-"))),
    },
    schedule_interval="{{ schedule_interval }}",
)


@dataclass
class ExampleResult:
    string: T.Optional[str]


def hello_airflow(execution_date: dt.datetime, argument=None, **kwargs):
    """
    Print the execution date (and other variables passed from airflow).
    Args:
        execution_date (dt.datetime): the time of the dag's execution (passed by airflow)
        argument: an example argument
        **kwargs: other variables passed from airflow
    """
    print(f"argument passed was: {argument}")
    print(f"execution date is: {execution_date}")
    print("variables (besides execution_date) passed from airflow:")
    pprint(kwargs)

    return ExampleResult(string="aloha, airflow")


def validate_hello_airflow(task_instance, **kwargs):
    """ABV always be validating."""
    example_result = task_instance.xcom_pull(task_ids="hello_airflow")

    assert example_result.string == "hello airflow", "failed, as expected"


def print_environment_variables():
    print("environment variables:")
    pprint(dict(os.environ))


def test_s3_hook_write():
    bucket = Variable.get("default_s3_bucket")

    profile = Variable.get(
        "test_airflow_hook_s3_profile", default_var="aws_default"
    )
    s3_hook = S3Hook(profile)

    key = "hello_airflow.txt"

    s3_hook.load_string(
        "hello, airflow",
        key=key,
        bucket_name=bucket,
        replace=True,
    )

    return bucket, profile, key


def test_s3_hook_delete(task_instance, **kwargs):
    bucket, profile, key = task_instance.xcom_pull(
        task_ids=test_s3_hook_write.__name__
    )

    s3_hook = S3Hook(profile)

    s3_hook.delete_objects(bucket, key)


with dag:

    _start = DummyOperator(task_id="start")

    _hello_airflow_operator = PythonOperator(
        task_id=hello_airflow.__name__,
        python_callable=partial(hello_airflow, argument="I'm a teapot"),
        provide_context=True,
    )

    _validate_hello_airflow_operator = PythonOperator(
        task_id=validate_hello_airflow.__name__,
        python_callable=validate_hello_airflow,
        provide_context=True,
    )

    _print_environment_variables = PythonOperator(
        task_id=print_environment_variables.__name__,
        python_callable=print_environment_variables,
        provide_context=False,
    )

    _test_airflow_hook_write = PythonOperator(
        task_id=test_s3_hook_write.__name__,
        python_callable=test_s3_hook_write,
        provide_context=False,
    )

    _test_airflow_hook_delete = PythonOperator(
        task_id=test_s3_hook_delete.__name__,
        python_callable=test_s3_hook_delete,
        provide_context=True,
    )

    _start >> _hello_airflow_operator >> _validate_hello_airflow_operator

    _start >> [_print_environment_variables, _test_airflow_hook_write]

    _test_airflow_hook_write >> _test_airflow_hook_delete
