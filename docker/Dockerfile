# Orchestrator base image: Python + snowflake-connector-python + langgraph (MIT).
# Dependencies pinned in docker/requirements.txt for reproducibility.
FROM python:3.11-slim

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Cortex Code CLI (native binary) — the agentic worker (M-series) spawns it.
# Downloaded from ai.snowflake.com at BUILD time only; the runtime container has
# no general egress. The pip SDK (cortex-code-agent-sdk) does NOT bundle the CLI.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:${PATH}"
ENV CORTEX_CODE_CLI_PATH="/root/.local/bin/cortex"

# In-container scripts (langgraph flow, agent smoke, orchestrator loop).
COPY app/ /app/

# Default: stay alive so a long-running service reaches status READY.
# Job-services override this with their own command in the service spec.
CMD ["python", "-u", "-c", "import time, snowflake.connector as c; print('container up — connector', c.__version__, flush=True); time.sleep(1e9)"]
