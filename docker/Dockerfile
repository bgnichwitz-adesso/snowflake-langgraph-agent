# Orchestrator base image: Python + snowflake-connector-python + langgraph (MIT).
# Dependencies pinned in docker/requirements.txt for reproducibility.
FROM python:3.11-slim

COPY docker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# In-container scripts (cortex test, langgraph flow).
COPY app/ /app/

# Default: stay alive so a long-running service reaches status READY.
# Job-services override this with their own command in the service spec.
CMD ["python", "-u", "-c", "import time, snowflake.connector as c; print('container up — connector', c.__version__, flush=True); time.sleep(1e9)"]
