# zed-dsa

LeetCode / GeeksforGeeks practice inside [Zed](https://zed.dev). Fetch any public problem, solve it in Python or Java,
run the example tests plus AI-generated edge cases from your local LM Studio model, keep dated solutions, and see heatmaps.

## Install

```sh
git clone https://github.com/sravannotshravan/zed-dsa && ./zed-dsa/install.sh
```

This installs the `dsa` command (pipx if you have it, otherwise its own venv linked into `~/.local/bin`). It also adds the
`DSA:` tasks and the ctrl-alt-l layout key to `~/.config/zed/tasks.json` and `keymap.json`. Old files are backed up as
`*.json.bak`, and it's safe to rerun. It needs Python 3.10+, `javac` for Java tests, and `git` for `dsa import`.

**Workspace:** any folder with a `dsa.json`. Problems go to `problems/<slug>/`, solutions to `solutions/<lang>/<YYYY-MM>/<DD>/`.
Commands run from elsewhere use the last workspace you used, or `$DSA_HOME`, or `~/dsa-practice`.

## Use it from Zed tasks

Everything runs from Zed tasks: **alt-shift-t** (`task: spawn`), then pick a `DSA:` task. **alt-t** reruns the last one.

| Task | What it does |
|---|---|
| DSA: fetch LeetCode/GFG problem | Paste a URL, slug, number (`1325`) or title (`rotate image`). GFG: URL or `gfg:<slug>`. Creates `problems/<slug>/` |
| DSA: run tests (current file: .py or .java) | Runs the focused `solution.py` or `solution.java` against `problem.json`. All pass: it's auto-saved |
| DSA: new AI problem (LM Studio) | Describe a problem ("remove leaves from a binary tree"). Your local model writes the statement, signature, tests and a reference solution |
| DSA: add AI test cases (current problem) | More edge-case tests for any problem. Expected outputs come from running the AI's reference solution, not from the model guessing |
| DSA: save solutions (current problem) | Copies every edited `solution.*` to `solutions/<lang>/<YYYY-MM>/<DD>/<slug>.<ext>` |
| DSA: heatmap | Your public LeetCode submission calendar plus local saves |

**Layout:** after a fetch, focus `solution.py` and press **ctrl-alt-l**. The rendered question goes on the left and the code on the right.

**Languages:** `config.json` has `"languages"`. Starters for those (e.g. `solution.java`) are written next to `solution.py`. Python and Java are test-run (Java needs `javac`; `System.out.println` debug output is shown as `[stdout]`).

**LM Studio:** load a model, then Developer tab, then Start Server (default `http://localhost:1234`). Override with `LMSTUDIO_URL` / `LMSTUDIO_MODEL`.

**Old solutions:** `dsa import https://github.com/sravannotshravan/LeetPractice.git` imports a LeetHub repo. It's safe to rerun.

Limits: LeetCode's hidden tests aren't public, so you get the examples plus AI tests. Premium problems, problems that use custom `Node` classes (N-ary, random pointer, graph) and cycle problems (`pos` argument) won't run.

## Zed extension (agent panel)

`extension/` is a Zed extension that registers `dsa mcp` as a context server. Zed's agent can then fetch problems, run
your tests, generate AI tests, save solutions and show the heatmap ("fetch two sum and run my solution.java").

Install it: command palette, **zed: install dev extension**, then pick the `extension/` folder (Zed builds it; needs `rustup`).
The `dsa` CLI must be installed first. To publish it, open a PR adding it to
[zed-industries/extensions](https://github.com/zed-industries/extensions).
