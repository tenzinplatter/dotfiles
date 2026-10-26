import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ORG = "greenroom-robotics/"
TAG = re.compile(r"\[sc-(\d+|none)\]")


def git(cwd: str, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip()


def body_file(command: str, cwd: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    for flag in ("--body-file", "-F"):
        if flag in tokens[:-1]:
            path = Path(cwd, tokens[tokens.index(flag) + 1])
            return path.read_text() if path.is_file() else ""
    return ""


def main() -> None:
    event = json.load(sys.stdin)
    command: str = event.get("tool_input", {}).get("command", "")
    cwd: str = event.get("cwd", ".")
    if not re.search(r"\bgh\s+pr\s+create\b", command):
        return
    if ORG not in command and ORG not in git(cwd, "remote", "get-url", "origin"):
        return
    if TAG.search(command) or TAG.search(body_file(command, cwd)):
        return

    branch = git(cwd, "branch", "--show-current")
    if match := re.search(r"sc-(\d+)", branch):
        hint = f"Branch '{branch}' names story sc-{match.group(1)}: add [sc-{match.group(1)}] to the PR body and retry."
    else:
        hint = (
            "Find the story: use the Shortcut MCP to list stories in the active Platform team iteration(s) "
            "and match against this branch and its changes. If none clearly match, ask the user with "
            "AskUserQuestion for the story id. Then add [sc-<id>] to the PR body and retry. "
            "If the user says there is no story, use [sc-none]."
        )
    print(f"greenroom-robotics PRs must reference a Shortcut story via [sc-<id>] in the body. {hint}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
