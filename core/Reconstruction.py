import numpy as np 
import matplotlib.pyplot as plt 
import os
import glob
import tkinter as Tk
from tkinter import filedialog
from tkinter import *
import importlib
from sklearn import mixture
import spectral.io.envi as envi
import time
from core.ImagingMethodBridge import *

def get_header_data(path):
    """
    This function allows to generate a dictionnary containing acquisition data 
    useful for the data cube reconstruction.

    Parameters
    ----------
    path : str
        Header file path

    Returns
    -------
    acq_data : dict
        Dictionnary containing acquisition data.

    """
    
    header=[]
    with open(path, 'r') as file:
       for line in file.readlines():
           header.append(line.split(':'))
    acq_data=dict()
    acq_data['Acquisition_name']=header[0][0][8:]
    for x in header:
        if x[0].strip()=='Imaging method':
            acq_data['imaging_method']=x[1].strip()
        
        if x[0].strip()=='Integration time':
            acq_data['integration_time_ms']=float(x[1].strip()[:-2])
    
    return acq_data


#%% method Selection

class Reconstruction:
    """ Class OPReconstruction to reconstruct datacubes according to a ONE-PIX method"""
    def __init__(self,acquisition_dict=None):

        if acquisition_dict is None:
            self.load_raw_data()
            self.imaging_method=self.acquisition_dict["imaging_method"]
            self.spectra=self.acquisition_dict["spectra"]
            self.pattern_order=self.acquisition_dict["patterns_order"]
        else :
            self.imaging_method=acquisition_dict["imaging_method"]
            self.spectra=acquisition_dict["spectra"]
            self.pattern_order=acquisition_dict["patterns_order"]
        
        self.spatial_res=0
        self.height=0
        self.width=0
        
        self.imaging_method=ImagingMethodBridge(self.imaging_method,self.spatial_res,self.height,self.width)
        
    
    def load_raw_data(self):
        """
        This function allows to load saved spectra with timers of the displays and spectrometers.
        at runtime, a window appears to select the folder path in which the data are located. 

        Returns
        -------
        acq_data : dict
            Dictionary containing data extracted from files saved after acquisition to reconstruct data cubes.

        """
    
        try:
            chemin_script = os.getcwd()
            root = Tk()
            root.withdraw()
            root.attributes('-topmost', 1)
            chemin_mesure = filedialog.askdirectory(title = "Select the folder containing the acquisitions", initialdir = chemin_script)
            os.chdir(chemin_mesure)
            
            header_name=glob.glob('*.txt')[0]
            self.acquisition_dict=get_header_data(header_name)
            
            list_nom_mesure = sorted(glob.glob('*.npy'),key=os.path.getmtime)
            
            indice=[x for x, s in enumerate(list_nom_mesure) if "spectra" in s]
            self.acquisition_dict['spectra']=np.load(list_nom_mesure[indice[0]])
            
            indice=[x for x, s in enumerate(list_nom_mesure) if "wavelengths" in s]
            self.acquisition_dict['wavelengths']=np.load(list_nom_mesure[indice[0]])
            
            indice=[x for x, s in enumerate(list_nom_mesure) if "patterns_order" in s]
            self.acquisition_dict['patterns_order']=np.load(list_nom_mesure[indice[0]])
            
            os.chdir(chemin_script)
        except Exception as e:
            print(e)
        
        

         
    def nan_corr(self):
        """
        nan_corr allows to filter nan from acquired spectra

        Returns
        -------
        None.

        """
        try:
            idx_nan=np.argwhere(np.isnan(self.spectra))[0,:-1]
            self.spectra[idx_nan,:]=self.spectra[idx_nan-1,:]
        except IndexError:
            pass
        
       
       
    def data_reconstruction(self):
        """
        image_reconstruction allows to reconstruct an image data cube from an actualised 
        spatial spectra data cube. Both are stored in the HSPIReconstruction class object.

        Returns
        -------
        None.

        """
        self.imaging_method.reconstruction(self.spectra,self.pattern_order)


    def save_reconstructed_image(self,filename,save_path):
        self.imaging_method.image_reconstruction_method.save_reconstructed_image(self.imaging_method.reconstructed_image,
                                                                                 self.acquisition_dict['wavelengths'],
                                                                                 filename,save_path)
        
