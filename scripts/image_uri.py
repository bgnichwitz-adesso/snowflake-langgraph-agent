"""Print the fully-qualified registry image URI for a given tag.

Derives the registry host from the live image repository (SHOW IMAGE
REPOSITORIES) so nothing account-specific is hardcoded. The image repository
must already exist (run p2_infra.py first).

Usage: image_uri.py <tag>   ->   <host>/<db>/<schema>/<repo>/<image>:<tag>
"""
import sys

import config
from sf import connect


def repository_url() -> str:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SHOW IMAGE REPOSITORIES LIKE '{config.IMAGE_REPO}' "
            f"IN SCHEMA {config.DATABASE}.{config.SCHEMA}"
        )
        cols = [c[0].lower() for c in cur.description]
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"image repository {config.DATABASE}.{config.SCHEMA}."
                f"{config.IMAGE_REPO} not found — run p2_infra.py first"
            )
        return dict(zip(cols, row))["repository_url"]


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "latest"
    print(f"{repository_url()}/{config.IMAGE_NAME}:{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
