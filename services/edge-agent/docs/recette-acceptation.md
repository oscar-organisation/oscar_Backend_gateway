# Recette d'acceptation robot

Chaque ligne doit etre horodatee avec le numero de serie, le profil et la
version OSCAR Edge.

## A. Materiel et base ROS

- [ ] Camera detectee avec un identifiant stable.
- [ ] Controleur moteur detecte et sans alarme batterie.
- [ ] Heure synchronisee par NTP.
- [ ] Image constructeur conforme a l'empreinte du profil.
- [ ] Une seule source OSCAR publie sur `/cmd_vel` en mode teleoperation.
- [ ] Le topic camera conserve la cadence cible pendant cinq minutes.

## B. Identite et acces

- [ ] Identifiant robot identique dans la plateforme et `/etc/oscar/robot.env`.
- [ ] Room du robot distincte des rooms de demonstration.
- [ ] Identites media et commande distinctes.
- [ ] Credentials lisibles uniquement par root et non presents dans l'image.
- [ ] `oscarctl preflight` termine sans erreur.

## C. Video

- [ ] Track `camera-front` visible dans le cockpit 2D.
- [ ] Resolution publiee : 640 x 480.
- [ ] Cible : 30 FPS ; mesure acceptee sur le ROSMASTER actuel : >= 27 FPS.
- [ ] Orientation conforme au montage physique.
- [ ] Absence de file d'images anciennes (QoS depth 1).
- [ ] Reconnexion automatique apres coupure reseau de 30 secondes.

## D. Commande et securite

- [ ] Aucun mouvement au demarrage.
- [ ] Aucun mouvement sans deadman.
- [ ] Avant/arriere, lateral et rotation suivent la convention du profil.
- [ ] Relachement du deadman : vitesse nulle immediate.
- [ ] Perte de paquets : commande nulle en moins de 300 ms.
- [ ] Sortie cockpit/deconnexion : commande nulle.
- [ ] Limites de vitesse mesurees conformes au profil.
- [ ] Mode bras bloque la base et respecte les limites articulaires.
- [ ] Arret materiel prioritaire et teste.

## E. Robustesse

- [ ] Redemarrage du conteneur apres arret force d'un agent.
- [ ] Redemarrage complet du robot sans intervention humaine.
- [ ] `oscarctl doctor` valide camera, `/cmd_vel` et les deux agents.
- [ ] Test continu de 30 minutes sans derive CPU/memoire ni accumulation video.
- [ ] Retour a la release precedente teste une fois avant livraison.

## Livrables de preuve

- sortie de `oscarctl version` et `oscarctl doctor` ;
- capture des participants/tracks de la room ;
- mesure de cadence, gigue et latence de commande ;
- resultat du test watchdog ;
- signature du technicien et du responsable de site.
