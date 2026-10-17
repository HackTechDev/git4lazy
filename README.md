# git4lazy

Un `git status` interactif en mode terminal : sélectionnez des fichiers,
ajoutez-les à l'index ou retirez-les, puis commitez sans quitter l'écran.

```
Sur la branche main

Changes to be committed :
  [ ] modified:   src/app.py

Changes not staged for commit :
  [x] modified:   README.md
  [ ] deleted:    old.txt

Untracked files :
  [x] notes.txt
```

## Prérequis

- Python 3.7 ou plus récent (uniquement la bibliothèque standard)
- Git 2.23 ou plus récent (pour `git restore`)
- Linux ou macOS : sous Windows, le module `curses` n'est pas fourni
  (`pip install windows-curses`)

## Lancement

Depuis n'importe quel dossier d'un dépôt git :

```sh
/chemin/vers/git4lazy.py
```

Pour l'avoir sous la main, placez-le dans votre `PATH`, par exemple :

```sh
ln -s "$PWD/git4lazy.py" ~/.local/bin/git4lazy
```

## Touches

| Touche     | Section                                          | Action                                                  |
|------------|--------------------------------------------------|---------------------------------------------------------|
| ↑/↓ ou k/j | toutes                                           | Déplacer le curseur                                     |
| Tab        | toutes                                           | Passer à la section suivante                            |
| Espace     | toutes                                           | Sélectionner ou désélectionner un fichier               |
| a          | Changes not staged for commit, Untracked files   | Ajouter les fichiers sélectionnés à l'index (`git add`) |
| r          | Changes not staged for commit                    | Annuler les modifications des fichiers sélectionnés (`git restore`), après confirmation |
| u          | Changes to be committed                          | Retirer les fichiers sélectionnés de l'index            |
| c          | Changes to be committed                          | Saisir un titre et un message, puis commiter les fichiers sélectionnés |
| F5         | toutes                                           | Rafraîchir                                              |
| q          | toutes                                           | Quitter                                                 |

`a`, `r`, `u` et `c` n'agissent que sur les fichiers sélectionnés : sans
sélection dans la section, rien ne se passe et un message le signale.
La liste est rafraîchie après chaque action ; le résultat, ou l'erreur
renvoyée par git, s'affiche en bas de l'écran.

### Fenêtre de commit

| Touche  | Action                                                |
|---------|-------------------------------------------------------|
| Entrée  | Dans le titre : passer au message ; dans le message : nouvelle ligne |
| Tab     | Changer de champ                                      |
| Ctrl+V  | Valider (le titre est obligatoire)                    |
| Échap   | Annuler                                               |

Le commit ne contient que les fichiers sélectionnés, dans leur version
indexée. Les autres fichiers indexés restent dans l'index pour un prochain
commit.

## Bon à savoir

- **Retirer de l'index** utilise `git restore --staged`, qui ne touche ni à
  la copie de travail ni au dépôt. Avant le premier commit, faute de `HEAD`,
  c'est `git rm --cached` qui est employé ; à ce stade tous les fichiers
  indexés sont nouveaux, et les deux commandes reviennent au même.
- **Annuler les modifications** (`r`) remet dans la copie de travail la
  version de l'index : les modifications non indexées sont perdues
  définitivement, celles déjà indexées sont conservées. Un fichier supprimé
  est restauré. Une confirmation (`o`) est demandée avant.
- Un fichier indexé puis modifié à nouveau apparaît dans les deux premières
  sections, comme dans `git status`.
- Les noms de fichiers sont pris littéralement : `*` ou un `:` initial ne
  sont pas interprétés comme des motifs git.
