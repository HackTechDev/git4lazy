# git4lazy

Un `git status` interactif en mode terminal : sélectionnez des fichiers,
ajoutez-les à l'index ou retirez-les, puis commitez sans quitter l'écran.
Une seconde page liste les commits pas encore poussés, pour les fusionner
(squash), corriger leur message ou annuler le dernier. Le diff d'un fichier
ou d'un commit s'affiche en plein écran d'une touche.

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

Pour une prise en main pas à pas, voir le [tutoriel](TUTORIAL.md) ; les
pistes d'évolution sont dans [IMPROVEMENTS.md](IMPROVEMENTS.md).

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

### Page des fichiers

| Touche     | Section                                          | Action                                                  |
|------------|--------------------------------------------------|---------------------------------------------------------|
| ↑/↓ ou k/j | toutes                                           | Déplacer le curseur                                     |
| Tab        | toutes                                           | Passer à la section suivante                            |
| Espace     | toutes                                           | Sélectionner ou désélectionner un fichier               |
| *          | toutes                                           | Sélectionner tous les fichiers de la section du curseur (ou tous les désélectionner s'ils l'étaient déjà) |
| d          | toutes                                           | Afficher le diff du fichier sous le curseur             |
| a          | Changes not staged for commit, Untracked files   | Ajouter les fichiers sélectionnés à l'index (`git add`) |
| r          | Changes not staged for commit                    | Annuler les modifications des fichiers sélectionnés (`git restore`), après confirmation |
| u          | Changes to be committed                          | Retirer les fichiers sélectionnés de l'index            |
| c          | Changes to be committed                          | Saisir un titre et un message, puis commiter les fichiers sélectionnés |
| →          | toutes                                           | Afficher les commits non poussés                        |
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

### Commits non poussés

La flèche droite affiche les commits locaux qui ne sont pas encore sur le
dépôt distant, du plus récent au plus ancien.

| Touche     | Action                                                  |
|------------|---------------------------------------------------------|
| ↑/↓ ou k/j | Parcourir la liste                                      |
| Espace     | Sélectionner ou désélectionner un commit                |
| s          | Squasher les commits sélectionnés en un seul            |
| e          | Modifier le titre et le message du commit sélectionné   |
| r          | Annuler le dernier commit (`git reset HEAD~`)           |
| d          | Afficher le contenu du commit sous le curseur           |
| ←          | Revenir aux fichiers                                    |

La ligne d'aide en bas de l'écran ne montre `s`, `e` et `r` que lorsque la
sélection en cours permet l'action.

Pour un squash, les commits sélectionnés doivent être au moins deux et se
suivre. Une fenêtre s'ouvre avec le titre du plus ancien et les messages
des autres, modifiables ; Ctrl+V valide, Échap annule. Comme avec
`git rebase -i`, le commit obtenu garde l'auteur et la date du plus ancien,
et les commits plus récents sont recréés par-dessus. Le contenu des
fichiers, l'index et la copie de travail ne changent pas. L'historique
d'avant reste accessible par `git reflog` (entrée « git4lazy: squash »).

Pour modifier un message, sélectionnez un seul commit puis appuyez sur `e` :
la fenêtre s'ouvre avec son titre et son message actuels. Seul le message
change ; l'auteur, la date et le contenu sont conservés, et les commits plus
récents sont recréés par-dessus (entrée « git4lazy: reword » dans le reflog).

Squash et modification sont refusés si l'historique concerné contient un merge.

Pour annuler le dernier commit, sélectionnez-le (le seul accepté est celui
en haut de la liste) puis appuyez sur `r` et confirmez avec `o`. C'est
l'équivalent de `git reset HEAD~` : le commit disparaît, ses modifications
restent dans les fichiers mais ne sont plus indexées (les autres fichiers
qui étaient dans l'index en sont retirés aussi). Comme la liste ne
montre que les commits non poussés, un commit déjà poussé ne peut pas être
annulé ainsi.

La comparaison se fait avec la branche distante suivie (par exemple
`origin/main`), telle que connue lors du dernier `git fetch` ou `git push` :
aucun accès réseau n'est fait. Sans branche distante suivie, la liste montre
les commits absents de toutes les branches distantes.

### Vue diff

`d` (ou `D`) ouvre le diff en plein écran, coloré : ajouts en vert,
suppressions en rouge, en-têtes de blocs en cyan. Les lignes trop longues
sont repliées.

| Élément sous le curseur         | Contenu affiché                                     |
|---------------------------------|-----------------------------------------------------|
| Fichier de *Changes to be committed* | Ce qui sera commité (`git diff --cached`)      |
| Fichier de *Changes not staged for commit* | Ce qui n'est pas encore indexé (`git diff`) |
| Fichier de *Untracked files*    | Tout son contenu, comme un ajout                    |
| Commit de la liste              | Fichiers modifiés puis diff (`git show --stat --patch`) |

| Touche                 | Action                    |
|------------------------|---------------------------|
| ↑/↓ ou k/j             | Défiler d'une ligne       |
| PgUp / PgDn ou Espace  | Défiler d'une page        |
| Début / Fin ou g / G   | Aller au début / à la fin |
| Échap, ←, q ou d       | Revenir à la liste        |

Contrairement aux actions, le diff ne demande pas de sélection : il porte
sur l'élément sous le curseur.

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
