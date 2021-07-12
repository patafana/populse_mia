from soma.qt_gui.qt_backend import Qt, QtCore
from soma.qt_gui.qt_backend.uic import loadUi
import os
import anatomist.direct.api as ana




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

        # connect GUI actions callbacks
        def findChild(x, y): return Qt.QObject.findChild(x, QtCore.QObject, y)

        self.window = awin
        self.viewNewWindow = findChild(awin, 'windows')
        self.newViewLay = Qt.QHBoxLayout(self.viewNewWindow)
        self.new_awindow = None
        self.object = None

        self.popup_window = Qt.QWidget()
        self.popups = []
        layout = Qt.QVBoxLayout()
        self.popup_window.setLayout(layout)
        self.popup_window.resize(730,780)
        self.window.setSizePolicy(Qt.QSizePolicy.Expanding,
                                          Qt.QSizePolicy.Expanding)
        layout.addWidget(self.window)

        #find views viewButtons
        self.viewButtons = [findChild(awin, 'actionAxial'), findChild(awin, 'actionSagittal'), findChild(awin, 'actionCoronal'), findChild(awin, 'action3D')]
        self.viewButtons[0].setChecked(True)
        #For now 3D doesn't work:
        self.viewButtons[3].setEnabled(False)

        self.viewButtons[0].triggered.connect(lambda : self.changeDisplay(0, self.object))
        self.viewButtons[1].triggered.connect(lambda : self.changeDisplay(1, self.object))
        self.viewButtons[2].triggered.connect(lambda : self.changeDisplay(2, self.object))
        self.viewButtons[3].triggered.connect(lambda : self.changeDisplay(3, self.object))

    def changeDisplay(self, index, object):
        a = ana.Anatomist('-b')
        views = ['Axial', 'Sagittal', 'Coronal', '3D']
        new_view = views[index]
        self.disableButton(index)
        self.createNewWindow(new_view)
        a.addObjects(object, self.new_awindow)


    def disableButton(self, index):
        for i in [0, 1, 2, 3]:
            #The i==3 will have to be removed when 3D is going to work
            if i == index or i==3:
                pass
            else:
                self.viewButtons[i].setChecked(False)
                self.viewButtons[i].setEnabled(True)

    def createNewWindow(self, wintype='Axial'):
        a = ana.Anatomist('-b')
        w = a.createWindow(wintype, no_decoration=True, options={'hidden': 1})
        w.setAcceptDrops(False)

        #Delete object if there is already one
        if self.newViewLay.itemAt(0):
            self.newViewLay.itemAt(0).widget().deleteLater()

        x = 0
        y = 0
        i = 0
        if not hasattr(self, '_winlayouts'):
            self._winlayouts = [[0, 0], [0, 0]]
        else:
            freeslot = False
            for y in (0, 1):
                for x in (0, 1):
                    i = i+1
                    if not self._winlayouts[x][y]:
                        freeslot = True
                        break
                if freeslot:
                    break
        self.newViewLay.addWidget(w.getInternalRep())
        self.new_awindow = w
        self._winlayouts[x][y] = 1

        #For now 3D isn't working
        if wintype == '3D':
            print("3D isn't working for now")
        #    a.execute('SetControl', windows=[w], control=self.control_3d_type)
        else:
            a.execute('SetControl', windows=[w], control='Simple2DControl')
            a.assignReferential(a.mniTemplateRef, w)
            # force redrawing in MNI orientation
            # (there should be a better way to do so...)
            if wintype == 'Axial':
                w.muteAxial()
                print('MUTEAXIAL', w.muteAxial)
            elif wintype == 'Coronal':
                w.muteCoronal()
            elif wintype == 'Sagittal':
                w.muteSagittal()
            elif wintype == 'Oblique':
                w.muteOblique()
        # set a black background
        a.execute('WindowConfig', windows=[w],
                  light={'background': [0., 0., 0., 1.]}, view_size=(500,600))


    def setObject(self, object):
        self.object = object

    def addNewObject(self, obj):
        """ Not used, maybe will be usefull for 3D rendering but not sure
        """
        opts = {}
        if obj.objectType == 'VOLUME':
            # volumes have a specific function since several volumes have to be
            # fusionned, and a volume rendering may occur
            return ['volume', opts]
        elif obj.objectType == 'SURFACE':
            return  ['mesh', opts]
        elif obj.objectType == 'GRAPH':
            opts['add_graph_nodes'] = 1
            return [None, opts]

    def close(self):
        self.window.close()
        self.window = None
        self.viewNewWindow = []
        self.newViewLay = None
        self.new_awindow = None
        self.object = []
