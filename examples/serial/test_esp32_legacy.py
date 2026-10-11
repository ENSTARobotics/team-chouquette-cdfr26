import serial
import time

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout = 1)
time.sleep(2) #pour laisser l'ESP32 se réinitialiser à la connexion

print("Taper '1' pour ON '0' pour OFF (ou 'q' pour quitter)")

try :
    while True:
        commande = input("Commande pour l'ESP32 : ")
        
        if commande == 'q':
            break
        
        ser.write((commande + '\n').encode('utf-8'))
        
        time.sleep(0.1)
        while ser.in_waiting > 0 :
            reponse = ser.readline().decode('utf-8').rstrip()
            print(f"L'ESP32 confirme : {reponse}")

except KeyboardInterrupt:
    print("Fermeture...")
finally :
    ser.close()