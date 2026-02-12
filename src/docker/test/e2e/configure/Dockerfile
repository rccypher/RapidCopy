FROM alpine:3.19

RUN apk add --no-cache curl bash

WORKDIR /
ADD src/docker/wait-for-it.sh /
ADD src/docker/test/e2e/configure/setup_rapidcopy.sh /
CMD ["/setup_rapidcopy.sh"]
