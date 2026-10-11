import cv2
import numpy as np

class CodeAruco:
    """
    Classe représentant un marqueur ArUco
    id : identifiant du marqueur
    coins : coordonnées des coins du marqueur (4x2 numpy array)
    centre : coordonnées du centre du marqueur (1x2 numpy array)
    heureDerniereDetection : heure de la dernière détection du marqueur
    """

    def __init__(self, id):
        """
        Initialise un marqueur ArUco avec son identifiant
        
        id : identifiant du marqueur (numero arUco)
        """
        self.id = id
        self.coins = None
        self.centre = None
        self.heureDerniereDetection = None

    def afficher(self, image):
        """
        Dessine le marqueur sur l'image passée en argument

        image : image sur laquelle dessiner le marqueur
        """
        if self.coins is None or self.centre is None:
            return  # rien à dessiner

        # carré vert autour du marqueur
        cv2.polylines(image, [self.coins.astype(int)], True, (0, 255, 0), 2)
        # ID en rouge
        cv2.putText(image, str(self.id),
                    (int(self.centre[0]), int(self.centre[1])),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        # centre en bleu
        cv2.circle(image, (int(self.centre[0]), int(self.centre[1])), 5, (255, 0, 0), -1)

    def actualiser(self, coins, tps):
        """
        Met à jour les informations du marqueur

        coins : coordonnées des coins du marqueur (4x2 numpy array)
        centre : coordonnées du centre du marqueur (1x2 numpy array)
        tps : heure de la détection
        """
        self.coins = coins
        self.centre = np.mean(coins, axis=0)
        self.heureDerniereDetection = tps

    def __str__(self):
        """
        Représentation sous forme de chaîne de caractères du marqueur
        """
        return f"CodeAruco(id={self.id}, coins={self.coins}, centre={self.centre})"


if __name__ == "__main__" :
    pass