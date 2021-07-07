
from soma.qt_gui.qt_backend import Qt
from soma.qt_gui.qt_backend.uic import loadUi





class NewWindowViewer(Qt.QObject):
    """
    Class defined to open a new window for a selected object with only one view possible
    The user will be able to choose which view he wants to display (axial,
    sagittal or coronal view)
    """

    def __init__(self):
        Qt.QObject.__init__(self)

        #Load ui file
        uifile = 'second_window.ui'
        cwd = os.getcwd()
        mainwindowdir = os.path.join(cwd,'user_interface/data_viewer/anatomist_2')
        os.chdir(mainwindowdir)
        awin = loadUi(os.path.join(mainwindowdir, uifile))
        os.chdir(cwd)
        self.window = awin

        # connect GUI actions callbacks
        def findChild(x, y): return Qt.QObject.findChild(x, QtCore.QObject, y)

        #find views viewButtons
        self.viewButtons = [findChild(awin, 'actionAxial'), findChild(awin, 'actionSagittal'), findChild(awin, 'actionCoronal'), findChild(awin, 'action3D')]
