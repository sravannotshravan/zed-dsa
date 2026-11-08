#!/usr/bin/env python3
"""DSA practice inside Zed. Run from (or below) a folder with dsa.json; otherwise $DSA_HOME or ~/dsa-practice.

  dsa fetch [url | slug | number | title]   LeetCode or GeeksforGeeks problem -> problems/<slug>/
  dsa new [title]                           invent a problem + tests with your LM Studio model
  dsa gen <problem-dir> [n]                 add n AI test cases (outputs come from an AI reference solution)
  dsa test <problem-dir | solution file>    run solution.py / solution.java (all pass -> auto-save)
  dsa save <problem-dir>                    archive solution.* -> solutions/<lang>/<YYYY-MM>/<DD>/<slug>.<ext>
  dsa import <git-url | path>               pull a LeetHub repo's solutions into solutions/ (dated by commit)
  dsa heatmap                               LeetCode submission calendar + your local saves
  dsa setup-zed                             add the DSA tasks + ctrl-alt-l layout key to your global Zed config
  dsa mcp                                   MCP server (stdio) for Zed's agent panel / the Zed extension
"""
import html, io, json, os, re, shutil, signal, subprocess, sys, tempfile, time, traceback, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PKG = Path(__file__).resolve().parent  # lc.py, LC.java
sys.path.insert(0, str(PKG))  # solutions' `from lc import *` must get this same module (isinstance checks)
from lc import build_list, build_tree, to_plain  # noqa: E402

ROOT = None  # practice workspace, set by find_root()


LAST = Path.home() / ".config" / "zed-dsa" / "workspace"  # last workspace used, for calls from elsewhere (MCP)


def find_root(start):
    for d in [Path(start).resolve(), *Path(start).resolve().parents]:
        if (d / "dsa.json").exists():
            LAST.parent.mkdir(parents=True, exist_ok=True)
            LAST.write_text(str(d))
            return d
    last = Path(LAST.read_text().strip()) if LAST.exists() else None
    if not os.environ.get("DSA_HOME") and last and (last / "dsa.json").exists():
        return last
    home = Path(os.environ.get("DSA_HOME") or Path.home() / "dsa-practice")
    if not (home / "dsa.json").exists():
        home.mkdir(parents=True, exist_ok=True)
        (home / "dsa.json").write_text(json.dumps({"leetcode_username": "", "languages": ["python3", "java"]}, indent=1))
        print(f"Created practice workspace {home}")
    return home


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:  # no terminal (MCP / piped)
        return ""
EXT = {"python3": "py", "cpp": "cpp", "java": "java", "javascript": "js", "typescript": "ts", "c": "c",
       "csharp": "cs", "golang": "go", "rust": "rs", "kotlin": "kt", "swift": "swift"}
LANG = {v: k for k, v in EXT.items()}
TIMEOUT = 5  # seconds per test
sys.setrecursionlimit(10**4)


def cfg():
    c = {"leetcode_username": "", "languages": ["python3"]}
    c.update(json.loads((ROOT / "dsa.json").read_text()))
    return c


def http_json(url, body=None, headers=None, timeout=30):
    h = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def leetcode(query, **variables):
    return http_json("https://leetcode.com/graphql", {"query": query, "variables": variables},
                     {"Referer": "https://leetcode.com"})["data"]


def html_to_text(h):
    h = re.sub(r"<sup>(.*?)</sup>", r"^\1", h or "")
    h = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', r"![](\1)", h)
    h = re.sub(r"</p>|<br\s*/?>|</li>|</pre>|</div>", "\n", h)
    h = re.sub(r"<li>", "- ", re.sub(r"<pre>", "\n", h))
    h = html.unescape(re.sub(r"<[^>]+>", "", h)).replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", h).strip()


def html_to_md(h):
    """Statement HTML -> Markdown for Zed's preview."""
    h = re.sub(r"<pre>(.*?)</pre>", lambda m: "\n```\n" + html_to_text(m.group(1)) + "\n```\n", h or "", flags=re.S)
    h = re.sub(r"</?(strong|b)\b[^>]*>", "**", h)
    h = re.sub(r"</?(em|i)\b[^>]*>", "*", h)
    h = re.sub(r"</?code\b[^>]*>", "`", h)
    return html_to_text(h)


def gfg_stdin(s):
    """'arr[] = [1, 2, 3], target = 12' -> '1 2 3\\n12' (GFG drivers read one argument per line)."""
    # shortcut: flattens 2-D arrays; matrix problems need `gen` for proper tests
    vals = re.split(r",?\s*\b\w+(?:\[\])*\s*=\s*", " " + s)[1:]
    return "\n".join(" ".join(re.sub(r'[\[\],"\']', " ", v).split()) for v in vals)


def lc_outputs(text):
    """Each 'Output:' value; JSON may span several lines (e.g. text-justification)."""
    outs = []
    for m in re.finditer(r"^Output:?\s*", text, re.M):
        lines = text[m.end():].split("\n")
        for k in range(1, min(len(lines), 40) + 1):
            try:
                outs.append(json.loads("\n".join(lines[:k])))
                break
            except ValueError:
                pass
        else:
            outs.append(lines[0].strip())
    return outs


def parse_val(s):
    try:
        return json.loads(s)
    except ValueError:
        return s.strip()


# ---------- fetching ----------

def fetch_lc(arg):
    m = re.search(r"leetcode\.com/problems/([\w-]+)", arg)
    slug = m.group(1) if m else arg if re.fullmatch(r"[a-z0-9-]+", arg) and "-" in arg else None
    if not slug:  # number or free-text title
        hits = leetcode('query q($k:String){questionList(categorySlug:"",limit:1,skip:0,filters:{searchKeywords:$k})'
                        "{data{titleSlug}}}", k=arg)["questionList"]["data"]
        slug = hits[0]["titleSlug"] if hits else sys.exit(f"No LeetCode match for {arg!r}")
    q = leetcode("query q($s:String!){question(titleSlug:$s){questionFrontendId title titleSlug difficulty content "
                 "exampleTestcases metaData codeSnippets{langSlug code}}}", s=slug)["question"]
    if not q:
        sys.exit(f"No LeetCode problem {slug!r}")
    if not q["content"]:
        sys.exit("That problem is premium-only; its statement isn't public.")
    meta, text = json.loads(q["metaData"]), html_to_text(q["content"])
    n = 2 if meta.get("systemdesign") else len(meta["params"])
    lines = q["exampleTestcases"].split("\n")
    inputs = [[json.loads(x) for x in lines[i:i + n]] for i in range(0, len(lines), n)]
    outputs = lc_outputs(text)
    # LeetCode's custom judge for in-place "return k" problems (26, 27, 80...): "2, nums = [1,2,_]"
    kp = [re.fullmatch(r"(\d+), nums = \[(.*)\]", o) for o in outputs if isinstance(o, str)]
    if kp and all(kp) and len(kp) == len(outputs):
        outputs = [[int(m.group(1)), [int(x) for x in m.group(2).split(",") if x.strip() not in ("", "_")]] for m in kp]
    snippets = {s["langSlug"]: s["code"] for s in q["codeSnippets"] or []}
    if "python3" not in snippets:
        sys.exit("No Python version of this problem (probably SQL/shell).")
    prob = {"mode": "lc", "slug": q["titleSlug"], "meta": meta, "any_order": "any order" in text.lower(),
            "k_prefix": bool(kp and all(kp) and len(kp) == len(outputs)),
            "tests": [{"input": i, "output": o} for i, o in zip(inputs, outputs)]}
    readme = (f"# {q['questionFrontendId']}. {q['title']} ({q['difficulty']})\n\n"
              f"https://leetcode.com/problems/{q['titleSlug']}/\n\n{html_to_md(q['content'])}\n")
    return prob, readme, snippets


def fetch_gfg(arg):
    m = re.search(r"geeksforgeeks\.org/problems/([\w-]+)", arg)
    slug = m.group(1) if m else arg.removeprefix("gfg:")
    r = http_json(f"https://practiceapi.geeksforgeeks.org/api/vr/problems/{slug}/")["results"]
    funcs = r["extra"]["initial_user_func"]
    if "python3" not in funcs:
        sys.exit("No Python version of this problem on GFG.")
    text = html_to_text(r["problem_question"])
    ins = re.findall(r"^Input:[ \t]*(.*)$", text, re.M)
    outs = [o.strip() for o in re.findall(r"^Output:?\s*(.+)$", text, re.M)]
    if ins and len(ins) == len(outs) and all("=" in i for i in ins):
        tests = [{"input": gfg_stdin(i), "output": o} for i, o in zip(ins, outs)]
    else:  # examples are images: pair GFG's one sample stdin with Example 1's output and hope
        sample = (r.get("test_cases") or "").replace("&!//!&", "\n").strip()
        tests = [{"input": sample, "output": outs[0], "unverified": True}] if sample and outs else []
    prob = {"mode": "gfg", "slug": slug, "driver": funcs["python3"]["initial_code"],
            "java_driver": funcs.get("java", {}).get("initial_code", ""), "tests": tests}
    readme = (f"# {r['problem_name']} ({r['difficulty']})\n\nhttps://www.geeksforgeeks.org/problems/{slug}/1\n\n"
              f"{html_to_md(r['problem_question'])}\n\n**Constraints:** {r.get('constraints_display', '')}\n")
    return prob, readme, {k: v["user_code"] for k, v in funcs.items()}


def write_problem(prob, readme, snippets):
    d = ROOT / "problems" / prob["slug"]
    if (d / "problem.json").exists():
        print(f"{d} already exists; keeping your work.")
        return d
    d.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "lc.py").exists():  # so Zed's Python language server resolves `from lc import *`
        shutil.copy(PKG / "lc.py", ROOT / "lc.py")
    langs = dict.fromkeys(["python3", *cfg()["languages"]])  # Python always: it's the one tests run on
    prob["starters"] = {}
    for lang in langs:
        if lang in snippets and lang in EXT:
            code = ("from lc import *\n\n" if lang == "python3" else "") + snippets[lang]
            name = f"solution.{EXT[lang]}"
            (d / name).write_text(code)
            prob["starters"][name] = code
    (d / "README.md").write_text(readme)
    (d / "problem.json").write_text(json.dumps(prob, indent=1))
    print(f"Created {d} with {len(prob['tests'])} example tests")
    return d


def open_in_zed(d):
    if shutil.which("zed"):
        subprocess.run(["zed", "-a", str(d / "README.md"), str(d / "solution.py")])
        print("In Zed press ctrl-alt-l (with solution.py focused): rendered question left, code right.")


def cmd_fetch(arg=None):
    arg = (arg or ask("LeetCode/GFG URL, slug, number or title (gfg:<slug> for GFG): ")).strip()
    prob, readme, snippets = fetch_gfg(arg) if "geeksforgeeks" in arg or arg.startswith("gfg:") else fetch_lc(arg)
    open_in_zed(write_problem(prob, readme, snippets))


# ---------- running ----------

def node(t, a):
    if t.endswith("[]") and "Node" in t:
        return [node(t[:-2], x) for x in a]
    return build_tree(a) if t == "TreeNode" else build_list(a) if t == "ListNode" else a


def run(prob, path, inp):
    src = Path(path).read_text()
    if prob["mode"] == "gfg":
        old, buf = (sys.stdin, sys.stdout), io.StringIO()
        sys.stdin, sys.stdout = io.StringIO(f"1\n{inp}\n"), buf
        try:
            exec(compile(src + "\n" + prob["driver"], str(path), "exec"), {"__name__": "__main__"})
        finally:
            sys.stdin, sys.stdout = old
        return buf.getvalue()
    ns, meta, args = {"__name__": "solution"}, prob["meta"], json.loads(json.dumps(inp))  # fresh copy
    exec(compile(src, str(path), "exec"), ns)
    if meta.get("systemdesign"):
        ops, params = args
        obj = ns[meta["classname"]](*params[0])
        return to_plain([None] + [getattr(obj, op)(*p) for op, p in zip(ops[1:], params[1:])])
    conv = [node(p["type"], a) for p, a in zip(meta["params"], args)]
    res = getattr(ns["Solution"](), meta["name"])(*conv)
    if meta.get("return", {}).get("type") == "void":  # in-place problems: check the mutated argument
        res = conv[meta.get("output", {}).get("paramindex", 0)]
    if prob.get("k_prefix"):
        res = [res, conv[0][:res]]
    return to_plain(res)


def close(a, e):
    if isinstance(a, (int, float)) and isinstance(e, (int, float)) and float in (type(a), type(e)):
        return abs(a - e) < 1e-5
    if isinstance(a, list) and isinstance(e, list):
        return len(a) == len(e) and all(map(close, a, e))
    return a == e


def same(prob, got, exp):
    if prob["mode"] == "gfg":
        norm = lambda s: re.sub(r"[\[\],]", " ", "\n".join(x for x in str(s).splitlines() if x.strip() != "~")).split()
        return norm(got) == norm(exp)
    if prob.get("k_prefix"):  # k must match; the first k elements may be in any order
        return isinstance(got, list) and got[0] == exp[0] and sorted(got[1]) == sorted(exp[1])
    meta = prob.get("meta", {})
    rtype = meta.get("return", {}).get("type", "")
    if rtype == "void" and meta.get("params"):  # in-place: the mutated argument is the answer
        rtype = meta["params"][meta.get("output", {}).get("paramindex", 0)]["type"]
    if got is None and exp == [] and "Node" in rtype:
        return True  # LeetCode prints an empty tree/list as []
    if close(got, exp):
        return True
    # shortcut: "any order" only sorts the outer list; inner-order-free answers (group anagrams) can false-fail
    key = lambda x: json.dumps(x, sort_keys=True)
    return bool(prob.get("any_order")) and isinstance(got, list) and isinstance(exp, list) and \
        sorted(map(key, got)) == sorted(map(key, exp))


def timed(prob, path, inp):
    def boom(*_):
        raise TimeoutError(f"> {TIMEOUT}s")
    signal.signal(signal.SIGALRM, boom)
    signal.setitimer(signal.ITIMER_REAL, TIMEOUT)
    try:
        return run(prob, path, inp)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def short(x, n=300):
    s = x if isinstance(x, str) else json.dumps(x)
    return s if len(s) <= n else s[:n] + "…"


def py_result(prob, path, inp):
    t0 = time.perf_counter()
    try:
        got, err = timed(prob, path, inp), None
    except Exception as e:
        got, err = None, "".join(traceback.format_exception(e)[-3:]).strip()
    return got, err, (time.perf_counter() - t0) * 1000


# ---------- Java ----------

JT = {"integer": "int", "long": "long", "double": "double", "float": "float", "boolean": "boolean",
      "string": "String", "character": "char", "void": "void"}
BOX = {"int": "Integer", "long": "Long", "double": "Double", "float": "Float", "boolean": "Boolean", "char": "Character"}
JAVA_IMPORT = re.compile(r"^\s*import\s+[\w.*\s]+;\s*$", re.M)


def jtype(t):
    if t.endswith("[]"):
        return jtype(t[:-2]) + "[]"
    m = re.fullmatch(r"list<(.+)>", t, re.I)
    if m:
        inner = jtype(m.group(1))
        return f"List<{BOX.get(inner, inner)}>"
    return JT.get(t, t)


def jlit(t, v):
    """JSON value of LeetCode type t -> Java expression."""
    if t == "TreeNode":
        return "LC.tree(new Integer[]{" + ",".join("null" if x is None else str(x) for x in v) + "})"
    if t == "ListNode":
        return "LC.list(new int[]{" + ",".join(map(str, v)) + "})"
    if v is None:
        return "null"
    if t.endswith("[]"):
        return f"new {jtype(t)}{{{', '.join(jlit(t[:-2], x) for x in v)}}}"
    m = re.fullmatch(r"list<(.+)>", t, re.I)
    if m:
        el = BOX.get(jtype(m.group(1)), jtype(m.group(1)))
        return f"new ArrayList<{el}>(Arrays.<{el}>asList({', '.join(jlit(m.group(1), x) for x in v)}))"
    if t == "character":
        return "'" + json.dumps(v)[1:-1].replace("'", "\\'") + "'"
    if t == "long":
        return f"{v}L"
    if t in ("double", "float"):
        return repr(float(v)) + ("f" if t == "float" else "")
    return json.dumps(v)  # int, boolean, string (JSON escapes are valid Java)


def java_test_body(prob, args):
    meta = prob["meta"]
    if meta.get("systemdesign"):
        ops, params = args
        methods = {m["name"]: m for m in meta["methods"]}
        lits = lambda ps, vals: ", ".join(jlit(p["type"], v) for p, v in zip(ps, vals))
        body = [f"{meta['classname']} o = new {meta['classname']}({lits(meta['constructor']['params'], params[0])});",
                "List<Object> res = new ArrayList<>(); res.add(null);"]
        for op, vals in zip(ops[1:], params[1:]):
            call = f"o.{op}({lits(methods[op]['params'], vals)})"
            body.append(f"{call}; res.add(null);" if methods[op]["return"]["type"] == "void" else f"res.add({call});")
        return " ".join(body + ["return res;"])
    decl = [f"{jtype(p['type'])} a{k} = {jlit(p['type'], v)};" for k, (p, v) in enumerate(zip(meta["params"], args))]
    call = f"new Solution().{meta['name']}({', '.join(f'a{k}' for k in range(len(args)))})"
    if meta.get("return", {}).get("type") == "void":
        return " ".join(decl + [f"{call}; return a{meta.get('output', {}).get('paramindex', 0)};"])
    if prob.get("k_prefix"):
        return " ".join(decl + [f"int k = {call}; return new Object[]{{k, Arrays.copyOf(a0, k)}};"])
    return " ".join(decl + [f"return {call};"])


def javac(src, out_dir, main):
    """Compile src (user code at line `offset`+1) together with LC.java. Returns error text or None."""
    (out_dir / f"{main}.java").write_text(src)
    r = subprocess.run(["javac", "-nowarn", "-d", out_dir, out_dir / f"{main}.java", PKG / "LC.java"],
                       capture_output=True, text=True)
    return r.returncode and r.stderr


def java_results(prob, path):
    user = Path(path).read_text()
    imports = "\n".join(dict.fromkeys(["import java.util.*;", "import java.util.stream.*;", "import java.io.*;",
                                        *JAVA_IMPORT.findall(prob.get("java_driver", "")), *JAVA_IMPORT.findall(user)]))
    user = JAVA_IMPORT.sub("", user)  # hoisted; sub keeps the line so line numbers survive
    user = re.sub(r"^public\s+(?=(final\s+)?class\b)", "", user, flags=re.M)  # one public class per file
    offset, last = imports.count("\n") + 1, user.count("\n") + 1
    fix = lambda txt: re.sub(r" ?(?:\S*Main\.java:|@line )(\d+)", lambda m: f" solution.java:{int(m.group(1)) - offset}"
                             if 0 < int(m.group(1)) - offset <= last else " (test harness)", str(txt)).strip()
    n = len(prob["tests"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if prob["mode"] == "gfg":
            driver = JAVA_IMPORT.sub("", prob.get("java_driver") or sys.exit("No GFG Java driver; re-fetch the problem."))
            main = re.findall(r"class\s+(\w+)[^{]*\{(?:(?!\bclass\b).)*?static\s+void\s+main", driver, re.S)[0]
            if err := javac(f"{imports}\n{user}\n{driver}".replace(f"class {main}", "class Main", 1), tmp, "Main"):
                return [(None, fix(err), 0)] * n
            out = []
            for t in prob["tests"]:
                t0 = time.perf_counter()
                try:
                    r = subprocess.run(["java", "-Xss256m", "-cp", tmp, "Main"], input=f"1\n{t['input']}\n",
                                       capture_output=True, text=True, timeout=TIMEOUT)
                    out.append((r.stdout, fix(r.stderr.strip()) or None, (time.perf_counter() - t0) * 1000))
                except subprocess.TimeoutExpired:
                    out.append((None, f"TimeoutError: > {TIMEOUT}s", TIMEOUT * 1000))
            return out
        tests = "\n".join(f"        LC.run({i}, () -> {{ {java_test_body(prob, t['input'])} }});"
                           for i, t in enumerate(prob["tests"]))
        src = f"{imports}\n{user}\n\npublic class Main {{\n    public static void main(String[] args) {{\n{tests}\n    }}\n}}\n"
        if err := javac(src, tmp, "Main"):
            return [(None, fix(err), 0)] * n
        try:
            r = subprocess.run(["java", "-Xss256m", "-cp", f"{tmp}", "Main"], capture_output=True, text=True,
                               timeout=TIMEOUT * n + 2)
            stdout = r.stdout
        except subprocess.TimeoutExpired as e:  # tests that never reported are the slow ones
            stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    res = {}
    for line in stdout.splitlines():
        m = re.match(r"@@(\d+) (\d+) (.*)", line)
        if not m:
            print(f"   [stdout] {line}")
            continue
        val = m.group(3)
        res[int(m.group(1))] = (None, fix(val[1:]), int(m.group(2))) if val.startswith("!") else (json.loads(val), None, int(m.group(2)))
    return [res.get(i, (None, f"TimeoutError: > {TIMEOUT}s (or crashed)", 0)) for i in range(n)]


def cmd_test(target):
    f = Path(target)
    d = f if f.is_dir() else f.parent
    if f.is_dir() or not re.fullmatch(r"solution\.(py|java)", f.name):
        f = d / "solution.py"  # e.g. README.md focused in Zed
    prob = json.loads((d / "problem.json").read_text())
    print(f"Testing {f.name}")
    results = java_results(prob, f) if f.suffix == ".java" else [py_result(prob, f, t["input"]) for t in prob["tests"]]
    passed = 0
    for i, (t, (got, err, ms)) in enumerate(zip(prob["tests"], results), 1):
        ok = err is None and same(prob, got, t["output"])
        detail = err or f"got      {short(got)}"
        tag = " (ai)" if t.get("source") == "ai" else " (unverified example pairing)" if t.get("unverified") else ""
        print(f"{'✅' if ok else '❌'} test {i}{tag}  {ms:.0f}ms")
        if not ok:
            print(f"   input    {short(t['input'])}\n   expected {short(t['output'])}\n   {detail}")
        passed += ok
    print(f"\n{passed}/{len(prob['tests'])} passed")
    if prob["tests"] and passed == len(prob["tests"]):
        cmd_save(d, only=f.name)
    sys.exit(passed != len(prob["tests"]))


# ---------- saving + heatmap ----------

def cmd_save(d, only=None):
    d, today = Path(d), date.today()
    prob = json.loads((d / "problem.json").read_text())
    for f in sorted(d.glob("solution.*")):
        lang = LANG.get(f.suffix[1:])
        if not lang or (only and f.name != only) or f.read_text() == prob.get("starters", {}).get(f.name):
            continue  # unknown language, or still the untouched starter
        dest = ROOT / "solutions" / lang / f"{today:%Y-%m}" / f"{today:%d}" / f"{prob['slug']}{f.suffix}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        print(f"💾 saved {dest.relative_to(ROOT)}")


def cmd_import(src):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(src).expanduser()
        if not repo.exists():
            subprocess.run(["git", "clone", "-q", src, tmp], check=True)
            repo = Path(tmp)
        added = 0
        for f in sorted(repo.glob("[0-9]*-*/*")):  # LeetHub layout: 0001-two-sum/0001-two-sum.java
            lang = LANG.get(f.suffix[1:])
            if not lang:
                continue
            log = subprocess.run(["git", "-C", repo, "log", "--diff-filter=A", "--format=%as", "--", f.relative_to(repo)],
                                 capture_output=True, text=True).stdout.split()
            day = date.fromisoformat(log[-1]) if log else date.today()  # first commit of the file
            dest = ROOT / "solutions" / lang / f"{day:%Y-%m}" / f"{day:%d}" / (re.sub(r"^\d+-", "", f.parent.name) + f.suffix)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                added += 1
        print(f"Imported {added} solutions into solutions/")


def draw(title, counts, weeks=52):
    shades, tty = [236, 22, 28, 34, 46], sys.stdout.isatty()
    start = date.today() - timedelta(days=date.today().weekday() + 7 * (weeks - 1))  # a Monday
    print(f"\n{title}: {sum(counts.values())} in the last {weeks} weeks")
    for wd in range(7):
        row = ""
        for w in range(weeks):
            day = start + timedelta(weeks=w, days=wd)
            c = counts.get(day, 0)
            lvl = 0 if c == 0 else 1 if c < 2 else 2 if c < 4 else 3 if c < 8 else 4
            row += " " if day > date.today() else f"\x1b[38;5;{shades[lvl]}m■\x1b[0m" if tty else " ░▒▓█"[lvl]
        print("  " + "MTWTFSS"[wd] + " " + row)


def cmd_heatmap():
    c = cfg()
    user = c["leetcode_username"] or ask("LeetCode username (saved to dsa.json): ")
    if user and not c["leetcode_username"]:
        (ROOT / "dsa.json").write_text(json.dumps({**c, "leetcode_username": user}, indent=1))
    if user:
        u = leetcode("query q($u:String!){matchedUser(username:$u){userCalendar{streak totalActiveDays "
                     "submissionCalendar}}}", u=user)["matchedUser"]
        if not u:
            print(f"LeetCode user {user!r} not found")
        else:
            cal = json.loads(u["userCalendar"]["submissionCalendar"])
            lc_counts = {datetime.fromtimestamp(int(ts), timezone.utc).date(): n for ts, n in cal.items()}
            draw(f"LeetCode @{user} (submissions, streak {u['userCalendar']['streak']})", lc_counts)
    local = {}
    for f in (ROOT / "solutions").glob("*/*/*/*"):  # <lang>/<YYYY-MM>/<DD>/<file>
        day = datetime.strptime(f"{f.parent.parent.name}-{f.parent.name}", "%Y-%m-%d").date()
        local[day] = local.get(day, 0) + 1
    draw("Local saved solutions", local)


# ---------- AI (LM Studio, OpenAI-compatible) ----------

def llm(prompt, schema):
    base = os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1")
    try:
        model = os.environ.get("LMSTUDIO_MODEL") or http_json(base + "/models", timeout=5)["data"][0]["id"]
    except (OSError, IndexError) as e:
        sys.exit(f"Can't use LM Studio at {base} ({e}). In LM Studio: load a model, Developer tab -> Start Server.")
    print(f"Asking {model} (local models can take a minute)…")
    body = {"model": model, "temperature": 0.2,
            "messages": [{"role": "system", "content": "You are an expert competitive programmer. Reply with JSON only."},
                         {"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}}
    txt = http_json(base + "/chat/completions", body, timeout=900)["choices"][0]["message"]["content"]
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    return json.loads(txt[txt.find("{"):txt.rfind("}") + 1])


def test_spec(prob):
    if prob["mode"] == "gfg":
        return ("Each input is the exact stdin text for ONE test case as read by this driver code (leave out the "
                f"leading test-count line):\n{prob['driver']}"), {"type": "string"}
    if prob["meta"].get("systemdesign"):
        return 'Each input is [operations, arguments], like LeetCode design problems: [["Cls","op"],[[ctor args],[op args]]].', {"type": "array"}
    return ("Each input is a JSON array of the positional arguments in order, LeetCode serialization "
            "(binary trees as level-order arrays with null, linked lists as arrays)."), {"type": "array"}


def valid(t, v):
    """Does JSON value v fit LeetCode type t? Small models emit junk; one bad literal breaks the Java build."""
    if t == "TreeNode":
        return isinstance(v, list) and all(x is None or type(x) is int for x in v)
    if t == "ListNode":
        return isinstance(v, list) and all(type(x) is int for x in v)
    m = re.fullmatch(r"(.+)\[\]|list<(.+)>", t, re.I)
    if m:
        return isinstance(v, list) and all(valid(m.group(1) or m.group(2), x) for x in v)
    return {"integer": type(v) is int, "long": type(v) is int, "boolean": type(v) is bool, "string": type(v) is str,
            "double": type(v) in (int, float), "character": type(v) is str and len(v) == 1}.get(t, True)


def add_ai_tests(d, prob, reference, inputs):
    ref = d / ".reference.py"
    ref.write_text("from lc import *\n\n" + reference)
    seen, added = [t["input"] for t in prob["tests"]], 0
    for inp in inputs:
        params = prob.get("meta", {}).get("params")
        if inp in seen:
            continue
        if prob["mode"] == "lc" and not prob["meta"].get("systemdesign") and not (
                isinstance(inp, list) and len(inp) == len(params) and all(map(valid, [p["type"] for p in params], inp))):
            print(f"  skipped malformed input {short(inp, 80)}")
            continue
        try:
            prob["tests"].append({"input": inp, "output": timed(prob, ref, inp), "source": "ai"})
            seen.append(inp)
            added += 1
        except Exception as e:
            print(f"  skipped an input the reference solution choked on: {short(inp, 80)} ({e!r:.80})")
    (d / "problem.json").write_text(json.dumps(prob, indent=1))
    print(f"Added {added} AI tests (expected outputs computed by the AI reference in {ref.name}; "
          "if a test looks wrong, delete it from problem.json)")


REF_ASK = ('"reference": a complete, correct, simple Python 3 solution (brute force is fine) using the same class '
           "and method names as the starter code; no input reading, standard library only.\n"
           '"inputs": {n} small, diverse test inputs: edge cases (empty/single element, min/max values, duplicates, '
           "negatives, skewed trees...) plus normal cases. {spec}")


def cmd_gen(d, n=8):
    d = Path(d)
    prob = json.loads((d / "problem.json").read_text())
    spec, item = test_spec(prob)
    out = llm(f"Problem:\n{(d / 'README.md').read_text()}\n\nStarter code:\n{(d / 'solution.py').read_text()}\n\n"
              "Return JSON with:\n" + REF_ASK.format(n=n, spec=spec),
              {"type": "object", "required": ["reference", "inputs"],
               "properties": {"reference": {"type": "string"}, "inputs": {"type": "array", "items": item}}})
    add_ai_tests(d, prob, out["reference"], out["inputs"])


def cmd_new(title=None):
    title = (title or ask("Problem to practice (e.g. remove leaves from a binary tree): ")).strip()
    types = ("integer, long, double, boolean, string, character, integer[], integer[][], string[], character[][], "
             "list<integer>, list<list<integer>>, list<string>, TreeNode, ListNode, ListNode[]")
    out = llm(f"Design a LeetCode-style coding problem: {title!r}. Return JSON with:\n"
              '"title"; "difficulty" (Easy/Medium/Hard); "description": markdown statement with 2 examples and constraints;\n'
              f'"function": {{"name": camelCase method name, "params": [{{"name","type"}}], "return_type"}}, types from: {types};\n'
              + REF_ASK.format(n=10, spec=test_spec({"mode": "lc", "meta": {}})[0]),
              {"type": "object", "required": ["title", "difficulty", "description", "function", "reference", "inputs"],
               "properties": {"title": {"type": "string"}, "difficulty": {"type": "string"},
                              "description": {"type": "string"}, "reference": {"type": "string"},
                              "inputs": {"type": "array", "items": {"type": "array"}},
                              "function": {"type": "object", "required": ["name", "params", "return_type"], "properties": {
                                  "name": {"type": "string"}, "return_type": {"type": "string"},
                                  "params": {"type": "array", "items": {"type": "object", "required": ["name", "type"],
                                             "properties": {"name": {"type": "string"}, "type": {"type": "string"}}}}}}}})
    f = out["function"]
    slug = "ai-" + re.sub(r"[^a-z0-9]+", "-", out["title"].lower()).strip("-")
    sig = ", ".join(p["name"] for p in f["params"])
    types_note = ", ".join(f"{p['name']}: {p['type']}" for p in f["params"]) + f" -> {f['return_type']}"
    starter = f"class Solution:\n    def {f['name']}(self, {sig}):\n        # {types_note}\n        pass\n"
    jparams = ", ".join(f"{jtype(p['type'])} {p['name']}" for p in f["params"])
    jstarter = f"class Solution {{\n    public {jtype(f['return_type'])} {f['name']}({jparams}) {{\n        \n    }}\n}}\n"
    prob = {"mode": "lc", "slug": slug, "tests": [],
            "meta": {"name": f["name"], "params": f["params"], "return": {"type": f["return_type"]}}}
    d = write_problem(prob, f"# {out['title']} ({out['difficulty']}, AI-generated)\n\n{out['description']}\n",
                      {"python3": starter, "java": jstarter})
    add_ai_tests(d, json.loads((d / "problem.json").read_text()), out["reference"], out["inputs"])
    open_in_zed(d)


def cmd_setup_zed():
    from zed_dsa import zed_config
    zed_config.install()


def cmd_mcp():
    from zed_dsa import mcp
    mcp.serve()


def main():
    global ROOT
    cmds = {"fetch": cmd_fetch, "new": cmd_new, "gen": cmd_gen, "test": cmd_test, "save": cmd_save, "import": cmd_import,
            "heatmap": cmd_heatmap, "setup-zed": cmd_setup_zed, "mcp": cmd_mcp}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    a = sys.argv[2:]
    if sys.argv[1] not in ("setup-zed", "mcp"):
        ROOT = find_root(a[0] if sys.argv[1] in ("test", "gen", "save") and a else ".")
    if sys.argv[1] in ("fetch", "new"):
        a = [" ".join(a)] if a else []
    if sys.argv[1] == "gen" and len(a) > 1:
        a[1] = int(a[1])
    cmds[sys.argv[1]](*a)


if __name__ == "__main__":
    main()
