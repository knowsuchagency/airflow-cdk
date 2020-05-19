FROM amazonlinux

RUN yum groupinstall -y "Development Tools"

RUN yum install -y python3-devel

ENV AIRFLOW__CORE__DAGS_FOLDER /src/dags

WORKDIR /src

COPY dags ./dags

COPY tasks.py ./

RUN pip3 install -U pip

ARG REQUIREMENTS

ENV REQUIREMENTS \
    apache-airflow[postgres,celery]>=1.10.10 \
    invoke

RUN pip3 install $REQUIREMENTS

ENTRYPOINT ["invoke"]

CMD ["webserver"]