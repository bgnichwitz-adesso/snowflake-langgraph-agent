# Orchestrator base image: Python + snowflake-connector-python + langgraph (MIT).
# Dependencies pinned in docker/requirements.txt for reproducibility.
FROM python:3.11-slim

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Cortex Code CLI (native binary) — the agentic worker (M-series) spawns it.
# PINNED to a fixed version (M2): the installer only pulls "latest", so we replicate
# its download directly from sfc-repo with a sha256 check → reproducible builds, and
# it dodges the risk of a future "stable" flipping to a Node.js build. The pip SDK
# (cortex-code-agent-sdk) does NOT bundle the CLI. Build-time egress only (sfc-repo).
ARG CORTEX_VERSION="1.1.66+001753.801adc2b71d7"
ARG CORTEX_SHA256="9edd273d408164cbc06c7e733b4e3edfa37730d3973adfb908133bc7e1a41371"
ARG CORTEX_REPO="https://sfc-repo.snowflakecomputing.com/cortex-code-cli/a4643c4278"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && enc_ver="$(printf '%s' "$CORTEX_VERSION" | sed 's/+/%2B/g')" \
 && tarname="coco-${CORTEX_VERSION}-linux-amd64.tar.gz" \
 && enc_tar="$(printf '%s' "$tarname" | sed 's/+/%2B/g')" \
 && curl -fL "${CORTEX_REPO}/${enc_ver}/${enc_tar}" -o /tmp/cc.tar.gz \
 && echo "${CORTEX_SHA256}  /tmp/cc.tar.gz" | sha256sum -c - \
 && mkdir -p "/root/.local/share/cortex/${CORTEX_VERSION}" /root/.local/bin \
 && tar -xzf /tmp/cc.tar.gz -C "/root/.local/share/cortex/${CORTEX_VERSION}" --strip-components=1 \
 && chmod +x "/root/.local/share/cortex/${CORTEX_VERSION}/cortex" \
 && ln -sf "/root/.local/share/cortex/${CORTEX_VERSION}/cortex" /root/.local/bin/cortex \
 && rm -f /tmp/cc.tar.gz \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:${PATH}"
ENV CORTEX_CODE_CLI_PATH="/root/.local/bin/cortex"

# In-container scripts (langgraph flow, agent smoke, orchestrator loop).
COPY app/ /app/

# Default: stay alive so a long-running service reaches status READY.
# Job-services override this with their own command in the service spec.
CMD ["python", "-u", "-c", "import time, snowflake.connector as c; print('container up — connector', c.__version__, flush=True); time.sleep(1e9)"]
