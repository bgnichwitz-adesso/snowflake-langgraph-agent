"""M1 smoke test — prove the Cortex Code CLI + SDK are present in the container.

Both operations are offline (no auth, no egress): `cortex --version` and importing
the pure-python SDK. Prints stable markers so a job log can be asserted:
  CLI: Cortex Code v...
  SDK OK <version>
  AGENT_SMOKE_OK
"""
import subprocess
import sys


def main() -> int:
    try:
        v = subprocess.run(
            ["cortex", "--version"], capture_output=True, text=True, timeout=60
        )
        print("CLI:", (v.stdout or v.stderr).strip(), flush=True)
        if v.returncode != 0:
            print(f"AGENT_SMOKE_FAIL: cortex --version rc={v.returncode}", flush=True)
            return 1

        import cortex_code_agent_sdk  # offline import
        ver = getattr(cortex_code_agent_sdk, "__version__", "?")
        print(f"SDK OK {ver}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"AGENT_SMOKE_FAIL: {type(exc).__name__}: {exc}", flush=True)
        return 1

    print("AGENT_SMOKE_OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
