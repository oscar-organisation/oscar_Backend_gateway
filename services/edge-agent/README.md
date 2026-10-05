# OSCAR Edge Runtime

Paquet embarque canonique pour raccorder un robot ROS 2 a OSCAR. Il regroupe
le transport video, la reception des commandes LiveKit, l'adaptation ROS 2,
les garde-fous, l'autodemarrage et le diagnostic dans une release versionnee.

Le paquet ne remplace pas les pilotes du constructeur. Il se pose au-dessus
d'une image robot contenant ROS 2, les messages du constructeur et les pilotes
camera/moteurs. Le profil `rosmaster-m3pro` documente l'integration actuelle.

## Construction

Depuis la racine du depot :

```bash
./services/edge-agent/scripts/build-release.sh
```

L'archive est creee dans `services/edge-agent/dist/` avec les modules Python
figés dans `services/edge-agent/runtime/`. Elle est autonome et ne dépend pas
d'un autre dépôt sur le robot.

## D'ou vient l'image

Le paquet ne contient pas l'image du runtime : il contient sa recette et la
reference de celle qui lui correspond. L'image vit dans un registre joint par
le seul tailnet, et le robot la tire.

La fabrication se fait sur un **robot de reference**, pas sur un serveur, pour
une raison materielle : l'image de base du constructeur ne vit que sur le
chassis et pese 8,68 Go. La construire ailleurs demanderait l'emulation d'une
architecture et une copie de cette base que le registre du constructeur, hors
d'atteinte du reseau actuel, ne peut pas fournir.

```bash
# Sur le robot de reference, une fois par version
sudo docker login "$OSCAR_REGISTRY" --username oscar-builder
sudo oscarctl build-image
```

L'image porte le nom de la famille de chassis :
`oscar/edge-rosmaster-m3pro:0.5.6`, `oscar/edge-unitree-g1:0.5.6`. Une version
du paquet ne produit pas une image mais une par famille, puisque chacune porte
la base ROS de son constructeur. Le suffixe vient de `OSCAR_ROBOT_PROFILE`, et
son absence fait refuser la release plutot que deviner.

Les robots de la flotte ne construisent rien. Leur compte n'a que la lecture :
le registre refuse l'ecriture, pour qu'une cle qui fuite ne permette pas de
pousser une image que tout le parc installerait ensuite.

## Installation sur un robot

```bash
tar -xzf oscar-edge-0.5.6.tar.gz
cd oscar-edge-0.5.6
sudo ./scripts/install.sh
sudoedit /etc/oscar/robot.env
sudo ./scripts/provision-registry.sh ca.crt oscar-robot
sudo install -m 600 media.json /etc/oscar/credentials/media.json
sudo install -m 600 command.json /etc/oscar/credentials/command.json
sudo install -m 600 agent.key /etc/oscar/credentials/agent.key
sudo oscarctl doctor
sudo oscarctl activate
```

`provision-registry.sh` pose l'autorite du registre et ouvre une session en
lecture. `activate` tire l'image, active l'autodemarrage et lance le runtime.
Aucun mouvement n'est possible sans commande fraiche et sans bouton de
presence maintenu.

Trois fichiers de configuration cohabitent, et la separation est volontaire :

| Fichier | Ecrit par | Dit |
| --- | --- | --- |
| `/etc/oscar/robot.env` | l'operateur | comment le chassis est cable |
| `/etc/oscar/bundle.env` | la console | ce qui doit tourner |
| `/etc/oscar/release.env` | le paquet | quelle image lui correspond |

La version du runtime a longtemps vecu dans `robot.env`. Tenue a la main, elle
y restait figee quand une release montait : le robot relancait alors l'ancienne
image avec les nouveaux outils d'hote, et les modules du runtime ne changeaient
jamais. Elle appartient desormais au paquet, qui l'ecrit a chaque installation
et a chaque bascule.

## Commandes d'exploitation

```bash
oscarctl status
oscarctl doctor
oscarctl logs
oscarctl restart
oscarctl stop
oscarctl version
oscarctl image
oscarctl pull
```

## Bundles publies depuis la console

Le robot tire sa configuration : `oscar-edge-sync.timer` interroge la console
toutes les 45 secondes, applique le bundle publie pour ce robot et rend compte.
Rien n'entre depuis l'exterieur, ce qui vaut aussi derriere un partage de
connexion telephonique.

Le partage des roles est strict : `/etc/oscar/robot.env` dit **comment** le
robot est cable (topics ROS, limites, resolution) et ne bouge qu'a la main ;
`/etc/oscar/bundle.env`, genere, dit **ce qui tourne** (quels agents, quelle
version). Une capacite reclamee par un bundle mais absente de ce runtime est
refusee et remontee avec son motif, plutot qu'appliquee a moitie.

## Renouvellement des identifiants LiveKit

`oscar-edge-credentials.timer` verifie les deux identifiants chaque nuit vers
03:00, avec un delai aleatoire d'une heure pour repartir la charge d'une
flotte. Il interroge la console lorsqu'un fichier manque, est illisible ou
expire dans moins de sept jours. Une console indisponible laisse les fichiers
en place et le prochain passage reessaie.

Les agents transmettent la chaine du jeton a LiveKit lors de leur connexion ;
ils ne relisent pas le fichier ensuite. Quand un jeton change, le runtime est
donc redemarre une fois, apres l'ecriture atomique des fichiers en mode `0600`.
Une reponse identique ne reecrit rien et ne coupe pas la video.

```bash
sudo systemctl status oscar-edge-credentials.timer
sudo systemctl start oscar-edge-credentials.service
sudo journalctl -u oscar-edge-credentials.service -n 50
```

```bash
oscarctl sync --no-restart   # verification a blanc, sans couper la video
oscarctl sync                # reconciliation immediate
oscarctl bundle              # bundle applique et verdict du dernier passage
```

Le protocole complet se trouve dans
[`docs/protocole-deploiement-embarque.md`](docs/protocole-deploiement-embarque.md).

## Synchronisation du runtime

Le runtime est la version embarquée validée. Les adaptations expérimentales
Isaac Sim sont maintenues séparément dans `oscar_script_simulateur_robot` afin
que le package physique ne dépende jamais de la scène de simulation.
