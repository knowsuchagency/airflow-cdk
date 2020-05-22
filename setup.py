import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="airflow_cdk",
    version="0.1.0",
    description="Custom cdk constructs for apache airflow",
    keywords=["aws", "cdk", "airflow", "k8s"],
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Stephan Fitzpatrick",
    package_dir={"": "airflow_cdk"},
    packages=setuptools.find_packages(where="airflow_cdk"),
    install_requires=[
        "apache-airflow[postgres,celery]>=1.10.10",
        "aws-cdk.core>=1.34.1",
        "aws-cdk.aws_ecs>=1.34.1",
        "aws-cdk.aws_ecs_patterns>=1.34.1",
        "aws-cdk.aws_rds>=1.34.1",
        "aws-cdk.aws_s3>=1.34.1",
        "invoke",
    ],
    extras_require={"dev": ["pytest", "toml", "black", "twine"]},
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
