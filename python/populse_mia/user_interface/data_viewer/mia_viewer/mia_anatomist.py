
'''
MIA data viewer implementation based on `Anatomist <http://brainvisa.info/anatomist/user_doc/index.html>`_
'''

from __future__ import print_function
from __future__ import absolute_import
import anatomist.direct.api as ana

from soma.qt_gui.qt_backend import Qt
from ..data_viewer import DataViewer
#from ..anasimpleviewer2 import AnaSimpleViewer
from populse_mia.user_interface.data_viewer.mia_viewer.anasimpleviewer2 import AnaSimpleViewer
from populse_mia.user_interface.data_viewer.mia_viewer import resources
from populse_mia.user_interface.data_browser.rapid_search import RapidSearch
from populse_mia.user_interface.data_browser.data_browser \
    import TableDataBrowser
from populse_mia.data_manager.project import TAG_FILENAME, COLLECTION_CURRENT
import os
from populse_mia.user_interface.data_browser.advanced_search import AdvancedSearch
from populse_mia.software_properties import Config
from PyQt5.QtWidgets import (QToolButton, QHBoxLayout, QLineEdit)
from PyQt5.QtGui import QIcon, QDoubleValidator

not_defined_value = "*Not Defined*"

class MiaViewer(Qt.QWidget, DataViewer):
    '''
    :class:`MIA data viewer <populse_mia.user_interface.data_viewer.data_viewer.DataViewer>`
    implementation based on `PyAnatomist <http://brainvisa.info/pyanatomist/sphinx/index.html>`_
    '''

    def __init__(self):

        super(MiaViewer, self).__init__()

        self.anaviewer = AnaSimpleViewer()

        findChild = lambda x, y: Qt.QObject.findChild(x, Qt.QObject, y)

        awidget = self.anaviewer.awidget

        #Filter action Icon (find images from the browser)
        filter_action = findChild(awidget, 'filterAction')
        preferences_action = findChild(awidget, 'actionPreferences')

        filter_action.triggered.connect(self.filter_documents)
        preferences_action.triggered.connect(self.preferences)

        layout = Qt.QVBoxLayout()
        self.setLayout(layout)
        self.anaviewer.awidget.setSizePolicy(Qt.QSizePolicy.Expanding,
                                          Qt.QSizePolicy.Expanding)
        layout.addWidget(self.anaviewer.awidget)

        #comments were for when I tried to display both viewers (must be added as arguments is init too)
        #self.project = project
        #self.documents = docs
        self.project = None
        self.documents = []
        self.displayed = []
        self.table_data = []
        self.im_sec = 5

    def display_files(self, files):
        self.displayed += files
        for filename in files:
            self.anaviewer.loadObject(filename)

    def displayed_files(self):
        return self.displayed

    def remove_files(self, files):
        self.anaviewer.deleteObjectsFromFiles(files)
        self.files = [doc for doc in self.displayed
                      if doc not in files]

    def set_documents(self, project, documents):
        if self.project is not project:
            self.clear()
        self.project = project
        self.documents = documents

    def reset_search_bar(self):
        """Reset the rapid search bar."""
        self.search_bar.setText("")

    def search_str(self, str_search):
        """Search a string in the table and updates the vnot_defined_value = "*Not Defined*"isualized documents.

        :param str_search: string to search
        """

        old_scan_list = self.table_data.scans_to_visualize
        return_list = []

        # Every scan taken if empty search
        if str_search == "":
            return_list = self.table_data.scans_to_search
        else:
            # Scans with at least a not defined value
            if str_search == not_defined_value:
                filter = self.search_bar.prepare_not_defined_filter(
                    self.project.session.get_shown_tags())
            # Scans matching the search
            else:
                filter = self.search_bar.prepare_filter(
                    str_search, self.project.session.get_shown_tags(),
                    self.table_data.scans_to_search)

            generator = self.project.session.filter_documents(
                COLLECTION_CURRENT, filter)

            # Creating the list of scans
            return_list = [getattr(scan, TAG_FILENAME) for scan in generator]

        self.table_data.scans_to_visualize = return_list

        # Rows updated
        self.table_data.update_visualized_rows(old_scan_list)

        self.project.currentFilter.search_bar = str_search

    def filter_documents(self):
        dialog = Qt.QDialog()
        dialog.setWindowTitle('Filter documents')
        dialog.resize(1150,500)
        layout = Qt.QVBoxLayout()
        dialog.setLayout(layout)

        #Some specific filtering
        #QLineEdit for research
        self.search_bar = RapidSearch(dialog)
        self.search_bar.textChanged.connect(self.search_str)
        #Cancel search button
        sources_images_dir = Config().getSourceImageDir()
        button_cross = QToolButton()
        button_cross.setStyleSheet('background-color:rgb(255, 255, 255);')
        button_cross.setIcon(
            QIcon(os.path.join(sources_images_dir, 'gray_cross.png')))
        button_cross.clicked.connect(self.reset_search_bar)

        title = Qt.QLabel()
        title.setText('Search by FileName: ')

        layout.addWidget(title)

        search_bar_layout = QHBoxLayout()
        search_bar_layout.addWidget(self.search_bar)
        search_bar_layout.addSpacing(3)
        search_bar_layout.addWidget(button_cross)
        #Add layout to dialogBox
        layout.addLayout(search_bar_layout)
        layout.addSpacing(8)

        self.table_data = TableDataBrowser(
            self.project, self, self.project.session.get_shown_tags(), False,
            True, link_viewer=False)
        layout.addWidget(self.table_data)
        hlay = Qt.QHBoxLayout()
        layout.addLayout(hlay)
        ok = Qt.QPushButton('Import')
        hlay.addWidget(ok)
        ok.clicked.connect(dialog.accept)
        ok.setDefault(True)
        cancel = Qt.QPushButton('Cancel')
        hlay.addWidget(cancel)
        cancel.clicked.connect(dialog.reject)
        hlay.addStretch(1)

        # Reducing the list of scans to selection
        all_scans = self.table_data.scans_to_visualize
        self.table_data.scans_to_visualize = self.documents
        self.table_data.scans_to_search = self.documents
        self.table_data.update_visualized_rows(all_scans)

        res = dialog.exec_()
        if res == Qt.QDialog.Accepted:
            points = self.table_data.selectedIndexes()
            result_names = []
            for point in points:
                row = point.row()
                # We get the FileName of the scan from the first row
                scan_name = self.table_data.item(row, 0).text()
                value = self.project.session.get_value(COLLECTION_CURRENT,
                                                       scan_name, TAG_FILENAME)
                value = os.path.abspath(os.path.join(self.project.folder,
                                                     value))
                result_names.append(value)
            self.display_files(result_names)

    def preferences(self):
        dialog = Qt.QDialog()
        dialog.setWindowTitle('Preferences')
        dialog.resize(800,500)
        layout = Qt.QVBoxLayout()
        dialog.setLayout(layout)


        #set automatic time frame rate
        frame_rate_layout = QHBoxLayout()
        title = Qt.QLabel()
        title.setText('Automatic time image display:')
        line_edit = Qt.QLineEdit()
        line_edit.setText(str(self.im_sec))
        line_edit.setValidator(QDoubleValidator(0,50,4))
        unit = Qt.QLabel()
        unit.setText('image/s')
        frame_rate_layout.addWidget(title)
        frame_rate_layout.addWidget(line_edit)
        frame_rate_layout.addWidget(unit)
        frame_rate_layout.insertSpacing(1, 200)
        layout.addLayout(frame_rate_layout)

        #Save and cancel buttons
        hlay = Qt.QHBoxLayout()
        layout.addLayout(hlay)
        ok = Qt.QPushButton('Save')
        hlay.addStretch(1)
        hlay.addWidget(ok)
        ok.clicked.connect(dialog.accept)
        ok.setDefault(True)
        cancel = Qt.QPushButton('Cancel')
        hlay.addWidget(cancel)
        cancel.clicked.connect(dialog.reject)
        hlay.addStretch(1)

        res = dialog.exec_()

        if res == Qt.QDialog.Accepted:
            if line_edit.isModified():
                self.im_sec = float(line_edit.text())

            self.anaviewer.setpreferences(self.im_sec)
