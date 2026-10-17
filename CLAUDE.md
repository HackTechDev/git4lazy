# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

git4lazy is an interactive `git status` TUI written in Python with `curses`, standard library only. All of the code is in `git4lazy.py`. Everything the user sees is in **French**: UI strings, code comments, docs and commit messages. Keep that language when you add anything.

## Running

```sh
./git4lazy.py          # from anywhere inside a git repo (it chdirs to the repo root)
```

The project has no build step, linter or test suite. To check syntax quickly, run `python3 -c "import ast; ast.parse(open('git4lazy.py').read())"`. That avoids creating `__pycache__`, which is not gitignored.

## Testing changes

So far, changes have been checked by driving the real app against throwaway repos in the scratchpad, never against this repo:

- **pty driving**: fork the app under `pty`, set the window size with `TIOCSWINSZ`, write keystrokes, then inspect the output and the resulting git state (`git status --short`, `git log`).
  - curses enables keypad mode, so arrow keys must be sent as `\x1bOA`/`\x1bOB`/`\x1bOC`/`\x1bOD` (not `\x1b[C`). End is `\x1bOF`.
  - curses redraws only the characters that changed, so grepping the output for a later screen state is unreliable. Check the resulting git state instead.
  - Space does not move the cursor. Tab jumps to the next *non-empty* section and wraps around. Account for both when scripting key sequences.
- **Logic tests without a terminal**: load the module with `importlib.util.spec_from_file_location`. Call methods on a `types.SimpleNamespace` stand-in, or on a fake screen object, after monkeypatching `curses.doupdate` and `curses.color_pair`. Run Python with `-B`: `-I` ignores `PYTHONDONTWRITEBYTECODE` and leaves a `__pycache__` in the repo.

## Architecture

The file has two layers, separated by `# --- Git ---` / `# --- Interface ---` banners.

**Git layer**: plain functions over `git()`, a `subprocess.run` wrapper that uses `errors="surrogateescape"` so non-UTF-8 paths round-trip. Use `printable()` before displaying any path or message.
- `main()` sets `GIT_LITERAL_PATHSPECS=1` for the whole process, so filenames like `*` or `:x` are literal. It also `chdir`s to the repo root, because porcelain paths are relative to the root.
- `read_status()` parses `git status --porcelain=v1 -z --untracked-files=all` into `Entry(section, code, paths)`.
  - A rename or copy consumes an extra NUL field, and `paths = (new, old)`.
  - A file that is both staged and modified (`MM`) yields **two** entries.
  - `Entry` is a frozen dataclass whose identity includes `section`. Selections (`App.selected`) are sets of `Entry`.
- `git_unstage` uses `git restore --staged`. It falls back to `git rm --cached` only when there is no `HEAD` yet.
- `git_commit` commits **only the selected staged files**, through a temporary index (`GIT_INDEX_FILE` = `.git/index.git4lazy`).
  - The temporary index is seeded from `HEAD`, then the selected entries are copied in with `ls-files --stage` piped to `update-index --index-info`. Paths absent from the real index are force-removed.
  - The real index keeps the files that were not selected.
  - Do not replace this with `git commit -- paths`, which would take working-tree content.
- `read_unpushed()` lists `@{upstream}..HEAD`. With no upstream, it lists `HEAD --not --remotes`. It never touches the network.
- `git_rewrite(shas, newest, oldest, message, label)` backs both squash and reword (reword is the case `newest == oldest`).
  - It recreates commits with `commit-tree`, reusing the original trees (`recommit`) and keeping authors and dates. A squash keeps the oldest commit's author.
  - It then moves `HEAD` with `update-ref -m "git4lazy: <label>"`. Trees never change, so there are no conflicts and the index and working tree are untouched.
  - Merges are refused up front (`has_merges`).
- `git_undo_last_commit` is `git reset HEAD~`. For a root commit it deletes the ref and runs `rm -r --cached`.

**Interface layer**:
- `App` has two views, `FILES` and `COMMITS`, switched with → and ←. Each has its own cursor and scroll offset (`self.top[view]`).
  - `run()` handles the global keys (`q`, F5), then delegates to `handle_files_key` or `handle_commits_key`.
  - `refresh()` re-reads status, branch and unpushed commits after every action.
- `CommitDialog` (title and message fields, Ctrl+V validates, Esc cancels) and `DiffView` (full screen, scrollable, lines wrapped) are modal loops. `CommitDialog` takes a `draw_background` callback so it can draw over the current view. `CommitDialog` is reused, prefilled, for squash and reword.
- Actions on files require an explicit selection; there is no fallback to the file under the cursor. They also require the cursor to be in the right section. `App.targets(*sections)` enforces both and posts the error message.
- In the commits view, `commit_action_error(key)` is the single source of truth for whether `s`, `e` or `r` is allowed. It decides both the key's behaviour and the contextual help: `HELP[COMMITS]` has an `{actions}` placeholder filled from `COMMIT_ACTIONS`.
- The diff key (`d`/`D`) is the exception to the selection rule: it acts on the item under the cursor.
- Destructive or history-changing actions ask for confirmation with `App.confirm()`. Only `o`/`y` accepts.

## Product decisions (do not revisit without being asked)

- **No `git push` or `git fetch` inside the tool.** The user pushes manually to avoid pushing by mistake.
- **No amend.** Committing the forgotten files and then squashing that commit with the previous one does the same job.

Both decisions are recorded under « Écarté volontairement » in `IMPROVEMENTS.md`.

## Docs to keep in sync

When a key or behaviour changes, update all of these:
- the module docstring of `git4lazy.py`;
- the `HELP` strings;
- `README.md`, the key tables per page;
- `TUTORIAL.md`, the step-by-step walkthrough;
- `IMPROVEMENTS.md`: remove ideas once they are implemented or rejected;
- `TODO.md`: accepted tasks, with their priority.

Only commit or push when the user asks.
