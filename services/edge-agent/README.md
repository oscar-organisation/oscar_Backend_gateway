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

## Installation sur un robot

```bash
tar -xzf oscar-edge-0.1.0.tar.gz
cd oscar-edge-0.1.0
sudo ./scripts/install.sh
sudoedit /etc/oscar/robot.env
sudo install -m 600 media.json /etc/oscar/credentials/media.json
sudo install -m 600 command.json /etc/oscar/credentials/command.json
sudo oscarctl doctor
sudo oscarctl activate
```

`activate` construit l'image locale, active l'autodemarrage et lance le
runtime. Aucun mouvement n'est possible sans commande fraiche et sans bouton
de presence maintenu.

## Commandes d'exploitation

```bash
oscarctl status
oscarctl doctor
oscarctl logs
oscarctl restart
oscarctl stop
oscarctl version
```

Le protocole complet se trouve dans
[`docs/protocole-deploiement-embarque.md`](docs/protocole-deploiement-embarque.md).

## Synchronisation du runtime

Le runtime est la version embarquée validée. Les adaptations expérimentales
Isaac Sim sont maintenues séparément dans `oscar_script_simulateur_robot` afin
que le package physique ne dépende jamais de la scène de simulation.
