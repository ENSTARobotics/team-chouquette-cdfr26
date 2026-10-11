import time
import math

class MockSerial:
    """Un port série virtuel avec simulation physique complète du robot."""
    
    def __init__(self, port, baud, timeout=0.1):
        self.port = port
        self.is_open = True
        self.start_time = time.time()
        self.last_update = time.time()
        self.tirette_tiree = False
        
        # --- État physique virtuel ---
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        
        # Vitesses actuelles des roues (mm/s)
        self.vl = 0.0
        self.vr = 0.0
        
        # --- Constantes du modèle physique ---
        self.MAX_SPEED = 600.0  # Vitesse max en mm/s (à PWM 255)
        self.ENTRAXE = 400.0    # Distance entre les roues en mm
        
        print(f"[MOCK] ESP32 avec physique virtuelle lancé sur {port}")

    def reset_input_buffer(self):
        pass

    def write(self, data):
        commande = data.decode('ascii', errors='ignore').strip()
        # On n'affiche pas les commandes MOT: en boucle pour ne pas polluer l'écran,
        # on affiche seulement les événements marquants.
        if not commande.startswith("MOT:"):
            print(f"   [ESP32 VIRTUEL] Action -> {commande}")
        
        if commande.startswith("SETPOS:"):
            # Initialisation de la position de départ demandée par la Pi
            parts = commande[7:].split(',')
            if len(parts) == 3:
                self.x, self.y, self.theta = float(parts[0]), float(parts[1]), float(parts[2])
                
        elif commande.startswith("MOT:"):
            # Calcul des vitesses cibles basées sur le PWM
            parts = commande[4:].split(',')
            if len(parts) == 4:
                d1, p1, d2, p2 = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                
                # Application de la symétrie de tes moteurs !
                # Moteur 1 (gauche) : 1 = avant
                sign_l = 1 if d1 == 1 else -1
                # Moteur 2 (droit) : 0 = avant
                sign_r = 1 if d2 == 0 else -1
                
                self.vl = (p1 / 255.0) * self.MAX_SPEED * sign_l
                self.vr = (p2 / 255.0) * self.MAX_SPEED * sign_r
                
        elif commande == "STOP":
            self.vl = 0.0
            self.vr = 0.0

    def read(self, size=128):
        # On tourne à 20Hz (comme ton vrai ESP32)
        time.sleep(0.05) 
        
        now = time.time()
        dt = now - self.last_update
        self.last_update = now
        
        # --- MOTEUR PHYSIQUE (Cinématique) ---
        # Vitesse linéaire globale du robot
        v = (self.vl + self.vr) / 2.0
        # Vitesse de rotation (rad/s)
        omega = (self.vr - self.vl) / self.ENTRAXE
        
        # Mise à jour du cap
        self.theta += omega * dt
        # Normalisation de l'angle entre -PI et +PI
        while self.theta > math.pi: self.theta -= 2 * math.pi
        while self.theta < -math.pi: self.theta += 2 * math.pi
        
        # Mise à jour de la position (Trigonométrie basique)
        self.x += v * math.cos(self.theta) * dt
        self.y += v * math.sin(self.theta) * dt
        
        # --- ÉVÉNEMENTS ---
        if not self.tirette_tiree and (now - self.start_time > 3.0):
            self.tirette_tiree = True
            print("\n[MOCK] >>> TIRETTE TIRÉE ! LE MATCH COMMENCE <<<")
            return b"EVT:START\n"
        
        # --- ENVOI DES DONNÉES À LA PI ---
        msg = f"POS:{self.x:.1f},{self.y:.1f},{self.theta:.4f}\nSONAR:9999\n"
        return msg.encode('ascii')

    def close(self):
        self.is_open = False
        print("[MOCK] Fin de la simulation.")