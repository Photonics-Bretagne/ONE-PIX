import os
import sys
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append('..')
import cv2

import numpy as np
from skimage.restoration import unwrap_phase

class ProfiloReconstruction:

    def __init__(self,raw_mesure=None):
        if type(raw_mesure)==str:
            self.raw_measure=np.load(raw_mesure)
        else:
            self.raw_measure=raw_mesure

    def reconstruction(self):
        Num = self.raw_measure[3].astype(float) - self.raw_measure[1].astype(float)
        Den = self.raw_measure[0].astype(float) - self.raw_measure[2].astype(float)
        PHI = np.arctan2(Num, Den)

        Num2 = self.raw_measure[7].astype(float) - self.raw_measure[5].astype(float)
        Den2 = self.raw_measure[4].astype(float) - self.raw_measure[6].astype(float)
        PHI2 = np.arctan2(Num2, Den2)

        ZOBJ = unwrap_phase(PHI)
        ZOBJ2 = unwrap_phase(PHI2)

        ZOBJ_moy=np.mean([ZOBJ, ZOBJ2], axis=0)

        se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        background = cv2.morphologyEx(ZOBJ_moy, cv2.MORPH_OPEN, se)


        depth_map = ZOBJ_moy - background
        return depth_map 
    
    def save_reconstructed_image(self,depth_map,save_path):
        depth_map_title="depthmap.npy"
        np.save(save_path+"\\"+depth_map_title,depth_map)




  