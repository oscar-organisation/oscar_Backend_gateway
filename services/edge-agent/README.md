# OSCAR Edge Runtime

Paquet embarque canonique pour raccorder un robot ROS 2 a OSCAR. Il regroupe
le transport video, la reception des commandes LiveKit, l'adaptation ROS 2,
les garde-fous, l'autodemarrage et le diagnostic dans une release versionnee.

Le paquet ne remplace pas les pilotes du constructeur : il les fait tourner
dans l'image livree avec le robot, telle quelle, a cote de son propre
conteneur. Le profil `rosmaster-m3pro` documente l'integration actuelle.

## Deux conteneurs, trois couches

| Couche | Contenu | Vient de | Change quand |
| --- | --- | --- | --- |
| Hote | systemd, compose, `oscarctl`, identite du robot | l'archive de release | a chaque release |
| `oscar-chassis` | pilotes du constructeur, arret de securite | `ROBOT_BASE_IMAGE`, deja sur le robot | jamais par nous |
| `oscar-edge` | runtime OSCAR (video, commande) | Harbor, par empreinte | a chaque release |

Les deux conteneurs se parlent par ROS 2 (FastDDS, UDPv4, reseau de l'hote).
Une mise a jour d'OSCAR redemarre `oscar-edge` seul : la camera et la base
continuent de tourner.

L'**arret de securite** (`runtime/arret_securite.py`) vit dans `oscar-chassis`.
Si la consigne `/cmd_vel` se tait plus de 300 ms apres un mouvement, il publie
une vitesse nulle. Il couvre le cas que le garde-fou de l'agent de commande ne
peut pas couvrir : la mort de l'agent lui-meme.

## Construction

Depuis la racine du depot :

```bash
OSCAR_EDGE_DIGEST=sha256:... ./services/edge-agent/scripts/build-release.sh
```

La CI le fait apres avoir construit et signe l'image. Une archive sans
empreinte est refusee, sauf pour un essai local
(`OSCAR_RELEASE_SANS_EMPREINTE=1`).

L'archive est creee dans `services/edge-agent/dist/` avec les modules Python
figés dans `services/edge-agent/runtime/`. Elle est autonome et ne dépend pas
d'un autre dépôt sur le robot.

## D'ou vient l'image

L'image `oscar/edge-humble` part de `ros:humble-ros-base` et ne contient que
le runtime OSCAR et les interfaces du chassis (`interfaces/`). Elle ne depend
donc que de la distribution ROS, et sert toutes les familles qui la partagent.

Elle est construite par la CI, jamais sur un robot : le workflow
`build-edge-arm64.yml` part d'une etiquette `edge-v<version>`, construit pour
`linux/arm64`, pousse dans Harbor, **signe l'image avec cosign**, puis
fabrique l'archive de release avec l'empreinte de l'image (`IMAGE_DIGEST`).

Le robot tire l'image par son empreinte et verifie sa signature avec la cle
publique livree dans la release (`config/cosign.pub`) avant de basculer. Une
image non signee, ou modifiee dans le registre, est refusee.

Les robots n'ont que la lecture sur le registre : une cle qui fuite ne permet
pas de pousser une image que tout le parc installerait ensuite.

## Installation sur un robot

```bash
tar -xzf oscar-edge-0.6.0.tar.gz
cd oscar-edge-0.6.0
sudo ./scripts/install.sh
sudoedit /etc/oscar/robot.env
sudo ./scripts/provision-registry.sh - 'compte-machine-oscar+coolify-et-robots-lecture-des-images'
sudo install -m 600 media.json /etc/oscar/credentials/media.json
sudo install -m 600 command.json /etc/oscar/credentials/command.json
sudo install -m 600 agent.key /etc/oscar/credentials/agent.key
sudo oscarctl doctor
sudo oscarctl activate
```

`provision-registry.sh` ouvre une session en lecture sur Harbor. `activate` tire l'image, active l'autodemarrage et lance le runtime.
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
