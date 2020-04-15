# -*- coding: utf-8 -*- #
"""
Populse-MIA data viewer GUI interface, in the "Data Viewer" tab.

Contains:
    Class:
        - DataViewerTab

"""

from soma.qt_gui.qt_backend import Qt
import importlib
import os


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

        self.viewers_combo.addItem('Anatomist')
        self.viewers_combo.activated.connect(self.viewer_activated)
        lay.addStretch(1)

        self.layout = lay
        self.viewer_name = None
        self.viewer = None

        # self.viewer_activated(0)

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
        print('activate viewer:', viewer_name)
        try:
            viewer_module = importlib.import_module(
                '%s.%s' % (__name__.rsplit('.', 1)[0], viewer_name))
            viewer = viewer_module.MiaViewer()
        except ImportError:
            print('viewer %s is not available or not working.' % viewer_name)
            return
        if self.viewer is not None:
            self.viewer.deleteLater()
            del self.viewer
        self.viewer_name = viewer_name
        self.viewer = viewer
        self.layout.insertWidget(1, viewer)

    def set_documents(self, project, documents):
        if self.viewer:
            self.viewer.set_documents(project, documents)





