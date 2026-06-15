"""Package 2 (part 2) — create the bootstrap SPCS service and wait for READY.

Confirms the pushed image is in the repository, creates a minimal
long-running service from an inline spec, then polls SYSTEM$GET_SERVICE_STATUS
until the container instance reports READY. Prints SHOW SERVICES status as
evidence. Scope: infra only, no app logic.
"""
import json
import sys
import time

import config
from sf import connect

DB = config.DATABASE
SCHEMA = config.SCHEMA
POOL = config.POOL
SVC = "BOOTSTRAP_SVC"
FQ_SVC = f"{DB}.{SCHEMA}.{SVC}"


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "phase0"
    spec = f"""
spec:
  containers:
    - name: bootstrap
      image: {config.spec_image_path(tag)}
"""
    create_service = f"""
CREATE SERVICE IF NOT EXISTS {FQ_SVC}
  IN COMPUTE POOL {POOL}
  FROM SPECIFICATION $${spec}$$
  MIN_INSTANCES = 1
  MAX_INSTANCES = 1
"""
    try:
        with connect() as conn:
            cur = conn.cursor()

            print("=== IMAGES IN REPOSITORY ===")
            cur.execute(
                f"SHOW IMAGES IN IMAGE REPOSITORY {DB}.{SCHEMA}.{config.IMAGE_REPO}"
            )
            cols = [c[0].lower() for c in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                print(f"  {rec.get('image_name')}  tags={rec.get('tags')}")

            print("\n=== CREATE SERVICE ===")
            cur.execute(create_service)
            print(f"  submitted: {FQ_SVC}")

            print("\n=== POLL FOR READY ===")
            ready = False
            last = None
            for attempt in range(60):  # up to ~10 min
                cur.execute(f"SELECT SYSTEM$GET_SERVICE_STATUS('{FQ_SVC}')")
                raw = cur.fetchone()[0]
                try:
                    instances = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    instances = []
                statuses = [i.get("status") for i in instances]
                last = statuses or raw
                print(f"  [{attempt:02d}] {statuses or raw}")
                if any(s == "READY" for s in statuses):
                    ready = True
                    break
                time.sleep(10)

            print("\n=== SHOW SERVICES ===")
            cur.execute(f"SHOW SERVICES LIKE '{SVC}' IN SCHEMA {DB}.{SCHEMA}")
            cols = [c[0].lower() for c in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                print(f"  name   : {rec.get('name')}")
                print(f"  status : {rec.get('status')}")

            if not ready:
                print(f"\nFAIL: service not READY (last={last})", file=sys.stderr)
                return 1
            print("\nPASS — service instance status = READY")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
