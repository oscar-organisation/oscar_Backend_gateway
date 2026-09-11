# Migration du ROSMASTER M3 Pro actuel

Le robot de demonstration fonctionne aujourd'hui avec des scripts ajoutes au
demarrage du conteneur constructeur. La migration vers OSCAR Edge doit etre
faite apres la demonstration, sans modifier le chemin actif avant validation.

## Inventaire a capturer

1. Image et commande exactes du conteneur `m3pro`.
2. Workspaces sources et chemins de `setup.bash`.
3. Regles udev et devices serie/camera.
4. Fichiers de lancement camera, `YB_Node` et bras.
5. Services/timers OSCAR actuellement actifs.
6. Profils DDS effectifs et variables ROS.
7. Credentials et room, sans les enregistrer dans Git.

## Strategie

1. Construire l'image OSCAR derivee de l'image `m3pro` exacte.
2. Lancer `oscar-edge` en mode diagnostic avec la sortie de commande desactivee.
3. Verifier la camera et la presence du subscriber constructeur `/cmd_vel`.
4. Arreter les anciens launchers OSCAR afin d'eviter les doubles participants.
5. Activer le service canonique et executer la recette roues levees.
6. Conserver les sauvegardes existantes jusqu'a validation sur deux redemarrages.

Les modifications historiques de `container_autostart.sh`, les launchers
ponctuels et les credentials copies dans `/root` deviennent alors obsoletes.
Ils ne seront supprimes qu'apres comparaison de leur comportement avec la
release canonique et archivage de la preuve de recette.

## Point DDS

Le conteneur OSCAR utilise `network_mode: host`, le meme `ROS_DOMAIN_ID` et le
meme middleware que la base constructeur. On conserve les transports UDP
natifs de Fast DDS. Aucun profil lie uniquement a `127.0.0.1` ni locator
metatrafic fixe ne doit etre injecte : ces variantes ont deja casse la
decouverte entre la camera, le bridge et `YB_Node`.
