#!/usr/bin/env python3
"""Harness kit: score a project's agent harness, check it, and wire the checks into hooks.

  audit            score the project on 32 checks in 7 groups; writes nothing
  init             install the kit: .harness/, hooks, .claude/verify.sh, a Verification block
  check            run the checks; exit 1 on a failure that is not accepted in the baseline
  baseline         accept today's failures as known debt (needs --reason; ask the user first)
  hook post|stop   Claude Code hook entry points (JSON on stdin)
  selftest         prove the checks catch seeded faults

Standard library only. Python 3.8+. Each audit check names the source it comes from;
see reference/blueprint.md in the skill folder.
"""
import argparse, datetime, fnmatch, json, os, re, shutil, stat, subprocess, sys, tempfile, urllib.parse
from pathlib import Path

DEFAULT = {
    "version": 1,
    "instruction_files": ["CLAUDE.md", "AGENTS.md"],
    "instruction_max_lines": 150,
    "session_start_files": [],
    "session_start_max_lines": 300,
    "state_files": [],
    "decision_files": [],
    "docs": {"include": ["**/*.md"],
             "exclude": [".git/**", "node_modules/**", ".venv/**", "venv/**", "dist/**", "build/**", "target/**", "vendor/**"]},
    "links": {"exempt": []},
    "frontmatter": None,
    "naming": None,
    "index": None,
    "commands": [],
    "main_branches": ["main", "master"],
    "max_uncommitted": 10,
}
STATE_GUESS = ["PROGRESS.md", "progress.md", "claude-progress.txt", "sessions/sessions.md", "PLAN.md", "TODO.md", "docs/PLANS.md"]
DECISION_GUESS = ["decisions.md", "DECISIONS.md", "docs/decisions.md", "docs/adr", "docs/design-docs"]
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".c", ".cc", ".cpp", ".cs", ".swift", ".sh"}
PINS = [".python-version", ".nvmrc", ".node-version", ".tool-versions", "Dockerfile", ".devcontainer", "rust-toolchain",
        "rust-toolchain.toml", "go.mod", "mise.toml", ".mise.toml"]
MANIFESTS = ["package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod", "Gemfile"]
LOCKS = ["package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "uv.lock", "poetry.lock", "Pipfile.lock",
         "Cargo.lock", "go.sum", "Gemfile.lock"]
SETUP = ["Makefile", "justfile", "Justfile", "init.sh", "setup.sh", "bin/setup", "scripts/setup.sh", "Taskfile.yml"]
SECRET = "." + "env"   # the secret-file name, built here so shell guards do not mistake this script for a reader
SECRET_DENY = [f"Read(./{SECRET})", f"Read(./{SECRET}.local)", f"Read(./{SECRET}.production)", f"Read(./{SECRET}.development)",
               f"Read(./{SECRET}rc)", f"Edit(./{SECRET})", f"Edit(./{SECRET}rc)"]
HOOKS = {"PostToolUse": {"matcher": "Edit|Write", "hooks": [{"type": "command", "timeout": 30,
                         "command": 'python3 "${CLAUDE_PROJECT_DIR}/.harness/harness.py" hook post'}]},
         "Stop": {"hooks": [{"type": "command", "timeout": 120,
                  "command": 'python3 "${CLAUDE_PROJECT_DIR}/.harness/harness.py" hook stop'}]}}
VERIFY_BLOCK = """
## Verification

Run this before saying a task is done. A failure prints the file, the problem and the fix.

```bash
python3 .harness/harness.py check --full   # links, frontmatter, names, indexes, plus the project's own commands
python3 .harness/harness.py audit          # score of the whole harness, by subsystem
```

The same check runs from hooks after every edit and before the agent stops. Known debt is listed in
`.harness/baseline.json`; add to it only when the user agrees. Log repeated mistakes in `.harness/failures.md`.
"""
FAILURES_MD = """# Failure log

One row per mistake the agent made. When the same cause shows up twice, add a check or a rule, and note it in the last column.
Causes: task unclear · context missing · environment · verification missing · state lost.

| Date | What went wrong | Cause | How it was found | Control added |
| --- | --- | --- | --- | --- |
"""
REVIEWS_MD = """# Review log

One row each time someone other than the writer checked a piece of work: a person, or a second agent with a different brief.

| Date | What was reviewed | Reviewer | Findings | Follow-up |
| --- | --- | --- | --- | --- |
"""


# ---------- helpers ----------
def sh(cmd, cwd, timeout=600):
    # A list runs without a shell. A string is a verification command from .harness/harness.json,
    # which the project owner wrote (same trust as a Makefile), so it runs through the shell.
    try:
        r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"


def match(rel, patterns):
    for p in patterns or []:
        if fnmatch.fnmatch(rel, p) or (p.startswith("**/") and fnmatch.fnmatch(rel, p[3:])):
            return True
    return False


def load_config(root, path=None):
    cfg = json.loads(json.dumps(DEFAULT))
    p = Path(path) if path else root / ".harness" / "harness.json"
    if p.exists():
        cfg.update(json.loads(p.read_text()))
    else:
        cfg.update(detect(root))
    return cfg


def detect(root):
    out = {"instruction_files": [f for f in DEFAULT["instruction_files"] if (root / f).exists()] or DEFAULT["instruction_files"],
           "state_files": [f for f in STATE_GUESS if (root / f).exists()][:2],
           "decision_files": [f for f in DECISION_GUESS if (root / f).exists()][:1], "commands": []}
    out["session_start_files"] = [f for f in out["instruction_files"] if (root / f).exists()]
    mk = (root / "Makefile").read_text(errors="replace") if (root / "Makefile").exists() else ""
    for t in ("check", "test", "lint"):
        if re.search(rf"^{t}:", mk, re.M):
            out["commands"].append({"name": f"make {t}", "run": f"make {t}", "when": "manual"})
    if (root / "package.json").exists():
        try:
            scripts = json.loads((root / "package.json").read_text()).get("scripts", {})
        except ValueError:
            scripts = {}
        for t in ("test", "lint", "typecheck", "build"):
            if t in scripts and "no test specified" not in scripts[t]:
                out["commands"].append({"name": t, "run": f"npm run -s {t}", "when": "manual"})
    if (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tests").is_dir():
        out["commands"].append({"name": "pytest", "run": "python3 -m pytest -x -q", "when": "manual"})
    if (root / "Cargo.toml").exists():
        out["commands"].append({"name": "cargo test", "run": "cargo test -q", "when": "manual"})
    if (root / "go.mod").exists():
        out["commands"].append({"name": "go test", "run": "go test ./...", "when": "manual"})
    return out


def docs(root, cfg):
    skip = {p[:-3] for p in cfg["docs"]["exclude"] if p.endswith("/**")}
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in skip)
        for f in sorted(fn):
            rel = (Path(dp) / f).relative_to(root).as_posix()
            if match(rel, cfg["docs"]["include"]) and not match(rel, cfg["docs"]["exclude"]):
                yield rel


def frontmatter(text):
    if not text.startswith("---"):
        return None, []
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return None, []
    block = parts[0][3:]
    return set(re.findall(r"^([\w-]+):", block, re.M)), re.findall(r"^\s+-\s+(\S+)\s*$", block, re.M)


def strip_code(text):
    return re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", text, flags=re.S))


# ---------- checks ----------
def check_file(root, cfg, rel, names):
    out, text = [], (root / rel).read_text(errors="replace")
    if not match(rel, cfg["links"]["exempt"]):
        for m in re.finditer(r"\]\((<[^>]+>|[^)\s]+)", strip_code(text)):
            t = m.group(1).strip("<>")
            if re.match(r"[a-zA-Z][\w+.-]*:", t) or t.startswith("#"):
                continue
            target = urllib.parse.unquote(t.split("#")[0])
            dest = (root / target.lstrip("/")) if target.startswith("/") else (root / rel).parent / target
            if not dest.exists():
                near = [n for n in names if Path(n).name == Path(target).name]
                hint = f" A file with that name is at `{near[0]}`." if near else " No file with that name exists in the project."
                out.append(("links", rel, f"broken link to {t}", "Point the link at a file that exists, or remove it." + hint))
    fm = cfg.get("frontmatter")
    if fm and not match(rel, fm.get("exempt")):
        keys, tags = frontmatter(text)
        if keys is None:
            out.append(("frontmatter", rel, "no frontmatter block", "Add a `---` block at the top with: " + ", ".join(fm.get("required_keys", []))))
        else:
            for k in fm.get("required_keys", []):
                if k not in keys:
                    out.append(("frontmatter", rel, f"missing key `{k}`", f"Add `{k}:` to the frontmatter."))
            for t in fm.get("required_tags", []):
                if t not in tags:
                    out.append(("frontmatter", rel, f"missing tag `{t}`", f"Add `  - {t}` under `tags:`."))
            for prefix, allowed in (fm.get("allowed") or {}).items():
                for t in tags:
                    if t.startswith(prefix) and t[len(prefix):] not in allowed:
                        out.append(("frontmatter", rel, f"tag `{t}` is not in the allowed list",
                                    "Use one of: " + ", ".join(allowed) + ". To allow a new value, add it to the instruction file and to `.harness/harness.json`."))
    nm = cfg.get("naming")
    if nm and not match(rel, nm.get("exempt")) and not re.match(nm["pattern"], Path(rel).name):
        out.append(("naming", rel, "file name does not match the naming rule", f"Rename it to match `{nm['pattern']}`, and update links to it."))
    if rel in cfg["instruction_files"]:
        n = text.count("\n") + 1
        if n > cfg["instruction_max_lines"]:
            out.append(("instruction-size", rel, f"{n} lines, limit {cfg['instruction_max_lines']}", "Move detail into a linked file or a skill; keep this file a map."))
    return out


def check_index(root, cfg, names):
    ix, out = cfg.get("index"), []
    if not ix:
        return out
    by_dir = {}
    for n in names:
        by_dir.setdefault(str(Path(n).parent), []).append(n)
    for d, files in by_dir.items():
        idx = root / d / ix["file"]
        if d == "." or match(d, ix.get("exempt_dirs")) or not idx.exists():
            continue
        text = idx.read_text(errors="replace")
        for n in files:
            name = Path(n).name
            if name != ix["file"] and name not in text and urllib.parse.quote(name) not in text:
                out.append(("index", n, f"not listed in {d}/{ix['file']}", f"Add a row or link for `{name}` to `{d}/{ix['file']}`."))
    return out


def run_checks(root, cfg, only=None, level="stop"):
    names = list(docs(root, cfg))
    out = []
    for rel in ([only] if only else names):
        if (root / rel).is_file():
            out += check_file(root, cfg, rel, names)
    if not only:
        out += check_index(root, cfg, names)
        for c in cfg["commands"]:
            if level == "full" or c.get("when") == "stop":
                rc, text = sh(c["run"], root)
                if rc != 0:
                    out.append(("command", c["name"], f"`{c['run']}` exited {rc}", "Output: " + " / ".join(text.splitlines()[-12:])))
    return out, len(names)


def key(f):
    return "|".join(f[:3])


def baseline(root):
    p = root / ".harness" / "baseline.json"
    return json.loads(p.read_text()).get("accepted", []) if p.exists() else []


def split(root, findings):
    known = {b["key"] for b in baseline(root)}
    return [f for f in findings if key(f) not in known], [f for f in findings if key(f) in known]


def report(new, old, n, stream=sys.stdout):
    for c, f, d, fix in new:
        print(f"FAIL  {c} | {f} | {d}\n      fix: {fix}", file=stream)
    for c, f, d, _ in old:
        print(f"known {c} | {f} | {d}", file=stream)
    print(f"harness check: {len(new)} new, {len(old)} known, {n} files", file=stream)


# ---------- commands ----------
def cmd_check(a):
    root = Path(a.project).resolve(); cfg = load_config(root, a.config)
    findings, n = run_checks(root, cfg, a.file, "full" if a.full else "stop")
    new, old = split(root, findings)
    if a.json:
        print(json.dumps({"new": new, "known": old, "files": n}))
    else:
        report(new, old, n)
    return 1 if new else 0


def cmd_baseline(a):
    root = Path(a.project).resolve(); cfg = load_config(root, a.config)
    findings, _ = run_checks(root, cfg, None, "full")
    today = datetime.date.today().isoformat()
    prev = {b["key"]: b for b in baseline(root)}
    acc = [prev.get(key(f)) or {"key": key(f), "reason": a.reason, "date": today} for f in findings]
    (root / ".harness").mkdir(exist_ok=True)
    (root / ".harness" / "baseline.json").write_text(json.dumps({"accepted": acc}, indent=2, ensure_ascii=False) + "\n")
    print(f"baseline: {len(acc)} accepted ({sum(key(f) not in prev for f in findings)} new today)")
    return 0


def cmd_hook(a):
    try:
        data = json.loads(sys.stdin.read() or "{}")
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or a.project).resolve(); cfg = load_config(root)
        if a.event == "post":
            fp = (data.get("tool_input") or {}).get("file_path")
            if not fp:
                return 0
            try:
                rel = Path(fp).resolve().relative_to(root).as_posix()
            except ValueError:
                return 0
            if not (match(rel, cfg["docs"]["include"]) and not match(rel, cfg["docs"]["exclude"])) or not (root / rel).exists():
                return 0
            findings, n = run_checks(root, cfg, rel)
        else:
            if data.get("stop_hook_active"):
                return 0
            findings, n = run_checks(root, cfg)
        new, _ = split(root, findings)
        if new:
            print("The harness check found problems. Fix them before finishing, or tell the user why they should stay:", file=sys.stderr)
            report(new[:12], [], n, sys.stderr)
            if len(new) > 12:   # keep the message short; the agent can run `check` for the rest
                kinds = {}
                for f in new:
                    kinds[f[0]] = kinds.get(f[0], 0) + 1
                print(f"... and {len(new) - 12} more ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))} in total). "
                      "Run `python3 .harness/harness.py check` for the full list.", file=sys.stderr)
            return 2
        return 0
    except Exception as e:  # a broken hook must never trap the session
        print(f"harness hook skipped: {e}", file=sys.stderr)
        return 0


def settings(root):
    p = root / ".claude" / "settings.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        return {}


def audit(root, cfg):
    R = []

    def add(i, group, title, source, ok, evidence, fix):
        R.append({"id": i, "group": group, "title": title, "source": source,
                  "status": "skip" if ok is None else "pass" if ok else "fail", "evidence": evidence, "fix": fix})
    inst = [f for f in cfg["instruction_files"] if (root / f).exists()]
    text = "\n".join((root / f).read_text(errors="replace") for f in inst)
    names = list(docs(root, cfg))
    installed = (root / ".harness" / "harness.py").exists()
    st = settings(root); perms = st.get("permissions", {}); hooks = st.get("hooks", {})
    code = [p for p in root.rglob("*") if p.suffix in CODE_EXT and p.is_file() and not ({".git", "node_modules", ".venv", "venv"} & set(p.parts))]
    is_git = sh(["git", "rev-parse", "--git-dir"], root)[0] == 0

    lines = max(((root / f).read_text(errors="replace").count("\n") + 1 for f in inst), default=0)
    add("I1", "Instructions", "An instruction file exists", "walkinglabs L02; OpenAI", bool(inst), ", ".join(inst) or "none", "Create AGENTS.md or CLAUDE.md.")
    add("I2", "Instructions", f"It is a map: at most {cfg['instruction_max_lines']} lines", "OpenAI; walkinglabs L02", bool(inst) and lines <= cfg["instruction_max_lines"], f"longest is {lines} lines", "Move detail into linked files.")
    m = re.search(r"^#{1,4} .*verif.*$", text, re.M | re.I)
    add("I3", "Instructions", "It lists verification commands", "walkinglabs L02", bool(m and "`" in text[m.end():m.end() + 1500]), m.group(0) if m else "no Verification heading", "Add a Verification section with the exact commands.")
    broken = [f for f in inst for x in check_file(root, cfg, f, names) if x[0] == "links"]
    add("I4", "Instructions", "Every link in it resolves", "OpenAI (stale rules)", bool(inst) and not broken, f"{len(broken)} broken", "Fix or remove the dead links.")
    top = sorted(p.name for p in root.iterdir() if not p.name.startswith(".") and not match(p.name + "/x", cfg["docs"]["exclude"]))
    miss = [t for t in top if t not in text]
    add("I5", "Instructions", "It names at least 90% of the top-level files and folders", "OpenAI (table of contents)", bool(top) and len(miss) <= 0.1 * len(top), f"{len(top) - len(miss)}/{len(top)} named" + (f"; missing: {', '.join(miss[:8])}" if miss else ""), "Add the missing entries to the file map.")
    m = re.search(r"^#{1,4} .*(setup|first run|getting started|install|stack|requirements|environment).*$", text, re.M | re.I)
    add("I6", "Instructions", "It says how to set up or names the stack", "walkinglabs L02", bool(m), m.group(0) if m else "no setup or stack heading", "Add first-run commands and stack versions.")
    nested = [n for n in names if Path(n).name in ("CLAUDE.md", "AGENTS.md") and "/" in n and not n.startswith(".claude/")]
    skills = list((root / ".claude" / "skills").glob("*/SKILL.md")) if (root / ".claude" / "skills").is_dir() else []
    add("I7", "Instructions", "Detail loads on demand: folder-level instruction files or skills", "Claude Code design; OpenAI", bool(nested or skills), f"{len(nested)} nested files, {len(skills)} skills", "Move a topic rule into that folder's CLAUDE.md, or a procedure into a skill.")

    add("T1", "Tools", "Shared project settings exist (.claude/settings.json)", "OpenAI (everything in the repo)", (root / ".claude" / "settings.json").exists(), "present" if st else "absent", "Run `init`.")
    add("T2", "Tools", "The project has its own deny list", "walkinglabs L02 (least privilege)", bool(perms.get("deny")), f"{len(perms.get('deny', []))} deny rules", "Add deny rules to .claude/settings.json.")
    has = any(SECRET in d for d in perms.get("deny", []))
    add("T3", "Tools", "Secret files are denied to the agent", "walkinglabs L02; learn-claude-code", has, "rule found" if has else "no rule for secret env files", "Deny Read and Edit on secret env files.")
    mode = perms.get("defaultMode")
    add("T4", "Tools", "The project sets a permission mode that is not bypass", "walkinglabs L02; Claude Code design", bool(mode) and mode != "bypassPermissions", f"defaultMode: {mode}", "The user decides: set permissions.defaultMode in .claude/settings.json.")

    gi = (root / ".gitignore").read_text(errors="replace") if (root / ".gitignore").exists() else ""
    add("E1", "Environment", ".gitignore covers secret env files", "walkinglabs L02", SECRET in gi, "found" if SECRET in gi else "missing", "Add the secret env file to .gitignore.")
    pin = [p for p in PINS if (root / p).exists()]
    add("E2", "Environment", "The runtime version is pinned", "walkinglabs L02", (bool(pin) if code else None), ", ".join(pin) or (f"{len(code)} code files, no pin" if code else "no code"), "The user decides: add .python-version, .nvmrc or a Dockerfile.")
    man = [p for p in MANIFESTS if (root / p).exists()]
    add("E3", "Environment", "Dependencies are locked", "walkinglabs L02", (any((root / l).exists() for l in LOCKS) if man else None), ", ".join(man) or "no manifest", "Commit a lockfile.")
    setup = [p for p in SETUP if (root / p).exists()]
    add("E4", "Environment", "One command sets the environment up", "Anthropic effective harnesses (init.sh)", (bool(setup) if code else None), ", ".join(setup) or ("none" if code else "no code"), "Add init.sh or a Makefile target.")

    sf = [f for f in cfg["state_files"] if (root / f).exists()]
    add("S1", "State", "A progress or state file exists", "walkinglabs L02; Anthropic effective harnesses", bool(sf), ", ".join(sf) or "none", "Add PROGRESS.md and name it in .harness/harness.json.")
    newest = max(((root / n).stat().st_mtime for n in names), default=0)
    fresh = max(((root / f).stat().st_mtime for f in sf), default=0)
    add("S2", "State", "It was updated within a day of the latest doc change", "Anthropic effective harnesses", bool(sf) and newest - fresh <= 86400, f"{(newest - fresh) / 3600:.1f} h behind" if sf else "no state file", "Update it before the session ends.")
    rc, n = sh(["git", "rev-list", "--count", "HEAD"], root) if is_git else (1, "0")
    commits = int(n) if rc == 0 and n.isdigit() else 0
    add("S3", "State", "Git history exists (2 or more commits)", "Anthropic effective harnesses", commits >= 2, f"{commits} commits", "The user decides: commit on a branch.")
    dirty = len(sh(["git", "status", "--short"], root)[1].splitlines()) if is_git else 0
    add("S4", "State", f"The working tree is nearly clean (at most {cfg['max_uncommitted']} changed entries)", "Anthropic effective harnesses (clean state)", is_git and dirty <= cfg["max_uncommitted"], f"{dirty} changed entries", "The user decides: commit or discard.")
    branch = sh(["git", "branch", "--show-current"], root)[1] if is_git else ""
    add("S5", "State", "Work is not sitting uncommitted on the main branch", "OpenAI (one worktree per task)", is_git and not (branch in cfg["main_branches"] and dirty), f"branch {branch or '?'}, {dirty} changed", "The user decides: create a branch or worktree for the task.")
    fl = root / ".harness" / "failures.md"
    rows = len(re.findall(r"^\| \d{4}-\d\d-\d\d", fl.read_text(errors="replace"), re.M)) if fl.exists() else 0
    add("S6", "State", "A failure log exists and has entries", "walkinglabs L02; martinfowler.com (steering loop)", rows > 0, f"{rows} entries", "Log each agent mistake with its cause in .harness/failures.md.")
    df = [f for f in cfg["decision_files"] if (root / f).exists()]
    add("S7", "State", "Decisions or plans are logged in the repo", "OpenAI (plans with decision logs)", bool(df), ", ".join(df) or "none", "Add a decisions file and name it in .harness/harness.json.")

    add("F1", "Feedback", "A verification command is set up", "walkinglabs L02", bool(installed or cfg["commands"]), ("harness check" + "".join(f", {c['name']}" for c in cfg["commands"])) if installed else f"{len(cfg['commands'])} detected, no checker installed", "Run `init`, then add the project's test, lint and build commands.")
    new = old = None
    if installed:
        f, _ = run_checks(root, cfg, None, "full"); new, old = split(root, f)
    add("F2", "Feedback", "The full check passes with no new failures", "walkinglabs L02", installed and not new, f"{len(new)} new failures" if installed else "no checker installed", "Run `check --full` and fix what it prints.")
    add("F3", "Feedback", "A hook checks each edit (PostToolUse)", "martinfowler.com (keep quality left)", "PostToolUse" in hooks, "configured" if "PostToolUse" in hooks else "none in .claude/settings.json", "Run `init`.")
    add("F4", "Feedback", "A hook checks before the agent stops (Stop)", "Claude Code design; Anthropic harness design", "Stop" in hooks, "configured" if "Stop" in hooks else "none in .claude/settings.json", "Run `init`.")
    ci = [p for p in (".github/workflows", ".pre-commit-config.yaml", ".git/hooks/pre-commit", ".gitlab-ci.yml") if (root / p).exists()]
    add("F5", "Feedback", "CI or a pre-commit check exists", "OpenAI; martinfowler.com", bool(ci), ", ".join(ci) or "none", "Add a workflow or pre-commit hook that runs .claude/verify.sh.")
    add("F6", "Feedback", "No accepted debt in the baseline", "OpenAI (pay debt continuously)", (len(old) == 0 if installed else None), f"{len(old)} known failures" if installed else "no checker installed", "Fix the known failures and re-run `baseline`.")
    add("F7", "Feedback", "The checker's self-test passes (seeded faults are caught)", "martinfowler.com (sensors that never fire)", installed and selftest(quiet=True) == 0, "passed" if installed else "no checker installed", "Run `selftest`.")
    add("F8", "Feedback", "Failure messages say how to fix the problem", "OpenAI; martinfowler.com", installed, "every finding carries a fix line" if installed else "no checker installed", "Run `init`.")

    rv = root / ".harness" / "reviews.md"
    rows = len(re.findall(r"^\| \d{4}-\d\d-\d\d", rv.read_text(errors="replace"), re.M)) if rv.exists() else 0
    add("R1", "Review", "Someone other than the writer has reviewed work", "Anthropic harness design; OpenAI", rows > 0, f"{rows} reviews logged", "Have a person or a second agent review, and log it in .harness/reviews.md.")
    ss = [f for f in cfg["session_start_files"] if (root / f).exists()]
    total = sum((root / f).read_text(errors="replace").count("\n") + 1 for f in ss)
    add("C1", "Context", f"Session start reads at most {cfg['session_start_max_lines']} lines", "HumanLayer; OpenAI", bool(ss) and total <= cfg["session_start_max_lines"], f"{total} lines in {len(ss)} files", "Shorten the files read at session start, or read fewer.")
    return R


def cmd_audit(a):
    root = Path(a.project).resolve(); cfg = load_config(root, a.config)
    R = audit(root, cfg)
    p = sum(r["status"] == "pass" for r in R); f = sum(r["status"] == "fail" for r in R)
    if a.json:
        print(json.dumps({"pass": p, "fail": f, "skip": len(R) - p - f, "checks": R}, indent=1, ensure_ascii=False)); return 0
    g = None
    for r in R:
        if r["group"] != g:
            g = r["group"]; print(f"\n{g}")
        print(f"  {r['status'].upper():4} {r['id']:3} {r['title']}  [{r['evidence']}]" + (f"\n           fix: {r['fix']}" if r["status"] == "fail" else ""))
    print(f"\nharness audit: {p} pass, {f} fail, {len(R) - p - f} not applicable  ->  {100 * p // max(p + f, 1)}%")
    return 0


def cmd_init(a):
    root = Path(a.project).resolve(); h = root / ".harness"; h.mkdir(exist_ok=True); did = []
    me = Path(__file__).resolve()
    if me != (h / "harness.py").resolve():
        shutil.copyfile(me, h / "harness.py"); did.append(".harness/harness.py (copied)")
    if not (h / "harness.json").exists():
        cfg = json.loads(json.dumps(DEFAULT)); cfg.update(detect(root))
        (h / "harness.json").write_text(json.dumps(cfg, indent=2) + "\n"); did.append(".harness/harness.json (detected defaults; edit it)")
    for name, body in (("failures.md", FAILURES_MD), ("reviews.md", REVIEWS_MD)):
        if not (h / name).exists():
            (h / name).write_text(body); did.append(f".harness/{name}")
    (root / ".claude").mkdir(exist_ok=True)
    v = root / ".claude" / "verify.sh"
    if not v.exists():
        v.write_text('#!/usr/bin/env bash\n# One command to verify this project. Used by hooks, CI and people.\ncd "$(dirname "$0")/.." && exec python3 .harness/harness.py check --full\n')
        v.chmod(v.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH); did.append(".claude/verify.sh")
    st = settings(root); hooks = st.setdefault("hooks", {})
    for ev, entry in HOOKS.items():
        if not any("harness.py" in h2.get("command", "") for g in hooks.get(ev, []) for h2 in g.get("hooks", [])):
            hooks.setdefault(ev, []).append(entry); did.append(f".claude/settings.json: {ev} hook")
    deny = st.setdefault("permissions", {}).setdefault("deny", [])
    extra = [d for d in SECRET_DENY if d not in deny]
    if extra:
        deny += extra; did.append(".claude/settings.json: deny rules for secret env files")
    (root / ".claude" / "settings.json").write_text(json.dumps(st, indent=2) + "\n")
    cfg = load_config(root)
    inst = [f for f in cfg["instruction_files"] if (root / f).exists()]
    if not inst:
        (root / "AGENTS.md").write_text(f"# {root.name}\n\n## What this is\n\n## First run\n\n## Rules\n\n## Where things are\n" + VERIFY_BLOCK)
        did.append("AGENTS.md (skeleton: fill in the four sections)")
    elif not re.search(r"^#{1,4} .*verif", (root / inst[0]).read_text(errors="replace"), re.M | re.I):
        with open(root / inst[0], "a") as f:
            f.write(VERIFY_BLOCK)
        did.append(f"{inst[0]}: Verification section")
    gi = root / ".gitignore"
    if gi.exists() and "settings.local.json" not in gi.read_text():
        with open(gi, "a") as f:
            f.write("\n# Local Claude Code settings\n.claude/settings.local.json\nCLAUDE.local.md\n")
        did.append(".gitignore: local settings")
    if not (h / "baseline.json").exists():
        findings, _ = run_checks(root, cfg, None, "stop")
        today = datetime.date.today().isoformat()
        (h / "baseline.json").write_text(json.dumps({"accepted": [{"key": key(f), "reason": "present when the harness was installed", "date": today} for f in findings]}, indent=2, ensure_ascii=False) + "\n")
        did.append(f".harness/baseline.json ({len(findings)} existing failures accepted as debt)")
    print("harness init:" + ("".join(f"\n  + {d}" for d in did) or " nothing to do"))
    return 0


def selftest(quiet=False):
    d = Path(tempfile.mkdtemp(prefix="harness-selftest-")); ok = []
    try:
        (d / "docs").mkdir(); (d / ".harness").mkdir()
        cfg = json.loads(json.dumps(DEFAULT))
        cfg.update({"frontmatter": {"required_keys": ["title"]}, "naming": {"pattern": r"^[A-Za-z0-9._-]+$"}, "index": {"file": "README.md"},
                    "commands": [{"name": "false", "run": "exit 3", "when": "manual"}]})
        (d / ".harness" / "harness.json").write_text(json.dumps(cfg))
        (d / "AGENTS.md").write_text("---\ntitle: a\n---\n[gone](docs/missing.md)\n")
        (d / "docs" / "README.md").write_text("---\ntitle: index\n---\n")
        (d / "docs" / "Bad Name.md").write_text("no frontmatter\n")
        got = {f[0] for f in run_checks(d, load_config(d), None, "full")[0]}
        ok.append(("seeded faults are caught", got >= {"links", "frontmatter", "naming", "index", "command"}))
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(d)); me = [sys.executable, str(Path(__file__).resolve())]
        r = subprocess.run(me + ["hook", "post"], input=json.dumps({"tool_input": {"file_path": str(d / "AGENTS.md")}}), text=True, capture_output=True, env=env)
        ok.append(("edit hook blocks with a fix message", r.returncode == 2 and "fix:" in r.stderr))
        r = subprocess.run(me + ["hook", "stop"], input=json.dumps({"stop_hook_active": True}), text=True, capture_output=True, env=env)
        ok.append(("stop hook never loops", r.returncode == 0))
        r = subprocess.run(me + ["hook", "stop"], input="not json", text=True, capture_output=True, env=env)
        ok.append(("a broken hook input fails open", r.returncode == 0))
        subprocess.run(me + ["baseline", "--project", str(d), "--reason", "selftest"], capture_output=True)
        r = subprocess.run(me + ["check", "--project", str(d), "--full"], capture_output=True, text=True)
        ok.append(("the baseline accepts known debt", r.returncode == 0 and "known" in r.stdout))
        (d / "docs" / "new.md").write_text("---\ntitle: n\n---\n[x](nope.md)\n")
        r = subprocess.run(me + ["check", "--project", str(d)], capture_output=True, text=True)
        ok.append(("a new failure still fails", r.returncode == 1))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    bad = [n for n, v in ok if not v]
    if not quiet:
        for n, v in ok:
            print(f"  {'ok  ' if v else 'FAIL'} {n}")
        print(f"selftest: {len(ok) - len(bad)}/{len(ok)} passed")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("audit", "init", "check", "baseline", "hook", "selftest"):
        p = sub.add_parser(name)
        p.add_argument("--project", default=".")
        p.add_argument("--config")
        if name in ("audit", "check"):
            p.add_argument("--json", action="store_true")
        if name == "check":
            p.add_argument("--file"); p.add_argument("--full", action="store_true")
        if name == "baseline":
            p.add_argument("--reason", required=True)
        if name == "hook":
            p.add_argument("event", choices=["post", "stop"])
    a = ap.parse_args()
    return {"audit": cmd_audit, "init": cmd_init, "check": cmd_check, "baseline": cmd_baseline, "hook": cmd_hook,
            "selftest": lambda a: selftest()}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
