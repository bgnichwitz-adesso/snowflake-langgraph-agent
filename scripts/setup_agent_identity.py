"""M6/B — provision the agent SQL identity (service user + PAT + SPCS secret).

The developer agent's SQL tool must run as a LEAST-PRIV role (ORCH_APP_<ID>: project-DB
read-write + Cortex, NO orchestrator artifact schema) so it can't read held-out tests.
In one SPCS container the agent needs a credential DISTINCT from the gate's OAuth token,
so we mint a role-restricted Programmatic Access Token (PAT) for a shared service user
and store it as an SPCS secret the loop job mounts as env AGENT_PAT.

Run AFTER register_project (which creates ORCH_APP_<ID> + its grants).
  setup_agent_identity.py --id DEMO
Idempotent: re-running rotates the PAT and replaces the secret.

Security notes: the PAT is role-restricted to ORCH_APP_<ID> (blast radius = the project
DB). The secret lives in the artifact schema (ORCHESTRATOR.<ID>) which ORCH_APP CANNOT
reach — only the service-owner ORCH_PROJ_<ID> gets USAGE to mount it. PAT expiry below.
"""
import argparse
import sys

import config
from sf import connect

DAYS_TO_EXPIRY = 90


def _rows(cur, sql):
    cur.execute(sql)
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="project id, e.g. DEMO")
    a = ap.parse_args()
    pid = a.id.upper()
    app = config.app_role(pid)                    # ORCH_APP_<ID>
    proj = config.project_role(pid)               # ORCH_PROJ_<ID> (service owner)
    user = config.AGENT_USER                      # ORCH_AGENT (shared service user)
    secret = config.app_pat_secret(pid)           # ORCHESTRATOR.<ID>.AGENT_PAT
    token_name = f"PAT_{pid}"

    try:
        with connect() as conn:
            cur = conn.cursor()

            # 0) the app role must already exist (register_project)
            if not _rows(cur, f"SHOW ROLES LIKE '{app}'"):
                raise RuntimeError(f"role {app} missing — run register_project first")

            # 1) shared service user (no password; PAT/keypair only), tagged
            cur.execute(f"CREATE USER IF NOT EXISTS {user} TYPE = SERVICE "
                        f"COMMENT = '{config.MANAGED_BY}'")
            cur.execute(f"GRANT ROLE {app} TO USER {user}")

            # 1b) Snowflake requires a network policy to mint a PAT. Scope it to THIS
            #     service user only (not the account). The PAT's real protection is
            #     role-restriction (ORCH_APP) + expiry; the policy just satisfies the
            #     requirement. (For tighter scoping, replace 0.0.0.0/0 with the SPCS
            #     egress range, or switch to key-pair auth which needs no policy.)
            netpol = f"{user}_NETPOL"
            cur.execute(f"CREATE NETWORK POLICY IF NOT EXISTS {netpol} "
                        f"ALLOWED_IP_LIST = ('0.0.0.0/0') "
                        f"COMMENT = '{config.MANAGED_BY}'")
            cur.execute(f"ALTER USER {user} SET NETWORK_POLICY = {netpol}")

            # 2) (re)mint a role-restricted PAT — rotate on re-run
            try:
                cur.execute(f"ALTER USER {user} REMOVE PROGRAMMATIC ACCESS TOKEN {token_name}")
            except Exception:  # noqa: BLE001
                pass
            recs = _rows(
                cur,
                f"ALTER USER {user} ADD PROGRAMMATIC ACCESS TOKEN {token_name} "
                f"ROLE_RESTRICTION = '{app}' DAYS_TO_EXPIRY = {DAYS_TO_EXPIRY}")
            rec = recs[0] if recs else {}
            pat = rec.get("token_secret") or rec.get("token") or rec.get("secret")
            if not pat:
                raise RuntimeError(f"could not read PAT secret from result: {rec}")

            # 3) store as an SPCS secret in the artifact schema (ORCH_APP can't reach
            #    it; the service owner ORCH_PROJ gets USAGE to mount it)
            cur.execute(f"CREATE OR REPLACE SECRET {secret} TYPE = GENERIC_STRING "
                        f"SECRET_STRING = '{pat}'")
            cur.execute(f"GRANT USAGE ON SECRET {secret} TO ROLE {proj}")

            # 4) evidence (never print the PAT)
            print(f"  service user : {user} (role {app} granted)")
            print(f"  PAT          : {token_name} role-restricted={app} "
                  f"expiry={DAYS_TO_EXPIRY}d (secret hidden)")
            print(f"  secret       : {secret} (USAGE -> {proj})")
            toks = _rows(cur, f"SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER {user}")
            have = any(t.get("name", "").upper() == token_name for t in toks)
            secs = _rows(cur, f"SHOW SECRETS LIKE 'AGENT_PAT' IN SCHEMA {config.artifact_schema(pid)}")
            ok = have and bool(secs)
            print(f"\n{'PASS — agent identity ready for ' + pid if ok else 'FAIL'}")
            return 0 if ok else 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
