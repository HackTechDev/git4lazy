#!/usr/bin/env python3
"""git4lazy — un « git status » interactif en mode terminal.

Touches :
  ↑/↓ ou k/j   déplacer le curseur        Tab   changer de section
  Espace       (dé)sélectionner           F5    rafraîchir
  a            git add (Changes not staged for commit, Untracked files)
  r            annuler les modifications (Changes not staged for commit)
  u            retirer de l'index (Changes to be committed)
  c            commit (Changes to be committed)
  q            quitter

a, r, u et c n'agissent que sur les fichiers sélectionnés de la section.
"""

import curses
import os
import subprocess
import sys
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
ESCAPE, CTRL_V = "\x1b", "\x16"
HELP = "Espace sélect.  a add  r restore  u unstage  c commit  Tab section  F5 rafraîchir  q quitter"


# --- Git ---------------------------------------------------------------------

def git(*args, env=None, input=None):
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          errors="surrogateescape", env=env, input=input)


def has_head():
    return git("rev-parse", "--verify", "--quiet", "HEAD").returncode == 0


@dataclass(frozen=True)
class Entry:
    section: int
    code: str
    paths: tuple  # (chemin,) ou (nouveau, ancien) pour un renommage ou une copie

    @property
    def label(self):
        shown = [p.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
                 for p in self.paths]
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

    def __init__(self, scr, draw_background):
        self.scr = scr
        self.draw_background = draw_background
        self.fields = [TextField(multiline=False), TextField(multiline=True)]
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
                if key == CTRL_V:
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
        put(win, 0, 2, " Commit ", curses.A_BOLD)
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
        put(win, height - 2, 2, "Ctrl+V valider · Tab changer de champ · Échap annuler", curses.A_DIM)
        try:
            win.move(*cursor)
        except curses.error:
            pass
        win.noutrefresh()
        curses.doupdate()


class App:
    def __init__(self, scr):
        self.scr = scr
        self.selected = set()
        self.cursor = self.top = 0
        self.message, self.message_is_error = "", False
        set_cursor_visible(0)
        if curses.has_colors():
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
        self.colors = {STAGED: curses.color_pair(1), UNSTAGED: curses.color_pair(2),
                       UNTRACKED: curses.color_pair(2)}
        self.refresh()

    # État

    def refresh(self):
        self.items = [e for entries in read_status() for e in entries]
        self.selected &= set(self.items)
        self.cursor = min(self.cursor, max(len(self.items) - 1, 0))
        self.branch = git("branch", "--show-current").stdout.strip() or "(HEAD détachée)"

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
        targets = self.targets(STAGED)
        if not targets:
            return
        answer = CommitDialog(self.scr, self.draw).run()
        if answer is None:
            self.notify("Commit annulé.")
            return
        result = git_commit(targets, *answer)
        self.refresh()
        self.report(result, result.stdout.splitlines()[0] if result.stdout else "Commit effectué.")

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

    # Affichage

    def draw(self):
        scr = self.scr
        scr.erase()
        h, w = scr.getmaxyx()
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

        body_height = max(h - 2, 1)
        cursor_row = next((n for n, row in enumerate(rows) if row[2] == self.cursor), 0)
        if cursor_row < self.top:
            self.top = cursor_row
        elif cursor_row >= self.top + body_height:
            self.top = cursor_row - body_height + 1
        for y, (text, attr, index) in enumerate(rows[self.top:self.top + body_height]):
            if index is not None and index == self.cursor:
                attr |= curses.A_REVERSE
            put(scr, y, 0, text, attr)

        put(scr, h - 2, 0, self.message,
            curses.color_pair(2) | curses.A_BOLD if self.message_is_error else curses.A_BOLD)
        put(scr, h - 1, 0, HELP, curses.A_DIM)
        scr.noutrefresh()

    def run(self):
        while True:
            self.draw()
            curses.doupdate()
            key = self.scr.get_wch()
            self.notify("")
            if key in ("q", "Q"):
                return
            elif key in (curses.KEY_UP, "k"):
                self.cursor = max(self.cursor - 1, 0)
            elif key in (curses.KEY_DOWN, "j"):
                self.cursor = max(min(self.cursor + 1, len(self.items) - 1), 0)
            elif key == "\t":
                self.jump_to_other_section()
            elif key == " ":
                self.toggle()
            elif key == "a":
                self.act((UNSTAGED, UNTRACKED), git_add, "ajouté(s) à l'index")
            elif key == "r":
                self.act((UNSTAGED,), git_restore, "restauré(s)",
                         "Annuler les modifications de {n} fichier(s) ? Elles seront perdues.")
            elif key == "u":
                self.act((STAGED,), git_unstage, "retiré(s) de l'index")
            elif key == "c":
                self.commit()
            elif key == curses.KEY_F5:
                self.refresh()


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
    curses.wrapper(lambda scr: App(scr).run())
    return 0


if __name__ == "__main__":
    sys.exit(main())
