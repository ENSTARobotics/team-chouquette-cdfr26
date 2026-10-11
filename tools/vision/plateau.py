import numpy as np
import cv2

class Plateau:
    """
    Classe représentant le plateau de jeu
    """

    def __init__(self):
        self.coin_plateau1 = None
        self.coin_plateau2 = None
        self.coin_plateau3 = None
        self.coin_plateau4 = None
        
        self.zone_depart_jaune_pts_img = None
        self.zone_depart_bleu_pts_img = None
        self.zone_grenier_pts_img = None
        
        self._H_plane2img = None
        self._H_img2plane = None  # Ajouté pour transformer pixel -> plateau

    def actualiser_plateau(self, A, B, C, D):
        if A is None or B is None or C is None or D is None:
            return

        img_pts = np.array([A, B, C, D], dtype=np.float32)
        W, H = 3000.0, 2000.0  # Unités arbitraires (ex: mm)
        dst_pts = np.array([[0.0, 0.0], [W, 0.0], [W, H], [0.0, H]], dtype=np.float32)

        self._H_img2plane = cv2.getPerspectiveTransform(img_pts, dst_pts)
        self._H_plane2img = cv2.getPerspectiveTransform(dst_pts, img_pts)

        pts = img_pts.reshape(-1, 1, 2)
        pts_plane = cv2.perspectiveTransform(pts, self._H_img2plane).reshape(-1, 2)
        Ar, Br, Cr, Dr = pts_plane

        vecteurAD = Dr - Ar
        vecteurAB = Br - Ar
        coin_plateau1_r = Ar - (1.0/3.0) * vecteurAB - (3.0/4.0) * vecteurAD
        coin_plateau2_r = coin_plateau1_r + (5.0/3.0) * vecteurAB
        coin_plateau3_r = coin_plateau1_r + (5.0/3.0) * vecteurAB + 2.5 * vecteurAD
        coin_plateau4_r = coin_plateau1_r + 2.5 * vecteurAD

        coins_plane = np.array([coin_plateau1_r, coin_plateau2_r, coin_plateau3_r, coin_plateau4_r], dtype=np.float32).reshape(-1, 1, 2)
        coins_img = cv2.perspectiveTransform(coins_plane, self._H_plane2img).reshape(-1, 2)
        self.coin_plateau1, self.coin_plateau2, self.coin_plateau3, self.coin_plateau4 = [tuple(p) for p in coins_img]

        # Zones spécifiques (Jaune, Bleu, Grenier)
        w_frac0, w_frac1 = 0.0, 600.0 / W
        h_frac0, h_frac1 = 1550.0 / H, 2000.0 / H
        plateau_w_vec = coin_plateau2_r - coin_plateau1_r
        plateau_h_vec = coin_plateau4_r - coin_plateau1_r

        # Calcul zone jaune
        z_j_p = np.array([coin_plateau1_r + w_frac0*plateau_w_vec + h_frac0*plateau_h_vec,
                          coin_plateau1_r + w_frac1*plateau_w_vec + h_frac0*plateau_h_vec,
                          coin_plateau1_r + w_frac1*plateau_w_vec + h_frac1*plateau_h_vec,
                          coin_plateau1_r + w_frac0*plateau_w_vec + h_frac1*plateau_h_vec], dtype=np.float32)
        self.zone_depart_jaune_pts_img = np.round(cv2.perspectiveTransform(z_j_p.reshape(-1,1,2), self._H_plane2img).reshape(-1,2)).astype(np.int32)

        # Calcul zone bleue
        z_b_p = np.array([coin_plateau1_r + (1.0-w_frac1)*plateau_w_vec + h_frac0*plateau_h_vec,
                          coin_plateau1_r + 1.0*plateau_w_vec + h_frac0*plateau_h_vec,
                          coin_plateau1_r + 1.0*plateau_w_vec + h_frac1*plateau_h_vec,
                          coin_plateau1_r + (1.0-w_frac1)*plateau_w_vec + h_frac1*plateau_h_vec], dtype=np.float32)
        self.zone_depart_bleu_pts_img = np.round(cv2.perspectiveTransform(z_b_p.reshape(-1,1,2), self._H_plane2img).reshape(-1,2)).astype(np.int32)

        # Calcul grenier
        z_g_p = np.array([coin_plateau1_r + w_frac1*plateau_w_vec + h_frac0*plateau_h_vec,
                          coin_plateau1_r + (1.0-w_frac1)*plateau_w_vec + h_frac0*plateau_h_vec,
                          coin_plateau1_r + (1.0-w_frac1)*plateau_w_vec + h_frac1*plateau_h_vec,
                          coin_plateau1_r + w_frac1*plateau_w_vec + h_frac1*plateau_h_vec], dtype=np.float32)
        self.zone_grenier_pts_img = np.round(cv2.perspectiveTransform(z_g_p.reshape(-1,1,2), self._H_plane2img).reshape(-1,2)).astype(np.int32)

    def afficher(self, image):
        if self.zone_depart_bleu_pts_img is not None:
            cv2.fillPoly(image, [self.zone_depart_bleu_pts_img], (255, 0, 0))
        if self.zone_depart_jaune_pts_img is not None:
            cv2.fillPoly(image, [self.zone_depart_jaune_pts_img], (0, 255, 255))
        if self.zone_grenier_pts_img is not None:
            cv2.fillPoly(image, [self.zone_grenier_pts_img], (0, 0, 0))
        
        if self.coin_plateau1 is not None:
            pts = np.array([self.coin_plateau1, self.coin_plateau2, self.coin_plateau3, self.coin_plateau4], np.int32).reshape((-1, 1, 2))
            cv2.polylines(image, [pts], True, (255, 0, 255), 2)