import serial
import time
from serial_link import SerialLink

PORT = "/dev/serial0"  # Port série matériel par défaut de la Pi
BAUD = 115200

print(f"--- TEST DE COMMUNICATION SERIE ---")
print(f"Ouverture du port {PORT} à {BAUD} bauds...")

try:
    ser = serial.Serial(PORT, BAUD, timeout=1.0)
    print("Connexion établie ! En attente des données de l'ESP32...")
    print("(Appuie sur Ctrl+C pour quitter)\n")

    while True:
        if ser.in_waiting > 0:
            # On lit la ligne, on la décode et on enlève les espaces/retours à la ligne
            ligne = ser.readline().decode('ascii', errors='ignore').strip()
            if ligne:
                print(f"ESP32 dit -> {ligne}")
        time.sleep(0.01)

except serial.SerialException as e:
    print(f"ERREUR : Impossible d'ouvrir le port série : {e}")
    print("Astuce : Le port série matériel (serial0) est-il bien activé dans raspi-config ?")
except KeyboardInterrupt:
    print("\nArrêt du test.")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Port fermé proprement.")
