import cv2
import time


class Camera:
    """
    Classe gérant une caméra USB avec OpenCV

    derniereFrame : dernière frame capturée
    heureDerniereFrame : timestamp de la dernière capture
    """

    def __init__(self, index_camera=0):
        # Ouvre la caméra USB
        self.cap = cv2.VideoCapture(index_camera)

        # Configuration de la résolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920/2)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080/2)

        if not self.cap.isOpened():
            raise RuntimeError("Impossible d'ouvrir la caméra USB")

        self.derniereFrame = None
        self.heureDerniereFrame = None

    def actualiserFrame(self):
        """
        Capture une nouvelle frame et met à jour l'heure
        """
        ret, frame = self.cap.read()

        if not ret:
            raise RuntimeError("Erreur lors de la capture vidéo")

        self.derniereFrame = frame
        self.heureDerniereFrame = time.time()

    def detruire(self):
        """
        Libère les ressources de la caméra
        """
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    cam = Camera()

    while True:
        cam.actualiserFrame()

        cv2.imshow("Camera USB", cam.derniereFrame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.detruire()
