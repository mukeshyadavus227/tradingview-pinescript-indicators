#!/usr/bin/env python3
"""
Static checks for Pine Script v6 sources that the real compiler is not here to run.

This is NOT a Pine compiler. It catches the bug classes that have actually bitten
this repository (see adaptive_scanner/asr_engine.pine:900, a missing `+` between
two string literals across a continuation line, which no static check caught):

  1. Delimiter balance per logical line: ( ) [ ] { } and string quotes, where a
     logical line is a line plus its continuation lines (Pine continues a line
     when the next line is indented by an amount that is not a multiple of 4).
  2. Adjacent string literals with no operator between them on a logical line
     ('"a"' + newline + '"b"') — the concatenation bug.
  3. A continuation line that starts with a string literal or identifier while
     the previous physical line does not end with an operator, comma, or an open
     delimiter (same bug, different shape).
  4. `alert(` / `alertcondition(` called inside a user-defined function body
     (Pine forbids alert() in local function scopes).
  5. `request.security(` more than 40 times (the per-script budget).
  6. Trailing whitespace and tabs (Pine accepts them, the diff reviewer does not).

Usage:
    python pine_lint.py path/to/script.pine [more.pine ...]
Exit status 1 if any error-level finding is reported.
"""
import re
import sys
from pathlib import Path

OPEN = {"(": ")", "[": "]", "{": "}"}
CLOSE = {v: k for k, v in OPEN.items()}
OPERATOR_END = re.compile(r"(\+|-|\*|/|%|=|<|>|!|\?|:|,|\(|\[|\{|and|or|not|=>)\s*$")


def strip_comment(line: str) -> str:
    """Remove a // comment unless the // is inside a string literal."""
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and i + 1 < len(line):
                out.append(line[i : i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
            out.append(ch)
        else:
            if ch in ("'", '"'):
                quote = ch
                out.append(ch)
            elif line.startswith("//", i):
                break
            else:
                out.append(ch)
        i += 1
    return "".join(out)


def is_continuation(line: str) -> bool:
    """Pine: a line is a continuation if its indentation is not a multiple of 4
    (the house style uses 5 spaces). Blank lines and comments are ignored."""
    stripped = line.lstrip(" ")
    if not stripped or stripped.startswith("//"):
        return False
    indent = len(line) - len(stripped)
    return indent > 0 and indent % 4 != 0


def depth_delta(line: str) -> int:
    """Net change in ( [ { depth for one line, ignoring strings and comments."""
    d = 0
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        else:
            if line.startswith("//", i):
                break
            if ch in ("'", '"'):
                quote = ch
            elif ch in OPEN:
                d += 1
            elif ch in CLOSE:
                d -= 1
        i += 1
    return d


def logical_lines(lines):
    """Yield (start_lineno, [physical lines]) groups.

    A line continues the previous one when a delimiter is still open (Pine
    allows comment-only lines inside a multi-line call) or when its indentation
    is not a multiple of 4, which is how Pine itself marks a continuation.
    """
    group = []
    start = 0
    depth = 0
    for n, line in enumerate(lines, 1):
        if group and (depth > 0 or is_continuation(line)):
            group.append(line)
            depth += depth_delta(line)
            continue
        if group:
            yield start, group
        group = [line]
        start = n
        depth = depth_delta(line)
    if group:
        yield start, group


def check_balance(start, group, findings):
    stack = []
    quote = None
    for off, raw in enumerate(group):
        line = raw
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            else:
                if line.startswith("//", i):
                    break
                if ch in ("'", '"'):
                    quote = ch
                elif ch in OPEN:
                    stack.append((ch, start + off))
                elif ch in CLOSE:
                    if not stack or stack[-1][0] != CLOSE[ch]:
                        findings.append(("error", start + off, f"unbalanced '{ch}'"))
                        return
                    stack.pop()
            i += 1
        if quote:
            findings.append(("error", start + off, "unterminated string literal"))
            return
    for ch, ln in stack:
        findings.append(("error", ln, f"'{ch}' never closed in logical line starting at {start}"))


def tokenize(code: str):
    """Split a comment-free line into ('str', text) and ('code', text) tokens,
    tracking which quote character opened each literal so that a double quote
    inside a single-quoted JSON fragment is not mistaken for a delimiter."""
    tokens = []
    buf = []
    quote = None
    i = 0
    while i < len(code):
        ch = code[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(code):
                buf.append(code[i + 1])
                i += 2
                continue
            if ch == quote:
                tokens.append(("str", "".join(buf)))
                buf = []
                quote = None
        else:
            if ch in ("'", '"'):
                if buf:
                    tokens.append(("code", "".join(buf)))
                    buf = []
                quote = ch
                buf.append(ch)
            else:
                buf.append(ch)
        i += 1
    if buf:
        tokens.append(("str" if quote else "code", "".join(buf)))
    return tokens


def check_adjacent_strings(start, group, findings):
    code = [strip_comment(l) for l in group]
    joined = " ".join(c.strip() for c in code)
    tokens = tokenize(joined)
    # Two string literals separated only by whitespace.
    for k in range(len(tokens) - 1):
        a, b = tokens[k], tokens[k + 1]
        if a[0] == "str" and b[0] == "str":
            findings.append(("error", start, f"adjacent string literals with no operator: {a[1][-20:]} {b[1][:20]}"))
        elif a[0] == "str" and b[0] == "code" and b[1].strip() == "" and k + 2 < len(tokens) and tokens[k + 2][0] == "str":
            findings.append(("error", start, f"adjacent string literals with no operator: {a[1][-20:]} {tokens[k + 2][1][:20]}"))
    # Continuation line starting with a literal/identifier after a line that
    # does not end with an operator or open delimiter.
    for off in range(1, len(code)):
        prev = code[off - 1].rstrip()
        cur = code[off].strip()
        if not prev or not cur:
            continue
        starts_value = cur[0] in "'\"" or re.match(r"[A-Za-z_]", cur) is not None or cur[0].isdigit()
        starts_operator = re.match(r"(\+|-|\*|/|and\b|or\b|\?|:|\)|\]|\}|,|=>)", cur) is not None
        if starts_value and not starts_operator and not OPERATOR_END.search(prev):
            # Allow a continuation that simply closes something on the previous line.
            findings.append(("error", start + off, f"continuation line starts a value but previous line ends without an operator: `{prev[-30:]}` -> `{cur[:30]}`"))


def check_alert_scope(lines, findings):
    in_func = False
    func_indent = 0
    for n, raw in enumerate(lines, 1):
        code = strip_comment(raw)
        if not code.strip():
            continue
        indent = len(code) - len(code.lstrip(" "))
        if in_func and indent <= func_indent and not is_continuation(raw):
            in_func = False
        if re.search(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*=>\s*$", code) or re.search(r"^\s*(export\s+)?method\s+", code):
            in_func = True
            func_indent = indent
            continue
        if in_func and re.search(r"\balert(condition)?\s*\(", code):
            findings.append(("error", n, "alert()/alertcondition() inside a user-defined function scope"))


def check_misc(lines, findings):
    n_sec = 0
    for n, raw in enumerate(lines, 1):
        if "\t" in raw:
            findings.append(("warn", n, "tab character"))
        if raw.rstrip("\n") != raw.rstrip("\n").rstrip():
            findings.append(("warn", n, "trailing whitespace"))
        n_sec += len(re.findall(r"\brequest\.(security|security_lower_tf)\s*\(", strip_comment(raw)))
    if n_sec > 40:
        findings.append(("error", 0, f"{n_sec} request.* calls exceed the 40-call budget"))
    if not any(l.startswith("//@version=6") for l in lines[:10]):
        findings.append(("error", 1, "missing //@version=6 in the first 10 lines"))


def lint(path: Path):
    text = path.read_text()
    lines = text.split("\n")
    findings = []
    for start, group in logical_lines(lines):
        check_balance(start, group, findings)
        check_adjacent_strings(start, group, findings)
    check_alert_scope(lines, findings)
    check_misc(lines, findings)
    return findings


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    status = 0
    for arg in argv[1:]:
        p = Path(arg)
        findings = lint(p)
        errors = [f for f in findings if f[0] == "error"]
        for level, ln, msg in sorted(findings, key=lambda f: f[1]):
            print(f"{p.name}:{ln}: {level}: {msg}")
        print(f"{p.name}: {len(errors)} error(s), {len(findings) - len(errors)} warning(s)")
        if errors:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
