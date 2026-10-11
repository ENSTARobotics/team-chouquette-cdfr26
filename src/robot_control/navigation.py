"""
navigation.py
--------------
Navigation point-à-point pour le gros robot.

Stratégie simple en 2 phases :
  1. ROTATION : se tourner vers le point cible (asservissement en cap)
  2. AVANCE    : avancer en ligne droite tout en corrigeant le cap

On utilise les sonars frontaux pour stopper l'avance en cas d'obstacle.

Convention :
  - Repère table : X horizontal (0..3000 mm), Y vertical (0..2000 mm)
  - theta = 0 -> robot pointe vers +X
  - theta croît dans le sens trigonométrique (anti-horaire)
  - Sonars : 0 = avant-gauche, 1 = avant-droit, 2 = arrière, 3 = côté
    (à adapter à votre implantation)
"""

import math
import time
from .serial_link import SerialLink


# ============================================================================
#                       PARAMÈTRES À CALIBRER
# ============================================================================
# Vitesses (PWM 0..255)
PWM_CRUISE        = 180     # vitesse de croisière
PWM_APPROACH      = 110     # vitesse réduite en approche
PWM_TURN          = 130     # vitesse de rotation sur place
PWM_MIN           = 80      # PWM en dessous duquel le moteur ne tourne pas

# Tolérances
TOL_DIST_MM       = 25.0    # on considère qu'on est arrivé à <25 mm
TOL_THETA_RAD     = 0.05    # ~3°
DIST_APPROACH_MM  = 200.0   # passage en mode lent

# Sécurité sonars
OBSTACLE_FRONT_MM = 800     # distance frontale en dessous de laquelle on freine
OBSTACLE_STOP_MM  = 700     # distance frontale -> arrêt

# Coefficients PID en cap (corrige la direction pendant l'avance)
KP_HEADING        = 80.0


# ============================================================================
#                       UTILITAIRES GÉOMÉTRIE
# ============================================================================
def wrap_angle(a: float) -> float:
    """Ramène un angle dans [-pi, +pi]."""
    while a >  math.pi: a -= 2 * math.pi
    while a < -math.pi: a += 2 * math.pi
    return a


def distance(x1, y1, x2, y2) -> float:
    return math.hypot(x2 - x1, y2 - y1)


# ============================================================================
#                       NAVIGATION
# ============================================================================
class Navigator:
    """
    Pilote le robot vers des points (x, y) sur la table.
    Utilise les retours d'odométrie de l'ESP32 via SerialLink.
    """

    def __init__(self, link: SerialLink):
        self.link = link

    # ------------------------------------------------------------- bas niveau
    def _drive(self, left_pwm: float, right_pwm: float):
        """
        Envoie des commandes aux 2 moteurs. Les PWM peuvent être signées :
        négatif = marche arrière. Le mapping (gauche/droite) dépend de votre
        câblage : ici moteur 1 = gauche, moteur 2 = droite.
        """
        d1 = 1 if left_pwm  >= 0 else 0
        d2 = 1 if right_pwm >= 0 else 0
        p1 = min(255, max(0, abs(int(left_pwm))))
        p2 = min(255, max(0, abs(int(right_pwm))))
        # Si on demande un mouvement mais que le PWM est sous le seuil mort,
        # on force au minimum exploitable.
        if 0 < p1 < PWM_MIN: p1 = PWM_MIN
        if 0 < p2 < PWM_MIN: p2 = PWM_MIN
        self.link.set_motors(d1, p1, d2, p2)

    def stop(self):
        self.link.stop_motors()

    # ------------------------------------------------------------- sécurité sonars
    def _front_obstacle(self) -> float:
        """Renvoie la plus petite distance frontale détectée (mm)."""
        s = self.link.state.sonars
        print(s)
        if len(s) >= 2:
            return min(s[0],s[1])
        elif len(s) == 1:
            return s[0]
        return 9999.0

    # ------------------------------------------------------------- rotation sur place
    def turn_to(self, target_theta: float, timeout_s: float = 5.0) -> bool:
        """
        Tourne le robot pour atteindre le cap target_theta (rad).
        Renvoie True si on atteint la tolérance, False si timeout.
        """
        t0 = time.time()
        while time.time() - t0 < timeout_s:

            err = wrap_angle(target_theta - self.link.state.theta)
            if abs(err) < TOL_THETA_RAD:
                self.stop()
                return True

            # Rotation sur place : roues en sens opposés
            pwm = PWM_TURN if abs(err) > 0.3 else max(PWM_MIN, PWM_TURN * 0.6)
            if err > 0:
                # tourner à gauche (sens trigonométrique) : roue G recule, roue D avance
                self._drive(-pwm, +pwm)
            else:
                self._drive(+pwm, -pwm)

            time.sleep(0.02)

        self.stop()
        return False

    # ------------------------------------------------------------- avance vers un point
    def goto(self, target_x: float, target_y: float,
             timeout_s: float = 15.0,
             stop_on_obstacle: bool = True) -> bool:
        """
        Se rend au point (target_x, target_y) sur la table (mm).
        Stratégie : on se tourne d'abord, puis on avance avec correction de cap.
        """
        # 1. Orientation initiale
        x0, y0 = self.link.state.x, self.link.state.y
        target_theta = math.atan2(target_y - y0, target_x - x0)
        if not self.turn_to(target_theta, timeout_s=4.0):
            self.stop()
            return False

        # 2. Avance avec correction continue
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            

            x, y, theta = self.link.state.x, self.link.state.y, self.link.state.theta
            d = distance(x, y, target_x, target_y)

            if d < TOL_DIST_MM:
                self.stop()
                return True

            # --- Sécurité sonars ---
            if stop_on_obstacle:
                front = self._front_obstacle()
                if front < OBSTACLE_STOP_MM:
                    self.stop()
                    # On attend que l'obstacle s'éloigne (max 3 s) avant d'abandonner
                    t_wait = time.time()
                    while time.time() - t_wait < 3.0:
                        if self._front_obstacle() > OBSTACLE_STOP_MM + 50:
                            break
                        time.sleep(0.1)
                    else:
                        return False
                    continue

            # --- Asservissement en cap ---
            desired_theta = math.atan2(target_y - y, target_x - x)
            err_theta = wrap_angle(desired_theta - theta)

            # Si on s'est trop écarté, on s'arrête et on retourne
            if abs(err_theta) > 0.6:
                self.stop()
                self.turn_to(desired_theta, timeout_s=3.0)
                continue

            # PWM de base, réduit en approche, et freiné par les sonars
            base = PWM_APPROACH if d < DIST_APPROACH_MM else PWM_CRUISE
            front = self._front_obstacle()
            if stop_on_obstacle and front < OBSTACLE_FRONT_MM:
                # ralentissement progressif
                base = int(base * (front - OBSTACLE_STOP_MM)
                                / (OBSTACLE_FRONT_MM - OBSTACLE_STOP_MM))
                base = max(PWM_MIN, base)

            # Correction proportionnelle : on penche les vitesses des 2 roues
            correction = KP_HEADING * err_theta
            left  = base - correction
            right = base + correction
            self._drive(left, right)
            time.sleep(0.02)

        self.stop()
        return False

    # ------------------------------------------------------------- marche arrière
    def back_off(self, distance_mm: float, timeout_s: float = 5.0) -> bool:
        """Recule de `distance_mm` à partir de la position actuelle."""
        x0, y0 = self.link.state.x, self.link.state.y
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            x, y = self.link.state.x, self.link.state.y
            if distance(x0, y0, x, y) >= distance_mm:
                self.stop()
                return True
            self._drive(-PWM_APPROACH, -PWM_APPROACH)
            time.sleep(0.02)
        self.stop()
        return False
