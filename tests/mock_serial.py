import time

class MockSerial:
    """Un faux port série qui se fait passer pour l'ESP32."""
    def __init__(self, port, baud, timeout=0.1):
        self.port = port
        self.is_open = True
        self.start_time = time.time()
        self.tirette_tiree = False
        print(f"[MOCK] Faux port série ouvert sur {port}")

    def reset_input_buffer(self):
        pass

    def write(self, data):
        # Au lieu d'envoyer au matériel, on affiche la commande dans la console
        commande = data.decode('ascii', errors='ignore').strip()
        print(f"   [ESP32 SIMULÉ EXÉCUTE] -> {commande}")

    def read(self, size=128):
        # On simule le temps de lecture
        time.sleep(0.1) 
        
        # Au bout de 3 secondes, on simule quelqu'un qui tire la tirette
        if not self.tirette_tiree and (time.time() - self.start_time > 3.0):
            self.tirette_tiree = True
            print("[MOCK] >>> TIRETTE TIRÉE VIRTUELLEMENT <<<")
            return b"EVT:START\n"
        
        # On renvoie une fausse position fixe et un sonar dégagé en boucle
        return b"POS:0.0,0.0,0.0\nSONAR:9999\n"

    def close(self):
        self.is_open = False
        print("[MOCK] Port série fermé.")