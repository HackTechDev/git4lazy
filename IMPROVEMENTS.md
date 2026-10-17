# Améliorations possibles

Pistes relevées en relisant le code (`git4lazy.py`, ~800 lignes) et en
l'utilisant. Chaque point indique le problème, une piste de solution et
un effort estimé (S : moins d'une heure, M : une demi-journée, L : plus).

## 1. Fiabilité

Ce qui peut aujourd'hui donner un résultat faux ou silencieux.

### Erreurs de `git status` ignorées — S
`read_status()` lit la sortie de `git status` sans regarder son code de
retour. Si la commande échoue (fichier `index.lock` laissé par un autre
processus, dépôt corrompu), l'écran affiche trois sections vides comme si
tout était propre.
**Piste** : vérifier `returncode` et afficher l'erreur dans la ligne de
message, comme pour les autres commandes.

### Conflits de fusion non gérés — M
Pendant un merge ou un rebase, les fichiers en conflit (`UU`, `AA`…)
apparaissent comme « unmerged » à la fois dans *Changes to be committed* et
*Changes not staged for commit*. `u` et `r` échouent dessus avec une erreur
git peu parlante.
**Piste** : une section *Unmerged paths*, où `a` marque le conflit comme
résolu ; afficher en en-tête qu'un merge ou un rebase est en cours.

### Squash et changement de message : hooks et signature — M
Ces deux opérations recréent les commits avec `git commit-tree`, qui
n'exécute aucun hook (`commit-msg`, par exemple pour un identifiant de
ticket obligatoire). D'après sa documentation, il ne signe pas non plus les
commits sans option `-S` explicite : avec `commit.gpgSign = true`, les
commits recréés perdent leur signature.
**Piste** : lire `commit.gpgSign` et passer `-S` ; exécuter le hook
`commit-msg` sur le nouveau message, ou le signaler dans le README.

### Commit partiel et hooks qui modifient des fichiers — M
Le commit des seuls fichiers sélectionnés passe par un index temporaire. Un
hook `pre-commit` qui reformate puis fait `git add` (cas de nombreux outils
de formatage) écrit dans cet index temporaire, pas dans le vrai : les
fichiers reformatés apparaîtront ensuite comme modifiés.
**Piste** : quand tous les fichiers indexés sont sélectionnés, faire un
`git commit` ordinaire sur le vrai index ; sinon, documenter la limite.

### Largeur des caractères — S
Les calculs de largeur utilisent `len()`. Avec des caractères larges
(chinois, japonais, emoji) dans un nom de fichier ou un message, les lignes
débordent ou le curseur de saisie se décale.
**Piste** : mesurer la largeur affichée avec `unicodedata.east_asian_width`
(ou `wcwidth` si une dépendance est acceptable).

### Redimensionnement pendant une confirmation — S
`confirm()` lit une seule touche : redimensionner le terminal pendant la
question envoie `KEY_RESIZE`, compris comme « non ».
**Piste** : ignorer `KEY_RESIZE` (redessiner et relire une touche).

## 2. Fonctionnalités

### Indexer une partie d'un fichier — L
L'équivalent de `git add -p`, pour ne commiter qu'une partie des
modifications d'un fichier.
**Piste** : dans la vue diff (`d`), sélectionner des blocs (hunks) avec
Espace et les appliquer avec `git apply --cached`.

### Corriger le dernier commit (amend) — S
Oublier un fichier dans le dernier commit est courant.
**Piste** : dans *Changes to be committed*, une touche qui ajoute les
fichiers sélectionnés au dernier commit, s'il n'est pas poussé.

### Fichiers non suivis : ignorer ou supprimer — S
**Piste** : `i` ajoute les fichiers sélectionnés au `.gitignore` ; `d` les
supprime, après confirmation.

### Annuler le dernier commit en gardant l'index — S
`r` dans la liste des commits fait un `git reset HEAD~` : les modifications
du commit ne sont plus indexées. Pour le recommiter tel quel, un
`git reset --soft HEAD~` serait plus pratique.
**Piste** : une seconde touche, ou un choix dans la confirmation.

### Remise et branches — M
Mettre de côté son travail (`git stash`) et changer de branche sont les
deux opérations suivantes les plus demandées dans ce type d'outil.
**Piste** : une troisième page (flèche droite depuis les commits) listant
les branches et les remises.

### Aide intégrée — S
La ligne d'aide du bas est tronquée sur un terminal étroit.
**Piste** : `?` affiche une fenêtre avec toutes les touches de la page.

### Message de commit : longueurs conseillées — S
**Piste** : afficher le nombre de caractères du titre, en orange au-delà de
50 et en rouge au-delà de 72, comme le font la plupart des éditeurs.

## 3. Confort et personnalisation

- **Raccourcis configurables** (M) : Ctrl+V colle dans certains terminaux
  (Windows Terminal) et n'arrive jamais à l'outil. Un fichier
  `~/.config/git4lazy/config.toml` (`tomllib` est dans la bibliothèque
  standard depuis Python 3.11) permettrait de redéfinir les touches.
- **Langue cohérente** (S) : les titres de section sont en anglais (repris de
  `git status`), le reste en français. Choisir une langue, ou suivre la
  langue de git (`LANG`).
- **Souris** (M) : `curses.mousemask` permet de cliquer pour placer le
  curseur et sélectionner.
- **Aide et merges** (S) : dans la liste des commits, l'aide affiche
  `s squash` ou `e modifier le message` d'après la seule sélection ; la
  présence d'un merge n'est vérifiée qu'à l'appui sur la touche, qui est
  alors refusée. Faire la vérification au moment de la sélection.
- **Chemins longs** (S) : un chemin plus large que l'écran est coupé.
  Couper au milieu (`src/…/fichier.py`) garderait visible le nom du fichier.
- **Gros dépôts** (M) : chaque action relance `git status`, `git branch` et
  `git log`. Sur un dépôt de plusieurs centaines de milliers de fichiers,
  ou avec un dossier non suivi très volumineux (`--untracked-files=all`),
  l'écran peut ralentir. Mesurer avant d'optimiser.

## 4. Qualité du code et distribution

### Tests automatisés — M
Les fonctionnalités ont été vérifiées à la main, avec des scripts jetables
qui pilotaient l'application dans un pseudo-terminal. Rien n'est versionné :
une régression passerait inaperçue.
**Piste** : des tests `pytest` sur des dépôts temporaires pour la couche
git (`read_status`, `git_commit` partiel, `git_rewrite`,
`git_undo_last_commit`), qui couvrent l'essentiel des risques ; quelques
tests de bout en bout dans un pseudo-terminal (module `pty`).

### Intégration continue — S
**Piste** : GitHub Actions exécutant les tests sur plusieurs versions de
Python et de git. Le README annonce Python 3.7 et Git 2.23 sans que ce soit
vérifié.

### Séparer la couche git de l'interface — M
`git4lazy.py` mêle fonctions git et code curses. Un module `git` séparé
faciliterait les tests et une éventuelle autre interface. À faire en même
temps que les tests, pas avant.

### Installation — S
**Piste** : un `pyproject.toml` avec un point d'entrée `git4lazy`, pour
`pipx install git+https://github.com/HackTechDev/git4lazy`. Nommé
`git-lazy`, l'exécutable deviendrait aussi la commande `git lazy`.

### Licence — S
Le dépôt n'a pas de licence : légalement, personne ne peut réutiliser le
code. Ajouter un fichier `LICENSE` (MIT, GPL…) selon vos intentions.

## Écarté volontairement

- **Pousser et récupérer depuis l'outil** (`git push`, `git fetch`) : ces
  opérations restent manuelles, pour éviter de pousser des commits par
  erreur. git4lazy ne communique jamais avec le dépôt distant.

## Par où commencer

Pour un maximum d'effet avec peu d'effort :

1. Erreurs de `git status` ignorées (fiabilité, S)
2. Tests de la couche git (M) : ils sécurisent tout le reste
3. Amend (S)
4. Licence (S)
