# The deploy unit: what CI tested is byte-for-byte what runs on the instance. Two
# stages so the shipped image carries the venv and the source, never uv or the
# build cache. The builder copies in the uv that wrote uv.lock — a lockfile only
# reproduces when the resolver replaying it matches. The base image is multi-arch;
# CI builds linux/arm64 (the Graviton instance) and linux/amd64 (the workstation)
# from this one file.
FROM python:3.13-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv

WORKDIR /app

# Bytecode compiled at build time, copy-mode links (the cache mount is another
# filesystem), no interpreter downloads (the base image's is the pinned one).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Dependencies before source: the lockfile layer survives every code edit.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.13-slim-bookworm

# Code identity baked at build time: no repo survives into a container. An image
# that cannot state its provenance refuses to BUILD — fail at the cause, not at
# the first run. CI passes --build-arg CODE_VERSION=$(git rev-parse --short HEAD);
# laptop builds append +dirty when the tree has changes.
ARG CODE_VERSION
RUN test -n "$CODE_VERSION" || { echo "CODE_VERSION build arg required — an image without provenance refuses to build" >&2; exit 1; }
ENV LEAVEIMPACT_CODE_VERSION=$CODE_VERSION

# Unprivileged uid 1000 — matches the instance's first user so bind-mounted
# state stays readable by host-side backups without chown games.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY src ./src

# Container-shape defaults only; secrets and host specifics come from Compose.
ENV PATH="/app/.venv/bin:$PATH"

USER app

CMD ["python", "-m", "leaveimpact"]
