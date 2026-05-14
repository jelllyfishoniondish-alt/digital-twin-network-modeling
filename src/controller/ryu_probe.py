"""Small CLI utility that checks whether the Ryu REST API is reachable."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def probe_ryu(base_url: str, timeout: float = 2.0) -> list[int]:
    """Fetch the switch list from Ryu and return the reported datapath ids."""

    url = f"{base_url.rstrip('/')}/stats/switches"
    with urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.load(response)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the Ryu probe."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)

    try:
        switches = probe_ryu(args.base_url, timeout=args.timeout)
    except (HTTPError, URLError, OSError) as exc:
        print(f"Ryu REST probe failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"switches": switches}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
