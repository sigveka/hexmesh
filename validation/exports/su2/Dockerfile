# SU2 for the .su2 export check (task 0183, decision 0057): the release
# binaries (OpenMP build) on Ubuntu 24.04, both pinned.  SU2 publishes no
# container image or pip package (docs/integrations/su2.md).
#
#     docker build -t hexmesh-su2:8.6.0 validation/exports/su2
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG SU2_ZIP=https://github.com/su2code/SU2/releases/download/v8.6.0/SU2_v8.6.0_linux64-omp.zip
ARG SU2_SHA256=b306dcb7e76caec54e376542916aae14a32abd6c2f6fa8b871ec10ffe80b41ac

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl unzip libgomp1 \
 && curl -fsSL -o /tmp/su2.zip "$SU2_ZIP" \
 && echo "$SU2_SHA256  /tmp/su2.zip" | sha256sum -c - \
 && unzip -q /tmp/su2.zip -d /opt/su2 \
 && rm /tmp/su2.zip \
 && apt-get purge -y curl unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/su2/bin:$PATH
WORKDIR /work
