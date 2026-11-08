"""Minimal MCP server over stdio (newline-delimited JSON-RPC). Each tool shells out to the `dsa` CLI."""
import json, os, re, subprocess, sys

TOOLS = {
    "fetch_problem": ("Fetch a LeetCode or GeeksforGeeks problem into the DSA workspace and open it in Zed.",
                      {"query": "URL, slug, problem number, title, or gfg:<slug>"}, lambda a: ["fetch", a["query"]]),
    "run_tests": ("Run a solution.py or solution.java against its problem's tests. All pass -> saved.",
                  {"path": "path to solution.py / solution.java, or the problem folder"}, lambda a: ["test", a["path"]]),
    "generate_tests": ("Add AI test cases (via the local LM Studio model) to a problem folder.",
                       {"problem_dir": "problem folder"}, lambda a: ["gen", a["problem_dir"]]),
    "new_problem": ("Invent a new practice problem with tests using the local LM Studio model.",
                    {"title": "what to practice, e.g. 'remove leaves from a binary tree'"}, lambda a: ["new", a["title"]]),
    "save_solution": ("Archive edited solution files to solutions/<lang>/<YYYY-MM>/<DD>/.",
                      {"problem_dir": "problem folder"}, lambda a: ["save", a["problem_dir"]]),
    "heatmap": ("Show the LeetCode submission heatmap and local practice heatmap.", {}, lambda a: ["heatmap"]),
}


def tool_list():
    return [{"name": n, "description": d, "inputSchema": {"type": "object", "required": list(p),
             "properties": {k: {"type": "string", "description": v} for k, v in p.items()}}}
            for n, (d, p, _) in TOOLS.items()]


def call(name, args):
    if name not in TOOLS:
        return {"content": [{"type": "text", "text": f"unknown tool {name}"}], "isError": True}
    try:
        argv = TOOLS[name][2](args)
    except KeyError as e:
        return {"content": [{"type": "text", "text": f"missing argument {e}"}], "isError": True}
    r = subprocess.run([sys.executable, "-m", "zed_dsa.cli", *argv], capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=1200, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr).strip() or "(no output)"
    return {"content": [{"type": "text", "text": out}], "isError": r.returncode != 0}


def handle(msg):
    method, params = msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": params.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}},
                "serverInfo": {"name": "dsa", "version": "0.1.0"}}
    if method == "tools/list":
        return {"tools": tool_list()}
    if method == "tools/call":
        return call(params.get("name"), params.get("arguments") or {})
    if method == "ping":
        return {}
    raise LookupError(method)


def serve():
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if "id" not in msg:  # notification
            continue
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
        except LookupError as e:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"method not found: {e}"}}
        except Exception as e:  # keep the server alive
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": repr(e)}}
        print(json.dumps(reply), flush=True)
