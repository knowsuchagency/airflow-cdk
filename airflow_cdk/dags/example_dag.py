"""
Do things.
"""
import datetime as dt
import typing as T
from dataclasses import dataclass
from functools import partial
from pprint import pprint

from airflow.models import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import PythonOperator

dag = DAG(
    dag_id="example_dag_v1_p3",
    default_args={
        "owner": "Stephan Fitzpatrick",
        "email": "knowsuchagency@gmail.com",
        "start_date": dt.datetime(*map(int, "2019-02-12".split("-"))),
    },
    schedule_interval="0 7 * * *",

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


def validate(task_instance, **kwargs):
    """ABV always be validating."""
    example_result = task_instance.xcom_pull(task_ids="hello_airflow")

    assert example_result.string == "hello airflow", "failed, as expected"


with dag:

    start = DummyOperator(task_id="start")

    start >> PythonOperator(
        task_id="hello_airflow",
        python_callable=partial(hello_airflow, argument="I'm a teapot"),
        provide_context=True,
        depends_on_past=True
    ) >> PythonOperator(
        task_id="validate_hello_airflow",
        python_callable=validate,
        provide_context=True,
    )
