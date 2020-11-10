# ==================================================================
# module list
# ------------------------------------------------------------------
# cuda          9.0    (apt)
# python        3.6    (apt)
# jupyter       latest (pip)
# pytorch       1.1.0  (pip)
# tensorflow    1.12.2  (pip)
# keras         2.1.6  (pip)
# opencv        4.1.0  (git)
# ==================================================================

FROM nvidia/cuda:9.0-cudnn7-devel-ubuntu16.04
RUN APT_INSTALL="apt-get install -y --no-install-recommends" && \
    PIP_INSTALL="python -m pip --no-cache-dir install --upgrade" && \
    GIT_CLONE="git clone --depth 10" && \

    rm -rf /var/lib/apt/lists/* \
           /etc/apt/sources.list.d/cuda.list \
           /etc/apt/sources.list.d/nvidia-ml.list && \

    apt-get update && \
# ==================================================================
# tools
# ------------------------------------------------------------------

    DEBIAN_FRONTEND=noninteractive $APT_INSTALL \
        build-essential \
        libcupti-dev \
        ca-certificates \
        cmake \
        curl \
        wget \
        unzip \
        git \
        tmux \
	graphviz \
        vim \

# ==================================================================
# python
# ------------------------------------------------------------------

    DEBIAN_FRONTEND=noninteractive $APT_INSTALL \
        software-properties-common \
        && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive $APT_INSTALL \
        python3.6 \
        python3.6-dev \
        python3.6-tk \
        && \
    wget -O ~/get-pip.py \
        https://bootstrap.pypa.io/get-pip.py && \
    python3.6 ~/get-pip.py && \
    ln -s /usr/bin/python3.6 /usr/local/bin/python3 && \
    ln -s /usr/bin/python3.6 /usr/local/bin/python && \
    $PIP_INSTALL \
        setuptools \
        && \

# ==================================================================
# jupyter
# ------------------------------------------------------------------

    $PIP_INSTALL \
        jupyter \
        && \

# ==================================================================
# pytorch
# ------------------------------------------------------------------

    $PIP_INSTALL \
        torch \
        torchvision \
        ontextlib2 \
        pillow \
        lxml \
        && \

# ==================================================================
# tensorflow
# ------------------------------------------------------------------

    $PIP_INSTALL \
        tensorflow-gpu==1.12.2 \
        && \

# ==================================================================
# keras
# ------------------------------------------------------------------

    $PIP_INSTALL \
        h5py \
	keras==2.1.6 \
        && \

# ==================================================================
# opencv
# ------------------------------------------------------------------

    $PIP_INSTALL \
        opencv-python \
        && \

# ==================================================================
# config & cleanup
# ------------------------------------------------------------------

    ldconfig && \
    apt-get clean && \
    apt-get autoremove && \
    rm -rf /var/lib/apt/lists/* /tmp/* ~/*

# ==================================================================
# install pip packages from requirements text file
# ------------------------------------------------------------------

    ADD requirements.txt /tmp/requirements.txt
    RUN pip install --no-cache-dir -r /tmp/requirements.txt


# ==================================================================
# Clone github tensorflow models repo 
# Get the tensorflow models research directory, and move it into tensorflow
# source folder to match recommendation of installation
# ------------------------------------------------------------------
RUN mkdir tensorflow && cd tensorflow
RUN git clone https://github.com/tensorflow/models.git && \
    (cd models && git checkout f788046ca876a8820e05b0b48c1fc2e16b0955bc) && \
    mv models /tensorflow/models

# ==================================================================
# Install object detection api dependencies
# ------------------------------------------------------------------

RUN apt-get update && \
    apt-get install -y python python-tk curl

# ===========================================================================================================
# Get protoc 3.0.0, rather than the old version already in the container
# -----------------------------------------------------------------------------------------------------------

RUN curl -OL "https://github.com/google/protobuf/releases/download/v3.0.0/protoc-3.0.0-linux-x86_64.zip" && \
    unzip protoc-3.0.0-linux-x86_64.zip -d proto3 && \
    mv proto3/bin/* /usr/local/bin && \
    mv proto3/include/* /usr/local/include && \
    rm -rf proto3 protoc-3.0.0-linux-x86_64.zip

# =====================================================================
# Install pycocoapi
# ---------------------------------------------------------------------

RUN git clone --depth 1 https://github.com/cocodataset/cocoapi.git && \
    cd cocoapi/PythonAPI && \
    make -j8 && \
    cp -r pycocotools /tensorflow/models/research && \
    cd ../../ && \
    rm -rf cocoapi

# ==================================================================
# Run protoc on the object detection repo
# ------------------------------------------------------------------

RUN cd /tensorflow/models/research && \
    protoc object_detection/protos/*.proto --python_out=.

# =====================================================================================
# Set the PYTHONPATH to finish installing the API
# -------------------------------------------------------------------------------------

ENV PYTHONPATH $PYTHONPATH:/tensorflow/models/research:/tensorflow/models/research/slim

# ===================================================================
# Install edgetpu compiler
# -------------------------------------------------------------------

RUN curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

RUN echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list

RUN apt-get update && \
    apt-get install -y edgetpu-compiler

# ==================================================================
# Get object detection transfer learning scripts
# ------------------------------------------------------------------

ARG work_dir=/tensorflow/models/research
COPY scripts/ ${work_dir}/
WORKDIR ${work_dir}

EXPOSE 8888 6006
