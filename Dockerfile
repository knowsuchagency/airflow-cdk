FROM amazonlinux

RUN yum groupinstall -y "Development Tools"

RUN yum install -y python3-devel

RUN mkdir /src

WORKDIR /src

RUN mkdir airflow_cdk

COPY setup.py .

RUN pip3 install -U pip

RUN pip3 install -e .[dev]

COPY . .

ENTRYPOINT ["invoke"]

CMD ["webserver"]