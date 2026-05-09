#!/usr/bin/env python3
"""
obsidian_sync.py — write a markdown note for one Kestra agent execution
and (optionally) git-commit + push the vault.

This is called as the LAST task of every flow. The wiki-links in each note
are what create the live graph in Obsidian's graph view.

Folder layout it produces inside the vault:

  $OBSIDIAN_VAULT_PATH/
    └── $OBSIDIAN_PROJECT_FOLDER/        (default: kestra-copilot)
        ├── goals/
        │   └── goal_<id>.md
        ├── executions/
        │   └── <iso-ts>_<agent>_<exec_id_short>.md
        ├── tools/
        │   └── tool_<name>.md           (one stub per tool type)
        └── reports/
            └── report_<goal_id>.md      (final summary, written by Communicator)

Usage (from a Kestra Python script task):
  python obsidian_sync.py \\
    --agent planner \\
    --execution-id "{{ execution.id }}" \\
    --parent-id "{{ trigger.executionId | default('') }}" \\
    --goal-id "{{ inputs.goal_id }}" \\
    --input "{{ inputs.goal | truncate(300) }}" \\
    --output "{{ outputs.agent.completion | default('') | truncate(500) }}" \\
    --tools-used "KestraFlow" \\
    --children "<comma-sep child execution ids>" \\
    --status completed
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

# Inside the Kestra container, the user's vault is mounted here:
VAULT = Path(os.environ.get("OBSIDIAN_VAULT_MOUNT", "/obsidian"))
PROJECT = os.environ.get("OBSIDIAN_PROJECT_FOLDER", "kestra-copilot")
AUTOCOMMIT = os.environ.get("OBSIDIAN_GIT_AUTOCOMMIT", "false").lower() == "true"
GRAPHIFY_REMOTE = os.environ.get("GRAPHIFY_REMOTE", "").strip()


def slugify(s: str, max_len: int = 60) -> str:
    """Turn an arbitrary string into a filename-safe slug."""
    out = "".join(c if c.isalnum() else "_" for c in (s or "")).strip("_")
    return (out[:max_len] or "x").lower()


def project_dir(*parts: str) -> Path:
    p = VAULT / PROJECT
    for part in parts:
        p = p / part
    p.mkdir(parents=True, exist_ok=True)
    return p


def wiki(name: str) -> str:
    """Format an Obsidian wiki-link. The graph view uses these to draw edges."""
    return f"[[{name}]]"


def ensure_tool_stub(tool_name: str) -> str:
    """Create a stub note for a tool type if it doesn't exist. Returns the link target name."""
    name = f"tool_{slugify(tool_name)}"
    p = project_dir("tools") / f"{name}.md"
    if not p.exists():
        p.write_text(dedent(f"""\
            ---
            type: tool
            name: {tool_name}
            ---

            # Tool: {tool_name}

            A Kestra plugin tool used by agents in this project. Wiki-linked from every
            execution that called it; appears in the Obsidian graph as a hub node.
            """), encoding="utf-8")
    return name


def ensure_goal_stub(goal_id: str, goal_text: str = "") -> str:
    """Create the goal note if it doesn't exist. Returns the link target name."""
    name = f"goal_{slugify(goal_id)}"
    p = project_dir("goals") / f"{name}.md"
    if not p.exists():
        p.write_text(dedent(f"""\
            ---
            type: goal
            goal_id: {goal_id}
            created: {datetime.now(timezone.utc).isoformat()}
            ---

            # Goal — {goal_id}

            > {goal_text or "(no brief recorded)"}

            ## Executions
            *(child executions will be linked here as they run)*
            """), encoding="utf-8")
    return name


def append_child_link_to_goal(goal_id: str, child_note: str) -> None:
    """Best-effort: append a link to a child execution under the goal's Executions heading."""
    name = f"goal_{slugify(goal_id)}"
    p = project_dir("goals") / f"{name}.md"
    if not p.exists():
        return
    try:
        content = p.read_text(encoding="utf-8")
        link_line = f"- {wiki(child_note)}"
        if link_line not in content:
            content = content.rstrip() + "\n" + link_line + "\n"
            p.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"[obsidian_sync] could not append to goal: {e}", file=sys.stderr)


def write_execution_note(args: argparse.Namespace) -> tuple[Path, str]:
    ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    short_id = slugify(args.execution_id)[:8] or "x"
    note_name = f"{ts_iso}_{slugify(args.agent)}_{short_id}"

    # split out lists
    children = [c.strip() for c in (args.children or "").split(",") if c.strip()]
    tools = [t.strip() for t in (args.tools_used or "").split(",") if t.strip()]

    # ensure linked stubs exist (so graph view has both endpoints)
    goal_link = ensure_goal_stub(args.goal_id, args.input) if args.goal_id else ""
    tool_links = [ensure_tool_stub(t) for t in tools]

    parent_link = ""
    if args.parent_id:
        # if the parent is "goal:<id>", we link to the goal note; otherwise we leave a wiki-link
        # to a sibling execution note (Obsidian will resolve it if/when that note exists).
        if args.parent_id.startswith("goal:"):
            parent_link = wiki(ensure_goal_stub(args.parent_id.split(":", 1)[1]))
        else:
            parent_link = wiki(args.parent_id)

    children_lines = "\n".join(f"- {wiki(c)}" for c in children) or "- _(none)_"
    tools_inline = ", ".join(wiki(t) for t in tool_links) or "_(none)_"
    goal_str = wiki(goal_link) if goal_link else "_(none)_"
    input_block = (args.input or "").strip() or "(empty)"
    output_block = (args.output or "").strip() or "(empty)"

    # Build body line-by-line to avoid dedent issues with multi-line interpolations.
    body = "\n".join([
        "---",
        "type: agent_execution",
        f"agent: {args.agent}",
        f"execution_id: {args.execution_id}",
        f"goal_id: {args.goal_id}",
        f"parent_id: {args.parent_id}",
        f"status: {args.status}",
        f"timestamp: {datetime.now(timezone.utc).isoformat()}",
        f"tools: [{', '.join(tools)}]",
        "---",
        "",
        f"# {args.agent} — {ts_iso}",
        "",
        f"**Goal:** {goal_str}",
        f"**Parent:** {parent_link or '_(root)_'}",
        f"**Status:** `{args.status}`",
        "",
        "## Input",
        "```",
        input_block,
        "```",
        "",
        "## Output",
        "```",
        output_block,
        "```",
        "",
        "## Tools used",
        tools_inline,
        "",
        "## Children spawned",
        children_lines,
        "",
    ])

    p = project_dir("executions") / f"{note_name}.md"
    p.write_text(body, encoding="utf-8")

    # cross-link from the goal note
    if args.goal_id:
        append_child_link_to_goal(args.goal_id, note_name)

    return p, note_name


def git_commit_and_push(message: str) -> None:
    if not AUTOCOMMIT:
        return
    vault = str(VAULT)
    try:
        subprocess.run(
            ["git", "-C", vault, "rev-parse", "--git-dir"],
            check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[obsidian_sync] vault is not a git repo, skipping commit", file=sys.stderr)
        return

    # mark as safe directory in case of UID mismatch with mounted volume
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", vault],
        check=False, capture_output=True,
    )

    subprocess.run(["git", "-C", vault, "add", PROJECT], check=False, capture_output=True)
    res = subprocess.run(
        ["git", "-C", vault, "commit", "-m", message, "--allow-empty"],
        check=False, capture_output=True, text=True,
    )
    print(f"[obsidian_sync] git commit: {res.returncode}")

    # push to default remote (best-effort — never blocks)
    push = subprocess.run(["git", "-C", vault, "push"], check=False, capture_output=True, text=True)
    print(f"[obsidian_sync] git push (default): {push.returncode}")

    # push to graphify remote too if configured
    if GRAPHIFY_REMOTE:
        push2 = subprocess.run(
            ["git", "-C", vault, "push", GRAPHIFY_REMOTE],
            check=False, capture_output=True, text=True,
        )
        print(f"[obsidian_sync] git push ({GRAPHIFY_REMOTE}): {push2.returncode}")


def write_final_report(goal_id: str, brief: str, repo_url: str, slack_status: str,
                       review_status: str, source_filename: str) -> Path:
    """Communicator writes this at the end. Links to goal + every execution under that goal."""
    name = f"report_{slugify(goal_id)}"
    p = project_dir("reports") / f"{name}.md"

    # Find every execution note tied to this goal_id (frontmatter goal_id field).
    exec_dir = project_dir("executions")
    linked = []
    for child in sorted(exec_dir.iterdir()):
        if not child.is_file() or not child.name.endswith(".md"):
            continue
        try:
            head = child.read_text(encoding="utf-8")[:600]
            if f"goal_id: {goal_id}" in head:
                linked.append(child.stem)
        except Exception:
            continue

    goal_link = ensure_goal_stub(goal_id, brief)
    exec_lines = [f"- {wiki(n)}" for n in linked] if linked else ["- _(none found)_"]
    body = "\n".join([
        "---",
        "type: final_report",
        f"goal_id: {goal_id}",
        f"created: {datetime.now(timezone.utc).isoformat()}",
        f"repo_url: {repo_url or '(none)'}",
        "---",
        "",
        f"# Final report — {goal_id}",
        "",
        f"**Goal:** {wiki(goal_link)}",
        f"**Brief:** {brief[:300]}",
        "",
        "## Outcome",
        f"- **Repo:** {repo_url or '_(not created)_'}",
        f"- **Slack:** `{slack_status}`",
        f"- **Review:** `{review_status}`",
        f"- **Source file:** `{source_filename or '(n/a)'}`",
        "",
        "## All executions",
        *exec_lines,
        "",
    ])
    p.write_text(body, encoding="utf-8")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True, help="agent name: planner, researcher, coder, reviewer, communicator")
    ap.add_argument("--execution-id", required=True, help="Kestra execution id, usually {{ execution.id }}")
    ap.add_argument("--goal-id", default="", help="stable id for the whole run, ties all executions to one goal")
    ap.add_argument("--parent-id", default="", help="id of the spawning execution, or 'goal:<id>' for the root")
    ap.add_argument("--input", default="", help="short description of input (truncated upstream)")
    ap.add_argument("--output", default="", help="short description of output (truncated upstream)")
    ap.add_argument("--tools-used", default="", help="comma-separated list of tool names used")
    ap.add_argument("--children", default="", help="comma-separated list of child execution ids spawned")
    ap.add_argument("--status", default="completed", help="completed | failed | warning")
    # Optional final-report mode (used by Communicator).
    ap.add_argument("--report", action="store_true", help="also write a reports/report_<goal_id>.md note")
    ap.add_argument("--repo-url", default="", help="GitHub repo URL (for the final report)")
    ap.add_argument("--slack-status", default="", help="Slack post status string (for the final report)")
    ap.add_argument("--review-status", default="", help="Reviewer status string (for the final report)")
    ap.add_argument("--source-filename", default="", help="Coder's filename (for the final report)")
    args = ap.parse_args()

    try:
        path, note_name = write_execution_note(args)
        print(f"[obsidian_sync] wrote {path}")
    except Exception as e:
        # logging-only failure: we never block the Kestra execution on Obsidian errors
        print(f"[obsidian_sync] WRITE FAILED: {e}", file=sys.stderr)
        return 0

    if args.report and args.goal_id:
        try:
            rp = write_final_report(
                goal_id=args.goal_id,
                brief=args.input or "",
                repo_url=args.repo_url,
                slack_status=args.slack_status,
                review_status=args.review_status,
                source_filename=args.source_filename,
            )
            print(f"[obsidian_sync] wrote final report {rp}")
        except Exception as e:
            print(f"[obsidian_sync] REPORT WRITE FAILED: {e}", file=sys.stderr)

    try:
        short = (args.execution_id or "")[:8]
        git_commit_and_push(f"kestra: {args.agent} {short}")
    except Exception as e:
        print(f"[obsidian_sync] git step failed (non-fatal): {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
