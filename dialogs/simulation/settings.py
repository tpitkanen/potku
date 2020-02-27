# coding=utf-8
"""
Created on 4.5.2018
Updated on 24.5.2019

Potku is a graphical user interface for analyzation and
visualization of measurement data collected from a ToF-ERD
telescope. For physics calculations Potku uses external
analyzation components.
Copyright (C) 2013-2018 Jarkko Aalto, Severi Jääskeläinen, Samuel Kaiponen,
Timo Konu, Samuli Kärkkäinen, Samuli Rahkonen, Miika Raunio, Heta Rekilä and
Sinikka Siironen

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program (file named 'LICENCE').
"""
__author__ = "Severi Jääskeläinen \n Samuel Kaiponen \n Heta Rekilä " \
             "\n Sinikka Siironen"
__version__ = "2.0"

import json
import os
import shutil
import time
import copy

import dialogs.dialog_functions as df

from modules.general_functions import delete_simulation_results
from modules.run import Run

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import uic

from widgets.detector_settings import DetectorSettingsWidget
from widgets.measurement.settings import MeasurementSettingsWidget


class SimulationSettingsDialog(QtWidgets.QDialog):
    """
    Dialog class for handling the simulation parameter input.
    """

    def __init__(self, tab, simulation, icon_manager):
        """
        Initializes the dialog.

        Args:
            tab: A SimulationTabWidget.
            simulation: A Simulation object whose parameters are handled.
            icon_manager: An icon manager.
        """
        super().__init__()
        self.tab = tab
        self.simulation = simulation
        self.icon_manager = icon_manager
        self.ui = uic.loadUi(os.path.join("ui_files",
                                          "ui_specific_settings.ui"), self)
        self.ui.setWindowTitle("Simulation Settings")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        screen_geometry = QtWidgets.QDesktopWidget.availableGeometry(
            QtWidgets.QApplication.desktop())
        self.resize(self.geometry().width() * 1.1,
                    screen_geometry.size().height() * 0.8)
        self.ui.defaultSettingsCheckBox.stateChanged.connect(
            self.__change_used_settings)
        self.ui.OKButton.clicked.connect(self.__save_settings_and_close)
        self.ui.applyButton.clicked.connect(self.__update_parameters)
        self.ui.cancelButton.clicked.connect(self.close)

        # Add measurement settings view to the settings view
        self.measurement_settings_widget = MeasurementSettingsWidget(
            self.simulation)
        self.ui.tabs.addTab(self.measurement_settings_widget, "Measurement")

        self.measurement_settings_widget.ui.picture.setScaledContents(True)
        pixmap = QtGui.QPixmap(os.path.join("images",
                                            "measurement_setup_angles.png"))
        self.measurement_settings_widget.ui.picture.setPixmap(pixmap)

        self.measurement_settings_widget.ui.beamIonButton.clicked.connect(
            lambda: df.change_element(
                self,
                self.measurement_settings_widget.ui.beamIonButton,
                self.measurement_settings_widget.ui.isotopeComboBox))

        # Add detector settings view to the settings view
        detector_object = self.simulation.detector
        if not detector_object:
            detector_object = self.simulation.request.default_detector
        self.detector_settings_widget = DetectorSettingsWidget(
            detector_object, self.simulation.request, self.icon_manager)

        # 2 is calibration tab that is not needed
        calib_tab_widget = self.detector_settings_widget.ui.tabs.widget(2)
        self.detector_settings_widget.ui.tabs.removeTab(2)
        calib_tab_widget.deleteLater()

        self.ui.tabs.addTab(self.detector_settings_widget, "Detector")

        if self.simulation.detector is not None:
            self.ui.defaultSettingsCheckBox.setCheckState(0)
            self.measurement_settings_widget.ui.nameLineEdit.setText(
                self.simulation.measurement_setting_file_name)
            self.measurement_settings_widget.ui.descriptionPlainTextEdit \
                .setPlainText(
                    self.simulation.measurement_setting_file_description)
            self.measurement_settings_widget.dateLabel.setText(time.strftime(
                "%c %z %Z", time.localtime(self.simulation.modification_time)))

        self.ui.tabs.currentChanged.connect(lambda: self.__check_for_red())
        self.__close = True

        self.use_default_settings = self.ui.defaultSettingsCheckBox.isChecked()

        self.exec()

    def __change_used_settings(self):
        """Set specific settings enabled or disabled based on the "Use
        request settings" checkbox.
        """
        check_box = self.sender()
        if check_box.isChecked():
            self.ui.tabs.setEnabled(False)
        else:
            self.ui.tabs.setEnabled(True)

    def __check_for_red(self):
        """
        Check whether there are any invalid field in the tabs.
        """
        df.check_for_red(self)

    def enabled_element_information(self):
        """
        Change the UI accordingly when an element is selected.
        """
        self.measurement_settings_widget.ui.isotopeComboBox.setEnabled(True)
        self.measurement_settings_widget.ui.isotopeLabel.setEnabled(True)
        self.ui.OKButton.setEnabled(True)

    def __update_parameters(self):
        """
         Update Simulation's Run, Detector and Target objects. If simulation
         specific parameters are in use, save them into a file.
        """
        if self.measurement_settings_widget.ui.isotopeComboBox.currentIndex()\
                == -1:
            QtWidgets.QMessageBox.critical(self, "Warning",
                                           "No isotope selected.\n\nPlease "
                                           "select an isotope for the beam "
                                           "element.",
                                           QtWidgets.QMessageBox.Ok,
                                           QtWidgets.QMessageBox.Ok)
            self.__close = False
            return

        if not self.simulation.measurement_setting_file_name:
            self.simulation.measurement_setting_file_name = \
                self.simulation.name

        if not self.ui.tabs.currentWidget().fields_are_valid:
            QtWidgets.QMessageBox.critical(self, "Warning",
                                           "Some of the setting values have"
                                           " not been set.\n" +
                                           "Please input values in fields "
                                           "indicated in red.",
                                           QtWidgets.QMessageBox.Ok,
                                           QtWidgets.QMessageBox.Ok)
            self.__close = False
            return

        # Lists of old and current simulations and optimizations
        simulations_run = self.check_if_simulations_run()
        simulations_running = self.simulations_running()
        optimization_running = self.optimization_running()
        optimization_run = self.check_if_optimization_run()

        check_box = self.ui.defaultSettingsCheckBox
        if check_box.isChecked() and not self.use_default_settings:
            if simulations_run and simulations_running:
                reply = QtWidgets.QMessageBox.question(
                    self, "Simulated and running simulations",
                    "There are simulations that use simulation settings, "
                    "and either have been simulated or are currently running."
                    "\nIf you save changes, the running simulations "
                    "will be stopped, and the result files of the simulated "
                    "and stopped simulations are deleted. This also applies "
                    "to possible optimization.\n\nDo you want to "
                    "save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    tmp_sims = copy.copy(self.simulation.running_simulations)
                    # Stop simulations
                    df.stop_simulations(self, tmp_sims)

                    for elem_sim in optimization_running:
                        elem_sim.optimization_stopped = True
                        elem_sim.optimization_running = False

                        self.tab.del_widget(elem_sim.optimization_widget)
                        elem_sim.simulations_done = False
                        # Handle optimization energy spectra
                        if elem_sim.optimization_recoils:
                            # Delete energy spectra that use
                            # optimized recoils
                            df.delete_optim_espe(self, elem_sim)

                            df.handle_old_sims_and_optims(
                                self, simulations_run, optimization_run)

            elif simulations_running:
                reply = QtWidgets.QMessageBox.question(
                    self, "Simulations running",
                    "There are simulations running that use simulation "
                    "settings.\nIf you save changes, the running "
                    "simulations will be stopped, and their result files "
                    "deleted. This also applies to possible "
                    "optimization.\n\nDo you want to save "
                    "changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    tmp_sims = copy.copy(self.simulation.running_simulations)
                    # Stop simulations
                    df.stop_simulations(self, tmp_sims)

            elif simulations_run:
                reply = QtWidgets.QMessageBox.question(
                    self, "Simulated simulations",
                    "There are simulations that use simulation settings, "
                    "and have been simulated.\nIf you save changes,"
                    " the result files of the simulated simulations are "
                    "deleted. This also affects possible "
                    "optimization.\n\nDo you want to save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    for elem_sim in simulations_run:
                        # Delete files
                        df.delete_simu_espe(self, elem_sim)

                        # Reset controls
                        if elem_sim.controls:
                            # TODO do not access controls via elem_sim. Use
                            #      observation.
                            elem_sim.controls.reset_controls()

                        # Change full edit unlocked
                        elem_sim.recoil_elements[0].widgets[0].parent. \
                            edit_lock_push_button.setText("Full edit unlocked")
                        elem_sim.simulations_done = False

                    df.update_optim_running(self, optimization_running)

                    for elem_sim in optimization_run:
                        self.tab.del_widget(elem_sim.optimization_widget)
                        elem_sim.simulations_done = False
                        if elem_sim.optimization_recoils:
                            # Delete energy spectra that use
                            # optimized recoils
                            df.delete_optim_espe(self, elem_sim)

            elif optimization_running:
                reply = QtWidgets.QMessageBox.question(
                    self, "Optimization running",
                    "There are optimizations running that use simulation "
                    "settings.\nIf you save changes, the running "
                    "optimizations will be stopped, and their result files "
                    "deleted.\n\nDo you want to save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    # Stop simulations
                    df.update_optim_running(self, optimization_running)

            elif optimization_run:
                reply = QtWidgets.QMessageBox.question(
                    self, "Optimization results",
                    "There are optimizations done that use simulation "
                    "settings.\nIf you save changes, result files will be "
                    "deleted.\n\nDo you want to save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    # Stop simulations
                    df.update_optim_running(self, optimization_run)

            # Use request settings
            self.simulation.run = None
            self.simulation.detector = None
            self.simulation.measurement_setting_file_description = ""
            self.simulation.target.target_theta = \
                self.simulation.request.default_target.target_theta

            # Remove setting files and folders
            det_folder_path = os.path.join(self.simulation.directory,
                                           "Detector")
            if os.path.exists(det_folder_path):
                shutil.rmtree(det_folder_path)
            filename_to_remove = ""
            for file in os.listdir(self.simulation.directory):
                if file.endswith(".measurement"):
                    filename_to_remove = file
                    break
            if filename_to_remove:
                os.remove(os.path.join(self.simulation.directory,
                                       filename_to_remove))
            self.use_default_settings = True
        else:
            if self.use_default_settings and check_box.isChecked():
                self.__close = True
                return
            only_unnotified_changed = False
            if not self.use_default_settings and not check_box.isChecked():
                # Check that values have been changed
                if not self.values_changed():
                    # Check if only those values that don't require rerunning
                    #  the simulations have been changed
                    if self.measurement_settings_widget.other_values_changed():
                        only_unnotified_changed = True
                    if self.detector_settings_widget.other_values_changed():
                        only_unnotified_changed = True
                    if not only_unnotified_changed:
                        self.__close = True
                        return
            if self.use_default_settings:
                settings = "request"
                tmp_sims = []
                for elem_sim in self.simulation.element_simulations:
                    if elem_sim in \
                            self.simulation.request.running_simulations:
                        tmp_sims.append(elem_sim)
            else:
                settings = "simulation"
                tmp_sims = copy.copy(self.simulation.running_simulations)

            if simulations_run and simulations_running and \
                    not only_unnotified_changed:
                reply = QtWidgets.QMessageBox.question(
                    self, "Simulated and running simulations",
                    "There are simulations that use " + settings + " settings, "
                    "and either have been simulated or are currently running."
                    "\nIf you save changes, the running simulations "
                    "will be stopped, and the result files of the simulated "
                    "and stopped simulations are deleted. This also applies "
                    "to possible optimization.\n\nDo you want to "
                    "save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    # Stop simulations
                    df.stop_simulations(self, tmp_sims)

                    for elem_sim in optimization_running:
                        elem_sim.optimization_stopped = True
                        elem_sim.optimization_running = False

                        self.tab.del_widget(elem_sim.optimization_widget)
                        elem_sim.simulations_done = False
                        # Handle optimization energy spectra
                        if elem_sim.optimization_recoils:
                            # Delete energy spectra that use
                            # optimized recoils
                            df.delete_optim_espe(self, elem_sim)

                    for elem_sim in simulations_run:
                        for recoil in elem_sim.recoil_elements:
                            delete_simulation_results(elem_sim, recoil)
                            # Delete energy spectra that use recoil
                            df.delete_recoil_espe(self, recoil.get_full_name())
                        elem_sim.simulations_done = False

                    for elem_sim in optimization_run:
                        self.tab.del_widget(elem_sim.optimization_widget)
                        elem_sim.simulations_done = False
                        if elem_sim.optimization_recoils:
                            # Delete energy spectra that use
                            # optimized recoils
                            df.delete_optim_espe(self, elem_sim)

            elif simulations_running and not only_unnotified_changed:
                reply = QtWidgets.QMessageBox.question(
                    self, "Simulations running",
                    "There are simulations running that use " + settings +
                    " settings.\nIf you save changes, the running "
                    "simulations will be stopped, and their result files "
                    "deleted. This also applies to possible "
                    "optimization.\n\nDo you want to save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    # Stop simulations
                    df.stop_simulations(self, tmp_sims)

            elif simulations_run and not only_unnotified_changed:
                reply = QtWidgets.QMessageBox.question(
                    self, "Simulated simulations",
                    "There are simulations that use " + settings +
                    " settings, and have been simulated.\nIf you save changes,"
                    " the result files of the simulated simulations are "
                    "deleted. This also affects possible optimization.\n\nDo "
                    "you want to save changes "
                    "anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    df.handle_old_sims_and_optims(self,
                                                  simulations_run,
                                                  optimization_run)

                    df.update_optim_running(self, optimization_running)

            elif optimization_running:
                reply = QtWidgets.QMessageBox.question(
                    self, "Optimization running",
                    "There are optimizations running that use " + settings +
                    " settings.\nIf you save changes, the running "
                    "optimizations will be stopped, and their result files "
                    "deleted.\n\nDo you want to save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    # Stop simulations
                    df.update_optim_running(self, optimization_running)

            elif optimization_run:
                reply = QtWidgets.QMessageBox.question(
                    self, "Optimization results",
                    "There are optimizations done that use " + settings +
                    " settings.\nIf you save changes, result files will be "
                    "deleted.\n\nDo you want to save changes anyway?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                    QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
                if reply == QtWidgets.QMessageBox.No or reply == \
                        QtWidgets.QMessageBox.Cancel:
                    self.__close = False
                    return
                else:
                    # Stop simulations
                    df.update_optim_running(self, optimization_run)

            # Use simulation specific settings
            try:
                measurement_settings_file_path = os.path.join(
                    self.simulation.directory,
                    self.simulation.measurement_setting_file_name
                    + ".measurement")
                target_file_path = os.path.join(self.simulation.directory,
                                                self.simulation.target.name
                                                + ".target")
                det_folder_path = os.path.join(self.simulation.directory,
                                               "Detector")

                if self.simulation.run is None:
                    # Create a default Run for simulation
                    self.simulation.run = Run()
                if self.simulation.detector is None:
                    df.update_detector_settings(
                        self.simulation,
                        det_folder_path,
                        measurement_settings_file_path)

                # Set Detector object to settings widget
                self.detector_settings_widget.obj = self.simulation. \
                    detector

                # Update settings
                self.measurement_settings_widget.update_settings()
                self.detector_settings_widget.update_settings()
                self.simulation.detector.path = \
                    os.path.join(det_folder_path,
                                 self.simulation.detector.name +
                                 ".detector")

                df.update_efficiency_files(self.simulation.detector)

                # Save measurement settings parameters.
                new_measurement_settings_file_path = os.path.join(
                    self.simulation.directory,
                    self.simulation.measurement_setting_file_name +
                    ".measurement")
                general_obj = {
                    "name": self.simulation.measurement_setting_file_name,
                    "description":
                        self.simulation.
                            measurement_setting_file_description,
                    "modification_time":
                        time.strftime("%c %z %Z", time.localtime(
                            time.time())),
                    "modification_time_unix": time.time()
                }

                if os.path.exists(new_measurement_settings_file_path):
                    obj = json.load(open(
                        new_measurement_settings_file_path))
                    obj["general"] = general_obj
                else:
                    obj = {
                        "general": general_obj
                    }

                # Delete possible extra .measurement files
                filename_to_remove = ""
                for file in os.listdir(self.simulation.directory):
                    if file.endswith(".measurement"):
                        filename_to_remove = file
                        break
                if filename_to_remove:
                    os.remove(os.path.join(self.simulation.directory,
                                           filename_to_remove))

                # Write measurement settings to file
                with open(new_measurement_settings_file_path, "w") as file:
                    json.dump(obj, file, indent=4)

                # Save Run object to file
                self.simulation.run.to_file(
                    new_measurement_settings_file_path)
                # Save Detector object to file
                self.simulation.detector.to_file(
                    self.simulation.detector.path,
                    new_measurement_settings_file_path)

                # Save Target object to file
                self.simulation.target.to_file(
                    target_file_path, new_measurement_settings_file_path)

            except TypeError:
                QtWidgets.QMessageBox.question(self, "Warning",
                                               "Some of the setting values "
                                               "have not been set.\n" +
                                               "Please input setting values"
                                               " to save them.",
                                               QtWidgets.QMessageBox.Ok,
                                               QtWidgets.QMessageBox.Ok)
            self.use_default_settings = False

    def __save_settings_and_close(self):
        """Save settings and close the dialog.
        """
        self.__update_parameters()
        if self.__close:
            self.close()

    def check_if_optimization_run(self):
        """
        Check if the re are any element simulations that have optimization
        results.

        Return:
             List of optimized simulations.
        """
        opt_run = []
        for elem_sim in self.simulation.element_simulations:
            if elem_sim.optimization_widget and not \
                    elem_sim.optimization_running:
                opt_run.append(elem_sim)
        return opt_run

    def check_if_simulations_run(self):
        """
        Check if the re are any element simulations that have been simulated.

        Return:
             List of run simulations.
        """
        simulations_run = []
        for elem_sim in self.simulation.element_simulations:
            if elem_sim.simulations_done:
                simulations_run.append(elem_sim)
        return simulations_run

    def simulations_running(self):
        """
        Check if there are any simulations running.

        Return:
            True or False.
        """
        for elem_sim in self.simulation.element_simulations:
            if elem_sim in self.simulation.request.running_simulations:
                return True
            elif elem_sim in self.simulation.running_simulations:
                return True
        return False

    def optimization_running(self):
        ret = []
        for elem_sim in self.simulation.element_simulations:
            if elem_sim.optimization_running:
                ret.append(elem_sim)
        return ret

    def values_changed(self):
        """
        Check if measurement or detector settings have
        changed.

        Return:

            True or False.
        """
        if self.measurement_settings_widget.values_changed():
            return True
        if self.detector_settings_widget.values_changed():
            return True
        return False
