"""
@author:PhotonicsOpenProject
Modified and traducted by Leo Brecheton Wed Jul 19 18:32:47 2023

"""


import numpy as np
import cv2
import time
import threading
import os
from datetime import date
import queue
from queue import Queue
import sys
import platform
import datetime
import gc
import screeninfo
import io

from src.SpectrometerBridge import * 
from src.PatternMethods import *
from src.DatacubeReconstructions import *
from src.datacube_analyse import *
from src.coregistration_lib import *
from pathlib import Path
import json
from tkinter import *
from tkinter.messagebox import askquestion

#root_path = '/'.join(os.getcwd().split('/')[:-1])
#json_path = f"{root_path}/acquisition_param_ONEPIX.json"
def is_raspberrypi():
    try:
        with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
            if 'raspberry pi' in m.read().lower(): return True
    except Exception: pass
    return False

screenWidth = screeninfo.get_monitors()[0].width

class OPConfig:
    """ 
    Class OPConfig is used to set up ONE-PIX acquisitions
    
    :param str spectro_name:
   		Spectrometer concrete bridge implementation:
   		
    :param float integration_time_ms:
   		spectrometer integration time in milliseconds.
           
    """

    def __init__(self,json_path,img=None,nb_patterns=0):
        f = open(json_path)
        acqui_dict = json.load(f)
        f.close()
        self.height = acqui_dict['height']
        self.width = acqui_dict["width"]
        self.spatial_res = acqui_dict['spatial_res']
        
        self.pattern_method = acqui_dict['pattern_method']
        self.name_spectro = acqui_dict["name_spectro"]
        self.integration_time_ms =acqui_dict["integration_time_ms"]
        self.mes_ratio=acqui_dict["mes_ratio"]
        
        self.pattern_lib = PatternMethodSelection(self.pattern_method, self.spatial_res, self.height, self.width)
        self.seq_basis = ['FourierSplit','FourierShift']
        self.full_basis = ['Adressing','Custom','Hadamard']
        self.nb_patterns = self.pattern_lib.nb_patterns

        self.chronograms = []
        self.pattern_order = []
        self.spectra = []

        
        # spectrometer acquistion time in ms
        self.wl_lim=acqui_dict["wl_lim"]
        self.spec_lib = SpectrometerBridge(self.name_spectro, self.integration_time_ms,self.wl_lim)
        self.wavelengths = []
        self.spectro_flag=False
        self.duration = 0
        self.periode_pattern = self.mes_ratio*self.integration_time_ms
        if self.periode_pattern < 120: self.periode_pattern = 120
        self.display_time = []
        self.duree_dark = 2
        self.time_spectro = []
        self.integ_time_flag=True
        self.display=False



    def get_optimal_integration_time(self):
        """
        This function allows to automatically set the right integration time for 
        ONE-PIX acqusitions depending on the mesurable optical flux. 
    
        Parameters
        ----------
        config : class
            OPConfig class object.
    
        Returns
        -------
        None. Actualisation of the integration_time_ms parameter of config
    
        """
        
        max_counts = 35000
        self.spec_lib.set_integration_time()
        
        flag = True
        self.spectro_flag=True
        count=0
        delta_wl=round(0.05*np.size(self.spec_lib.get_wavelengths()))
        while flag:
            #mes=self.spec_lib.get_intensities()[100:-100]
            mes = []
            for acq in range(10):
                mes.append(self.spec_lib.get_intensities())
            mes = np.mean(np.array(mes), 0)[delta_wl:-delta_wl]
            delta = max(mes)-max_counts
            print(f"Tint{count}={self.integration_time_ms} ms with intensity peak at {round(max(mes))} counts")
    
            if (abs(delta)<2500):
                flag = False
            elif self.spec_lib.integration_time_ms >= 10E3 or self.spec_lib.integration_time_ms==0:
                flag = False
                self.spec_lib.spec_close()
                raise Exception(f"Integration time: {self.spec_lib.integration_time_ms} ms, if you want to continue set the parameter by hand")
                
            elif (count>=10):
                flag=False
                print(f"Measures stopped after {count} iterations. Integration time= {self.integration_time_ms} ms with intensity peak at {round(max(mes))} counts")
            else:
                count+=1
                flag = True
                coeff = (max_counts/max(mes))
                self.integration_time_ms = int(self.integration_time_ms*coeff)
                self.spec_lib.integration_time_ms = self.integration_time_ms
                self.spec_lib.set_integration_time()
                
            self.spec_lib.set_integration_time()
            self.spectro_flag=False
        print(f"Integration time (ms): {self.integration_time_ms}")


    def OP_init(self):
        """
        This functions allows to display one Fourier pattern and then adapt and
        set the spectrometer's integration time within the OPConfig class.
    
        Parameters
        ----------
        config : class
            OPConfig class object.
    
        Returns
        -------
        config : class
            actualised OPConfig class object.
    
        """
               
            
        os_name = platform.system()
        if self.spec_lib.DeviceName=='':
            self.spec_lib.spec_open()
            self.spec_lib.DeviceName=self.spec_lib.decorator.DeviceName
    
        if os_name == 'Windows':
            x=list(range(self.height)) # horizontal vector for the pattern creation 
            y=list(range(self.width))# vertical vector for the pattern creation
            Y,X = np.meshgrid(x,y)# horizontal and vertical array for the pattern creation
            A=2*np.pi*X*1/self.height
            B=2*np.pi*Y*5/self.width
            pos_r=np.cos(A+B) #gray pattern creation
            
            cv2.namedWindow('Init', cv2.WINDOW_NORMAL)
            cv2.moveWindow('Init', 1920, 0)
            cv2.setWindowProperty("Init", cv2.WND_PROP_FULLSCREEN, 1)
            cv2.imshow('Init', pos_r)
            cv2.waitKey(300)
        print('Finding the optimal integration time (ms):')
        self.get_optimal_integration_time()
        cv2.destroyAllWindows()
        
        self.periode_pattern = self.mes_ratio*self.integration_time_ms
    
        if self.periode_pattern < 120:
            self.periode_pattern = 120
        #self.spec_lib.set_integration_time()
        


    def spectrometer_acquisition(self):
        """
        This function allows to use the spectrometer in free runing mode to record 
        a chronogram of acquisitions.
    
        Parameters
        ----------
        q : Queue 
            queue to check when patterns display is over.
        config : class
            OPConfig class object.
    
        Returns
        -------
        None. chronograms are stored in config.
    
        """
        
        begin = time.time()
        # Spectrometer connection
        if self.spec_lib.DeviceName=='':
            self.spec_lib.spec_open()
        self.spec_lib.set_integration_time()
        self.wavelengths = self.spec_lib.get_wavelengths()
        flag=True
        while True:
            flag=self.integ_time_flag
            if flag:
                self.chronograms.append(np.float32(self.spec_lib.get_intensities()))
                self.time_spectro.append((time.time()-begin)*1e3)
            else:
                
                self.chronograms.append(2*np.float32(self.spec_lib.get_intensities()))
                self.time_spectro.append((time.time()-begin)*1e3)
    
            try:
                self.q.get_nowait()
                break
    
            except queue.Empty:
                pass
    
        self.spec_lib.spec_close()


    def affichage_sequence(self):
        """
        This function allows to display a sequence of patterns.
       
        Parameters
        ----------
        q : Queue 
            queue to check when patterns display is over.
        config : class
            OPConfig class object.
    
        Returns
        -------
        None.
    
        """
        
        os_name = platform.system()
    
        begin = time.time()
    
        black_patterns = np.zeros((self.height, self.width,10))
        temps = []
    
        cv2.namedWindow('ImageWindow', cv2.WND_PROP_FULLSCREEN)
        
        cv2.moveWindow('ImageWindow', screenWidth, 0)
           
        cv2.setWindowProperty("ImageWindow", cv2.WND_PROP_FULLSCREEN, 1)
        for i in range(0, np.size(black_patterns, 2)):
    
            cv2.imshow('ImageWindow', black_patterns[:, :, i])
            cv2.waitKey(round(self.periode_pattern))
            
    
        if self.pattern_method in self.seq_basis:
            # horizontal vector for the pattern creation
            x = list(range(self.width))
            # vertical vector for the pattern creation
            y = list(range(self.height))
            # horizontal and vertical array for the pattern creation
            Y, X = np.meshgrid(x, y)
    
            self.pattern_order, freqs = self.pattern_lib.decorator.sequence_order()
    
            for freq in freqs:
                patterns = self.pattern_lib.decorator.creation_patterns(X, Y, freq)  # patterns creations 
                    
                for pattern in patterns:
                    if freq==(0,0):
                        self.integ_time_flag=False
                        self.spec_lib.integration_time_ms=self.spec_lib.integration_time_ms/2
                        self.spec_lib.set_integration_time()
                    
                    temps.append(time.time())
                    cv2.imshow('ImageWindow', pattern)
                    cv2.waitKey(round(self.periode_pattern))
                    temps.append(time.time())
                    
                    if freq==(0,0):
                        self.integ_time_flag=True
                        self.spec_lib.integration_time_ms=self.spec_lib.integration_time_ms*2
                        self.spec_lib.set_integration_time()
                del patterns
                gc.collect()
                    
    
        elif self.pattern_method in self.full_basis:
            for pattern in self.pattern_lib.decorator.sequence:
                if pattern.all()==self.pattern_lib.decorator.sequence[0].all() and self.pattern_method=='Hadamard':
                    self.integ_time_flag=False
                    self.spec_lib.integration_time_ms=self.spec_lib.integration_time_ms/2
                    self.spec_lib.set_integration_time()
                temps.append(time.time())
                cv2.imshow('ImageWindow', cv2.resize(pattern,(800,600),interpolation=cv2.INTER_AREA))
                cv2.waitKey(round(self.periode_pattern))
                temps.append(time.time())
                
                if pattern.all()==self.pattern_lib.decorator.sequence[0].all() and self.pattern_method=='Hadamard':
                    self.integ_time_flag=True
                    self.spec_lib.integration_time_ms=self.spec_lib.integration_time_ms*2
                    self.spec_lib.set_integration_time()
        
        time.sleep(0.1)
        self.q.put(True)
        gc.collect()
        cv2.destroyAllWindows()
        self.display_time = (np.asarray(temps)-begin)*1e3


    def thread_acquisition(self, path=None, time_warning=True):
        """
        This funtion allows to run in parallel the projection of a sequence of 
        patterns and spectrometers' measurements in free running mode. 
        The result is measured hyperspectral chronograms need to be processed to 
        extract means spectrums for each patterns.
    
    
        Parameters
        ----------
        config : class
            OPConfig class object.
    
        Returns
        -------
        config : class
        * actualised OPConfig class object.
        * display_time : (array of floats) 1D array of time values of the beginning and the end of projection for each pattern. 
        * time_spectro : (array of floats) 1D array of time values for each measured spectrum.
        * chronograms : (array of floats) 3D array of spectra stored in chronological order.
        * wavelengths : (array of floats) 1D wavelengths sampled by the spectrometer.
    
        """
        
        begin_acq = time.time()
        if self.pattern_method in self.full_basis:
            self.pattern_order,freq=self.pattern_lib.decorator.creation_patterns()
            self.pattern_lib.nb_patterns=self.pattern_lib.decorator.nb_patterns
        est_duration=round(1.5*self.pattern_lib.nb_patterns*self.periode_pattern/(60*1000),2)
        if time_warning and self.pattern_method!="Adressing":
            ans=askquestion(message=f"Estimated acquisition duration : {est_duration} min ")
            if ans=='yes':
                est_end=(datetime.datetime.now()+datetime.timedelta(minutes=round(est_duration))).strftime('%H:%M:%S')
                # print("Estimated end of the acquisition: "+est_end)
                self.q = Queue()
                first_thread = threading.Thread(
                    target=self.affichage_sequence)
                second_thread = threading.Thread(
                    target=self.spectrometer_acquisition)
                first_thread.start()
                second_thread.start()
        
                first_thread.join()
                second_thread.join()
        
                self.duration = time.time()-begin_acq
                if path!=None:
                    self.save_acquisition_envi(path)
                else:
                    self.save_acquisition_envi()
                gc.collect()
            else:
                pass
        else:
            est_end=(datetime.datetime.now()+datetime.timedelta(minutes=round(est_duration))).strftime('%H:%M:%S')
            # print("Estimated end of the acquisition: "+est_end)
            self.q = Queue()
            first_thread = threading.Thread(
                target=self.affichage_sequence)
            second_thread = threading.Thread(
                target=self.spectrometer_acquisition)
            first_thread.start()
            second_thread.start()
    
            first_thread.join()
            second_thread.join()
    
            self.duration = time.time()-begin_acq
            if path!=None:
                self.save_acquisition_envi(path)
            else:
                self.save_acquisition_envi()
            gc.collect()
       

    def save_acquisition_envi(self, path = "../Hypercubes"):
        """
        This function allow to save the resulting acquisitions from one 
        OPConfig object into the Hypercube folder.
    
        Parameters
        ----------
        config : class
            OPConfig class object.
    
        Returns
        -------
        None.
    
        """
        
        #extract spectra from chronograms
        self.display_time = time_aff_corr(
            self.chronograms, self.time_spectro, self.display_time)
        self.spectra = calculate_pattern_spectrum(
            self.display_time, 0, self.time_spectro, self.chronograms, 0)
        root_path=os.getcwd()
        #path=os.path.join(root_path,'Hypercubes')
        if(os.path.isdir(path)):
            pass
        else:
            os.mkdir(path)
        os.chdir(path)
        
        fdate = date.today().strftime('%d_%m_%Y')  # convert the current date in string
        actual_time = time.strftime("%H-%M-%S")  # get the current time
        folder_name = f"ONE-PIX_acquisition_{fdate}_{actual_time}"
        os.mkdir(folder_name)
        os.chdir(folder_name)
        
        if self.pattern_method not in ['Custom',"Adressing"]:
            res=OPReconstruction(self.pattern_method,self.spectra,self.pattern_order)
            res.Selection()
            # saving the acquired spatial spectra hypercube
            py2envi(folder_name,res.hyperspectral_image,self.wavelengths,os.getcwd())
        else:
            np.save(folder_name,self.spectra)
            if self.pattern_method=="Adressing":
                
                title_acq = f"spectra_{fdate}_{actual_time}.npy"
                title_wavelengths = f"wavelengths_{fdate}_{actual_time}.npy"
                title_patterns = f"pattern_order_{fdate}_{actual_time}.npy"
                title_mask= f"mask_{fdate}_{actual_time}.npy"
                np.save(title_mask, self.pattern_lib.decorator.sequence)
                np.save(title_acq, self.spectra)
                np.save(title_wavelengths, self.wavelengths)  # saving wavelength
                np.save(title_patterns, self.pattern_order)  # saving wavelength
        # Header
        title_param = f"Acquisition_parameters_{fdate}_{actual_time}.txt"
    
        header = f"ONE-PIX acquisition_{fdate}_{actual_time}"+"\n"\
            + "--------------------------------------------------------"+"\n"\
            + "\n"\
            + f"Acquisition method : {self.pattern_method}"+"\n"\
            + "Acquisition time : %f s" % self.duration+"\n" \
            + f"Spectrometer {self.name_spectro} : {self.spec_lib.DeviceName}"+"\n"\
            + "Number of projected patterns : %d" % self.nb_patterns+"\n" \
            + "Height of pattern window : %d pixels" % self.height+"\n" \
            + "Width of pattern window : %d pixels" % self.width+"\n" \
            + "Dark pattern duration : %d ms" % self.duree_dark+"\n" \
            + "Integration time : %d ms" % self.integration_time_ms+"\n" 
    
    
        text_file = open(title_param, "w+")
        text_file.write(header)
        text_file.close()
        
        
        os_name=platform.system()
        print('is_raspberrypi() : ',is_raspberrypi())
        if is_raspberrypi():
            root=Tk()
            root.geometry("{}x{}+{}+{}".format(800, 600,1024,0))
            root.wm_attributes('-fullscreen', 'True')
            c=Canvas(root,width=800,height=600,bg='gray',highlightthickness=0)
            c.pack()
            root.update()
            try:
                from picamera import PiCamera, PiCameraError
                camera = PiCamera()
                camera.resolution = (1024, 768)
                camera.start_preview()
                camera.shutter_speed=7*1176
                camera.vflip=True
                camera.hflip=True
                # Camera warm-up time
                time.sleep(2)
                camera.capture(f"RGBCam_{fdate}_{actual_time}.jpg")
                camera.close()
                
                if(self.pattern_method=='Adressing'):
                    rgb_name=f"RGBCam_{fdate}_{actual_time}.jpg"
                    RGB_img = cv2.imread(rgb_name)
                    RGB_img= np.asarray(RGB_img)
                    os.chdir(root_path)
                    print('acq_conf_cor_path', os.path.abspath(os.curdir))
                    RGB_img=apply_corregistration(RGB_img,'../acquisition_param_ONEPIX.json')
                    os.chdir(path)
                    os.chdir(folder_name)
                    print('corPath : ',os.getcwd())
                    cv2.imwrite(f"RGB_cor_{fdate}_{actual_time}.jpg",RGB_img)
            except PiCameraError:
                print("Warning; check a RPi camera is connected. No picture were stored !")
            root.destroy()
        # os.chdir(root_path)
        del self.chronograms,self.time_spectro, self.display_time # saves RAM for large acquisitions
        gc.collect()
