# The deploy unit: what CI tested is byte-for-byte what runs on the instance. Two
# stages so the shipped image carries the venv and the source, never uv or the
# build cache. The builder copies in the uv that wrote uv.lock — a lockfile only
# reproduces when the resolver replaying it matches. The base image is multi-arch;
# CI builds linux/arm64 (the Graviton instance) and linux/amd64 (the workstation)
# from this one file.
# Pulled from this repository's GHCR mirror of the Docker Hub library at the library's
# own index digest (mirror-base-images.yml): the shared GitHub runner pool's anonymous
# quota failed CI closed on Docker Hub and then on the public ECR mirror, and a rerun
# only redraws the pool's IP. The tag is the human label; the digest is the identity.
FROM ghcr.io/arda-basarici/leave-impact-agent/python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641 AS builder
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


FROM ghcr.io/arda-basarici/leave-impact-agent/python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641

# Code identity baked at build time: no repo survives into a container. An image
# that cannot state its provenance refuses to BUILD — fail at the cause, not at
# the first run. CI passes --build-arg CODE_VERSION=$(git rev-parse HEAD), the full
# sha, which the agent's commands require of the image they run in; laptop builds
# mint a short form with +dirty appended, an identity those commands refuse.
ARG CODE_VERSION
RUN test -n "$CODE_VERSION" || { echo "CODE_VERSION build arg required — an image without provenance refuses to build" >&2; exit 1; }
ENV LEAVEIMPACT_CODE_VERSION=$CODE_VERSION

# Unprivileged, fixed uid: the process owns nothing on disk (the only state is
# PostgreSQL's, in its own container), and a stable uid keeps file ownership
# predictable if a mount ever appears.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY src ./src
# The committed registration, so the demo surface folds a replayed run under the rules its
# admission froze; the service checks the file's digest against the demo configuration's
# registration digest at start, so the copy can never silently drift from the configuration.
COPY preregistration/registration.json ./preregistration/registration.json

# Container-shape defaults only; secrets and host specifics come from Compose.
ENV PATH="/app/.venv/bin:$PATH" \
    LEAVEIMPACT_REGISTRATION_FILE=/app/preregistration/registration.json

USER app

CMD ["python", "-m", "leaveimpact"]
