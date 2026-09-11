# Architecture embarquee OSCAR

## Principe

OSCAR Edge est une couche d'adaptation entre un robot ROS 2 et le plan de
controle OSCAR. Le navigateur ne publie jamais directement sur un moteur.

```text
Cockpit 2D / WebXR
        |
        | LiveKit video + DataPacket oscar.xr.input
        v
Serveur LiveKit OSCAR
        |
        +--------------------------+
        | Robot : oscar-edge       |
        |  command_agent           | -> mapping + deadman + watchdog
        |        |                 |
        |        v                 |
        |  adaptateur ROS 2        | -> /cmd_vel, /arm_joint
        |                          |
        |  /camera/...             | -> media_agent -> camera-front
        +--------------------------+
                    |
                    v
        Pilotes constructeur / MCU / actionneurs
```

## Quatre couches contractuelles

1. **Materiel constructeur** : calculateur, camera, bus serie/CAN, moteurs,
   controleur temps reel et arret d'urgence.
2. **Base robot ROS 2** : Ubuntu, Docker, ROS 2 Humble, messages constructeur,
   pilotes et topics. Cette base est consideree comme une dependance livree par
   le profil robot.
3. **OSCAR Edge** : agents media/commande, mapping, securite, supervision et
   diagnostic. Cette couche est identique pour toute la flotte.
4. **Plan de controle** : organisation, robot, room, permissions, emission et
   rotation des credentials.

Un nouveau modele de robot ne doit modifier que son profil et son adaptateur
ROS. Le protocole LiveKit, le watchdog et l'exploitation restent inchanges.

## Identite canonique

Chaque robot recoit un identifiant immuable, par exemple `oscar-02`. Il donne
lieu a des ressources distinctes :

| Ressource | Convention |
|---|---|
| Robot plateforme | `oscar-02` |
| Room LiveKit | attribuee par l'API au robot, jamais partagee avec une demo |
| Participant media | `robot-oscar-02` |
| Participant commande | `robot-oscar-02-command` |
| Track video | `camera-front` |
| Topic entree | `oscar.xr.input` |
| Topic diagnostic | `oscar.robot.command` |

La video de demonstration possede son propre robot logique, sa propre room et
ses propres credentials. Elle ne constitue jamais un fallback silencieux pour
un robot physique.

## Securite de mouvement

- Demarrage a vitesse nulle.
- Presence operateur obligatoire pour tout mouvement.
- Limites de vitesse appliquees avant ROS puis bornees dans l'adaptateur.
- Commande ignoree apres 300 ms sans paquet frais.
- Publication d'un `Twist` nul au relachement, a la deconnexion et a l'arret.
- Commande bras et commande base mutuellement exclusives.
- L'arret materiel constructeur demeure prioritaire sur OSCAR.

Tailscale appartient au plan de maintenance (SSH, diagnostic, mise a jour). Le
flux LiveKit et les commandes temps reel ne doivent pas en dependre.
