# coding=utf-8
"""
Created on 26.3.2018
Updated on 12.4.2018
"""
__author__ = "Severi Jääskeläinen \n Samuel Kaiponen \n Heta Rekilä " \
             "\n Sinikka Siironen"
__version__ = "2.0"

import enum
import matplotlib
import random

from dialogs.simulation.layer_properties import LayerPropertiesDialog
from modules.target import Target
from modules.layer import Layer
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from widgets.matplotlib.base import MatplotlibWidget

class TargetCompositionWidget(MatplotlibWidget):
    """Matplotlib target composition widget. Using this widget, the user
    can edit target composition for the simulation.
    """

    def __init__(self, parent, icon_manager):
        """Inits

        Args:
            parent: A SimulationDepthProfileWidget class object.
            icon_manager: An iconmanager class object.
        """
        super().__init__(parent)
        self.canvas.manager.set_title("Target Composition")

        # Remove Y-axis ticks and label
        self.axes.yaxis.set_tick_params("both", left="off", labelleft="off")

        self.axes.fmt_xdata = lambda x: "{0:1.0f}".format(x)
        self.name_x_axis = "Depth"

        self.__icon_manager = icon_manager
        self.__fork_toolbar_buttons()

        self.__layer_colors = []

        self.target = Target()

        self.on_draw()

    def on_draw(self):
        """Draw method for matplotlib.
        """
        self.axes.clear()  # Clear old stuff
        self.axes.set_xlabel(self.name_x_axis.title())

        # Remove axis ticks and draw
        self.remove_axes_ticks()
        self.canvas.draw()



    def __toggle_tool_drag(self):
        if self.__button_drag.isChecked():
            self.mpl_toolbar.mode_tool = 1
        else:
            self.mpl_toolbar.mode_tool = 0
            # self.elementSelectionButton.setChecked(False)
        # self.elementSelectUndoButton.setEnabled(False)
        # self.elementSelectionSelectButton.setChecked(False)
        self.canvas.draw_idle()

    def __toggle_tool_zoom(self):
        if self.__button_zoom.isChecked():
            self.mpl_toolbar.mode_tool = 2
        else:
            self.mpl_toolbar.mode_tool = 0
            # self.elementSelectionButton.setChecked(False)
        # self.elementSelectUndoButton.setEnabled(False)
        # self.elementSelectionSelectButton.setChecked(False)
        self.canvas.draw_idle()

    def __toggle_drag_zoom(self):
        self.__tool_label.setText("")
        if self.__button_drag.isChecked():
            self.mpl_toolbar.pan()
        if self.__button_zoom.isChecked():
            self.mpl_toolbar.zoom()
        self.__button_drag.setChecked(False)
        self.__button_zoom.setChecked(False)

    def __fork_toolbar_buttons(self):
        # super().fork_toolbar_buttons()
        self.mpl_toolbar.mode_tool = 0
        self.__tool_label = self.mpl_toolbar.children()[24]
        self.__button_drag = self.mpl_toolbar.children()[12]
        self.__button_zoom = self.mpl_toolbar.children()[14]
        self.__button_drag.clicked.connect(self.__toggle_tool_drag)
        self.__button_zoom.clicked.connect(self.__toggle_tool_zoom)

        # Make own buttons
        self.mpl_toolbar.addSeparator()

        # Button for adding a new layer
        self.button_add_layer = QtWidgets.QToolButton(self)
        self.button_add_layer.clicked.connect(lambda: (self.__add_layer()))
        self.__icon_manager.set_icon(self.button_add_layer, "add.png")  # TODO: Change icon!
        self.mpl_toolbar.addWidget(self.button_add_layer)

    def __add_layer(self, position = -1):
        """Adds a new layer to the target. A random color is given for the
        layer in such manner, that the layers next to it doesn't have same
        color.

        Args:
            position: A position where the layer should be added. If -1 is
                      given, the layer is added at the end of the target.
        """
        dialog = LayerPropertiesDialog()

        if dialog.layer:
            layer_color = dialog.layer_color
            self.target.layers.append(dialog.layer)
            self.__layer_colors.append(layer_color)
            self.__update_figure()

    def __update_figure(self):
        next_layer_position = 0
        for idx, layer in enumerate(self.target.layers):
            layer_patch = matplotlib.patches.Rectangle(
                (next_layer_position, 0),
                layer.thickness, 1,
                color = self.__layer_colors[idx]
            )
            self.axes.add_patch(layer_patch)

            # Don't add a line before the first layer.
            if next_layer_position != 0:
                # Add a line between layers.
                layer_line = matplotlib.patches.ConnectionPatch(
                    (next_layer_position, 0),
                    (next_layer_position, 1),
                    coordsA="data"
                )
                self.axes.add_line(layer_line)

            # Put annotation in the middle of the rectangular patch.
            self.axes.annotate(layer.name,
                               (next_layer_position + layer.thickness / 2, 0.5),
                               ha="center")

            # Move the position where the next layer starts.
            next_layer_position += layer.thickness

        self.axes.set_xbound(0, next_layer_position)
        self.canvas.draw_idle()
        self.mpl_toolbar.update()
