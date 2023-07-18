from picamera import PiCamera
import time
import numpy as np
import imutils
import cv2
import matplotlib.pyplot as plt
import tkinter as tk
from functools import partial
import json
import os
import math
from tkinter.messagebox import showinfo

print('coregistration_path', os.path.abspath(os.curdir))
#%% Get and handle camera pictures       
def get_picture(tag,save_path='./'):
    camera = PiCamera()
    camera.resolution = (1024, 768)
    camera.hflip = True
    camera.vflip = True 
    camera.start_preview()
    camera.shutter_speed=7*1176
    # Camera warm-up time
    time.sleep(2)
    if tag=='init': save_path=f"./{tag}.png"
    
    camera.capture(save_path)
    camera.close()
    return

def order_corners(pts):
    """
    Given the four points found for our contour, order them into
    Top Left, Top Right, Bottom Right, Bottom Left
    This order is important for perspective transforms
    :param pts: Contour points to be ordered correctly
    """
    rect = np.zeros((4, 2), dtype='float32')

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect

def get_reference_image(img_resolution=(800, 600)):
    """
    Build the image we will be searching for.  In this case, we just want a
    large white box (full screen)
    :param img_resolution: this is our screen/projector resolution
    """
    width, height = img_resolution
    img = np.ones((height, width, 1), np.uint8) * 255
    return img


def get_destination_array(rect):
    """
    Given a rectangle return the destination array
    :param rect: array of points  in [top left, top right, bottom right, bottom left] format
    """
    (tl, tr, br, bl) = rect  # Unpack the values
    # Compute the new image width
    width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))

    # Compute the new image height
    height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))

    # Our new image width and height will be the largest of each
    max_width = max(int(width_a), int(width_b))
    max_height = max(int(height_a), int(height_b))

    # Create our destination array to map to top-down view
    dst = np.array([
        [0, 0],  # Origin of the image, Top left
        [max_width - 1, 0],  # Top right point
        [max_width - 1, max_height - 1],  # Bottom right point
        [0, max_height - 1],  # Bottom left point
        ], dtype='float32')
    return dst, max_width, max_height

def find_edges(frame):
    """
    Given a frame, find the edges
    :param frame: Camera Image
    :return: Found edges in image
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)  # Add some blur
    edged = cv2.Canny(gray, 30, 200)  # Find our edges
    return edged

def get_region_corners(frame):
    """
    Find the four corners of our projected region and return them in
    the proper order
    :param frame: Camera Image
    :return: Projection region rectangle
    """
    edged = find_edges(frame)
    # findContours is destructive, so send in a copy
    contours, hierarchy = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    # Sort our contours by area, and keep the 10 largest
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    screen_contours = None

    for c in contours:
        # Approximate the contour
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        # If our contour has four points, we probably found the screen
        if len(approx) == 4:
            screen_contours = approx
            break
    else:
        print('Did not find contour')
    # Uncomment these lines to see the contours on the image
    # cv2.drawContours(frame, [screen_contours], -1, (0, 255, 0), 3)
    # cv2.imshow('Screen', frame)
    # cv2.waitKey(0)
    pts = screen_contours.reshape(4, 2)
    rect = order_corners(pts)
    return rect

def show_full_frame(frame):
    """
    Given a frame, display the image in full screen
    :param frame: image to display full screen
    """
    cv2.namedWindow('FullScreen', cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty('FullScreen', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.moveWindow('FullScreen', 1600, 0)
    cv2.imshow('FullScreen', frame)


def hide_full_frame(window='FullScreen'):
    """
    Kill a named window, the default is the window named 'FullScreen'
    :param window: Window name if different than default
    """
    cv2.destroyWindow(window)
    cv2.waitKey(1)

def get_perspective_transform(tag,screen_resolution=(800,600), prop_file=None):
    """
    Determine the perspective transform for the current physical layout
    return the perspective transform, max_width, and max_height for the
    projected region
    
    """
    json_path='../acquisition_param_ONEPIX.json'
    f = open(json_path)
    setup_dict = json.load(f)
    m=setup_dict["m"]
    max_width=setup_dict["max_width"]
    max_height=setup_dict["max_height"]
    
    res=False
    keys=list(setup_dict.keys())
    if m==[]:
        res=True
        
    if(res):
        tag='init'
    else:
        m=np.reshape(m,(3,3))
        
    if tag=='init':
        reference_image = get_reference_image(screen_resolution)

        # Display the reference image
        show_full_frame(reference_image)
        # Delay execution a quarter of a second to make sure the image is displayed 
        # Don't use time.sleep() here, we want the IO loop to run.  Sleep doesn't do that
        cv2.waitKey(250)
        

        # Grab a photo of the frame
        get_picture(tag)
        save_path=f"./{tag}.png"
        frame = cv2.imread(save_path)
        #os.remove(save_path)

        # We're going to work with a smaller image, so we need to save the scale
        ratio = frame.shape[0] / 300.0

        # Undistort the camera image
        #frame = undistort_image(frame, prop_file=prop_file)
        pict = frame.copy()
        # Resize our image smaller, this will make things a lot faster
        frame = imutils.resize(frame, height=300)

        rect = get_region_corners(frame)
        rect *= ratio  # We shrank the image, so now we have to scale our points up

        dst, max_width, max_height = get_destination_array(rect)
        # Remove the reference image from the display
        hide_full_frame()

        m = cv2.getPerspectiveTransform(rect, dst)
        showinfo(message='Initialisation du vidéoprojecteur réussie.')
        
        file = open(json_path, "r")
        setup_dict = json.load(file)
        file.close()
        
        setup_dict["m"]=m.tolist()
        setup_dict["max_width"]=max_width
        setup_dict["max_height"]=max_height
                
        file = open(json_path, "w")
        json.dump(setup_dict,file)
        file.close()
        
        
    else:
        
        
        # Grab a photo of the frame
        get_picture(tag)
        save_path=f"./{tag}.png"
        pict = cv2.imread(save_path)
        #os.remove(save_path)
           
        
    # Uncomment the lines below to see the transformed image
    wrap = cv2.resize(cv2.warpPerspective(pict, m, (max_width, max_height)),(800,600))
    cv2.imwrite(save_path,wrap)

#     cv2.imshow('all better', wrap)
#     cv2.waitKey(0)
#     return wrap

def coregistration_calibration(screen_resolution=(800,600)):
    
    """
    Function allow to calibrate teh coregistration between video projector and the PI camera
    
    """
    json_path='acquisition_param_ONEPIX.json'
    reference_image = get_reference_image(screen_resolution)
    show_full_frame(reference_image)
    # Delay execution a quarter of a second to make sure the image is displayed 
    # Don't use time.sleep() here, we want the IO loop to run.  Sleep doesn't do that
    cv2.waitKey(250)
        
    # Grab a photo of the frame
    get_picture('calibration',"init.png")
    save_path="init.png"
    frame = cv2.imread(save_path)

    # We're going to work with a smaller image, so we need to save the scale
    ratio = frame.shape[0] / 300.0

    # Undistort the camera image
    #frame = undistort_image(frame, prop_file=prop_file)
    pict = frame.copy()
    # Resize our image smaller, this will make things a lot faster
    frame = imutils.resize(frame, height=300)

    rect = get_region_corners(frame)
    rect *= ratio  # We shrank the image, so now we have to scale our points up

    dst, max_width, max_height = get_destination_array(rect)
    # Remove the reference image from the display
    hide_full_frame()

    m = cv2.getPerspectiveTransform(rect, dst)
#     root=tk.Tk()
#     showinfo(root,message='Initialisation du vidéoprojecteur réussie.')
#     root.destroy()
    
    file = open(json_path, "r")
    setup_dict = json.load(file)
    file.close()
    
    setup_dict["m"]=m.tolist()
    setup_dict["max_width"]=max_width
    setup_dict["max_height"]=max_height
            
    file = open(json_path, "w")
    json.dump(setup_dict,file)
    file.close()
    
def apply_corregistration(img,json_path):
    """
    Function allow to resize image of the pi with coregistration with the video projector
    """
    
    #json_path='acquisition_param_ONEPIX.json'
    f = open(json_path)
    setup_dict = json.load(f)
    m=setup_dict["m"]
    m=np.asarray(m)
    max_width=setup_dict["max_width"]
    max_height=setup_dict["max_height"]
    wrap = cv2.resize(cv2.warpPerspective(img, m, (max_width, max_height)),(800,600))
    return wrap
