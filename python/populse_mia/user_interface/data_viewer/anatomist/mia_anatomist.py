
'''
MIA data viewer implementation based on `Anatomist <http://brainvisa.info/anatomist/user_doc/index.html>`_
'''

from __future__ import print_function
from __future__ import absolute_import

from soma.qt_gui.qt_backend import Qt
from ..data_viewer import DataViewer
from anatomist.simpleviewer.anasimpleviewer import AnaSimpleViewer
from populse_mia.user_interface.data_browser.data_browser \
    import TableDataBrowser
from populse_mia.data_manager.project import TAG_FILENAME, COLLECTION_CURRENT
import os


class MiaViewer(Qt.QWidget, DataViewer):
    '''
    :class:`MIA data viewer <populse_mia.user_interface.data_viewer.data_viewer.DataViewer>`
    implementation based on `PyAnatomist <http://brainvisa.info/pyanatomist/sphinx/index.html>`_
    '''

    def __init__(self, init_global_handlers = None):

        super(MiaViewer, self).__init__()

        self.anaviewer = AnaSimpleViewer(init_global_handlers)

        # count global number of viewers using anatomist, in order to close it
        # nicely
        if not hasattr(DataViewer, 'mia_viewers'):
            DataViewer.mia_viewers = 0
        DataViewer.mia_viewers += 1

        findChild = lambda x, y: Qt.QObject.findChild(x, Qt.QObject, y)

        awidget = self.anaviewer.awidget
        toolbar = findChild(awidget, 'toolBar')
        open_action = findChild(awidget, 'fileOpenAction')
        db_action = Qt.QAction(open_action.icon(), 'filter', awidget)
        toolbar.insertAction(open_action, db_action)
        db_action.triggered.connect(self.filter_documents)

        layout = Qt.QVBoxLayout()
        self.setLayout(layout)
        self.anaviewer.awidget.setSizePolicy(Qt.QSizePolicy.Expanding,
                                          Qt.QSizePolicy.Expanding)
        layout.addWidget(self.anaviewer.awidget)

        self.project = None
        self.documents = []
        self.displayed = []

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

    def filter_documents(self):
        dialog = Qt.QDialog()
        layout = Qt.QVBoxLayout()
        dialog.setLayout(layout)
        table_data = TableDataBrowser(
            self.project, self, self.project.session.get_shown_tags(), False,
            True, link_viewer=False)
        layout.addWidget(table_data)
        hlay = Qt.QHBoxLayout()
        layout.addLayout(hlay)
        ok = Qt.QPushButton('Display')
        hlay.addWidget(ok)
        ok.clicked.connect(dialog.accept)
        ok.setDefault(True)
        cancel = Qt.QPushButton('Cancel')
        hlay.addWidget(cancel)
        cancel.clicked.connect(dialog.reject)
        hlay.addStretch(1)

        # Reducing the list of scans to selection
        all_scans = table_data.scans_to_visualize
        table_data.scans_to_visualize = self.documents
        table_data.scans_to_search = self.documents
        table_data.update_visualized_rows(all_scans)

        res = dialog.exec_()
        if res == Qt.QDialog.Accepted:
            points = table_data.selectedIndexes()
            result_names = []
            for point in points:
                row = point.row()
                # We get the FileName of the scan from the first row
                scan_name = table_data.item(row, 0).text()
                value = self.project.session.get_value(COLLECTION_CURRENT,
                                                       scan_name, TAG_FILENAME)
                value = os.path.abspath(os.path.join(self.project.folder,
                                                     value))
                result_names.append(value)
            self.display_files(result_names)

    def close(self):
        super(MiaViewer, self).close()
        close_ana = False
        DataViewer.mia_viewers -= 1 # dec count
        if DataViewer.mia_viewers == 0:
            close_ana = True
        self.anaviewer.closeAll(close_ana)
