import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.transforms as transforms
from .zgoubiplot import ZgoubiPlot


class ZgoubiMpl(ZgoubiPlot):
    def __init__(self, ax=None, with_boxes=True, with_frames=True):
        super().__init__(with_boxes, with_frames)
        if ax is None:
            self._init_plot()
        else:
            self._ax = ax

    def _init_plot(self):
        self._fig = plt.figure()
        self._ax = self._fig.add_subplot(111)

    def cartesian_bend(self, entry, sortie, rotation, width):
        def do_frame():
            self._ax.annotate(s='',
                              xy=(
                                  entry[0].to('cm').magnitude,
                                  entry[1].to('cm').magnitude
                              ),
                              xytext=(
                                  sortie[0].to('cm').magnitude,
                                  sortie[1].to('cm').magnitude
                              ),
                              arrowprops=dict(arrowstyle='<->')
                              )

        def do_box():
            tr = transforms.Affine2D().rotate_deg_around(
                entry[0].to('cm').magnitude,
                entry[1].to('cm').magnitude,
                rotation.to('degree').magnitude) + self._ax.transData
            self._ax.add_patch(
                patches.Rectangle(
                    (
                        entry[0].to('cm').magnitude,
                        (entry[1] - width / 2).to('cm').magnitude
                    ),
                    np.linalg.norm(
                        np.array([sortie[0].to('cm').magnitude, sortie[1].to('cm').magnitude])
                        - np.array([entry[0].to('cm').magnitude, entry[1].to('cm').magnitude])
                    ),
                    width.to('cm').magnitude,
                    alpha=0.2,
                    facecolor=self._palette['blue'],
                    edgecolor='#268bd2',
                    transform=tr,
                )
            )

        if self._with_boxes:
            do_box()
        if self._with_frames:
            do_frame()
