from camera import Camera
from codearuco import CodeAruco
from plateau import Plateau
import numpy as np
import cv2

class Partie:
    def __init__(self):
        self.camera = Camera()
        self.listeCodeAruco = {id: CodeAruco(id) for id in range(100)}
        self.zoneplateau = Plateau()

    def actualiserAruco(self):
        self.camera.actualiserFrame()
        if self.camera.derniereFrame is None:
            return

        # Compatibilité toutes versions OpenCV
        dictionnaire = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
        parametres = cv2.aruco.DetectorParameters()
        
        # Gestion de l'erreur AttributeError (version d'OpenCV)
        if hasattr(cv2.aruco, 'ArucoDetector'):
            detector = cv2.aruco.ArucoDetector(dictionnaire, parametres)
            coins, ids, _ = detector.detectMarkers(self.camera.derniereFrame)
        else:
            coins, ids, _ = cv2.aruco.detectMarkers(self.camera.derniereFrame, dictionnaire, parameters=parametres)

        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                if marker_id in self.listeCodeAruco:
                    pts = coins[i][0]
                    self.listeCodeAruco[marker_id].actualiser(pts, self.camera.heureDerniereFrame)
            
            # Mise à jour du plateau avec les IDs 20, 21, 22, 23
            ids_p = [22, 23, 21, 20]
            if all(self.listeCodeAruco[i].centre is not None for i in ids_p):
                self.zoneplateau.actualiser_plateau(
                    self.listeCodeAruco[22].centre,
                    self.listeCodeAruco[23].centre,
                    self.listeCodeAruco[21].centre,
                    self.listeCodeAruco[20].centre
                )

    def obtenir_position_plateau(self, id_marqueur):
        """Renvoie (x, y) du marqueur dans le repère du plateau (0-3000, 0-2000)"""
        marqueur = self.listeCodeAruco.get(id_marqueur)
        if marqueur and marqueur.centre is not None and self.zoneplateau._H_img2plane is not None:
            point_pixel = np.array([[marqueur.centre]], dtype=np.float32)
            point_plateau = cv2.perspectiveTransform(point_pixel, self.zoneplateau._H_img2plane)
            return point_plateau[0][0]
        return None

    def afficher(self):
        if self.camera.derniereFrame is None: return
        for code in self.listeCodeAruco.values():
            if code.centre is not None:
                code.afficher(self.camera.derniereFrame)
        self.zoneplateau.afficher(self.camera.derniereFrame)

if __name__ == "__main__" :
    partie = Partie()
    while True:
        partie.actualiserAruco()
        
        # Test du code ArUco 70
        pos_70 = partie.obtenir_position_plateau(70)
        if pos_70 is not None:
            x, y = pos_70
            #cv2.putText(partie.camera.derniereFrame, f"ID 70: x={int(x)} y={int(y)}", 
            #            (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            print(f"Position Robot (70): x={x:.1f}, y={y:.1f}")

        partie.afficher()
        cv2.imshow("Plateau", partie.camera.derniereFrame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    partie.camera.detruire()