FROM ghcr.io/astral-sh/uv:0.12.5@sha256:db2d5999728c5837e1bf9ba278ee6b05cef1e95e82a20e27b0c915cb4478b9d7 AS uv

FROM python:3.12.11-slim-bookworm@sha256:c00fc7b44d844b6da22861ec24af43968a5200eac4ec607b4725d585165d6b49 AS builder
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/perfeng-analysis
WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.12.11-slim-bookworm@sha256:c00fc7b44d844b6da22861ec24af43968a5200eac4ec607b4725d585165d6b49
ARG VCS_REF=unknown
LABEL org.opencontainers.image.source="https://github.com/stanimirivanov/perfeng-analysis" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.title="perfeng-analysis"
ENV PATH="/opt/perfeng-analysis/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY --from=builder /opt/perfeng-analysis /opt/perfeng-analysis
WORKDIR /work
USER 65532:65532
ENTRYPOINT ["perfeng-analysis"]
CMD ["--help"]
