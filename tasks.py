import os

from invoke import task


@task
def bootstrap(c):
    """Bootstrap AWS account for use with cdk."""
    c.run("cdk bootstrap aws://$AWS_ACCOUNT/$AWS_DEFAULT_REGION")


@task(aliases=["format"])
def black(c):
    """Format modules using black."""
    c.run("black airflow_cdk/ setup.py app.py tasks.py")


@task(aliases=["check-black"])
def check_formatting(c):
    """Check that files conform to black standards."""
    c.run("black --check airflow_cdk/ setup.py app.py tasks.py")


@task
def build(c, password=None, username=None):
    username = username or os.getenv("PYPI_USERNAME")
    password = password or os.getenv("PYPI_PASSWORD")
    c.run("rm -rf build/* dist/*")
    c.run("python setup.py sdist bdist_wheel")
    c.run("twine check dist/*")
    return password, username


@task(check_formatting)
def publish(c, username=None, password=None):
    """Publish to pypi."""

    password, username = build(c, password, username)

    c.run(
        f"twine upload -u {username} -p {password} "
        f"--repository-url https://test.pypi.org/legacy/ dist/*"
    )

    c.run(f"twine upload -u {username} -p {password} dist/*")
