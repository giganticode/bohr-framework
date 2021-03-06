FROM ubuntu:18.04

WORKDIR /usr/src/bohr-framework

MAINTAINER hlib <hlibbabii@gmail.com>

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    bc \
    build-essential \
    bzip2 \
    curl \
    git \
    libbz2-dev \
    libcairo2-dev \
    libffi-dev \
    libfontconfig-dev \
    libgif-dev \
    libjpeg-dev \
    liblzma-dev \
    libpango1.0-dev \
    libpython3-dev \
    librsvg2-dev \
    libsqlite3-dev \
    libssl-dev \
    openssl \
    p7zip-full \
    python-openssl

#cml
RUN curl -sL https://deb.nodesource.com/setup_15.x | bash
RUN apt-get update
RUN apt-get install -y nodejs
RUN node -v
RUN npm -v

#RUN npm install -g vega-cli vega-lite
RUN npm i -g @dvcorg/cml

RUN unset PYENV_ROOT
RUN curl -L https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer | bash

ENV PATH="/root/.pyenv/bin:$PATH"

RUN pyenv install 3.8.0

COPY . .

RUN curl -fsSL https://get.docker.com -o get-docker.sh
RUN sh get-docker.sh
RUN docker --version

ENV PYTHONPATH="/usr/src/bohr-framework/:$PYTHONPATH"

RUN /root/.pyenv/versions/3.8.0/bin/pip install --upgrade pip wheel setuptools
RUN /root/.pyenv/versions/3.8.0/bin/pip install Cython==0.29.21
RUN /root/.pyenv/versions/3.8.0/bin/pip install -r requirements.txt

RUN bash test-b2b/scenario1/tools/install-refactoring-miner /usr/src/tools/
ENV SOFTWARE_DIR /usr/src/tools

RUN pyenv global 3.8.0
RUN echo 'eval "$(pyenv init -)"' >> /etc/profile
RUN echo "echo \"image built on $(date)\"" >> /etc/profile

