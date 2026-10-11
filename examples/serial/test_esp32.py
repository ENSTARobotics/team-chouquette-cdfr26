import serial
import time

try :
    ser = serial.Serial('/dev/ttyUSB0',115200,timeout=1)
    ser.reset_input_buffer()
    print("Connexion reussie avec l'ESP32 !")
except :
    print("Erreur : impossible de trouver l'ESP32 sur /dev/ttyUSB0")
    exit()
    
try :
    while True :
        #on vérifie si l'ESP32 a envoyé quelque chose
        if ser.in_waiting > 0 :
            ligne = ser.readline().decode('utf-8').rstrip()
            print(f"ESP32 dit : {ligne}")
            
        time.sleep(0.1)
        
except KeyboardInterrupt :
    print("\nProgramme arrete par l'utilisateur")
    ser.close()