# Interfaces ROS du chassis

Les types de messages que le runtime publie et qui n'existent pas dans ROS 2
lui-meme. Ils viennent du constructeur et sont recopies ici, a l'identique,
pour que l'image OSCAR se construise sans l'image constructeur.

| Paquet | Origine | Utilise par |
|---|---|---|
| `arm_msgs` | `/root/yahboomcar_ws/src/arm_msgs` de l'image ROSMASTER M3 Pro | `robot_control.py`, topic `/arm_joint` |

Un message doit rester identique, au champ pres, a celui du constructeur :
DDS compare les types, et un champ different rend les deux cotes muets l'un
pour l'autre sans aucune erreur.
