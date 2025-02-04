import numpy as np
import matplotlib.pyplot as plt
from plugins.imaging_methods.FIS_common_functions.FIS_common_analysis import FisAnalysis


class Analysis:
    """Class to reconstruct a data cube from Fourier splitting ONE-PIX method."""

    def __init__(self, data_path=None):
        self.data_path = data_path
        self.analyse = FisAnalysis()

    def load_reconstructed_data(self, data_path=None):
        if data_path is None:
            data_path = self.data_path
        self.data_dict = self.analyse.load_hypercube(data_path)
        self.reconstructed_data = self.data_dict["reconstructed_image"]
        self.wavelengths = self.data_dict["wavelengths"]

    def data_normalisation(self, ref_datacube,data):
        normalised_data = self.analyse.datacube_reflectance_normalisation(
            data, ref_datacube
        )
        return normalised_data

    def get_rgb_image(self, datacube, wavelengths):
        rgb_image = self.analyse.RGB_reconstruction(datacube, wavelengths)
        return rgb_image

    def plot_reconstructed_image(self, datacube, wavelengths):
        rgb_image = self.get_rgb_image(self, datacube, wavelengths)
        plt.figure()
        plt.imshow(rgb_image)
        plt.show()
