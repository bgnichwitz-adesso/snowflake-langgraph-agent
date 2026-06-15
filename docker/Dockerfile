# Package 2 — minimal SPCS base image: Python + snowflake-connector-python.
# Scope: no LangGraph, no Cortex, no app logic. A long-running container so the
# bootstrap service reaches status READY.
FROM python:3.11-slim

# langgraph = MIT library only. NOT langgraph-api / langgraph-cli (Elastic 2.0).
RUN pip install --no-cache-dir snowflake-connector-python langgraph

# In-container scripts (cortex test, langgraph flow).
COPY app/ /app/

# Stay alive so SHOW SERVICES reports READY; print a marker on startup.
CMD ["python", "-u", "-c", "import time, snowflake.connector as c; print('container up — connector', c.__version__, flush=True); time.sleep(1e9)"]
