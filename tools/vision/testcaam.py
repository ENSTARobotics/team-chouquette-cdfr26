import cv2
import time


class DetecteurCamera:

    def __init__(self):

        self.backends = {
            "DEFAULT": None,
            "DSHOW": cv2.CAP_DSHOW,
            "MSMF": cv2.CAP_MSMF,
            "V4L2": cv2.CAP_V4L2,
        }

        self.resolutions = [
            (320, 240),
            (640, 480),
            (800, 600),
            (1280, 720),
            (1920, 1080),
        ]

    def trouver_cameras(self, max_index=10):

        cameras = []

        print("=== SCAN CAMERAS ===\n")

        for i in range(max_index):

            cap = cv2.VideoCapture(i)

            if cap.isOpened():

                ret, frame = cap.read()

                if ret and frame is not None:
                    print(f"✅ Camera trouvée : {i}")
                    cameras.append(i)

            cap.release()

        return cameras

    def tester_configuration(self, index, backend_name, backend):

        print("\n" + "=" * 60)
        print(f"TEST CAMERA {index} | BACKEND {backend_name}")
        print("=" * 60)

        # ouverture
        if backend is None:
            cap = cv2.VideoCapture(index)
        else:
            cap = cv2.VideoCapture(index, backend)

        if not cap.isOpened():
            print("❌ ouverture impossible")
            return None

        meilleur = None

        for w, h in self.resolutions:

            print(f"\nTest {w}x{h}")

            # MJPG
            cap.set(
                cv2.CAP_PROP_FOURCC,
                cv2.VideoWriter_fourcc(*'MJPG')
            )

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)

            time.sleep(0.5)

            ret, frame = cap.read()

            rw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            rh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            if ret and frame is not None:

                print(f"✅ OK -> {rw}x{rh} | FPS {fps}")

                meilleur = {
                    "index": index,
                    "backend_name": backend_name,
                    "backend": backend,
                    "width": rw,
                    "height": rh,
                    "fps": fps,
                }

            else:
                print("❌ ECHEC")

        cap.release()

        return meilleur

    def trouver_meilleure_configuration(self):

        cameras = self.trouver_cameras()

        if not cameras:
            print("Aucune caméra trouvée")
            return None

        meilleur_global = None

        for cam in cameras:

            for backend_name, backend in self.backends.items():

                try:

                    resultat = self.tester_configuration(
                        cam,
                        backend_name,
                        backend
                    )

                    if resultat is not None:
                        meilleur_global = resultat

                except Exception as e:
                    print("ERREUR :", e)

        return meilleur_global


def filmer(config):

    print("\n" + "=" * 60)
    print("CONFIGURATION FINALE")
    print("=" * 60)

    print(f"INDEX CAMERA : {config['index']}")
    print(f"BACKEND      : {config['backend_name']}")
    print(f"RESOLUTION   : {config['width']}x{config['height']}")
    print(f"FPS          : {config['fps']}")

    print("\n=== CODE A UTILISER ===\n")

    print("import cv2\n")

    if config["backend"] is None:
        print(
            f"cap = cv2.VideoCapture({config['index']})"
        )
    else:
        print(
            f"cap = cv2.VideoCapture("
            f"{config['index']}, "
            f"cv2.CAP_{config['backend_name']})"
            ")"
        )

    print("""
cap.set(
    cv2.CAP_PROP_FOURCC,
    cv2.VideoWriter_fourcc(*'MJPG')
)
""")

    print(
        f"cap.set(cv2.CAP_PROP_FRAME_WIDTH, "
        f"{config['width']})"
    )

    print(
        f"cap.set(cv2.CAP_PROP_FRAME_HEIGHT, "
        f"{config['height']})"
    )

    print("\n=== DEMARRAGE VIDEO ===\n")

    # ouverture réelle
    if config["backend"] is None:
        cap = cv2.VideoCapture(config["index"])
    else:
        cap = cv2.VideoCapture(
            config["index"],
            config["backend"]
        )

    # paramètres
    cap.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*'MJPG')
    )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        config["width"]
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        config["height"]
    )

    while True:

        ret, frame = cap.read()

        if not ret or frame is None:
            print("Erreur capture")
            break

        cv2.imshow(
            "Flux Camera",
            frame
        )

        key = cv2.waitKey(1)

        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":

    detecteur = DetecteurCamera()

    config = detecteur.trouver_meilleure_configuration()

    if config is not None:
        filmer(config)

    else:
        print("Aucune configuration fonctionnelle")
