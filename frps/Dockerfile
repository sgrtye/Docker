ARG FRP_VERSION=0.71.0

FROM alpine:3.22 AS downloader

ARG FRP_VERSION
ARG TARGETARCH

RUN apk add --no-cache curl tar ca-certificates

RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) FRP_ARCH="amd64" ;; \
        arm64) FRP_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
        "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${FRP_ARCH}.tar.gz" \
        -o /tmp/frp.tar.gz; \
    mkdir -p /tmp/frp; \
    tar -xzf /tmp/frp.tar.gz \
        -C /tmp/frp \
        --strip-components=1

FROM alpine:3.22

RUN apk add --no-cache ca-certificates tzdata \
    && addgroup -S frp \
    && adduser -S -G frp frp \
    && mkdir -p /etc/frp

COPY --from=downloader /tmp/frp/frps /usr/local/bin/frps

USER frp

ENTRYPOINT ["/usr/local/bin/frps"]
CMD ["-c", "/etc/frp/frps.toml"]