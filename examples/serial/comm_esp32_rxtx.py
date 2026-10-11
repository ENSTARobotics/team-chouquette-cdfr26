import serial
import time
import threading

# Configuration du port
try:
    ser = serial.Serial(
        port='/dev/serial0',
        baudrate=115200,
        timeout=1
    )
    print("Connexion UART OK avec ESP32")
except Exception as e:
    print(f"Erreur UART : {e}")
    exit()

def lecture_uart():
    """Fonction qui tourne en arrière-plan pour lire les messages"""
    while True:
        if ser.in_waiting > 0:
            try:
                ligne = ser.readline().decode('utf-8', errors='ignore').rstrip()
                if ligne:
                    print(f"\rESP32 : {ligne}\nEnvoyer : ", end="")
            except Exception as e:
                print(f"\nErreur lecture : {e}")

# Lancement du thread de lecture (daemon=True pour qu'il s'arrête avec le programme)
thread_reception = threading.Thread(target=lecture_uart, daemon=True)
thread_reception.start()

try:
    while True:
        # L'envoi reste dans la boucle principale
        message = input("Envoyer : ")
        if message:
            ser.write((message + '\n').encode('utf-8'))
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nArrêt programme")
    ser.close()
