"""`dsa setup-zed`: merge DSA tasks + layout keybinding into ~/.config/zed (backs up what it replaces)."""
import json, re, shutil
from pathlib import Path

ZED = Path.home() / ".config" / "zed"


def task(label, cmd):
    return {"label": f"DSA: {label}", "command": cmd, "cwd": "$ZED_WORKTREE_ROOT", "reveal": "always"}


TASKS = [
    task("fetch LeetCode/GFG problem", "dsa fetch"),
    task("run tests (current file: .py or .java)", 'dsa test "$ZED_FILE"'),
    task("new AI problem (LM Studio)", "dsa new"),
    task("add AI test cases (current problem)", 'dsa gen "$ZED_DIRNAME"'),
    task("save solutions (current problem)", 'dsa save "$ZED_DIRNAME"'),
    task("heatmap", "dsa heatmap"),
]
# ctrl-alt-l: move focused tab (the solution) into a right split, render README.md as a preview on the left.
# The ctrl-alt-shift-* keys are internal steps chained by SendKeystrokes.
KEYMAP = [
    {"context": "Workspace", "bindings": {
        "ctrl-alt-l": ["workspace::SendKeystrokes", "ctrl-alt-shift-y ctrl-alt-shift-u ctrl-alt-shift-i ctrl-alt-shift-o"],
        "ctrl-alt-shift-y": "pane::SplitAndMoveRight",
        "ctrl-alt-shift-u": "workspace::ActivatePaneLeft",
        "ctrl-alt-shift-o": "workspace::ActivatePaneRight"}},
    {"context": "Editor", "bindings": {"ctrl-alt-shift-i": "markdown::OpenPreview"}},
]


def load(path):
    """Zed's JSON allows // comments and trailing commas; None if we still can't read it."""
    if not path.exists():
        return []
    txt = re.sub(r"^\s*//.*$", "", path.read_text(), flags=re.M)
    txt = re.sub(r",(\s*[\]}])", r"\1", txt)
    try:
        data = json.loads(txt or "[]")
        return data if isinstance(data, list) else None
    except ValueError:
        return None


def merge(path, ours, is_ours):
    current = load(path)
    if current is None:
        print(f"Couldn't parse {path}; add this yourself:\n{json.dumps(ours, indent=2)}")
        return
    if path.exists():
        shutil.copy(path, path.with_suffix(".json.bak"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([x for x in current if not is_ours(x)] + ours, indent=2) + "\n")
    print(f"Updated {path}" + (f" (backup: {path.with_suffix('.json.bak').name})" if current else ""))


def ours_key(entry):
    return any(k.startswith("ctrl-alt-shift-") or k == "ctrl-alt-l" for k in entry.get("bindings", {}))


def install():
    merge(ZED / "tasks.json", TASKS, lambda t: str(t.get("label", "")).startswith("DSA: "))
    merge(ZED / "keymap.json", KEYMAP, ours_key)
    print("Done. In Zed: alt-shift-t -> pick a 'DSA:' task. ctrl-alt-l -> question left, code right.")
