#!/usr/bin/env python3
import json
import re
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    cmd = payload.get("tool_input", {}).get("command", "")

    if "git commit" in cmd and re.search(r"co-authored-by", cmd, re.I):
        print("Blocked: no Co-Authored-By trailers. Commit with a one-line semantic message only.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
