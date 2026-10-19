# À faire

Tâches retenues, par ordre de priorité. Les pistes encore à l'étude sont
dans [IMPROVEMENTS.md](IMPROVEMENTS.md).

## Priorité moyenne

### Rafraîchissement automatique

**Besoin** : la liste devrait se mettre à jour toute seule quand un fichier
est ajouté, modifié ou supprimé, sans appuyer sur F5.

**Approche retenue** : relire l'état à intervalle régulier. `scr.timeout(2000)`
fait rendre la main à `get_wch()` au bout de 2 s sans touche (il lève alors
`curses.error`) ; on relance `refresh()` et on redessine. Pas de
surveillance des fichiers : la bibliothèque standard n'en fournit pas,
`watchdog` est une dépendance externe, et `inotify` via `ctypes` ne
marcherait que sous Linux.

**À faire** :
1. Dans `App.run()`, rafraîchir à l'expiration du délai. F5 reste
   disponible pour forcer un rafraîchissement.
2. **Garder le curseur sur le même fichier** (ou commit) : aujourd'hui
   `self.cursor` est une position dans la liste. Si un fichier apparaît
   au-dessus, le curseur glisserait sur un autre fichier à l'insu de
   l'utilisateur, juste avant un `a` ou un `r`. Le recaler sur la même
   entrée après chaque `refresh()`.
3. Ne rien rafraîchir pendant la fenêtre de commit, une confirmation (o/N),
   la vue diff ou la fenêtre d'aide : ces boucles ont leur propre
   `get_wch()`, il suffit de ne pas y activer le délai.
4. Ne pas effacer le message du bas lors d'un rafraîchissement automatique
   (aujourd'hui `run()` le vide à chaque touche).
5. Les sélections sont déjà conservées (`selected &= set(items)`) ; seule
   celle d'un fichier disparu tombe.

**À surveiller** : sur un très gros dépôt, `git status` peut dépasser une
seconde. Si besoin, espacer l'intervalle ou ne relancer `git status` que si
la date de modification de `.git/index` ou des dossiers a changé.

## Priorité basse

### Gérer les erreurs de `git status`

**Problème** : `read_status()` lit la sortie de `git status` sans regarder
son code de retour. Quand la commande échoue, la sortie est vide :
l'écran affiche « (aucun fichier) » dans les trois sections, sans message,
comme si le dépôt était propre.

**Cas où `git status` échoue (code 128)** — vérifiés sur un dépôt d'essai,
sauf le dernier :

| Situation                                              | Message de git                                                  |
|--------------------------------------------------------|-----------------------------------------------------------------|
| Index corrompu (plantage, disque plein)                | `fatal: .git/index : fichier d'index plus petit qu'attendu`     |
| Index illisible (droits, par exemple après `sudo git`) | `fatal: … l'ouverture du fichier d'index a échoué: Permission non accordée` |
| Objets manquants ou corrompus                          | `fatal: bad object HEAD`                                        |
| `.git/config` mal formé                                | `fatal: ligne N de config incorrecte dans le fichier .git/config` |
| Dépôt supprimé ou déplacé pendant l'utilisation        | `fatal: ni ceci ni aucun de ses répertoires parents … n'est un dépôt git` |
| Dépôt d'un autre utilisateur (`safe.directory`)        | `fatal: detected dubious ownership in repository`               |

**Cas trompeurs (code 0)** :
- Dossier non suivi illisible : git écrit un `warning` sur la sortie
  d'erreur, aujourd'hui ignoré ; le dossier manque sans explication.
- Référence de branche corrompue : `git status` réussit mais montre le
  dépôt comme s'il n'avait aucun commit. Non détectable par le code de
  retour ; à laisser de côté.
- `index.lock` présent : `git status` fonctionne normalement. Les actions
  (`a`, `u`, `c`…) échouent, mais leur erreur est déjà affichée.

**À faire** :
1. Si `git status` renvoie un code non nul, afficher son message en rouge
   dans la ligne du bas et garder la liste précédente plutôt qu'une liste
   vide.
2. Afficher aussi les `warning` de git (sortie d'erreur avec code 0).
3. Appliquer la même règle à `git log` dans la liste des commits
   (`read_unpushed()`).
4. Si `git` est introuvable dans le `PATH`, afficher un message clair au
   lieu de la trace Python (`FileNotFoundError` levée par `subprocess`).
