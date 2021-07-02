# -*- coding: utf-8 -*- #
"""
Populse-MIA data viewer GUI interface, in the "Data Viewer" tab.

Contains:
    Class:
        - DataViewerTab

"""

from soma.qt_gui.qt_backend import Qt
#import anatomist.direct.api as ana
import importlib
import os
import traceback


class DataViewerTab(Qt.QWidget):
    '''
    DataViewerTab is the widget in the data viewer tab of Populse-MIA GUI.
    A combobox containing the available viewers will always appear
    If import of anatomist and anatomist_2 fails, it won't impact the work of Mia itself
    Viewers are put in Qt.QStackedLayout in order to share a same project
    A new viewer can be added
    '''

    def __init__(self, main_window):

        super(DataViewerTab, self).__init__()

        self.stacks = []
        self.lay = []
        self.viewer_name = None
        self.viewer = None
        self.project = []
        self.docs = []
        self.viewers = []

        #Display of combobox containing the viewers
        self.main_window = main_window
        self.lay = Qt.QVBoxLayout()
        self.setLayout(self.lay)

        hlay = Qt.QHBoxLayout()
        self.lay.addLayout(hlay)
        hlay.addWidget(Qt.QLabel('use viewer:'))

        #Combobox will contain the viewers if they are available
        self.viewers_combo = Qt.QComboBox()
        self.viewers_combo.setMinimumWidth(150)

        hlay.addWidget(self.viewers_combo)
        hlay.addStretch(1)

        self.viewers_combo.currentIndexChanged.connect(self.change_viewer)

    def change_viewer(self):
        '''switche to viewer selected in the combobox
        pass the project from on viewer to the other
        '''
        index = self.viewers_combo.currentIndex()
        self.viewer_activated(index)
        self.set_documents(self.project, self.docs)

    def current_viewer(self):
        if self.viewer_name is None:
            return self.viewers_combo.currentText().lower()
        else:
            return self.viewer_name

    def viewer_activated(self, index):
        viewer_name = self.viewers_combo.itemText(index).lower()
        self.activate_viewer(viewer_name)

    def load_viewer(self, viewer_name):

        if self.viewers.__len__() == 0:
            self.stacks = Qt.QStackedLayout()
            self.lay.addLayout(self.stacks)

        init_global_handlers = True

        #Try import anatomist viewer
        if 'anatomist' not in self.viewers:
            try:
                viewer_name = 'anatomist'
                viewer_module = importlib.import_module(
                '%s.%s' % (__name__.rsplit('.', 1)[0], viewer_name))
                self.viewer_anatomist = viewer_module.MiaViewer()
                self.stacks.addWidget(self.viewer_anatomist)
                self.viewers_combo.addItem('Anatomist')
                self.viewers.append('anatomist')
                #Check if initialization of controls has been done:
                if self.viewer_anatomist.anaviewer._global_handlers_initialized:
                    init_global_handlers = False

            except Exception as e:
                print('\n{0} viewer is not available or not working '
                      '...!\nTraceback:'.format(viewer_name))
                print(''.join(traceback.format_tb(e.__traceback__)), end='')
                print('{0}: {1}\n'.format(e.__class__.__name__, e))

        #Try import anatomist_2
        if 'anatomist_2' not in self.viewers:
            try:
                viewer_name = 'anatomist_2'
                viewer_module = importlib.import_module(
                '%s.%s' % (__name__.rsplit('.', 1)[0], viewer_name))
                self.viewer_anatomist_2 = viewer_module.MiaViewer(init_global_handlers)
                self.stacks.addWidget(self.viewer_anatomist_2)
                self.viewers_combo.addItem('Anatomist_2')
                self.viewers.append('anatomist_2')

            except Exception as e:
                print('\n{0} viewer is not available or not working '
                      '...!\nTraceback:'.format(viewer_name))
                print(''.join(traceback.format_tb(e.__traceback__)), end='')
                print('{0}: {1}\n'.format(e.__class__.__name__, e))

    def activate_viewer(self, viewer_name):
        viewer = viewer_name
        if self.viewer_name == viewer_name:
            return
        print('- activate viewer:', viewer_name)

        if viewer_name == 'anatomist':
            viewer = self.viewer_anatomist
        if viewer_name == 'anatomist_2':
            viewer = self.viewer_anatomist_2

        if viewer:
            self.stacks.setCurrentWidget(viewer)
            self.viewer = viewer

    def set_documents(self, project, documents):
        if self.viewer:
            self.viewer.set_documents(project, documents)
            self.project = project
            self.docs = documents
