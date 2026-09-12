#!/usr/bin/env python3
"""Regenerate the CRV2-12 static language-inventory evidence.

This is deliberately a static *candidate* inventory.  It identifies wording
which can leave an API/view/serializer or is a likely visible frontend literal;
it does not claim that every candidate is reachable on every route.  That
boundary makes the Stage 1 evidence repeatable without silently excluding new
player-facing wording.

Usage (from the repository root):
    python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py
    python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py --check
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
JSON_OUTPUT = EVIDENCE / "STATIC_STRING_INVENTORY.json"
MARKDOWN_OUTPUT = EVIDENCE / "STATIC_STRING_INVENTORY.md"

BACKEND_ROOTS = (
    "backend/core/serializers",
    "backend/core/views",
    "backend/core/engine",
    "backend/core/services",
)
BACKEND_FILES = ("backend/core/utils/participant_messages.py",)
FRONTEND_ROOT = "frontend/globalstrat-frontend/src"

# Literal text inside these response-construction calls is reviewable wording.
MESSAGE_CALLS = {
    "ValidationError", "Response", "_create_alert", "InstructorAlert",
    "append", "extend", "participant_message",
}
MESSAGE_KEYS = {
    "detail", "error", "errors", "message", "messages", "title",
    "teaching_note", "description", "narrative", "warning", "warnings",
    "help_text", "label", "placeholder",
}
INSTRUCTOR_PATH_MARKERS = (
    "/instructor", "/course.py", "/grading", "/overrides", "/round_control",
    "/scenario_views", "/team_config", "/team_control",
)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def function_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def is_text(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) or isinstance(node, ast.JoinedStr)


def source_text(source: str, node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return node.value
    # ast.get_source_segment re-splits the entire source for every f-string;
    # ast.unparse is linear in this small expression and keeps the sweep fast.
    return ast.unparse(node)


def human_text(text: str) -> bool:
    """Exclude ids/imports/format tokens while retaining short UI status labels."""
    stripped = text.strip()
    if len(stripped) < 3 or not re.search(r"[A-Za-z\u4e00-\u9fff]", stripped):
        return False
    if stripped in {"en", "zh", "zh-CN", "GET", "POST", "PUT", "PATCH", "DELETE"}:
        return False
    if re.fullmatch(r"[a-z][a-z0-9_./:-]*", stripped):
        return False
    return True


def backend_audience(path: str) -> str:
    if path.endswith("/utils/participant_messages.py"):
        return "participant-facing"
    if any(marker in path for marker in INSTRUCTOR_PATH_MARKERS):
        return "instructor-facing"
    if path.endswith("/engine/instructor_alerts.py"):
        return "instructor-facing"
    if "/serializers/" in path or "/views/" in path:
        return "participant-facing"
    if path.endswith("/services/persona_engine.py") or "/engine/" in path:
        return "participant-facing"
    # Service-layer candidates require route tracing before wording changes.
    return "operator-or-log-only"


def backend_workstream(path: str) -> str:
    if path.endswith("/views/decisions.py") or "/serializers/decision" in path:
        return "decision validation and submission"
    if path.endswith("/views/auth.py"):
        return "account and access"
    if path.endswith("/engine/instructor_alerts.py"):
        return "instructor coaching alerts"
    if any(name in path for name in ("persona_engine", "/narratives.py", "/briefing.py", "/events.py")):
        return "templated/player generated content"
    if "/services/" in path:
        return "service-to-route boundary review"
    return "API response review"


def backend_candidates(path: Path) -> list[dict]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        raise RuntimeError(f"Cannot inventory invalid Python: {path}: {error}") from error
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    # Memoising the enclosing response context keeps a full-repository sweep
    # linear in the syntax-tree size (large decision views contain many
    # literals beneath shared response nodes).
    context_cache: dict[ast.AST, str | None] = {}

    def enclosing_context(node: ast.AST) -> str | None:
        if node in context_cache:
            return context_cache[node]
        parent = parents.get(node)
        if parent is None:
            context_cache[node] = None
            return None
        context = None
        if isinstance(parent, ast.Call) and function_name(parent.func) in MESSAGE_CALLS:
            context = f"call:{function_name(parent.func)}"
        elif isinstance(parent, ast.Dict):
            for key in parent.keys:
                if isinstance(key, ast.Constant) and key.value in MESSAGE_KEYS:
                    context = f"payload:{key.value}"
                    break
        if context is None:
            context = enclosing_context(parent)
        context_cache[node] = context
        return context

    path_text = rel(path)
    audience = backend_audience(path_text)
    rows = []
    seen = set()
    for node in ast.walk(tree):
        if not is_text(node):
            continue
        # Record an interpolated sentence once.  ast.walk also visits every
        # literal fragment and format specification inside a JoinedStr, which
        # would turn one alert into several unusable inventory rows.
        ancestor = parents.get(node)
        nested_in_fstring = False
        while ancestor is not None:
            if isinstance(ancestor, ast.JoinedStr):
                nested_in_fstring = True
                break
            ancestor = parents.get(ancestor)
        if nested_in_fstring:
            continue
        # A catalogue module contains explanatory docstrings beside the actual
        # EN/ZH entries; documentation is not a runtime participant message.
        if isinstance(parents.get(node), ast.Expr):
            continue
        text = source_text(source, node)
        if not human_text(text):
            continue
        matched_context = enclosing_context(node)
        if matched_context is None and path_text.endswith("/utils/participant_messages.py"):
            matched_context = "shared participant-message catalogue"
        if not matched_context:
            continue
        key = (node.lineno, text)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "surface": "backend-response-or-generated-content",
            "audience": audience,
            "path": path_text,
            "line": node.lineno,
            "text": text,
            "context": matched_context,
            "workstream": backend_workstream(path_text),
            "translation_action": (
                "review EN/ZH wording and route through shared catalogue"
                if audience != "operator-or-log-only"
                else "confirm operator/log boundary; exempt only with rationale"
            ),
        })
    return rows


# A deliberately simple same-line literal matcher.  The inventory is a
# conservative candidate report, so a false positive is preferable to an
# exponential-time regex on a JSX-heavy source file.
QUOTED = re.compile(r"(?P<quote>['\"])(?P<text>(?:\\.|[^'\"\\\n])*)['\"]")
JSX_TEXT = re.compile(r">\s*([^<{>][^<{>]*?)\s*<")
VISIBLE_PROP = re.compile(
    r"\b(?:aria-label|alt|description|error|helperText|label|message|placeholder|subtitle|title|tooltip)\s*=\s*$"
)


def frontend_audience(path: str) -> str:
    return "instructor-facing" if "/instructor/" in path or "Instructor" in Path(path).name else "participant-facing"


def frontend_workstream(path: str) -> str:
    name = Path(path).name
    if "/instructor/" in path or "Instructor" in name:
        return "instructor UI"
    if name in {"GameDashboard.js", "CorporateStrategyPage.js", "FinancialReportsPage.js", "MarketingPage.js", "ProductsPage.js", "RDPage.js", "StrategyPage.js"}:
        return "participant decision UI"
    return "participant supporting UI"


def frontend_candidates(path: Path) -> list[dict]:
    """Find likely human literals outside t(); JSX is intentionally lexical.

    React files use JSX and template literals, so this light scanner avoids a
    non-reproducible node_modules dependency.  It reports candidates for human
    review rather than pretending to prove reachability.
    """
    rows = []
    path_text = rel(path)
    audience = frontend_audience(path_text)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Omit imports, translation calls, URL/path/config-like values and CSS classes.
        if line.lstrip().startswith(("import ", "//", "*")):
            continue
        for match in QUOTED.finditer(line):
            text = match.group("text").replace("\\'", "'").replace('\\"', '"')
            prefix = line[max(0, match.start() - 48):match.start()]
            if re.search(r"\bt\(\s*$", prefix) or "className" in prefix or "data-testid" in prefix:
                continue
            if not human_text(text):
                continue
            if not (VISIBLE_PROP.search(prefix) or re.search(r"[ .,!?:;]|[A-Z]", text)):
                continue
            rows.append({
                "surface": "frontend-non-t-literal",
                "audience": audience,
                "path": path_text,
                "line": number,
                "text": text,
                "context": "quoted literal outside t()",
                "workstream": frontend_workstream(path_text),
                "translation_action": "move to en.json and zh-CN.json, then call t()",
            })
        for match in JSX_TEXT.finditer(line):
            text = match.group(1).strip()
            if "{" in text or not human_text(text):
                continue
            rows.append({
                "surface": "frontend-non-t-literal",
                "audience": audience,
                "path": path_text,
                "line": number,
                "text": text,
                "context": "JSX text outside t()",
                "workstream": frontend_workstream(path_text),
                "translation_action": "move to en.json and zh-CN.json, then call t()",
            })
    return rows


def inventory() -> dict:
    rows = []
    for root in BACKEND_ROOTS:
        rows.extend(backend_candidates(path) for path in sorted((ROOT / root).rglob("*.py")))
    rows.extend(backend_candidates(ROOT / filename) for filename in BACKEND_FILES if (ROOT / filename).exists())
    # Flatten after the comprehensible per-root loop above.
    rows = [row for group in rows for row in group]
    for suffix in ("*.js", "*.jsx"):
        for path in sorted((ROOT / FRONTEND_ROOT).rglob(suffix)):
            rows.extend(frontend_candidates(path))
    rows.sort(key=lambda row: (row["audience"], row["surface"], row["path"], row["line"], row["text"]))
    source_files = []
    for root in (*BACKEND_ROOTS, FRONTEND_ROOT):
        source_files.extend(sorted((ROOT / root).rglob("*.py")))
        source_files.extend(sorted((ROOT / root).rglob("*.js")))
        source_files.extend(sorted((ROOT / root).rglob("*.jsx")))
    source_files.extend(ROOT / filename for filename in BACKEND_FILES if (ROOT / filename).exists())
    digest = hashlib.sha256()
    for path in sorted(set(source_files)):
        digest.update(rel(path).encode())
        digest.update(path.read_bytes())
    counts = Counter(row["audience"] for row in rows)
    workstream_counts = Counter(row["workstream"] for row in rows)
    return {
        "generator": rel(Path(__file__)),
        "source_sha256": digest.hexdigest(),
        "candidate_count": len(rows),
        "counts_by_audience": dict(sorted(counts.items())),
        "counts_by_workstream": dict(sorted(workstream_counts.items())),
        "rows": rows,
    }


def markdown(data: dict) -> str:
    lines = [
        "# CRV2-12 static string inventory (generated)",
        "",
        "This is a reproducible Stage 1 candidate inventory, not a claim that every",
        "candidate is reachable. Reviewers must classify each candidate before changing",
        "wording; `operator-or-log-only` rows require an explicit exemption rationale.",
        "",
        f"Source fingerprint: `{data['source_sha256']}`",
        f"Candidate strings: **{data['candidate_count']}**",
        "",
        "| Audience | Candidate count |",
        "| --- | ---: |",
    ]
    for audience, count in data["counts_by_audience"].items():
        lines.append(f"| {audience} | {count} |")
    lines.extend([
        "",
        "| Workstream | Candidate count |",
        "| --- | ---: |",
    ])
    for workstream, count in data["counts_by_workstream"].items():
        lines.append(f"| {workstream} | {count} |")
    lines.extend([
        "",
        "## Candidate rows",
        "",
        "| Audience | Workstream | Surface | Location | Candidate text | Required action |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for row in data["rows"]:
        text = row["text"].replace("|", "\\|").replace("\n", " ")
        if len(text) > 180:
            text = text[:177] + "..."
        location = f"`{row['path']}:{row['line']}`"
        lines.append(
            f"| {row['audience']} | {row['workstream']} | {row['surface']} | {location} | {text} | {row['translation_action']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated evidence is stale")
    args = parser.parse_args()
    data = inventory()
    json_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    markdown_text = markdown(data)
    if args.check:
        stale = (
            not JSON_OUTPUT.exists() or JSON_OUTPUT.read_text(encoding="utf-8") != json_text or
            not MARKDOWN_OUTPUT.exists() or MARKDOWN_OUTPUT.read_text(encoding="utf-8") != markdown_text
        )
        if stale:
            print("CRV2-12 inventory is stale; rerun generate_inventory.py", file=sys.stderr)
            return 1
        return 0
    JSON_OUTPUT.write_text(json_text, encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(markdown_text, encoding="utf-8")
    print(f"wrote {len(data['rows'])} candidate rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
