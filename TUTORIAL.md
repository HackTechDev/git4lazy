# Tutoriel git4lazy

Ce tutoriel fait le tour de git4lazy en une vingtaine de minutes, sur un
dépôt d'essai : rien de ce que vous ferez ici ne touche à vos vrais projets.

Pour la liste complète des touches, voir le [README](README.md).

## 0. Préparer un bac à sable

Créez un dépôt vide et quelques fichiers :

```sh
mkdir ~/bac-a-sable && cd ~/bac-a-sable
git init -b main
echo "Bonjour" > bonjour.txt
echo "Liste de courses" > courses.txt
echo "Brouillon" > brouillon.txt
```

Si git ne connaît pas encore votre nom, indiquez-le une fois pour toutes,
sinon les commits échoueront :

```sh
git config --global user.name "Votre Nom"
git config --global user.email "vous@example.com"
```

Lancez ensuite git4lazy depuis le dépôt :

```sh
/chemin/vers/git4lazy.py
```

## 1. Lire l'écran

```
Sur la branche main

Changes to be committed :
    (aucun fichier)

Changes not staged for commit :
    (aucun fichier)

Untracked files :
  [ ] bonjour.txt
  [ ] brouillon.txt
  [ ] courses.txt
```

- **Changes to be committed** (en vert) : fichiers indexés, prêts à être commités.
- **Changes not staged for commit** (en rouge) : fichiers suivis par git,
  modifiés ou supprimés, mais pas encore indexés.
- **Untracked files** (en rouge) : fichiers que git ne suit pas encore.

La ligne en surbrillance est le curseur. Déplacez-le avec ↑/↓ (ou `j`/`k`),
et sautez d'une section à l'autre avec **Tab**. En bas de l'écran, l'avant-
dernière ligne affiche le résultat de chaque action (ou l'erreur de git) et
la dernière rappelle les touches. Elle s'adapte à la section du curseur :
`a add` n'apparaît que dans *Changes not staged for commit* et *Untracked
files*, `u unstage` et `c commit` que dans *Changes to be committed*.

En cas de doute, appuyez sur **?** : une fenêtre liste tous les raccourcis
clavier, en commençant par ceux de la page où vous êtes. **Échap** (ou **?**)
la referme.

## 2. Ajouter des fichiers à l'index

Ajoutons `bonjour.txt` et `courses.txt`, mais pas le brouillon.

1. Placez le curseur sur `bonjour.txt` et appuyez sur **Espace** : la case
   devient `[x]`. Le curseur ne bouge pas.
2. Descendez sur `courses.txt` et appuyez sur **Espace**.
3. Appuyez sur **a**.

Les deux fichiers passent dans *Changes to be committed* et le message
« 2 fichier(s) ajouté(s) à l'index. » s'affiche.

Pour sélectionner d'un coup tous les fichiers d'une section, appuyez sur
**\*** avec le curseur dans cette section ; un second appui les
désélectionne tous.

> Les actions ne portent que sur les fichiers **sélectionnés** de la section
> où se trouve le curseur. Sans sélection, git4lazy ne fait rien et affiche
> « Aucun fichier sélectionné ». Si le curseur est dans une autre section,
> il vous indique où le placer.

## 3. Se raviser : retirer de l'index

Finalement, `courses.txt` n'a rien à faire dans ce commit.

1. Sélectionnez `courses.txt` dans *Changes to be committed* (**Espace**).
2. Appuyez sur **u**.

Le fichier revient dans *Untracked files*. Son contenu n'a pas changé : seul
son passage dans l'index est annulé.

## 4. Premier commit

1. Sélectionnez `bonjour.txt` dans *Changes to be committed*.
2. Appuyez sur **c** : une fenêtre s'ouvre. Le titre est vide, puisque c'est
   le premier commit du dépôt.
3. Tapez le titre, par exemple `Ajoute le fichier de bienvenue`.
4. **Entrée** passe au champ du message (facultatif). Tapez quelques lignes ;
   ici, Entrée crée une nouvelle ligne.
5. **Ctrl+S** valide. (**Tab** passe d'un champ à l'autre, **Échap** annule.)
6. git4lazy demande confirmation : appuyez sur **o** pour commiter. Toute
   autre touche ramène à la fenêtre, avec le titre et le message conservés.

Pendant le commit, la ligne du bas indique « Commit de 1 fichier(s) en
cours… » ; une fois terminé, elle affiche la sortie de git, par exemple
`[main (commit racine) 1a2b3c4] Ajoute le fichier de bienvenue`.

> Seuls les fichiers sélectionnés sont commités. Si d'autres fichiers sont
> indexés sans être sélectionnés, ils restent dans l'index pour un prochain
> commit.

Avant de continuer, ajoutez et commitez aussi `courses.txt` : sélectionnez-le
et appuyez sur **a**, puis sélectionnez-le dans *Changes to be committed* et
appuyez sur **c**. Cette fois, le titre est prérempli avec celui du dernier
commit : effacez-le (Retour arrière) et tapez `Ajoute la liste de courses`.

## 5. Modifier un fichier suivi

Sans quitter git4lazy, ouvrez un autre terminal et modifiez un fichier :

```sh
cd ~/bac-a-sable
echo "Pain" >> courses.txt
```

Revenez dans git4lazy et appuyez sur **F5** pour rafraîchir :
`modified: courses.txt` apparaît dans *Changes not staged for commit*.

### Voir ce qui a changé

Placez le curseur sur `courses.txt` et appuyez sur **d** : le diff s'affiche
en plein écran, côte à côte : l'ancienne version à gauche, la nouvelle à
droite, où la ligne `Pain` apparaît en vert. Appuyez sur **v** pour passer
au diff unifié de `git diff` (la ligne devient `+Pain`), et de nouveau sur
**v** pour revenir. Les lignes `diff --git`, `index`, `---` et `+++` en
tête du diff sont des informations techniques de git : **h** les remplace
par le seul nom du fichier, `courses.txt`, et un second **h** les
réaffiche. Faites défiler avec ↑/↓ ou PgUp/PgDn ; dans un long diff,
**n** et **p** sautent directement à la modification suivante ou
précédente. Revenez à la liste avec **Échap** (ou ←, ou q).

Le diff ne demande pas de sélection : il porte sur le fichier sous le
curseur. Selon la section, il montre ce qui sera commité (*Changes to be
committed*), ce qui n'est pas encore indexé (*Changes not staged for
commit*) ou, pour un fichier non suivi, tout son contenu.

### Annuler la modification

Imaginons que cette modification était une erreur.

1. Sélectionnez `courses.txt` dans *Changes not staged for commit*.
2. Appuyez sur **r**.
3. git4lazy demande confirmation : appuyez sur **o** pour valider (toute
   autre touche annule).

Le fichier retrouve sa dernière version indexée ou commitée.

> **Attention** : c'est la seule action de git4lazy qui perd des données.
> La modification annulée n'est récupérable nulle part.

### Indexer la modification

Refaites la modification (`echo "Pain" >> courses.txt`), appuyez sur **F5**,
puis sélectionnez le fichier et appuyez sur **a** : il passe dans
*Changes to be committed*. Sélectionnez-le dans cette section et commitez-le
(**c**) avec le titre `Ajoute le pain`.

## 6. La liste des commits

Appuyez sur la **flèche droite** :

```
Commits non poussés de main (aucune branche distante suivie)

  [ ] 9f8e7d6  Ajoute le pain  (Votre Nom, il y a 1 minute)
  [ ] 5c4b3a2  Ajoute la liste de courses  (Votre Nom, il y a 3 minutes)
  [ ] 1a2b3c4  Ajoute le fichier de bienvenue  (Votre Nom, il y a 5 minutes)
```

Cette page montre les commits qui ne sont pas encore sur le dépôt distant,
du plus récent au plus ancien. Notre bac à sable n'a pas de dépôt distant,
donc tous les commits y figurent. La **flèche gauche** ramène aux fichiers.

On ne retouche que des commits non poussés : les modifier ne gêne personne.

Pour voir le contenu d'un commit, placez le curseur dessus et appuyez sur
**d** : la liste des fichiers modifiés s'affiche, suivie du diff.

La ligne d'aide du bas s'adapte à votre sélection : elle n'affiche `s`, `e`
ou `r` que lorsque l'action est possible. Sans sélection, aucune des trois
n'apparaît.

### Modifier un message

Le titre `Ajoute le pain` est un peu court.

1. Sélectionnez ce commit avec **Espace** (un seul commit à la fois) :
   `e modifier le message` apparaît dans l'aide.
2. Appuyez sur **e** : la fenêtre s'ouvre avec le titre et le message actuels.
3. Modifiez le titre, par exemple `Ajoute le pain à la liste de courses`,
   puis **Ctrl+S**.

Le hash du commit change (c'est un nouveau commit), mais son contenu, son
auteur et sa date restent les mêmes.

### Fusionner des commits (squash)

`Ajoute la liste de courses` et `Ajoute le pain…` iraient mieux en un seul
commit.

1. Sélectionnez les deux commits avec **Espace**. Ils doivent se suivre dans
   la liste ; `s squash` apparaît alors dans l'aide.
2. Appuyez sur **s**. La fenêtre propose le titre du plus ancien et, dans le
   message, ceux des autres.
3. Ajustez le texte, puis **Ctrl+S**.

La liste ne compte plus que deux commits. Le contenu des fichiers n'a pas
changé, et le commit fusionné garde l'auteur et la date du plus ancien.

### Annuler le dernier commit

1. Sélectionnez le commit **en haut** de la liste (le seul accepté) :
   `r reset` apparaît dans l'aide.
2. Appuyez sur **r**, puis **o** pour confirmer.

Le commit disparaît. Revenez aux fichiers (**flèche gauche**) : ses
modifications sont toujours là, dans *Changes not staged for commit* ou
*Untracked files*. Vous pouvez les recommiter autrement.

C'est l'équivalent de `git reset HEAD~` : rien n'est perdu. Les autres
fichiers qui étaient indexés sont eux aussi retirés de l'index.

## 7. Pousser

git4lazy ne pousse pas lui-même, volontairement : pousser reste un geste
manuel, pour ne jamais envoyer des commits par erreur. Une fois vos commits
prêts, dans un autre terminal :

```sh
git push
```

Revenez dans git4lazy et appuyez sur **F5** (ou rouvrez la liste avec la
flèche droite) : les commits poussés ont disparu de la liste. La comparaison
se fait avec l'état du dépôt distant connu lors du dernier `git push` ou
`git fetch`.

## 8. Si quelque chose tourne mal

**Revenir avant un squash ou une modification de message** : juste après
l'opération, dans un terminal :

```sh
git reset --soft HEAD@{1}
```

Comme ces opérations ne changent pas le contenu des fichiers, cette commande
rétablit exactement l'historique d'avant, sans toucher à votre travail en
cours.

**Revenir avant l'annulation du dernier commit (r)** :

```sh
git reset HEAD@{1}
```

Le commit revient et ses modifications ne sont plus en attente. Si d'autres
fichiers étaient indexés avant, il faudra les réindexer.

Si vous avez fait d'autres opérations entre-temps, `git reflog` liste les
positions précédentes de la branche ; les entrées de git4lazy s'appellent
« git4lazy: squash » et « git4lazy: reword ».

**Messages fréquents** :

| Message                               | Ce qu'il faut faire                                       |
|---------------------------------------|-----------------------------------------------------------|
| Aucun fichier sélectionné             | Sélectionnez au moins un fichier avec Espace              |
| Placez le curseur dans « … »          | Déplacez le curseur dans la section indiquée (Tab)        |
| Les commits sélectionnés doivent se suivre | Pour un squash, choisissez des commits voisins       |
| Sélectionnez un seul commit           | `e` ne modifie qu'un commit à la fois                     |
| Sélectionnez uniquement le dernier commit | `r` n'annule que le commit en haut de la liste        |
| Le titre est obligatoire              | Remplissez le champ Titre avant Ctrl+S                    |

## 9. Ranger le bac à sable

Quittez git4lazy avec **q**, puis :

```sh
rm -rf ~/bac-a-sable
```
