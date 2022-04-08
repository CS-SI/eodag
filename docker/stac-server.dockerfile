FROM python:3.9-slim

# start from root
WORKDIR /eodag

ENV \
    # force stdin, stdout and stderr to be totally unbuffered. (equivalent to `python -u`)
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files(equivalent to `python -B`)
    PYTHONDONTWRITEBYTECODE=1 \
    # enable hash randomization (equivalent to `python -R`)
    PYTHONHASHSEED=random \
    # fault handler (equivalent to `python -X`)
    PYTHONFAULTHANDLER=1 \
    # python encoding
    PYTHONIOENCODING=UTF-8 \
    \
    # set pip settings
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # set time.zone
    TZ=UTC

# update system
RUN apt-get update \
    && apt-get upgrade -y

# reconfigure timezone
RUN echo $TZ > /etc/timezone && \
    apt-get install -y tzdata && \
    rm /etc/localtime && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean

# install locales
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y locales

# ensure locales are configured correctly
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8

# copy necessary files
COPY setup.py setup.py
COPY setup.cfg setup.cfg
COPY pyproject.toml pyproject.toml
COPY README.rst README.rst
COPY ./eodag /eodag/eodag

# install eodag
RUN python setup.py install

# add python path
ENV PYTHONPATH="${PYTHONPATH}:/eodag/eodag"

# copy start-stac script
COPY ./docker/run-stac-server.sh /eodag/run-stac-server.sh

# and make executable
RUN chmod +x /eodag/run-stac-server.sh

# add user
RUN addgroup --system user \
    && adduser --system --group user

# switch to non-root user
USER user

# and then start STAC
CMD ["/bin/bash", "/eodag/run-stac-server.sh"]
