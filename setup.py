from pathlib import Path

import setuptools

setuptools.setup(
    name="airflow_cdk",
    version=Path("VERSION").read_text().strip(),
    description="Custom cdk constructs for apache airflow",
    url="https://github.com/knowsuchagency/airflow-cdk",
    keywords=["aws", "cdk", "airflow", "k8s"],
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Stephan Fitzpatrick",
    author_email="stephan@knowsuchagency.com",
    license_files=["LICENSE"],
    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=[
        "aws-cdk.core>=1.34.1",
        "aws-cdk.aws_ecs>=1.34.1",
        "aws-cdk.aws_ecs_patterns>=1.34.1",
        "aws-cdk.aws_rds>=1.34.1",
        "aws-cdk.aws_s3>=1.34.1",
        "aws-cdk.aws_elasticloadbalancingv2>=1.34.1",
    ],
    extras_require={"dev": ["pytest", "toml", "black", "twine", "invoke"]},
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
