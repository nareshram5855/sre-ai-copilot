"""
Shared shell security helpers used by execute.py and agent_run.py.

Two security tiers:
  SRE mode  (full_mode=False) — strict allowlist: kubectl/helm/git/docker only
  Full mode (full_mode=True)  — block-only: only truly catastrophic ops blocked

Full mode is equivalent to Claude Code's terminal capability — it lets the agent
create files, install packages, read directories, run Python/Node, etc.
"""
import os
import re

# ── SRE mode: strict allowlist ────────────────────────────────────────────────

_SRE_ALLOWED_PREFIXES = (
    "helm ",
    "kubectl get", "kubectl describe", "kubectl apply", "kubectl create",
    "kubectl rollout", "kubectl logs", "kubectl top", "kubectl version",
    "kubectl explain", "kubectl diff",
    "git init", "git clone", "git status", "git log",
    "docker build", "docker pull", "docker images", "docker ps",
)

_SRE_BLOCKED = re.compile(
    r"(rm\s+-[rf]|sudo|eval|exec\s|;\s*bash|;\s*sh|\|\s*bash|\|\s*sh"
    r"|>\s*/|chmod\s+777|curl\s+.*\|\s*sh|wget\s+.*\|\s*sh"
    r"|kubectl\s+delete|kubectl\s+exec|kubectl\s+cp|kubectl\s+port-forward"
    r"|helm\s+delete|helm\s+uninstall)",
    re.IGNORECASE,
)

# ── Full mode: block catastrophic ops only ────────────────────────────────────
# Allows mkdir, pip, touch, cat, ls, find, python, node, npm, echo, cp, mv, etc.
# Blocks: wipe /, format disks, fork bomb, curl|bash, shutdown, privilege escalation.

_FULL_BLOCKED = re.compile(
    # Wipe root or home entirely (rm -rf / or rm -rf ~)
    r"rm\s+(-[a-z]*f[a-z]*\s+)*-[a-z]*r[a-z]*\s+[/~]\s*$"
    r"|rm\s+(-[a-z]*r[a-z]*\s+)*-[a-z]*f[a-z]*\s+[/~]\s*$"
    # Sudo rm -rf (block sudo destructive)
    r"|sudo\s+rm\s+-[rf]"
    # Block device writes (would destroy disk)
    r"|>\s*/dev/(sd|nvme|disk|vd)[a-z0-9]"
    # Disk formatting
    r"|\bmkfs\b|\bformat\s+[cC]:"
    # dd to real disk
    r"|dd\s+.*of=/dev/[a-z]+[0-9]?"
    # Fork bomb
    r"|:\s*\(\s*\)\s*\{"
    # curl/wget piped directly into a shell (supply chain attack)
    r"|(curl|wget)\s+[^\|]+\|\s*(bash|sh|zsh|fish|dash)"
    # System shutdown / power commands
    r"|\b(shutdown|reboot|halt|poweroff)\b"
    # Privilege escalation / user manipulation
    r"|\bpasswd\b|\buseradd\b|\busermod\b|\bvisudo\b"
    r"|echo\s+.*>>\s*/etc/(passwd|shadow|sudoers)",
    re.IGNORECASE | re.MULTILINE,
)


def check_command(command: str, full_mode: bool) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    reason is empty string when allowed=True.
    """
    cmd = command.strip()
    if not cmd:
        return False, "Empty command"

    if full_mode:
        if _FULL_BLOCKED.search(cmd):
            return False, "Blocked: catastrophic or irreversible operation"
        return True, ""
    else:
        if _SRE_BLOCKED.search(cmd):
            return False, "Blocked: destructive or shell-injection risk"
        if not any(cmd.lower().startswith(p) for p in _SRE_ALLOWED_PREFIXES):
            return False, "SRE mode: only kubectl/helm/git/docker allowed — enable Full mode for general commands"
        return True, ""


# ── Working directory tracking ────────────────────────────────────────────────
# Persists cwd across sequential commands within a session so `cd myapp`
# followed by `pip install flask` runs in the right directory.

_session_cwd: dict[str, str] = {}
_SERVER_ROOT = os.getcwd()


def get_cwd(session_id: str) -> str:
    return _session_cwd.get(session_id, _SERVER_ROOT)


def update_cwd(session_id: str, command: str, exit_code: int, cwd: str) -> None:
    """
    If the command (or the last segment of a compound command) is `cd <path>`
    and it succeeded, update the stored cwd for this session.
    """
    if exit_code != 0:
        return
    # Handle compound commands (&&, ;) — look at the last cd directive
    segments = re.split(r"&&|;", command)
    for seg in reversed(segments):
        seg = seg.strip()
        m = re.match(r"^cd\s+(.+)$", seg)
        if m:
            target = m.group(1).strip().strip("'\"")
            if target == "-":
                return  # cd - (previous dir) — too complex to track
            if target.startswith("~"):
                target = os.path.expanduser(target)
            if not os.path.isabs(target):
                target = os.path.normpath(os.path.join(cwd, target))
            if os.path.isdir(target):
                _session_cwd[session_id] = target
            return
