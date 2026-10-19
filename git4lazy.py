#!/usr/bin/env python3
"""git4lazy — un « git status » interactif en mode terminal.

Touches :
  ↑/↓ ou k/j   déplacer le curseur        Tab   changer de section
  Espace       (dé)sélectionner           F5    rafraîchir
  *            (dé)sélectionner toute la section du curseur
  d            diff du fichier sous le curseur (ou du commit, dans la liste des commits)
  a            git add (Changes not staged for commit, Untracked files)
  r            annuler les modifications (Changes not staged for commit)
  u            retirer de l'index (Changes to be committed)
  c            commit (Changes to be committed), après confirmation
  →            liste des commits non poussés (← pour revenir aux fichiers)
               Espace pour sélectionner, s pour squasher les commits choisis,
               e pour modifier le message du commit choisi,
               r pour annuler le dernier commit (git reset HEAD~)
  q            quitter

a, r, u et c n'agissent que sur les fichiers sélectionnés de la section.
La ligne d'aide n'affiche que les actions possibles dans la section du curseur.
"""

import curses
import os
import subprocess
import sys
import termios
from dataclasses import dataclass

STAGED, UNSTAGED, UNTRACKED = 0, 1, 2
SECTION_TITLES = {
    STAGED: "Changes to be committed",
    UNSTAGED: "Changes not staged for commit",
    UNTRACKED: "Untracked files",
}
STATUS_LABELS = {
    "M": "modified", "A": "new file", "D": "deleted", "R": "renamed",
    "C": "copied", "T": "typechange", "U": "unmerged",
}
BACKSPACE = (curses.KEY_BACKSPACE, "\x7f", "\b")
ENTER = (curses.KEY_ENTER, "\n", "\r")
ESCAPE, CTRL_S = "\x1b", "\x13"
FILES, COMMITS = "files", "commits"
# Touche, libellé de l'aide et sections où le curseur doit se trouver.
FILE_ACTIONS = (("a", "a add", (UNSTAGED, UNTRACKED)), ("r", "r restore", (UNSTAGED,)),
                ("u", "u unstage", (STAGED,)), ("c", "c commit", (STAGED,)))
FILE_ACTION_SECTIONS = {key: sections for key, _, sections in FILE_ACTIONS}
COMMIT_ACTIONS = (("s", "s squash"), ("e", "e modifier le message"), ("r", "r reset"))
HELP = {
    # {actions} : seulement les actions possibles dans la section du curseur.
    FILES: "Espace sélect.  * tout  d diff  {actions}Tab section  → commits  F5 rafraîchir  q quitter",
    # {actions} : seulement les actions que la sélection de commits permet.
    COMMITS: "Espace sélect.  {actions}d diff  ← fichiers  F5 rafraîchir  q quitter",
}


# --- Git ---------------------------------------------------------------------

def git(*args, env=None, input=None):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          errors="surrogateescape", env=env, input=input)


def has_head():
    return git("rev-parse", "--verify", "--quiet", "HEAD").returncode == 0


def printable(text):
    """Remplace les octets non UTF-8 (gardés tels quels pour git) avant affichage."""
    return text.encode("utf-8", "surrogateescape").decode("utf-8", "replace")


@dataclass(frozen=True)
class Entry:
    section: int
    code: str
    paths: tuple  # (chemin,) ou (nouveau, ancien) pour un renommage ou une copie

    @property
    def label(self):
        shown = [printable(p) for p in self.paths]
        if self.section == UNTRACKED:
            return shown[0]
        target = f"{shown[1]} -> {shown[0]}" if len(shown) == 2 else shown[0]
        return f"{STATUS_LABELS.get(self.code, self.code) + ':':<12}{target}"


def read_status():
    out = git("status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    fields = iter(out.split("\0"))
    staged, unstaged, untracked = [], [], []
    for field in fields:
        if not field:
            continue
        x, y, path = field[0], field[1], field[3:]
        # En -z, le chemin d'origine d'un renommage/d'une copie suit dans un champ à part.
        paths = (path, next(fields)) if {x, y} & {"R", "C"} else (path,)
        if x == "?":
            untracked.append(Entry(UNTRACKED, x, paths))
            continue
        if x not in " !":
            staged.append(Entry(STAGED, x, paths))
        # Un fichier indexé puis modifié à nouveau apparaît dans les deux sections ;
        # côté copie de travail seul le nouveau chemin d'un renommage compte.
        if y != " ":
            unstaged.append(Entry(UNSTAGED, y, paths[:1]))
    return staged, unstaged, untracked


def read_unpushed():
    """Renvoie (branche distante comparée, commits locaux absents du distant).

    La comparaison se fait avec l'état du distant connu localement (dernier
    fetch). Sans branche distante suivie, on exclut les commits présents sur
    n'importe quelle branche distante.
    """
    if not has_head():
        return None, []
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream.returncode == 0:
        ref, revisions = upstream.stdout.strip(), ["@{upstream}..HEAD"]
    else:
        ref, revisions = None, ["HEAD", "--not", "--remotes"]
    out = git("log", "--format=%H%x1f%h%x1f%ar%x1f%an%x1f%s", *revisions).stdout
    return ref, [tuple(line.split("\x1f", 4)) for line in out.splitlines()]


def message_of(sha):
    return git("log", "-1", "--format=%B", sha).stdout.strip()


def recommit(source, parent, message, author=None):
    """Crée au-dessus de parent un commit avec l'arbre de source et l'auteur
    de author (par défaut, celui de source)."""
    name, email, date = git("log", "-1", "--format=%an%x00%ae%x00%aD",
                            author or source).stdout.strip().split("\0")
    env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": date}
    parents = ["-p", parent] if parent else []
    return git("commit-tree", source + "^{tree}", *parents, env=env, input=message + "\n")


def has_merges(shas):
    return bool(git("rev-list", "--min-parents=2", "--no-walk", *shas).stdout.strip())


def git_rewrite(shas, newest, oldest, message, label):
    """Remplace shas[newest..oldest] (du plus récent au plus ancien) par un seul
    commit portant message : un squash, ou un changement de message si
    newest == oldest.

    Les arbres ne changent pas : le nouveau commit prend l'arbre du plus récent
    commit remplacé et les commits suivants sont recréés à l'identique par-dessus.
    Aucun conflit n'est donc possible, et l'index comme la copie de travail
    restent intacts. L'ancienne version reste accessible par git reflog.
    """
    parent = git("rev-parse", "--verify", "--quiet", shas[oldest] + "^").stdout.strip()
    # Comme git rebase, un squash garde l'auteur du plus ancien commit.
    result = recommit(shas[newest], parent, message, author=shas[oldest])
    for sha in reversed(shas[:newest]):
        if result.returncode:
            break
        result = recommit(sha, result.stdout.strip(), message_of(sha))
    if result.returncode:
        return result
    return git("update-ref", "-m", f"git4lazy: {label}", "HEAD", result.stdout.strip(), shas[0])


def git_undo_last_commit():
    # Équivaut à git reset HEAD~ : le commit disparaît et ses modifications
    # reviennent dans la copie de travail, non indexées.
    if git("rev-parse", "--verify", "--quiet", "HEAD^").returncode == 0:
        return git("reset", "--quiet", "HEAD~")
    # Premier commit du dépôt : pas de parent, la branche redevient vide.
    result = git("update-ref", "-d", "HEAD")
    return result if result.returncode else git("rm", "-r", "--cached", "--quiet", ".")


def file_diff(entry):
    """Renvoie (description, texte du diff) d'un fichier selon sa section."""
    options = ("--no-color", "--no-ext-diff")
    if entry.section == STAGED:
        return "indexé", git("diff", "--cached", *options, "--", *entry.paths).stdout
    if entry.section == UNSTAGED:
        return "non indexé", git("diff", *options, "--", *entry.paths).stdout
    # Fichier non suivi : diff contre un fichier vide, soit tout son contenu en ajout.
    return "non suivi", git("diff", "--no-index", *options, "--", os.devnull, entry.paths[0]).stdout


def commit_diff(sha):
    return git("show", "--stat", "--patch", "--no-color", "--no-ext-diff", sha).stdout


def paths_of(entries):
    return [p for e in entries for p in e.paths]


def git_add(entries):
    return git("add", "--", *paths_of(entries))


def git_unstage(entries):
    # restore --staged annule l'indexation sans rien supprimer du dépôt. Avant le
    # premier commit il n'y a pas de HEAD : tout fichier indexé est alors nouveau
    # et rm --cached fait exactement la même chose.
    if has_head():
        return git("restore", "--staged", "--", *paths_of(entries))
    return git("rm", "--cached", "--quiet", "--", *paths_of(entries))


def git_restore(entries):
    # Remet la version de l'index dans la copie de travail : les modifications
    # non indexées sont perdues, celles déjà indexées sont conservées.
    return git("restore", "--", *paths_of(entries))


def git_commit(entries, title, body):
    # Le commit ne doit contenir que les fichiers sélectionnés, dans leur version
    # indexée. Il est construit dans un index temporaire partant de HEAD, où l'on
    # recopie leurs entrées ; les autres fichiers restent indexés dans l'index réel.
    paths = paths_of(entries)
    index = os.path.abspath(git("rev-parse", "--git-path", "index.git4lazy").stdout.strip())
    env = {**os.environ, "GIT_INDEX_FILE": index}
    args = ["commit", "-m", title] + (["-m", body] if body else [])
    try:
        if os.path.exists(index):
            os.remove(index)
        if has_head():
            git("read-tree", "HEAD", env=env)
        staged = git("ls-files", "--stage", "-z", "--", *paths).stdout
        git("update-index", "-z", "--index-info", env=env, input=staged)
        # Absent de l'index réel : suppression indexée (ou ancien nom d'un renommage).
        present = {f.split("\t", 1)[1] for f in staged.split("\0") if f}
        removed = [p for p in paths if p not in present]
        if removed:
            git("update-index", "--force-remove", "--", *removed, env=env)
        return git(*args, env=env)
    finally:
        if os.path.exists(index):
            os.remove(index)


# --- Interface ---------------------------------------------------------------

def put(win, y, x, text, attr=0):
    """Écrit en tronquant au bord de la fenêtre (curses lève une erreur sinon)."""
    h, w = win.getmaxyx()
    if 0 <= y < h and x < w - 1:
        try:
            win.addnstr(y, x, text, w - x - 1, attr)
        except curses.error:
            pass


def set_cursor_visible(visible):
    try:
        curses.curs_set(visible)
    except curses.error:
        pass


class TextField:
    """Champ de saisie éditable, sur une ligne ou plusieurs."""

    def __init__(self, multiline):
        self.multiline = multiline
        self.lines, self.row, self.col, self.top = [""], 0, 0, 0

    def set(self, text):
        self.lines = text.split("\n")
        self.row, self.col = len(self.lines) - 1, len(self.lines[-1])

    @property
    def text(self):
        return "\n".join(self.lines).strip()

    def handle(self, key):
        """Applique une touche ; renvoie False si elle n'est pas gérée ici."""
        lines, row, col = self.lines, self.row, self.col
        line = lines[row]
        if isinstance(key, str) and key.isprintable():
            lines[row] = line[:col] + key + line[col:]
            self.col += 1
        elif key in ENTER and self.multiline:
            lines[row:row + 1] = [line[:col], line[col:]]
            self.row, self.col = row + 1, 0
        elif key in BACKSPACE:
            if col:
                lines[row] = line[:col - 1] + line[col:]
                self.col -= 1
            elif row:
                self.row, self.col = row - 1, len(lines[row - 1])
                lines[row - 1] += lines.pop(row)
        elif key == curses.KEY_DC:
            if col < len(line):
                lines[row] = line[:col] + line[col + 1:]
            elif row < len(lines) - 1:
                lines[row] += lines.pop(row + 1)
        elif key == curses.KEY_LEFT:
            if col:
                self.col -= 1
            elif row:
                self.row, self.col = row - 1, len(lines[row - 1])
        elif key == curses.KEY_RIGHT:
            if col < len(line):
                self.col += 1
            elif row < len(lines) - 1:
                self.row, self.col = row + 1, 0
        elif key == curses.KEY_UP and row:
            self.row, self.col = row - 1, min(col, len(lines[row - 1]))
        elif key == curses.KEY_DOWN and row < len(lines) - 1:
            self.row, self.col = row + 1, min(col, len(lines[row + 1]))
        elif key == curses.KEY_HOME:
            self.col = 0
        elif key == curses.KEY_END:
            self.col = len(line)
        else:
            return False
        return True

    def draw(self, win, y, x, width, height, attr):
        """Dessine le champ et renvoie la position du curseur à l'écran."""
        if self.row < self.top:
            self.top = self.row
        elif self.row >= self.top + height:
            self.top = self.row - height + 1
        offset = max(0, self.col - width + 1)
        for i in range(height):
            n = self.top + i
            text = self.lines[n][offset:offset + width] if n < len(self.lines) else ""
            put(win, y + i, x, text.ljust(width), attr)
        return y + self.row - self.top, x + self.col - offset


class CommitDialog:
    """Fenêtre de saisie du titre et du message de commit."""

    def __init__(self, scr, draw_background, heading="Commit", title="", body=""):
        self.scr = scr
        self.draw_background = draw_background
        self.heading = heading
        self.fields = [TextField(multiline=False), TextField(multiline=True)]
        self.fields[0].set(title)
        self.fields[1].set(body)
        self.active = 0
        self.error = ""

    def run(self):
        """Renvoie (titre, message), ou None si la saisie est annulée."""
        set_cursor_visible(1)
        try:
            while True:
                self.draw()
                key = self.scr.get_wch()
                title, body = self.fields
                if key == ESCAPE:
                    return None
                if key == CTRL_S:
                    if title.text:
                        return title.text, body.text
                    self.error, self.active = "Le titre est obligatoire.", 0
                elif key in ("\t", curses.KEY_BTAB):
                    self.active ^= 1
                elif not self.fields[self.active].handle(key) and key in ENTER:
                    self.active = 1  # Entrée dans le titre : passer au message
        finally:
            set_cursor_visible(0)

    def draw(self):
        self.draw_background()
        h, w = self.scr.getmaxyx()
        height, width = max(min(h - 2, 18), 10), max(min(w - 4, 76), 30)
        win = curses.newwin(height, width, max((h - height) // 2, 0), max((w - width) // 2, 0))
        win.keypad(True)
        win.box()
        put(win, 0, 2, f" {self.heading} ", curses.A_BOLD)
        inner = width - 4
        labels = ("Titre :", "Message :")
        tops = (2, 5)
        heights = (1, height - 9)
        cursor = None
        for i, field in enumerate(self.fields):
            active = i == self.active
            put(win, tops[i] - 1, 2, labels[i], curses.A_BOLD if active else curses.A_DIM)
            pos = field.draw(win, tops[i], 2, inner, heights[i],
                             curses.A_REVERSE if active else curses.A_UNDERLINE)
            if active:
                cursor = pos
        put(win, height - 3, 2, self.error, curses.color_pair(2) | curses.A_BOLD)
        put(win, height - 2, 2, "Ctrl+S valider · Tab changer de champ · Échap annuler", curses.A_DIM)
        try:
            win.move(*cursor)
        except curses.error:
            pass
        win.noutrefresh()
        curses.doupdate()


def diff_attr(line):
    if line.startswith(("diff --git", "index ", "+++ ", "--- ")):
        return curses.A_BOLD
    if line.startswith("+"):
        return curses.color_pair(1)
    if line.startswith("-"):
        return curses.color_pair(2)
    if line.startswith("@@"):
        return curses.color_pair(4)
    if line.startswith("commit "):
        return curses.color_pair(3)
    return 0


class DiffView:
    """Affichage plein écran d'un diff, défilant ; les lignes longues sont repliées."""

    def __init__(self, scr, title, text):
        self.scr = scr
        self.title = title
        self.lines = [printable(l).expandtabs(4) for l in text.splitlines()] or ["(aucune différence)"]
        self.top = 0

    def rows(self, width):
        rows = []
        for line in self.lines:
            attr = diff_attr(line)
            rows += [(line[i:i + width], attr) for i in range(0, len(line), width)] or [("", 0)]
        return rows

    def run(self):
        while True:
            h, w = self.scr.getmaxyx()
            rows, page = self.rows(max(w - 1, 1)), max(h - 2, 1)
            self.top = max(0, min(self.top, len(rows) - page))
            self.draw(rows, page)
            key = self.scr.get_wch()
            if key in (ESCAPE, "q", "Q", "d", "D", curses.KEY_LEFT):
                return
            elif key in (curses.KEY_UP, "k"):
                self.top -= 1
            elif key in (curses.KEY_DOWN, "j"):
                self.top += 1
            elif key == curses.KEY_PPAGE:
                self.top -= page
            elif key in (curses.KEY_NPAGE, " "):
                self.top += page
            elif key in (curses.KEY_HOME, "g"):
                self.top = 0
            elif key in (curses.KEY_END, "G"):
                self.top = len(rows)

    def draw(self, rows, page):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        put(scr, 0, 0, self.title.ljust(w), curses.A_REVERSE | curses.A_BOLD)
        for y, (text, attr) in enumerate(rows[self.top:self.top + page], start=1):
            put(scr, y, 0, text, attr)
        last = min(self.top + page, len(rows))
        put(scr, h - 1, 0, f"↑/↓ défiler  PgUp/PgDn page  Échap retour   "
                           f"lignes {self.top + 1}-{last} sur {len(rows)}", curses.A_DIM)
        scr.noutrefresh()
        curses.doupdate()


class App:
    def __init__(self, scr):
        self.scr = scr
        self.selected = set()
        self.selected_commits = set()
        self.view = FILES
        self.cursor = self.commit_cursor = 0
        self.top = {FILES: 0, COMMITS: 0}
        self.message, self.message_is_error = "", False
        set_cursor_visible(0)
        if curses.has_colors():
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
        self.colors = {STAGED: curses.color_pair(1), UNSTAGED: curses.color_pair(2),
                       UNTRACKED: curses.color_pair(2)}
        self.refresh()

    # État

    def refresh(self):
        self.items = [e for entries in read_status() for e in entries]
        self.selected &= set(self.items)
        self.cursor = min(self.cursor, max(len(self.items) - 1, 0))
        self.branch = git("branch", "--show-current").stdout.strip() or "(HEAD détachée)"
        self.upstream, self.commits = read_unpushed()
        self.selected_commits &= {c[0] for c in self.commits}
        self.commit_cursor = min(self.commit_cursor, max(len(self.commits) - 1, 0))

    @property
    def current(self):
        return self.items[self.cursor] if self.items else None

    def notify(self, text, error=False):
        self.message, self.message_is_error = text, error

    def report(self, result, success):
        if result.returncode:
            lines = [l for l in (result.stderr or result.stdout).splitlines() if l.strip()]
            self.notify(lines[-1] if lines else "La commande git a échoué.", error=True)
        else:
            self.notify(success)

    def confirm(self, question):
        self.notify(f"{question} (o/N)", error=True)
        self.draw()
        curses.doupdate()
        return self.scr.get_wch() in ("o", "O", "y", "Y")

    def in_section(self, *sections):
        """Vérifie que le curseur est dans une des sections attendues par l'action."""
        if self.current is None or self.current.section not in sections:
            names = " ou ".join(f"« {SECTION_TITLES[s]} »" for s in sections)
            self.notify(f"Placez le curseur dans {names}.", error=True)
            return False
        return True

    def targets(self, *sections):
        """Fichiers sélectionnés visés par une action ; liste vide s'il n'y en a pas."""
        if not self.in_section(*sections):
            return []
        targets = [e for e in self.items if e.section in sections and e in self.selected]
        if not targets:
            self.notify("Aucun fichier sélectionné : utilisez Espace pour en choisir.", error=True)
        return targets

    # Actions

    def act(self, sections, action, done, question=None):
        targets = self.targets(*sections)
        if not targets:
            return
        if question and not self.confirm(question.format(n=len(targets))):
            self.notify("Annulé.")
            return
        result = action(targets)
        self.refresh()
        self.report(result, f"{len(targets)} fichier(s) {done}.")

    def commit(self):
        targets = self.targets(*FILE_ACTION_SECTIONS["c"])
        if not targets:
            return
        answer = ("", "")
        while True:
            answer = CommitDialog(self.scr, self.draw, "Commit", *answer).run()
            if answer is None:
                self.notify("Commit annulé.")
                return
            if self.confirm(f"Commiter {len(targets)} fichier(s) ?"):
                break
            # Non : retour à la fenêtre, titre et message conservés.
        result = git_commit(targets, *answer)
        self.refresh()
        self.report(result, result.stdout.splitlines()[0] if result.stdout else "Commit effectué.")

    def chosen_commits(self):
        """Positions des commits sélectionnés, du plus récent au plus ancien."""
        return [i for i, c in enumerate(self.commits) if c[0] in self.selected_commits]

    def commit_action_error(self, key):
        """Raison pour laquelle l'action s, e ou r est impossible avec la sélection
        actuelle, ou None si elle est possible."""
        chosen = self.chosen_commits()
        if key == "s":
            if len(chosen) < 2:
                return "Sélectionnez au moins deux commits avec Espace."
            if chosen[-1] - chosen[0] + 1 != len(chosen):
                return "Les commits sélectionnés doivent se suivre."
        elif key == "e" and len(chosen) != 1:
            return "Sélectionnez un seul commit avec Espace pour modifier son message."
        elif key == "r" and chosen != [0]:
            return "Sélectionnez uniquement le dernier commit (en haut de la liste) avec Espace."
        return None

    def check_commit_action(self, key):
        error = self.commit_action_error(key)
        if error:
            self.notify(error, error=True)
        return error is None

    def squash(self):
        if not self.check_commit_action("s"):
            return
        shas = [c[0] for c in self.commits]
        chosen = self.chosen_commits()
        newest, oldest = chosen[0], chosen[-1]
        # Comme git rebase : titre du plus ancien, puis le reste des messages dans l'ordre.
        messages = [message_of(sha) for sha in reversed(shas[newest:oldest + 1])]
        title, _, first_body = messages[0].partition("\n")
        body = "\n\n".join(m for m in [first_body.strip(), *messages[1:]] if m)
        self.rewrite(shas, newest, oldest, "squash", "Squash", title, body,
                     f"{oldest - newest + 1} commits fusionnés en un seul.")

    def reword(self):
        if not self.check_commit_action("e"):
            return
        shas = [c[0] for c in self.commits]
        index = self.chosen_commits()[0]
        title, _, body = message_of(shas[index]).partition("\n")
        self.rewrite(shas, index, index, "reword", "Modifier le commit", title,
                     body.strip(), "Message du commit modifié.")

    def undo_last_commit(self):
        if not self.check_commit_action("r"):
            return
        if not self.confirm("Annuler le dernier commit ? Ses modifications resteront dans les fichiers."):
            self.notify("Annulé.")
            return
        result = git_undo_last_commit()
        self.selected_commits.clear()
        self.refresh()
        self.report(result, "Dernier commit annulé : ses modifications ne sont plus indexées.")

    def rewrite(self, shas, newest, oldest, label, heading, title, body, done):
        # Les commits plus récents sont recréés aussi : aucun ne doit être un merge.
        if has_merges(shas[:oldest + 1]):
            self.notify("Impossible : l'historique concerné contient un merge.", error=True)
            return
        answer = CommitDialog(self.scr, self.draw, heading, title, body).run()
        if answer is None:
            self.notify("Annulé.")
            return
        message = answer[0] + (f"\n\n{answer[1]}" if answer[1] else "")
        result = git_rewrite(shas, newest, oldest, message, label)
        self.selected_commits.clear()
        self.commit_cursor = newest
        self.refresh()
        self.report(result, done)

    def show_file_diff(self):
        if self.current is None:
            return
        where, text = file_diff(self.current)
        DiffView(self.scr, f" {printable(self.current.paths[0])} ({where})", text).run()

    def show_commit_diff(self):
        if not self.commits:
            return
        sha, short, _, _, subject = self.commits[self.commit_cursor]
        DiffView(self.scr, f" Commit {short} : {printable(subject)}", commit_diff(sha)).run()

    def jump_to_other_section(self):
        if self.current is None:
            return
        # Premier fichier de la section suivante non vide, en revenant au début si besoin.
        later = [i for i, e in enumerate(self.items) if e.section > self.current.section]
        firsts = later or [i for i, e in enumerate(self.items) if e.section < self.current.section]
        self.cursor = firsts[0] if firsts else self.cursor

    def toggle(self):
        if self.current is None:
            return
        self.selected ^= {self.current}

    def toggle_section(self):
        """Sélectionne toute la section du curseur, ou la désélectionne si elle l'était déjà."""
        if self.current is None:
            return
        section = {e for e in self.items if e.section == self.current.section}
        if section <= self.selected:
            self.selected -= section
        else:
            self.selected |= section

    # Affichage

    def file_rows(self):
        rows = [(f"Sur la branche {self.branch}", curses.A_BOLD, None), ("", 0, None)]
        for section in SECTION_TITLES:
            rows.append((SECTION_TITLES[section] + " :", curses.A_BOLD, None))
            entries = [(i, e) for i, e in enumerate(self.items) if e.section == section]
            if not entries:
                rows.append(("    (aucun fichier)", curses.A_DIM, None))
            for i, e in entries:
                mark = "[x]" if e in self.selected else "[ ]"
                rows.append((f"  {mark} {e.label}", self.colors[section], i))
            rows.append(("", 0, None))
        return rows

    def commit_rows(self):
        target = self.upstream or "aucune branche distante suivie"
        rows = [(f"Commits non poussés de {self.branch} ({target})", curses.A_BOLD, None),
                ("", 0, None)]
        if not self.commits:
            rows.append(("    (aucun commit à pousser)", curses.A_DIM, None))
        for i, (sha, short, date, author, subject) in enumerate(self.commits):
            mark = "[x]" if sha in self.selected_commits else "[ ]"
            rows.append((f"  {mark} {short}  {subject}  ({author}, {date})", curses.color_pair(3), i))
        return rows

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
        if self.view == FILES:
            rows, cursor = self.file_rows(), self.cursor
        else:
            rows, cursor = self.commit_rows(), self.commit_cursor

        body_height = max(h - 2, 1)
        top = self.top[self.view]
        cursor_row = next((n for n, row in enumerate(rows) if row[2] == cursor), 0)
        if cursor_row < top:
            top = cursor_row
        elif cursor_row >= top + body_height:
            top = cursor_row - body_height + 1
        self.top[self.view] = top
        for y, (text, attr, index) in enumerate(rows[top:top + body_height]):
            if index is not None and index == cursor:
                attr |= curses.A_REVERSE
            put(scr, y, 0, text, attr)

        put(scr, h - 2, 0, self.message,
            curses.color_pair(2) | curses.A_BOLD if self.message_is_error else curses.A_BOLD)
        if self.view == FILES:
            section = self.current.section if self.current else None
            actions = "".join(f"{label}  " for _, label, sections in FILE_ACTIONS
                              if section in sections)
        else:
            actions = "".join(f"{label}  " for key, label in COMMIT_ACTIONS
                              if self.commit_action_error(key) is None)
        put(scr, h - 1, 0, HELP[self.view].format(actions=actions), curses.A_DIM)
        scr.noutrefresh()

    def run(self):
        while True:
            self.draw()
            curses.doupdate()
            key = self.scr.get_wch()
            self.notify("")
            if key in ("q", "Q"):
                return
            elif key == curses.KEY_F5:
                self.refresh()
            elif self.view == COMMITS:
                self.handle_commits_key(key)
            else:
                self.handle_files_key(key)

    def handle_commits_key(self, key):
        if key == curses.KEY_LEFT:
            self.view = FILES
        elif key in (curses.KEY_UP, "k"):
            self.commit_cursor = max(self.commit_cursor - 1, 0)
        elif key in (curses.KEY_DOWN, "j"):
            self.commit_cursor = max(min(self.commit_cursor + 1, len(self.commits) - 1), 0)
        elif key == " " and self.commits:
            self.selected_commits ^= {self.commits[self.commit_cursor][0]}
        elif key == "s":
            self.squash()
        elif key == "e":
            self.reword()
        elif key == "r":
            self.undo_last_commit()
        elif key in ("d", "D"):
            self.show_commit_diff()

    def handle_files_key(self, key):
        if key == curses.KEY_RIGHT:
            self.refresh()  # prend en compte un push fait depuis un autre terminal
            self.view = COMMITS
        elif key in (curses.KEY_UP, "k"):
            self.cursor = max(self.cursor - 1, 0)
        elif key in (curses.KEY_DOWN, "j"):
            self.cursor = max(min(self.cursor + 1, len(self.items) - 1), 0)
        elif key == "\t":
            self.jump_to_other_section()
        elif key == " ":
            self.toggle()
        elif key == "*":
            self.toggle_section()
        elif key in ("d", "D"):
            self.show_file_diff()
        elif key == "a":
            self.act(FILE_ACTION_SECTIONS["a"], git_add, "ajouté(s) à l'index")
        elif key == "r":
            self.act(FILE_ACTION_SECTIONS["r"], git_restore, "restauré(s)",
                     "Annuler les modifications de {n} fichier(s) ? Elles seront perdues.")
        elif key == "u":
            self.act(FILE_ACTION_SECTIONS["u"], git_unstage, "retiré(s) de l'index")
        elif key == "c":
            self.commit()


def disable_flow_control():
    """Laisse Ctrl+S arriver à l'outil au lieu de figer le terminal (XOFF).
    curses.endwin() rétablit les réglages d'origine du terminal en quittant."""
    try:
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[0] &= ~termios.IXON
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except (termios.error, OSError, ValueError):
        pass


def start(scr):
    disable_flow_control()
    App(scr).run()


def main():
    toplevel = git("rev-parse", "--show-toplevel")
    if toplevel.returncode:
        print("git4lazy : ce dossier n'est pas dans un dépôt git.", file=sys.stderr)
        return 1
    # Les chemins de --porcelain sont relatifs à la racine du dépôt.
    os.chdir(toplevel.stdout.strip())
    # Un nom de fichier contenant « * » ou commençant par « : » reste un nom littéral.
    os.environ["GIT_LITERAL_PATHSPECS"] = "1"
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
