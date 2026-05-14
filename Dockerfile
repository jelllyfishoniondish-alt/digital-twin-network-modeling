FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    mininet \
    openvswitch-switch \
    openvswitch-testcontroller \
    python3 \
    python3-pip \
    iputils-ping \
    iproute2 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Ryu with compatible eventlet, then patch the ALREADY_HANDLED import
RUN pip3 install "eventlet==0.33.3" ryu \
    && sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
       /usr/local/lib/python3.10/dist-packages/ryu/app/wsgi.py

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .
