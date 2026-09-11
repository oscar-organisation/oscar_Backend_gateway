# Protocole de deploiement embarque

Ce document decrit le passage d'un robot vierge a un robot exploitable dans
OSCAR. Chaque etape produit une preuve et peut etre reprise sans effet de bord.

## 1. Qualification du modele

Avant toute installation en serie, creer une fiche de profil contenant :

- architecture CPU/GPU, OS et version ROS 2 ;
- image Docker constructeur et empreinte immuable ;
- topic camera, encodage, resolution et cadence mesurable ;
- topic de vitesse et convention des axes ;
- messages des bras/outils et limites mecaniques ;
- procedure d'arret materiel et comportement en perte de commande ;
- devices requis (`/dev/ttyUSB*`, camera, CAN) et regles udev stables.

La qualification n'est faite qu'une fois par modele. Le ROSMASTER M3 Pro de
reference utilise ROS 2 Humble, `/camera/color/image_raw`, `/cmd_vel` et
`/arm_joint`.

## 2. Image de base constructeur

La base livree dans le package robot contient Ubuntu, Docker Compose v2, ROS 2,
les pilotes et messages constructeur. Elle doit pouvoir satisfaire seule :

```bash
ros2 topic list
ros2 topic hz /camera/color/image_raw
ros2 topic info /cmd_vel
```

A ce stade aucune cle LiveKit et aucun secret OSCAR ne sont presents.

## 3. Preparation reseau et temps

1. Donner au robot un acces DNS, HTTPS/WSS et UDP sortant.
2. Activer NTP ; les JWT et les mesures de latence dependent d'une heure juste.
3. Enroler Tailscale pour la maintenance distante si la politique du site
   l'autorise. Son nom est derive de l'identite, par exemple `oscar-robot-m3`.
4. Tester le serveur OSCAR et le SFU depuis le robot.

Le Wi-Fi client ne doit jamais etre code dans une image. Il est configure au
site, via NetworkManager ou la plateforme du fabricant.

## 4. Enrolement OSCAR

Le processus cible emploie un code d'enrolement a usage unique genere par la
plateforme de deploiement :

1. Le technicien saisit le code et le numero de serie.
2. L'API cree ou associe le robot a l'organisation et au site.
3. L'API renvoie l'identite canonique, le profil, la room et deux credentials
   separes : media et commande.
4. Le robot stocke les credentials dans `/etc/oscar/credentials`, mode `0600`.
5. Les credentials sont renouveles avant expiration ; ils ne sont ni inclus
   dans l'image ni inscrits dans les journaux.

Tant que l'endpoint d'enrolement automatique n'est pas livre, les deux fichiers
JSON sont poses manuellement. Cette exception est explicite et auditable.

## 5. Installation de la release

La CI fabrique `oscar-edge-VERSION.tar.gz` avec :

- le manifeste et la version ;
- les agents Python valides ;
- l'image reproductible derivee de la base constructeur ;
- les profils, services, controles et documentation.

Sur le robot :

```bash
tar -xzf oscar-edge-VERSION.tar.gz
cd oscar-edge-VERSION
sudo ./scripts/install.sh
sudoedit /etc/oscar/robot.env
sudo install -m 600 media.json /etc/oscar/credentials/media.json
sudo install -m 600 command.json /etc/oscar/credentials/command.json
```

La release est copiee dans `/opt/oscar/releases/VERSION`. Le lien
`/opt/oscar/current` rend le basculement atomique. Les fichiers de site restent
hors release dans `/etc/oscar` et survivent aux mises a jour.

## 6. Prevol sans mouvement

```bash
sudo oscarctl preflight
```

Le prevol refuse le lancement si Docker, l'image ROS, la configuration ou les
credentials sont incoherents. Il verifie notamment que les deux agents ciblent
la meme room avec des identites distinctes et des droits minimaux.

Ensuite construire et lancer :

```bash
sudo oscarctl activate
sudo oscarctl doctor
```

Le premier demarrage est realise roues levees ou robot sur chandelles. Aucun
paquet recu ne doit produire de mouvement sans maintien du deadman.

## 7. Recette usine puis recette site

La recette usine couvre materiel, ROS, video, commandes, securite et endurance.
La recette site repete la connectivite, la video et un mouvement borne apres
association a l'organisation cliente. Les resultats sont attaches au robot
dans la plateforme.

## 8. Exploitation

- `oscarctl status` : etat du service et du conteneur.
- `oscarctl logs` : journaux bornes par rotation Docker.
- `oscarctl doctor` : configuration, agents et graphe ROS.
- `oscarctl restart` : redemarrage complet et coherent.
- `oscarctl stop` : arret des agents avec publication finale nulle.

Le timer de sante produit une verification chaque minute. Une supervision
centrale pourra ensuite collecter ce meme contrat de sante.

## 9. Mise a jour et retour arriere

Une mise a jour n'ecrase jamais la release courante :

1. installer la nouvelle version dans un nouveau repertoire ;
2. executer le prevol ;
3. basculer `/opt/oscar/current` ;
4. redemarrer et executer la recette courte ;
5. en cas d'echec, repointer le lien vers la release precedente et redemarrer.

Les migrations de configuration doivent etre compatibles avec au moins une
version precedente. La base constructeur n'est mise a jour qu'avec une matrice
de compatibilite validee.

## 10. Retrait du service

Le retrait arrete le runtime, revoque les credentials, retire le robot de son
organisation, supprime l'acces Tailscale puis efface `/etc/oscar/credentials`.
Les journaux d'audit restent sur le plan de controle selon la politique de
conservation.
