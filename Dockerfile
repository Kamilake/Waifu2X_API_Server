FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu20.04
RUN apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/3bf863cc.pub
RUN apt update
RUN export DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true && \
 apt install -y   libboost-system-dev libboost-filesystem-dev libboost-thread-dev libopenblas-dev libboost-iostreams-dev libopenblas-dev libhdf5-dev \
  git build-essential cmake pkg-config libprotobuf-dev libleveldb-dev libsnappy-dev libopencv-dev libhdf5-serial-dev \
 protobuf-compiler libgflags-dev libgoogle-glog-dev liblmdb-dev && apt clean
RUN git clone -b waifu2x-caffe-ubuntu https://github.com/nagadomi/caffe.git /usr/src/lltcggie-caffe && \
  cd /usr/src/lltcggie-caffe && \
  cp Makefile.config.example-ubuntu Makefile.config && \
  make -j$(nproc)
RUN git clone -b ubuntu https://github.com/nagadomi/waifu2x-caffe.git /usr/src/waifu2x-caffe && \
  cd /usr/src/waifu2x-caffe && \
  git submodule update --init --recursive && \
  ln -s ../lltcggie-caffe ./caffe && \
  ln -s ../lltcggie-caffe ./libcaffe
RUN apt install -y sudo nano python3-pip python3-dev python3-setuptools python3-wheel && apt clean
RUN apt install -y cmake && apt clean
RUN cd /usr/src/waifu2x-caffe && ls -lh && rm -fr build && \
  mkdir build && cd build && apt-get install -y libatlas-base-dev && apt clean&& \
  cmake .. -DCUDA_NVCC_FLAGS="-D_FORCE_INLINES -gencode arch=compute_52,code=sm_52 -gencode arch=compute_60,code=sm_60 \
   -gencode arch=compute_61,code=sm_61 -gencode arch=compute_70,code=sm_70 \
   -gencode arch=compute_75,code=sm_75 -gencode arch=compute_80,code=sm_80 \
   -gencode arch=compute_86,code=sm_86" && \
  make -j$(nproc)
RUN cd /usr/src/waifu2x-caffe/build && mv waifu2x-caffe /usr/local/bin/waifu2x-caffe && \
  mkdir -p /opt/libcaffe && mv libcaffe/lib/* /opt/libcaffe/ && echo /opt/libcaffe/ > /etc/ld.so.conf.d/caffe.conf && \
  ldconfig && cd .. && mv bin ../waifu2x && rm -rf /usr/src/waifu2x-caffe && rm -rf /usr/src/lltcggie-caffe && apt clean

RUN apt-get update && apt-get install -y imagemagick && apt clean
RUN groupadd -g 1000 appgroup && \
  useradd -m -s /bin/bash -u 1000 -g appgroup appuser && \
  chown -R appuser:appgroup /usr/src/waifu2x /opt/libcaffe
USER appuser

RUN pip3 install flask werkzeug gunicorn Pillow --user 
ENV PATH="/home/appuser/.local/bin:${PATH}"

RUN waifu2x-caffe --help
WORKDIR /usr/src/waifu2x
COPY app.py /usr/src/waifu2x/app.py
EXPOSE 80

CMD ["gunicorn", "--timeout=60", "-w", "2", "-b", "0.0.0.0:80", "app:app"]

# docker build -t waifu2x-api-server .
# docker tag waifu2x-api-server:latest kamilake/waifu2x-api-server:latest
# docker push kamilake/waifu2x-api-server:latest
# docker run -d kamilake/waifu2x-api-server

# docker run --gpus 1 --user 1000:1000 -p 8080:80 waifu2x-api-server gunicorn --timeout=60 -w 2 -b 0.0.0.0:80 app:app
