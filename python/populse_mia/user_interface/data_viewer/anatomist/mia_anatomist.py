
from __future__ import absolute_import

from soma.qt_gui.qt_backend import Qt
from ..data_viewer import DataViewer
from anatomist.simpleviewer.anasimpleviewer import AnaSimpleViewer


class MiaViewer(Qt.QWidget, DataViewer):

    def __init__(self):

        super(MiaViewer, self).__init__()

        self.anaviewer = AnaSimpleViewer()

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
        print('display:', files)
        self.displayed += files

    def displayed_files(self):
        return self.displayed

    def remove_files(self, files):
        print('remove:', files)
        self.files = [doc for doc in self.displayed
                      if doc not in files]

    def set_documents(self, project, documents):
        self.project = project
        self.documents = documents

    def filter_documents(self):
        print('filter docs')



