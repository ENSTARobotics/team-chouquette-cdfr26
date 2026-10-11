"""
main.py
--------
Programme principal du robot Team Chouquette pour la Coupe de France 2026.

Déroulement d'un match (100 secondes) :
  1. Initialisation des liaisons série + des servos en position de départ.
  2. Attente de la tirette de départ (signal "EVT:START" envoyé par l'ESP32).
  3. Exécution séquentielle de la stratégie :
       - aller vers une zone de ramassage
       - glisser sous les caisses (servos avant ouverts)
       - refermer les servos avant pour caler les caisses
       - aller vers une zone de dépôt (garde-manger ou nid)
       - ouvrir le servo arrière, reculer -> caisses laissées en place
       - répéter
  4. Stop final : retour au nid avant la fin du match (points "ON EST MIEUX
     DANS SON NID").

Convention de table (Coupe de France 2026) :
  - table 3000 x 2000 mm
  - origine (0, 0) coin de la table
  - équipe BLEUE  : nid arrière côté X faible
  - équipe JAUNE  : nid arrière côté X élevé
  Adaptez les coordonnées de la séquence selon votre côté et votre stratégie
  réelle, après avoir mesuré les positions exactes sur la table de jeu.
"""

import math
import time
import sys

from .serial_link import SerialLink
from .navigation import Navigator
from .actuators import CrateHandler


# ============================================================================
#                       CONFIGURATION DU MATCH
# ============================================================================
SERIAL_PORT     = "/dev/serial0"   # UART de la Pi (GPIO 14/15)
MATCH_DURATION  = 100.0            # secondes
TEAM            = "BLEU"           # "BLEU" ou "JAUNE"


# ============================================================================
#                       POSITIONS DE LA TABLE
# ============================================================================
# À MESURER ET ADAPTER selon votre côté de table et votre stratégie.
# Toutes les coordonnées sont en mm, dans le repère (0,0) = coin de la table.

if TEAM == "BLEU":
    START_POSE = (225, 1775, 0.0)         # centre approx. du nid bleu, cap +X
    # Zone de ramassage la plus proche (à mesurer précisément)
    PICKUP_ZONES = [
        (600, 1700),
        (1100, 1700),
    ]
    # Garde-mangers où déposer les caisses
    DROP_ZONES = [
        (700, 1100),
        (1200, 1100),
    ]
    NID_FINAL = (225, 1775)
else:  # JAUNE
    START_POSE = (2775, 1775, math.pi)
    PICKUP_ZONES = [
        (2400, 1700),
        (1900, 1700),
    ]
    DROP_ZONES = [
        (2300, 1100),
        (1800, 1100),
    ]
    NID_FINAL = (2775, 1775)


# ============================================================================
#                       MACHINE D'ÉTAT DU MATCH
# ============================================================================
class MatchRunner:
    def __init__(self):
        self.link = SerialLink(SERIAL_PORT, 115200)
        self.nav: Navigator = None
        self.crates: CrateHandler = None
        self.t_start: float = 0.0

    # -------------------------------------------------------------- helpers
    def time_left(self) -> float:
        return MATCH_DURATION - (time.time() - self.t_start)

    def log(self, msg: str):
        t = time.time() - self.t_start if self.t_start else 0.0
        print(f"[{t:6.2f}s] {msg}", flush=True)


    # -------------------------------------------------------------- séquences
    def pickup_sequence(self, pickup_xy: tuple) -> bool:
        """
        Va sur une zone de ramassage et capture les caisses.
        Renvoie True si succès, False sinon.
        """
        px, py = pickup_xy
        self.log(f"Pickup -> ({px}, {py})")

        # 1. Barrières avant OUVERTES, arrière FERMÉE
        self.crates.prepare_pickup()

        # 2. On vise un point juste avant la zone pour s'approcher droit
        if not self.nav.goto(px, py, timeout_s=12.0):
            self.log("Échec navigation vers pickup")
            return False
        if self.emergency_check(): return False

        # 3. On a glissé sous les caisses : on referme les barrières avant
        self.log("Capture des caisses")
        self.crates.capture_crates()
        return True

    def drop_sequence(self, drop_xy: tuple) -> bool:
        """Va sur une zone de dépôt et libère les caisses par l'arrière."""
        dx, dy = drop_xy
        self.log(f"Drop -> ({dx}, {dy})")

        if not self.nav.goto(dx, dy, timeout_s=12.0):
            self.log("Échec navigation vers drop")
            return False
        if self.emergency_check(): return False

        # Libération : on ouvre l'arrière puis on recule de 200 mm.
        # La barrière arrière, encore relevée, "racle" les caisses contre la
        # ligne de la zone et les y maintient pendant qu'on recule.
        self.log("Libération des caisses")
        def reculer():
            self.nav.back_off(200.0, timeout_s=4.0)
        self.crates.release_crates(back_motion_callback=reculer)
        return True

    def return_to_nest(self):
        """Retour au nid avant la fin du match (+5 ou +10 points)."""
        self.log("Retour au nid")
        nx, ny = NID_FINAL
        self.crates.reset_actuators()
        # On laisse une marge de 6 s pour rentrer
        self.nav.goto(nx, ny, timeout_s=8.0)
        self.link.stop_motors()

    # -------------------------------------------------------------- run
    def run(self):
        # 1. Démarrage liaison série
        self.log("Ouverture liaison ESP32...")
        print("Ouverture liaison ESP32")
        self.link.start()
        time.sleep(0.5)

        self.nav    = Navigator(self.link)
        self.crates = CrateHandler(self.link)

        # 2. Calibration : on dit à l'ESP32 où on est (position de départ)
        sx, sy, sth = START_POSE
        self.link.set_position(sx, sy, sth)
        self.crates.initial_position()
        time.sleep(0.3)

        # 3. Attente tirette
        self.log("En attente de la tirette de départ (PIN 13 ESP32)...")
        while not self.link.state.match_started:
            print(f"DEBUG:Attente....etat actuel : {self.link.state}" , flush = True)
            time.sleep(1)
        print(self.link.state)
        

        # 4. Match démarré !
        self.t_start = time.time()
        self.log(">>> MATCH START <<<")

        try:
            # Stratégie : alterner pickup / drop tant qu'il reste du temps
            for pickup_xy, drop_xy in zip(PICKUP_ZONES, DROP_ZONES):
                # Garde une marge de sécurité pour le retour au nid (~10 s)
                if self.time_left() < 15.0:
                    break
                if not self.pickup_sequence(pickup_xy):
                    continue
                if self.time_left() < 12.0:
                    break
                self.drop_sequence(drop_xy)

            # Retour au nid en fin de match
            self.return_to_nest()

        finally:
            # 5. Fin du match : tout arrêter proprement
            self.log("Fin de séquence -> arrêt")
            self.link.stop_motors()
            self.crates.reset_actuators()
            time.sleep(0.2)
            self.link.close()


# ============================================================================
#                       POINT D'ENTRÉE
# ============================================================================
if __name__ == "__main__":
    try:
        MatchRunner().run()
    except KeyboardInterrupt:
        print("\nInterruption clavier - arrêt", flush=True)
        sys.exit(0)
