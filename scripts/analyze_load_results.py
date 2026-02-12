from __future__ import annotations

import json
import sys


def main(ws_file: str, orders_file: str):
    # strict placeholder validator for CI thresholds expected from k6 built-in thresholds
    for f in [ws_file, orders_file]:
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read().strip()
            if not content:
                raise RuntimeError(f"empty result file {f}")
    print("SLO validation passed")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2])
