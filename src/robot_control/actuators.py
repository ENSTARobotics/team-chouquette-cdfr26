"""
actuators.py
-------------
Logique métier des servos du gros robot.

Votre stratégie :
  - Le robot ne retourne PAS les caisses : il prend uniquement celles qui sont
    déjà du bon côté (couleur de votre équipe vers le haut).
  - 4 servos AVANT (S1..S4) jouent le rôle de "barrières" à l'avant du robot.
       OUVERTS  -> le robot peut glisser sous les caisses, qui se logent
                   sous le châssis.
       FERMÉS   -> les barrières maintiennent les caisses calées sous le robot
                   pendant le déplacement.
  - 1 servo ARRIÈRE (S5) joue le rôle de barrière arrière.
       FERMÉ    -> les caisses restent piégées sous le robot.
       OUVERT   -> on libère les caisses vers l'arrière en avançant
                   (ou en laissant tomber par gravité).

ATTENTION : adaptez les angles ci-dessous au sens de montage de vos servos.
Si une barrière monte au lieu de descendre, inversez OPEN/CLOSE pour ce servo.
"""

import time
from .serial_link import SerialLink


# ============================================================================
#                       ANGLES DES SERVOS (à calibrer)
# ============================================================================
# Servos avant : on définit OPEN et CLOSE par servo car ils peuvent être
# montés tête-bêche (gauche/droite, intérieur/extérieur).
FRONT_CLOSE  = {1:   0, 2:   0, 3:   0, 4:   0}    # barrière levée
FRONT_OPEN = {1:  100, 2:  100, 3:  100, 4:  100}    # barrière baissée pour caler

# Servo arrière
REAR_CLOSE  = 100      # barrière arrière baissée -> caisses retenues
REAR_OPEN   = 0     # barrière arrière levée   -> caisses libérées


# ============================================================================
#                       MANIPULATEUR DE CAISSES
# ============================================================================
class CrateHandler:
    """
    Encapsule les opérations métier de manipulation des caisses :
      - prepare_pickup   : s'apprêter à ramasser (avant ouvert, arrière fermé)
      - capture_crates   : refermer les barrières avant pour caler les caisses
      - release_crates   : ouvrir la barrière arrière pour libérer les caisses
      - reset_actuators  : remise en position de transport sans caisses
    """

    def __init__(self, link: SerialLink):
        self.link = link

    # ------------------------------------------------------- positions de base
    def prepare_pickup(self):
        """
        Phase 1 : on arrive sur une zone de ramassage.
        - Les 4 barrières avant sont OUVERTES : le robot peut glisser dessous.
        - La barrière arrière est FERMÉE : les caisses ne pourront pas sortir
          en passant par l'arrière pendant le ramassage.
        """
        self.link.set_all_servos(
            FRONT_OPEN[1], FRONT_OPEN[2], FRONT_OPEN[3], FRONT_OPEN[4],
            REAR_CLOSE
        )
        time.sleep(0.3)   # laisse le temps aux servos de bouger

    def capture_crates(self):
        """
        Phase 2 : le robot a glissé sous les caisses, on referme les barrières
        avant pour les caler sous le châssis pendant le transport.
        """
        self.link.set_all_servos(
            FRONT_CLOSE[1], FRONT_CLOSE[2], FRONT_CLOSE[3], FRONT_CLOSE[4],
            REAR_CLOSE
        )
        time.sleep(0.4)

    def release_crates(self, back_motion_callback=None):
        """
        Phase 3 : le robot est arrivé sur la zone de dépôt (garde-manger ou nid).
        On ouvre la barrière arrière, ce qui libère les caisses. Si on fournit
        `back_motion_callback`, on l'appelle juste après pour reculer en laissant
        les caisses sur place (méthode "barrière qui retient pendant qu'on recule").
        """
        # 1. On ouvre l'arrière
        self.link.set_servo(5, REAR_OPEN)
        time.sleep(0.3)

        # 2. (optionnel) le robot recule -> les caisses sont "raclées"
        #    par la barrière arrière qui les maintient à la position de dépôt
        if back_motion_callback:
            back_motion_callback()

        # 3. On peut aussi ouvrir l'avant pour libérer complètement
        self.link.set_all_servos(
            FRONT_OPEN[1], FRONT_OPEN[2], FRONT_OPEN[3], FRONT_OPEN[4],
            REAR_OPEN
        )
        time.sleep(0.2)

    def alternative_release(self):
        """
        Variante : le robot s'arrête, ouvre l'AVANT (pas l'arrière). C'est utile
        quand on dépose dans une zone où on a approché en marche avant et qu'on
        veut s'éloigner en avançant.
        """
        self.link.set_all_servos(
            FRONT_OPEN[1], FRONT_OPEN[2], FRONT_OPEN[3], FRONT_OPEN[4],
            REAR_CLOSE
        )
        time.sleep(0.3)

    def reset_actuators(self):
        """Position de repos : tout fermé (caisses ou pas)."""
        self.link.set_all_servos(
            FRONT_CLOSE[1], FRONT_CLOSE[2], FRONT_CLOSE[3], FRONT_CLOSE[4],
            REAR_CLOSE
        )
        time.sleep(0.3)

    def initial_position(self):
        """
        Position de départ du match : barrières avant ouvertes (prêt à attraper),
        arrière fermée. Identique à prepare_pickup() pour le moment.
        """
        self.prepare_pickup()
