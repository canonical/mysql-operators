#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Agentic bug-fix workflow for mysql-operators.

Scans open GitHub issues labelled **bug**, analyses each against the codebase
with Claude, and opens a pull request when the fix confidence is high.

Two-phase design
────────────────
Phase 1 — *Analysis*   Read-only exploration. The agent investigates the bug
                        and returns a confidence score.  No files are modified.
Phase 2 — *Fix*        Only entered when confidence ≥ threshold.  The agent
                        edits files, then changes are committed and a PR is
                        opened.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import anthropic

# ── Logging ───────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("bug-fix-agent")

# ── Configuration ─────────────────────────────────────────────────────

MODEL = "claude-opus-4-5"
MAX_TOKENS = 16_384
MAX_AGENT_TURNS = 40
MAX_ISSUES = int(os.environ.get("MAX_ISSUES", "5"))
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.85"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
SINGLE_ISSUE = os.environ.get("SINGLE_ISSUE", "").strip() or None
REPO_ROOT = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
_BASE_BRANCH_OVERRIDE = os.environ.get("BASE_BRANCH", "").strip() or None
DEFAULT_BASE_BRANCH = "8.0/edge"
BRANCH_PREFIX = "auto-fix"

# Tag prefixes used to map revision numbers to branches.
# mysql-k8s/revNNN → k8s charm revision, mysql/revNNN → VM charm revision.
_REVISION_TAG_PREFIXES = ("mysql-k8s/rev", "mysql/rev")

client = anthropic.Anthropic()

# ── Tool schemas ──────────────────────────────────────────────────────

READ_FILE = {
    "name": "read_file",
    "description": (
        "Read the contents of a file. Returns numbered lines. "
        "Use start_line / end_line to read a slice of large files."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the repository root.",
            },
            "start_line": {
                "type": "integer",
                "description": "1-based first line to return (inclusive, optional).",
            },
            "end_line": {
                "type": "integer",
                "description": "1-based last line to return (inclusive, optional).",
            },
        },
        "required": ["path"],
    },
}

SEARCH_CODE = {
    "name": "search_code",
    "description": (
        "Grep the codebase for a regex pattern. "
        "Returns matching lines with file paths and line numbers (capped at 8 KB)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Extended regex (grep -E)."},
            "path": {
                "type": "string",
                "description": "Directory to search in, relative to repo root (default: .).",
            },
            "include": {
                "type": "string",
                "description": "File-name glob, e.g. '*.py'.",
            },
        },
        "required": ["pattern"],
    },
}

LIST_FILES = {
    "name": "list_files",
    "description": "List files and directories under a path.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to list (default: repo root).",
            },
            "pattern": {
                "type": "string",
                "description": "Glob filter, e.g. '*.py'.",
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum directory depth (default: 3).",
            },
        },
    },
}

RUN_COMMAND = {
    "name": "run_command",
    "description": (
        "Run a shell command for read-only inspection (git log, python -m py_compile, etc.). "
        "Destructive commands are blocked."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
        },
        "required": ["command"],
    },
}

EDIT_FILE = {
    "name": "edit_file",
    "description": (
        "Replace an exact substring in a file. "
        "old_content must appear exactly once; include surrounding lines for uniqueness."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to repo root."},
            "old_content": {"type": "string", "description": "Exact text to replace."},
            "new_content": {"type": "string", "description": "Replacement text."},
        },
        "required": ["path", "old_content", "new_content"],
    },
}

CREATE_FILE = {
    "name": "create_file",
    "description": "Create a new file (fails if it already exists).",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to repo root."},
            "content": {"type": "string", "description": "Full file content."},
        },
        "required": ["path", "content"],
    },
}

SUBMIT_ANALYSIS = {
    "name": "submit_analysis",
    "description": (
        "Submit your bug analysis.  Call this once you have finished investigating."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "confidence": {
                "type": "number",
                "description": (
                    "0.0–1.0 confidence that you can produce a correct, complete, "
                    "and safe fix.  Be conservative — data loss is unacceptable."
                ),
            },
            "root_cause": {"type": "string", "description": "Root-cause analysis."},
            "proposed_fix": {
                "type": "string",
                "description": "Detailed description of the fix you would apply.",
            },
            "files_to_modify": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files that need changes.",
            },
            "risk_assessment": {
                "type": "string",
                "description": "Potential risks and side-effects of the fix.",
            },
            "test_strategy": {
                "type": "string",
                "description": "How to verify the fix (unit tests, integration tests, manual).",
            },
        },
        "required": [
            "confidence",
            "root_cause",
            "proposed_fix",
            "files_to_modify",
            "risk_assessment",
        ],
    },
}

SUBMIT_IMPLEMENTATION = {
    "name": "submit_implementation",
    "description": "Signal that all code changes are complete.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Summary of changes made."},
            "files_changed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files that were modified or created.",
            },
        },
        "required": ["summary", "files_changed"],
    },
}

READONLY_TOOLS = [READ_FILE, SEARCH_CODE, LIST_FILES, RUN_COMMAND]
ANALYSIS_TOOLS = [*READONLY_TOOLS, SUBMIT_ANALYSIS]
IMPLEMENTATION_TOOLS = [*READONLY_TOOLS, EDIT_FILE, CREATE_FILE, SUBMIT_IMPLEMENTATION]

# ── Tool execution ────────────────────────────────────────────────────

_BLOCKED_COMMANDS = re.compile(
    r"|".join(
        [
            r"\brm\s+(-\w+\s+)*(/|\.\.|~)",
            r"\bgit\s+(push|reset\s+--hard|checkout\s+\.)",
            r"\bsudo\b",
            r"\bmkfs\b",
            r"\bdd\s+",
            r"\b(curl|wget)\b.*\|\s*(ba)?sh",
            r"\bchmod\b.*777",
        ]
    )
)


def _resolve(path: str) -> Path:
    """Resolve *path* relative to the repo root; reject escapes."""
    resolved = (REPO_ROOT / path).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise ValueError(f"Path escapes repository root: {path}")
    return resolved


def _run(cmd: str | list[str], *, timeout: int = 30, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        **kw,
    )


def exec_tool(name: str, params: dict) -> str:
    """Execute a tool call and return a text result."""
    try:
        return _exec_tool_inner(name, params)
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 60 s."
    except Exception as exc:
        return f"Error: {exc}"


def _exec_tool_inner(name: str, params: dict) -> str:
    if name == "read_file":
        fp = _resolve(params["path"])
        if not fp.is_file():
            return f"Error: file not found: {params['path']}"
        try:
            lines = fp.read_text(errors="replace").splitlines()
        except Exception as exc:
            return f"Error reading file: {exc}"
        start = max((params.get("start_line") or 1) - 1, 0)
        end = params.get("end_line") or len(lines)
        numbered = [f"{i + start + 1:>5}\t{line}" for i, line in enumerate(lines[start:end])]
        if not numbered:
            return "(empty range)"
        return "\n".join(numbered)

    if name == "search_code":
        cmd = ["grep", "-rnI", "-E", params["pattern"]]
        if inc := params.get("include"):
            cmd += ["--include", inc]
        cmd.append(str(_resolve(params.get("path", "."))))
        result = _run(cmd, timeout=30)
        if result.returncode == 1:
            return "No matches found."
        return (result.stdout[:8000] or "No matches found.").rstrip()

    if name == "list_files":
        target = _resolve(params.get("path", "."))
        depth = str(min(params.get("max_depth", 3), 5))
        cmd = ["find", str(target), "-maxdepth", depth, "-not", "-path", "*/.git/*"]
        if pat := params.get("pattern"):
            cmd += ["-name", pat]
        result = _run(cmd, timeout=15)
        return (result.stdout[:8000] or "(empty)").rstrip()

    if name == "run_command":
        command = params["command"]
        if _BLOCKED_COMMANDS.search(command):
            return "Error: command blocked by safety policy."
        result = _run(command, shell=True, timeout=60)
        out = result.stdout[:6000]
        if result.stderr:
            out += f"\n--- stderr ---\n{result.stderr[:2000]}"
        return out.rstrip() or "(no output)"

    if name == "edit_file":
        fp = _resolve(params["path"])
        if not fp.is_file():
            return f"Error: file not found: {params['path']}"
        content = fp.read_text()
        old = params["old_content"]
        if old not in content:
            return (
                f"Error: old_content not found in {params['path']}. "
                "Check whitespace and include enough surrounding context."
            )
        if content.count(old) > 1:
            return (
                f"Error: old_content matches {content.count(old)} locations in {params['path']}. "
                "Include more surrounding context to make the match unique."
            )
        fp.write_text(content.replace(old, params["new_content"], 1))
        return f"OK: updated {params['path']}"

    if name == "create_file":
        fp = _resolve(params["path"])
        if fp.exists():
            return f"Error: file already exists: {params['path']}"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(params["content"])
        return f"OK: created {params['path']}"

    if name in ("submit_analysis", "submit_implementation"):
        return json.dumps(params)

    return f"Error: unknown tool '{name}'"


# ── Agentic loop ──────────────────────────────────────────────────────

def run_agent(
    system: str,
    user_prompt: str,
    tools: list[dict],
    stop_tool: str,
) -> dict | None:
    """Drive the agent until it calls *stop_tool* or exhausts turns."""
    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    for turn in range(1, MAX_AGENT_TURNS + 1):
        log.info(f"  Turn {turn}/{MAX_AGENT_TURNS}")

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=messages,
        )

        for block in response.content:
            if hasattr(block, "text") and block.text and block.text.strip():
                log.info(f"  Agent: {block.text[:300]}")

        tool_blocks = [b for b in response.content if b.type == "tool_use"]

        if response.stop_reason == "end_turn" and not tool_blocks:
            log.warning("  Agent stopped without calling the stop tool.")
            return None

        stop_result: dict | None = None
        tool_results: list[dict] = []

        for block in tool_blocks:
            log.info(f"  → {block.name}({json.dumps(block.input, ensure_ascii=False)[:200]})")
            result_text = exec_tool(block.name, block.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
            )
            if block.name == stop_tool:
                stop_result = block.input

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if stop_result is not None:
            return stop_result

    log.warning("  Agent exhausted all turns.")
    return None


# ── System prompts ────────────────────────────────────────────────────

ANALYSIS_SYSTEM = """\
You are a senior software engineer analysing a bug report against the \
**mysql-operators** codebase (Charmed MySQL Operators for Juju).

Repository layout
─────────────────
• machines/          — VM / bare-metal charm
• kubernetes/        — Kubernetes charm
• Both contain lib/charms/mysql/v0/  — shared library (kept in sync)

Your task
─────────
1. Read the bug report carefully.
2. Explore the codebase to locate the relevant code paths.
3. Identify the root cause.
4. Decide whether you can produce a safe, correct, and complete fix.
5. Call **submit_analysis** with your findings and a confidence score.

Scoring guidelines
──────────────────
• 0.85–1.0  — You are highly confident the fix is correct and safe.
• 0.60–0.84 — Likely correct but some ambiguity or risk remains.
• < 0.60    — Too uncertain or risky to attempt an automated fix.

Lower your score when:
 – The fix touches critical recovery or data-replication paths.
 – The bug description is vague or under-specified.
 – Data loss is a conceivable side-effect.
 – The fix requires changes across many interacting components.
 – Thorough integration testing is the only way to validate correctness.

Consider both machines/ and kubernetes/ variants — many bugs apply to both.
"""

IMPLEMENTATION_SYSTEM = """\
You are implementing a bug fix for the **mysql-operators** codebase.

The bug has already been analysed and a fix strategy determined.  \
Your job is to apply the changes.

Rules
─────
• Make minimal, targeted edits.  Do not refactor surrounding code.
• If the fix is in lib/charms/mysql/v0/*, update the copy in **both** \
  machines/ and kubernetes/.
• Preserve the existing coding style and conventions.
• Do not add unnecessary comments.
• When finished, call **submit_implementation** with a summary.
"""

# ── Base-branch inference ─────────────────────────────────────────────

# Patterns used to extract revision numbers and MySQL version references
# from issue titles and bodies.
_RE_REVISION = re.compile(
    r"(?:rev(?:ision)?|charm\s+revision)\s*#?\s*(\d{2,})", re.IGNORECASE
)
_RE_MYSQL_VERSION = re.compile(
    r"(?:mysql|innodb)[- _]*(\d+\.\d+)", re.IGNORECASE
)
_RE_BRANCH_LITERAL = re.compile(
    r"\b(\d+\.\d+/edge)\b"
)


def _branch_for_revision(rev: int) -> str | None:
    """Look up the git tag for *rev* and return the edge branch that contains it."""
    for prefix in _REVISION_TAG_PREFIXES:
        tag = f"{prefix}{rev}"
        result = _run(["git", "tag", "-l", tag])
        if not result.stdout.strip():
            continue
        branch_result = _run(
            ["git", "branch", "-r", "--contains", tag],
        )
        for line in branch_result.stdout.splitlines():
            branch = line.strip()
            # Match only the canonical edge branches (e.g. origin/8.0/edge).
            if re.fullmatch(r"origin/\d+\.\d+/edge", branch):
                return branch.removeprefix("origin/")
    return None


def _branch_for_version(version: str) -> str | None:
    """Map a MySQL version string like '8.4' to its edge branch if it exists."""
    candidate = f"{version}/edge"
    result = _run(["git", "branch", "-r", "--list", f"origin/{candidate}"])
    if result.stdout.strip():
        return candidate
    return None


def infer_base_branch(issue: dict) -> str:
    """Determine the target edge branch from the issue's content.

    If the ``BASE_BRANCH`` env var is set, it takes precedence (manual override).

    Otherwise, resolution order:
    1. Explicit branch reference (e.g. ``8.4/edge``) in title or body.
    2. Revision number (e.g. "revision 408") → git tag → branch lookup.
    3. MySQL version mention (e.g. "mysql 8.4") → branch mapping.
    4. Issue labels containing a version (e.g. label "8.4").
    5. Fall back to DEFAULT_BASE_BRANCH.
    """
    if _BASE_BRANCH_OVERRIDE:
        log.info(f"  Base branch (env override): {_BASE_BRANCH_OVERRIDE}")
        return _BASE_BRANCH_OVERRIDE

    text = f"{issue.get('title', '')} {issue.get('body', '')}"

    # 1. Literal branch name
    if m := _RE_BRANCH_LITERAL.search(text):
        candidate = m.group(1)
        result = _run(["git", "branch", "-r", "--list", f"origin/{candidate}"])
        if result.stdout.strip():
            log.info(f"  Base branch (literal): {candidate}")
            return candidate

    # 2. Revision number → tag → branch
    for m in _RE_REVISION.finditer(text):
        rev = int(m.group(1))
        if branch := _branch_for_revision(rev):
            log.info(f"  Base branch (rev {rev}): {branch}")
            return branch

    # 3. MySQL version mention
    for m in _RE_MYSQL_VERSION.finditer(text):
        version = m.group(1)
        if branch := _branch_for_version(version):
            log.info(f"  Base branch (version {version}): {branch}")
            return branch

    # 4. Check issue labels for version hints (e.g. "8.4", "mysql-8.0")
    for label in issue.get("labels", []):
        name = label if isinstance(label, str) else label.get("name", "")
        version_match = re.search(r"(\d+\.\d+)", name)
        if version_match:
            if branch := _branch_for_version(version_match.group(1)):
                log.info(f"  Base branch (label '{name}'): {branch}")
                return branch

    log.info(f"  Base branch (default): {DEFAULT_BASE_BRANCH}")
    return DEFAULT_BASE_BRANCH


# ── GitHub helpers ────────────────────────────────────────────────────


def gh(*args: str, **kw) -> subprocess.CompletedProcess:
    return _run(["gh", *args], timeout=30, **kw)


def fetch_bug_issues() -> list[dict]:
    """Return open issues labelled 'bug'."""
    if SINGLE_ISSUE:
        result = gh("issue", "view", SINGLE_ISSUE, "--json", "number,title,body,labels,url")
        if result.returncode != 0:
            log.error(f"Failed to fetch issue #{SINGLE_ISSUE}: {result.stderr}")
            return []
        return [json.loads(result.stdout)]

    result = gh(
        "issue", "list",
        "--label", "bug",
        "--state", "open",
        "--limit", str(MAX_ISSUES),
        "--json", "number,title,body,labels,url",
    )
    if result.returncode != 0:
        log.error(f"Failed to list issues: {result.stderr}")
        return []
    return json.loads(result.stdout)


def pr_exists_for_issue(issue_number: int) -> bool:
    branch = f"{BRANCH_PREFIX}/issue-{issue_number}"
    result = gh("pr", "list", "--head", branch, "--state", "open", "--json", "number")
    if result.returncode != 0:
        return False
    return len(json.loads(result.stdout)) > 0


def create_branch(issue_number: int, base_branch: str) -> str:
    branch = f"{BRANCH_PREFIX}/issue-{issue_number}"
    _run(["git", "checkout", base_branch])
    _run(["git", "pull", "--ff-only"])
    _run(["git", "checkout", "-B", branch])
    return branch


def commit_and_push(branch: str, issue: dict, summary: str) -> bool:
    _run(["git", "add", "-A"])
    diff = _run(["git", "diff", "--cached", "--stat"])
    if not diff.stdout.strip():
        log.warning("  No changes to commit.")
        return False

    number = issue["number"]
    title = issue["title"]
    commit_msg = (
        f"fix: {title} (#{number})\n\n"
        f"{summary}\n\n"
        f"Closes #{number}\n\n"
        f"Co-Authored-By: Claude <noreply@anthropic.com>"
    )
    _run(["git", "commit", "-m", commit_msg])
    result = _run(["git", "push", "-u", "origin", branch, "--force-with-lease"], timeout=60)
    if result.returncode != 0:
        log.error(f"  git push failed: {result.stderr}")
        return False
    return True


def open_pr(
    branch: str, base_branch: str, issue: dict, analysis: dict, implementation: dict,
) -> str | None:
    number = issue["number"]
    title = f"[Auto-fix] {issue['title']} (#{number})"
    if len(title) > 70:
        title = title[:67] + "..."

    files_md = "\n".join(f"- `{f}`" for f in implementation.get("files_changed", []))

    body = f"""\
## Summary

Automated fix for #{number} (target: `{base_branch}`).

## Root cause

{analysis["root_cause"]}

## Fix

{analysis["proposed_fix"]}

## Changes

{implementation["summary"]}

### Files modified
{files_md}

## Risk assessment

{analysis["risk_assessment"]}

## Confidence

**{analysis["confidence"]:.0%}**

## Test plan

{analysis.get("test_strategy", "Manual verification required.")}

---

> **Note** — this PR was generated automatically by the bug-fix agent.
> Base branch `{base_branch}` was inferred from the issue content.
> Please review carefully before merging.
>
> 🤖 Generated with Claude (`{MODEL}`)
"""

    result = gh(
        "pr", "create",
        "--title", title,
        "--body", body,
        "--head", branch,
        "--base", base_branch,
    )
    if result.returncode != 0:
        log.error(f"  gh pr create failed: {result.stderr}")
        return None

    pr_url = result.stdout.strip()
    log.info(f"  ✓ PR created: {pr_url}")
    return pr_url


# ── Per-issue pipeline ────────────────────────────────────────────────


def process_issue(issue: dict) -> dict:
    """Run analysis → implementation → PR for one issue."""
    number = issue["number"]
    title = issue["title"]
    body = issue.get("body") or "(no description)"
    log.info(f"{'─' * 60}")
    log.info(f"Issue #{number}: {title}")

    if pr_exists_for_issue(number):
        log.info("  Skipped — open PR already exists.")
        return {"issue": number, "status": "skipped", "reason": "PR exists"}

    base_branch = infer_base_branch(issue)

    # ── Phase 1: Analysis (read-only) ─────────────────────────────

    log.info("  Phase 1 — Analysis")
    user_prompt = (
        f"Analyse the following bug report and determine whether you can "
        f"propose a safe, correct fix.\n\n"
        f"## Issue #{number}: {title}\n\n{body}\n\n"
        f"Target branch: `{base_branch}`\n\n"
        f"Explore the codebase, identify the root cause, and call "
        f"**submit_analysis** when ready."
    )

    analysis = run_agent(
        system=ANALYSIS_SYSTEM,
        user_prompt=user_prompt,
        tools=ANALYSIS_TOOLS,
        stop_tool="submit_analysis",
    )

    if not analysis:
        log.warning("  Analysis phase produced no result.")
        return {"issue": number, "status": "analysis_failed"}

    confidence = analysis.get("confidence", 0.0)
    log.info(f"  Confidence: {confidence:.0%}  (threshold: {CONFIDENCE_THRESHOLD:.0%})")
    log.info(f"  Root cause: {analysis.get('root_cause', 'N/A')[:200]}")

    if confidence < CONFIDENCE_THRESHOLD:
        log.info("  Below threshold — skipping implementation.")
        return {
            "issue": number,
            "status": "low_confidence",
            "confidence": confidence,
            "analysis": analysis,
        }

    if DRY_RUN:
        log.info("  Dry-run mode — skipping implementation.")
        return {
            "issue": number,
            "status": "dry_run",
            "confidence": confidence,
            "analysis": analysis,
        }

    # ── Phase 2: Implementation (writes allowed) ─────────────────

    log.info("  Phase 2 — Implementation")
    branch = create_branch(number, base_branch)

    impl_prompt = (
        f"Implement the following fix for issue #{number}: {title}\n\n"
        f"## Prior analysis\n\n"
        f"**Root cause:** {analysis['root_cause']}\n\n"
        f"**Proposed fix:** {analysis['proposed_fix']}\n\n"
        f"**Files to modify:** {', '.join(analysis.get('files_to_modify', []))}\n\n"
        f"Apply the changes now, then call **submit_implementation**."
    )

    implementation = run_agent(
        system=IMPLEMENTATION_SYSTEM,
        user_prompt=impl_prompt,
        tools=IMPLEMENTATION_TOOLS,
        stop_tool="submit_implementation",
    )

    if not implementation:
        log.warning("  Implementation phase produced no result.")
        _run(["git", "checkout", base_branch])
        return {"issue": number, "status": "impl_failed", "analysis": analysis}

    # ── Phase 3: Commit & PR ─────────────────────────────────────

    log.info("  Phase 3 — Commit & PR")

    if not commit_and_push(branch, issue, implementation.get("summary", "")):
        _run(["git", "checkout", base_branch])
        return {"issue": number, "status": "no_changes", "analysis": analysis}

    pr_url = open_pr(branch, base_branch, issue, analysis, implementation)
    _run(["git", "checkout", base_branch])

    return {
        "issue": number,
        "status": "pr_created",
        "confidence": confidence,
        "pr_url": pr_url,
        "base_branch": base_branch,
        "analysis": analysis,
    }


# ── Entry point ───────────────────────────────────────────────────────


def write_github_summary(results: list[dict]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a") as fh:
        fh.write("## Bug Fix Agent results\n\n")
        fh.write("| Issue | Base branch | Status | Confidence | PR |\n")
        fh.write("|-------|-------------|--------|------------|----|\n")
        for r in results:
            base = f"`{r['base_branch']}`" if r.get("base_branch") else "—"
            conf = f"{r['confidence']:.0%}" if "confidence" in r else "—"
            pr = f"[Link]({r['pr_url']})" if r.get("pr_url") else "—"
            fh.write(f"| #{r['issue']} | {base} | `{r['status']}` | {conf} | {pr} |\n")
        fh.write("\n")


def main() -> None:
    log.info("=" * 60)
    log.info("Bug Fix Agent")
    log.info(f"  Model              : {MODEL}")
    log.info(f"  Confidence threshold: {CONFIDENCE_THRESHOLD:.0%}")
    log.info(f"  Max issues         : {MAX_ISSUES}")
    log.info(f"  Dry run            : {DRY_RUN}")
    log.info(f"  Single issue       : {SINGLE_ISSUE or '(all)'}")
    log.info("=" * 60)

    issues = fetch_bug_issues()
    if not issues:
        log.info("No open bug issues found.")
        return

    log.info(f"Found {len(issues)} issue(s) to process.")

    results: list[dict] = []
    for issue in issues:
        try:
            result = process_issue(issue)
        except Exception:
            log.exception(f"Unhandled error on issue #{issue['number']}")
            result = {"issue": issue["number"], "status": "error"}
        results.append(result)

    log.info("")
    log.info("=" * 60)
    log.info("Results")
    log.info("=" * 60)
    for r in results:
        extra = ""
        if "confidence" in r:
            extra += f"  confidence={r['confidence']:.0%}"
        if "pr_url" in r and r["pr_url"]:
            extra += f"  → {r['pr_url']}"
        if r.get("reason"):
            extra += f"  ({r['reason']})"
        log.info(f"  #{r['issue']:>5}  {r['status']}{extra}")

    write_github_summary(results)

    if results and all(r["status"] == "error" for r in results):
        log.error("All issues failed — marking workflow as failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
