# -*- coding: utf-8 -*- #
"""
Populse-MIA data viewer GUI interface, in the "Data Viewer" tab.

Contains:
    Class:
        - DataViewerTab

"""

from soma.qt_gui.qt_backend import Qt
import anatomist.direct.api as ana
import importlib
import os
import traceback


class DataViewerTab(Qt.QWidget):
    '''
    DataViewerTab is the widget in the data viewer tab of Populse-MIA GUI.
    '''

    def __init__(self, main_window):

        super(DataViewerTab, self).__init__()

        self.main_window = main_window
        lay = Qt.QVBoxLayout()
        self.setLayout(lay)

        hlay = Qt.QHBoxLayout()
        lay.addLayout(hlay)
        hlay.addWidget(Qt.QLabel('use viewer:'))

        self.viewers_combo = Qt.QComboBox()
        hlay.addWidget(self.viewers_combo)
        hlay.addStretch(1)

        self.viewers_combo.addItem('Mia_viewer')
        #self.viewers_combo.activated.connect(self.viewer_activatedbis)
        lay.addStretch(1)

        self.viewers_combo.addItem('Anatomist')
        #self.viewers_combo.activated.connect(self.viewer_activated)
        lay.addStretch(1)

        stacks = Qt.QStackedLayout()
        lay.addLayout(stacks)
        lay.addStretch(2)

        #Try import both viewers
        try:
            module_anatomist = 'populse_mia.user_interface.data_viewer.anatomist'
            path = os.getcwd()
            viewer_module_anatomist = importlib.import_module(module_anatomist, os.path.join(path,'user_interface/data_viewer/anatomist/__init__.py'))
            self.viewer_anatomist = viewer_module_anatomist.MiaViewer()

            module_miaViewer = 'populse_mia.user_interface.data_viewer.mia_viewer'
            viewer_module_miaViewer = importlib.import_module(module_miaViewer, os.path.join(path,'user_interface/data_viewer/mia_viewer/__init__.py'))
            self.viewer_miaViewer = viewer_module_miaViewer.MiaViewer()

        except Exception as e:
            print('\n{0} viewer is not available or not working '
                  '...!\nTraceback:'.format(viewer_name))
            print(''.join(traceback.format_tb(e.__traceback__)), end='')
            print('{0}: {1}\n'.format(e.__class__.__name__, e))
            return

        #Add Widgets to QStackLayout (defaulf display is the first widget added)
        stacks.addWidget(self.viewer_anatomist)
        stacks.addWidget(self.viewer_miaViewer)

        self.stacks = stacks
        self.layout = lay
        self.viewer_name = None
        self.viewer = None
        self.project = []
        self.docs = []

        self.viewers_combo.currentIndexChanged.connect(self.change_viewer)

    def change_viewer(self):
        index = self.viewers_combo.currentIndex()
        self.viewer_activated(index)
        self.viewer.project = self.project
        self.viewer.documents = self.docs

    def current_viewer(self):
        if self.viewer_name is None:
            return self.viewers_combo.currentText().lower()
        else:
            return self.viewer_name

    def viewer_activated(self, index):
        viewer_name = self.viewers_combo.itemText(index).lower()
        self.activate_viewer(viewer_name)

    def activate_viewer(self, viewer_name):
        if self.viewer_name == viewer_name:
            return

        print('- activate viewer:', viewer_name)

        if viewer_name == 'anatomist':
            viewer = self.viewer_anatomist
        else:
            viewer = self.viewer_miaViewer
        self.stacks.setCurrentWidget(viewer)
        self.viewer = viewer

    def set_documents(self, project, documents):
        if self.viewer:
            self.viewer.set_documents(project, documents)
            self.project = project
            self.docs = documents
