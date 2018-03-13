FROM centos:centos7.4.1708

RUN yum install -y epel-release
RUN yum install -y fuse-libs gcc git make python2-pip
RUN pip install --upgrade pip

# Build and install libfaketime
RUN git clone --branch v0.9.7 --depth 1 --quiet https://github.com/wolfcw/libfaketime.git
RUN cd libfaketime && make
RUN cp /libfaketime/src/libfaketime.so.1 /usr/lib64/libfaketime.so.1

# Create test script
RUN mkdir /run/libfaketimefs
RUN echo "libfaketimefs /run/libfaketimefs &" > test.sh
#RUN echo "echo '' > /run/libfaketimefs/faketimerc" >> test.sh
RUN echo "watch -n 1 date" >> test.sh
CMD bash test.sh

# Install libfaketimefs
COPY dist/*.whl /
RUN pip install /*.whl

# Enable libfaketime
ENV LD_PRELOAD libfaketime.so.1
ENV FAKETIME_TIMESTAMP_FILE /run/libfaketimefs/faketimerc
ENV FAKETIME_NO_CACHE 1
