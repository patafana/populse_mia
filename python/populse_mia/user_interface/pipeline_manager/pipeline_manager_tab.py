# -*- coding: utf-8 -*- #
"""
Module to define pipeline manager tab appearance, settings and methods.

Contains:
    Class:
        - PipelineManagerTab
        - RunProgress
        - RunWorker

"""

##########################################################################
# Populse_mia - Copyright (C) IRMaGe/CEA, 2018
# Distributed under the terms of the CeCILL license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL_V2.1-en.html
# for details.
##########################################################################

# Populse_MIA imports
from populse_mia.user_interface.pipeline_manager.process_mia import ProcessMIA
from populse_mia.user_interface.pop_ups import (PopUpSelectIteration,
                                                PopUpInheritanceDict)
from populse_mia.user_interface.pipeline_manager.iteration_table import (
                                                                 IterationTable)
from populse_mia.data_manager.project import (COLLECTION_CURRENT,
                                              COLLECTION_INITIAL,
                                              COLLECTION_BRICK, BRICK_NAME,
                                              BRICK_OUTPUTS, BRICK_INPUTS,
                                              TAG_BRICKS, BRICK_INIT,
                                              BRICK_INIT_TIME, TAG_TYPE,
                                              TAG_EXP_TYPE, TAG_FILENAME,
                                              TAG_CHECKSUM, TYPE_NII, TYPE_MAT,
                                              TYPE_TXT, TYPE_UNKNOWN)
from populse_mia.user_interface.pipeline_manager.node_controller import (
    NodeController, CapsulNodeController)
from populse_mia.user_interface.pipeline_manager.pipeline_editor import (
                                                             PipelineEditorTabs)
from populse_mia.user_interface.pipeline_manager.process_library import (
                                                           ProcessLibraryWidget)
from populse_mia.software_properties import Config

# Capsul imports
from capsul.api import (get_process_instance, NipypeProcess, Pipeline,
                        PipelineNode, ProcessNode, StudyConfig, Switch)
from capsul.qt_gui.widgets.pipeline_developper_view import (
                                                         PipelineDevelopperView)
from capsul.engine import WorkflowExecutionError
from capsul.pipeline import pipeline_tools
import soma_workflow.constants as swconstants
from soma.controller.trait_utils import is_file_trait

# PyQt5 imports
from PyQt5.QtCore import Signal, Qt, QThread, QTimer
from PyQt5.QtWidgets import (QMenu, QVBoxLayout, QWidget, QSplitter,
                             QApplication, QToolBar, QAction, QHBoxLayout,
                             QScrollArea, QMessageBox, QProgressDialog,
                             QPushButton)
from PyQt5.QtGui import QCursor, QIcon, QMovie

# Other import
import datetime
import inspect
import os
import re
import sys
import uuid
import copy
import threading
from collections import OrderedDict
from matplotlib.backends.qt_compat import QtWidgets
from traits.trait_errors import TraitError
from traits.api import TraitListObject, Undefined


if sys.version_info[0] >= 3:
    unicode = str

    def values(d):
        return list(d.values())
else:
    def values(d):
        return d.values()


# FIXME hack
NodeController = CapsulNodeController


class PipelineManagerTab(QWidget):
    """
    Widget that handles the Pipeline Manager tab.

    .. Methods:
        - add_plug_value_to_database: add the plug value to the database.
        - add_process_to_preview: add a process to the pipeline
        - controller_value_changed: update history when a pipeline node is
          changed
        - displayNodeParameters: display the node controller when a node is
          clicked
        - init_pipeline: initialize the current pipeline of the pipeline
          editor
        - initialize: clean previous initialization then initialize the current
          pipeline
        - layout_view : initialize layout for the pipeline manager
        - loadParameters: load pipeline parameters to the current pipeline of
          the pipeline editor
        - loadPipeline: load a pipeline to the pipeline editor
        - redo: redo the last undone action on the current pipeline editor
        - runPipeline: run the current pipeline of the pipeline editor
        - saveParameters: save the pipeline parameters of the the current
          pipeline of the pipeline editor
        - savePipeline: save the current pipeline of the pipeline editor
        - savePipelineAs: save the current pipeline of the pipeline editor
          under another name
        - undo: undo the last action made on the current pipeline editor
        - updateProcessLibrary: update the library of processes when a
          pipeline is saved
        - update_user_mode: update the visibility of widgets/actions
          depending of the chosen mode
        - update_project: update the project attribute of several objects
        - update_scans_list: update the user-selected list of scans
    """

    item_library_clicked = Signal(str)

    def __init__(self, project, scan_list, main_window):
        """
        Initialization of the Pipeline Manager tab

        :param project: current project in the software
        :param scan_list: list of the selected database files
        :param main_window: main window of the software
        """

        config = Config()

        # Necessary for using MIA bricks
        ProcessMIA.project = project
        self.project = project
        self.inheritance_dict = None
        self.init_clicked = False
        self.test_init = False
        if len(scan_list) < 1:
            self.scan_list = self.project.session.get_documents_names(
                COLLECTION_CURRENT)
        else:
            self.scan_list = scan_list
        self.main_window = main_window
        self.enable_progress_bar = False

        # This list is the list of scans contained in the iteration table
        # If it is empty, the scan list in the Pipeline Manager is the scan
        # list from the data_browser
        self.iteration_table_scans_list = []
        self.brick_list = []

        # Used for the inheritance dictionary
        self.key = {}
        self.ignore = {}
        self.ignore_node = False

        QWidget.__init__(self)

        self.verticalLayout = QVBoxLayout(self)
        self.processLibrary = ProcessLibraryWidget(self.main_window)
        self.processLibrary.process_library.item_library_clicked.connect(
            self.item_library_clicked)
        self.item_library_clicked.connect(self._show_preview)

        # self.diagramScene = DiagramScene(self)
        self.pipelineEditorTabs = PipelineEditorTabs(
            self.project, self.scan_list, self.main_window)
        self.pipelineEditorTabs.node_clicked.connect(
            self.displayNodeParameters)
        self.pipelineEditorTabs.process_clicked.connect(
            self.displayNodeParameters)
        self.pipelineEditorTabs.switch_clicked.connect(
            self.displayNodeParameters)
        self.pipelineEditorTabs.pipeline_saved.connect(
            self.updateProcessLibrary)
        self.nodeController = NodeController(
            self.project, self.scan_list, self, self.main_window)
        self.nodeController.visibles_tags = \
            self.project.session.get_shown_tags()

        self.iterationTable = IterationTable(
            self.project, self.scan_list, self.main_window)
        self.iterationTable.iteration_table_updated.connect(
            self.update_scans_list)

        self.previewBlock = PipelineDevelopperView(
            pipeline=None, allow_open_controller=False,
            show_sub_pipelines=True, enable_edition=False)

        self.startedConnection = None

        # Actions
        self.load_pipeline_action = QAction("Load pipeline", self)
        self.load_pipeline_action.triggered.connect(self.loadPipeline)

        self.save_pipeline_action = QAction("Save pipeline", self)
        self.save_pipeline_action.triggered.connect(self.savePipeline)

        self.save_pipeline_as_action = QAction("Save pipeline as", self)
        self.save_pipeline_as_action.triggered.connect(self.savePipelineAs)

        self.load_pipeline_parameters_action = QAction(
            "Load pipeline parameters", self)
        self.load_pipeline_parameters_action.triggered.connect(
            self.loadParameters)

        self.save_pipeline_parameters_action = QAction(
            "Save pipeline parameters", self)
        self.save_pipeline_parameters_action.triggered.connect(
            self.saveParameters)

        sources_images_dir = config.getSourceImageDir()
        self.init_pipeline_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'init32.png')),
            "Initialize pipeline", self)
        self.init_pipeline_action.triggered.connect(self.initialize)

        self.run_pipeline_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'run32.png')),
            "Run pipeline", self)
        self.run_pipeline_action.triggered.connect(self.runPipeline)
        self.run_pipeline_action.setDisabled(True)

        self.stop_pipeline_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'stop32.png')),
            "Stop", self)
        self.stop_pipeline_action.triggered.connect(self.stop_execution)
        self.stop_pipeline_action.setDisabled(True)

        self.show_pipeline_status_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'gray_cross.png')),
            "Status", self)
        self.show_pipeline_status_action.triggered.connect(self.show_status)

        # if config.get_user_mode() == True:
        #     self.save_pipeline_action.setDisabled(True)
        #     self.save_pipeline_as_action.setDisabled(True)
        #     self.processLibrary.setHidden(True)
        #     self.previewBlock.setHidden(True)

        # Initialize toolbar
        self.menu_toolbar = QToolBar()
        self.tags_menu = QMenu()
        self.tags_tool_button = QtWidgets.QToolButton()
        self.scrollArea = QScrollArea()

        # Initialize Qt layout
        self.hLayout = QHBoxLayout()
        self.splitterRight = QSplitter(Qt.Vertical)
        self.splitter0 = QSplitter(Qt.Vertical)
        self.splitter1 = QSplitter(Qt.Horizontal)

        self.layout_view()

        # To undo/redo
        self.nodeController.value_changed.connect(
            self.controller_value_changed)

    def _show_preview(self, name_item):

        self.previewBlock.centerOn(0, 0)
        self.find_process(name_item)

    def add_plug_value_to_database(self, p_value, brick_id, node_name,
                                   plug_name, full_name, node, trait):
        """Add the plug value to the database.

        Parameters
        ----------
        p_value: any
            plug value, a file name or a list of file names
        brick_id: str
            brick id in the database
        node_name: str
            name of the node
        plug_name: str
            name of the plug
        full_name:  str
            full name of the node, including parent brick(s).
            If there is no parent brick, full_name = node_name.
        node: Node
            node containing the plug
        trait: Trait
            handler of the plug trait, or sub-trait if the plug is a list.
            It will be used to check the value type (file or not)
        """

        if isinstance(p_value, (list, TraitListObject)):
            inner_trait = trait.handler.inner_traits()[0]
            for elt in p_value:
                self.add_plug_value_to_database(elt, brick_id, node_name,
                                                plug_name, full_name, node,
                                                inner_trait)
            return

        if not is_file_trait(trait, allow_dir=True) \
                or p_value in ("<undefined>", Undefined, [Undefined]):
            # This means that the value is not a filename
            return

        # Deleting the project's folder in the file name so it can
        # fit to the database's syntax
        old_value = p_value
        #p_value = p_value.replace(self.project.folder, "")
        p_value = os.path.abspath(p_value)
        if not p_value.startswith(os.path.abspath(os.path.join(
                self.project.folder, ''))):
            # file name is outside the project folder: don't index it in the
            # database
            return

        p_value = p_value.replace(os.path.abspath(self.project.folder), "")
        if p_value and p_value[0] in ["\\", "/"]:
            p_value = p_value[1:]

        # If the file name is already in the database,
        # no exception is raised
        # but the user is warned
        if self.project.session.get_document(COLLECTION_CURRENT, p_value):
            print("Path {0} already in database.".format(p_value))
        else:
            self.project.session.add_document(COLLECTION_CURRENT, p_value)
            self.project.session.add_document(COLLECTION_INITIAL, p_value)

        # Adding the new brick to the output files
        bricks = self.project.session.get_value(
            COLLECTION_CURRENT, p_value, TAG_BRICKS)
        if bricks is None:
            bricks = []
        bricks.append(brick_id)
        self.project.session.set_value(
            COLLECTION_CURRENT, p_value, TAG_BRICKS, bricks)
        self.project.session.set_value(
            COLLECTION_INITIAL, p_value, TAG_BRICKS, bricks)
        # Type tag
        filename, file_extension = os.path.splitext(p_value)
        ptype = TYPE_UNKNOWN
        if file_extension == ".nii":
            ptype = TYPE_NII
        elif file_extension == ".mat":
            ptype = TYPE_MAT
        elif file_extension == ".txt":
            ptype = TYPE_TXT

        self.project.session.set_value(
            COLLECTION_CURRENT, p_value, TAG_TYPE, ptype)
        self.project.session.set_value(
            COLLECTION_INITIAL, p_value, TAG_TYPE, ptype)

        inputs = self.inputs
        # Automatically fill inheritance dictionary if empty
        if self.ignore_node:
            pass
        elif ((self.inheritance_dict is None or old_value not in
                self.inheritance_dict) and
              (node_name not in self.ignore) and
              (node_name + plug_name not in self.ignore)):
            values = {}
            for key in inputs:
                paths = []
                if isinstance(inputs[key], list):
                    for val in inputs[key]:
                        if isinstance(val, str):
                            paths.append(val)
                elif isinstance(inputs[key], str):
                    paths.append(inputs[key])
                for path in paths:
                    if os.path.exists(path):
                        name, extension = os.path.splitext(path)
                        if extension == ".nii":
                            values[key] = name + extension
            if len(values) >= 1:
                self.inheritance_dict = {}
                if len(values) == 1:
                    value = values[list(values.keys(
                    ))[0]]
                    self.inheritance_dict[old_value] = value
                else:
                    if node_name in self.key:
                        value = values[self.key[node_name]]
                        self.inheritance_dict[old_value] = value
                    elif node_name + plug_name in self.key:
                        value = values[self.key[node_name + plug_name]]
                        self.inheritance_dict[old_value] = value
                    else:
                        pop_up = PopUpInheritanceDict(
                          values, full_name, plug_name,
                          self.iterationTable.check_box_iterate.isChecked())
                        pop_up.exec()
                        self.ignore_node = pop_up.everything
                        if pop_up.ignore:
                            self.inheritance_dict = None
                            if pop_up.all is True:
                                self.ignore[node_name] = True
                            else:
                                self.ignore[node_name+plug_name] = True
                        else:
                            value = pop_up.value
                            if pop_up.all is True:
                                self.key[node_name] = pop_up.key
                            else:
                                self.key[node_name+plug_name] = pop_up.key
                            self.inheritance_dict[old_value] = value

        # Adding inherited tags
        if self.inheritance_dict and old_value in self.inheritance_dict:
            database_parent_file = None
            parent_file = self.inheritance_dict[old_value]
            for scan in self.project.session.get_documents_names(
                    COLLECTION_CURRENT):
                if scan in str(parent_file):
                    database_parent_file = scan
            banished_tags = [TAG_TYPE, TAG_EXP_TYPE, TAG_BRICKS,
                              TAG_CHECKSUM, TAG_FILENAME]
            for tag in self.project.session.get_fields_names(
                    COLLECTION_CURRENT):
                if tag not in banished_tags and database_parent_file is \
                        not None:
                    parent_current_value = self.project.session.get_value(
                        COLLECTION_CURRENT, database_parent_file, tag)
                    self.project.session.set_value(
                        COLLECTION_CURRENT, p_value, tag,
                        parent_current_value)
                    parent_initial_value = self.project.session.get_value(
                        COLLECTION_INITIAL, database_parent_file, tag)
                    self.project.session.set_value(
                        COLLECTION_INITIAL, p_value, tag,
                        parent_initial_value)

        self.project.saveModifications()

    def add_process_to_preview(self, class_process, node_name=None):
        """Add a process to the pipeline.

        :param class_process: process class's name (str)
        :param node_name: name of the corresponding node
           (using when undo/redo) (str)
        """

        # pipeline = self.previewBlock.scene.pipeline
        pipeline = Pipeline()
        if not node_name:
            class_name = class_process.__name__
            i = 1

            node_name = class_name.lower() + str(i)

            while node_name in pipeline.nodes and i < 100:
                i += 1
                node_name = class_name.lower() + str(i)

            process_to_use = class_process()

        else:
            process_to_use = class_process

        try:
            process = get_process_instance(
                process_to_use)
        except Exception as e:
            return

        pipeline.add_process(node_name, process)
        self.previewBlock.set_pipeline(pipeline)

        # Capsul update
        node = pipeline.nodes[node_name]
        # gnode = self.scene.add_node(node_name, node)

        return node, node_name

    def controller_value_changed(self, signal_list):
        """
        Update history when a pipeline node is changed

        :param signal_list: list of the needed parameters to update history
        """

        case = signal_list.pop(0)

        # For history
        history_maker = []

        if case == "node_name":
            history_maker.append("update_node_name")
            for element in signal_list:
                history_maker.append(element)
            # update pipeline view
            pipeline = self.pipelineEditorTabs.get_current_pipeline()
            editor = self.pipelineEditorTabs.get_current_editor()
            rect = editor.sceneRect()
            trans = editor.transform()
            editor.set_pipeline(pipeline)
            editor.setSceneRect(rect)
            editor.setTransform(trans)

        elif case == "plug_value":
            history_maker.append("update_plug_value")
            for element in signal_list:
                history_maker.append(element)

        self.pipelineEditorTabs.undos[
            self.pipelineEditorTabs.get_current_editor()].append(history_maker)
        self.pipelineEditorTabs.redos[
            self.pipelineEditorTabs.get_current_editor()].clear()

        if case == "plug_value":
            node_name = signal_list[0]
            if node_name in ['inputs', 'outputs']:
                node_name = ''

        if case == "node_name":
            node_name = signal_list[1]

        self.nodeController.update_parameters(
            self.pipelineEditorTabs.get_current_pipeline().nodes[
                node_name].process)

        # Cause a segmentation fault
        # from capsul.qt_gui.widgets.pipeline_developper_view import NodeGWidget
        # for item in self.pipelineEditorTabs.get_current_editor().scene.items():
        #     if isinstance(item, NodeGWidget):
        #         self.pipelineEditorTabs.get_current_editor(
        #
        #         ).scene.process_clicked.emit(item.name, item.process)


    def displayNodeParameters(self, node_name, process):
        """
        Display the node controller when a node is clicked

        :param node_name: name of the node to display parameters
        :param process: process instance of the corresponding node
        :return:
        """

        self.nodeController.display_parameters(
            node_name, process,
            self.pipelineEditorTabs.get_current_pipeline())
        self.scrollArea.setWidget(self.nodeController)

    def find_process(self, path):
        """
        Find the dropped process in the system's paths

        :param path: class's path (e.g. "nipype.interfaces.spm.Smooth") (str)
        """

        package_name, process_name = os.path.splitext(path)
        process_name = process_name[1:]
        __import__(package_name)
        pkg = sys.modules[package_name]
        for name, instance in sorted(list(pkg.__dict__.items())):
            if name == process_name and inspect.isclass(instance):
                try:
                    process = get_process_instance(instance)
                except Exception as e:
                    print(e)
                    return
                else:
                    node, node_name = self.add_process_to_preview(instance)
                    gnode = self.previewBlock.scene.gnodes[node_name]
                    gnode.setPos(0, 0)
                    gnode.updateInfoActived(True)
                    # gnode.active = True
                    # gnode.update_node()
                    rect = gnode.sceneBoundingRect()
                    self.previewBlock.scene.setSceneRect(rect)
                    self.previewBlock.fitInView(
                        rect.x(), rect.y(), rect.width() * 1.2,
                                            rect.height() * 1.2,
                        Qt.KeepAspectRatio)
                    self.previewBlock.setAlignment(Qt.AlignCenter)

    def get_capsul_engine(self):
        """
        Get a CapsulEngine object from the edited pipeline, and set it up from
        MIA config object
        """
        return self.pipelineEditorTabs.get_capsul_engine()

    def complete_pipeline_parameters(self, pipeline=None):
        """
        Complete pipeline parameters using Capsul's completion engine
        mechanism.
        This engine works using a set of attributes which can be retreived from
        the database.
        """
        from capsul.attributes.completion_engine import ProcessCompletionEngine

        # get a working / configured CapsulEngine
        engine = self.get_capsul_engine()
        if not pipeline:
            pipeline = self.pipelineEditorTabs.get_current_pipeline()
        completion = ProcessCompletionEngine.get_completion_engine(pipeline)
        if completion:
            # record initial param values to get manually set ones
            init_params = pipeline.get_inputs()
            init_params.update(pipeline.get_outputs())

            nodes = list(pipeline.nodes.items())
            while nodes:
                name, node = nodes.pop(0)
                if name == '': continue
                if isinstance(node, PipelineNode):
                    nodes += list(node.process.nodes.items())

            attributes = completion.get_attribute_values()
            # try to find out attribute values from files in parameters
            # this is a temporary trick which should be replaced with a proper
            # attributes selection from the database (directly)
            #for name, trait in pipeline.user_traits().items():

            #print('attributes:', attributes.export_to_dict())
            #print('SC:', engine.study_config.export_to_dict())

            # TODO....


            completion.complete_parameters()

            # re-force manually set params
            for param, value in init_params.items():
                if value not in (None, Undefined, '', []) \
                        and value != getattr(pipeline, param):
                    print('set back param:', param, ':', getattr(pipeline, param), '->', value)
                    setattr(pipeline, param, value)

    def _register_node_io_in_database(self, node, proc_outputs,
                                      pipeline_name=''):
        if isinstance(node, ProcessNode):
            process = node.process
            inputs = process.get_inputs()
            outputs = process.get_outputs()
            # ProcessMIA / Process_Mia specific
            if hasattr(process, 'list_outputs') \
                    and hasattr(process, 'outputs'):
                # normally same as outputs, but it may contain an additional
                # "notInDb" key.
                outputs.update(process.outputs)
        else:
            outputs = {
                param: node.get_plug_value(param)
                for param, trait in node.user_traits()
                if trait.output}
            inputs = {
                param: node.get_plug_value(param)
                for param, trait in node.user_traits()
                if not trait.output}

        # Adding I/O to database history
        self.inputs = inputs  # used during add_plug_value_to_database()

        for key in inputs:

            if inputs[key] in [Undefined, [Undefined]]:
                inputs[key] = "<undefined>"

        for key in outputs:
            value = outputs[key]

            if value in [Undefined, [Undefined]]:
                outputs[key] = "<undefined>"

        self.project.saveModifications()

        node_name = node.name

        # Updating the database with output values obtained from
        # initialisation. If a plug name is in
        # outputs['notInDb'], then the corresponding
        # output value is not added to the database.
        notInDb = set(outputs.get('notInDb', []))

        for plug_name, plug_value in outputs.items():

            if plug_name not in node.plugs.keys():
                continue

            if plug_value != "<undefined>":

                if plug_name not in notInDb:

                    if pipeline_name != "":
                        full_name = pipeline_name + "." + node_name

                    else:
                        full_name = node_name

                    trait = node.get_trait(plug_name)
                    self.add_plug_value_to_database(plug_value,
                                                    self.brick_id,
                                                    node_name,
                                                    plug_name,
                                                    full_name,
                                                    node,
                                                    trait)

        # Adding I/O to database history
        self.project.session.set_value(COLLECTION_BRICK, self.brick_id,
                                        BRICK_INPUTS, inputs)
        self.project.session.set_value(COLLECTION_BRICK, self.brick_id,
                                        BRICK_OUTPUTS, outputs)
        # Setting brick init state if init finished correctly
        self.project.session.set_value(COLLECTION_BRICK, self.brick_id,
                                        BRICK_INIT, "Done")

    def init_pipeline(self, pipeline=None, pipeline_name=""):
        """
        Initialize the current pipeline of the pipeline editor

        :param pipeline: not None if this method call a sub-pipeline
        :param pipeline_name: name of the parent pipeline
        """

        # Denis: I don't understand everything of this 700 lines function.
        # It's quite difficult to follow. I understand that there are checks
        # for every node in the pipeline. But they don't expect non-process
        # nodes (switches, custom nodes), and they don't bother about disabled
        # nodes. There are lots of special cases (nipype or non-nipype
        # processes, SPM handling), sometimes I suspect assumptions that
        # processes are MiaProcesses and not regular Capsul  ones.
        # So we cannot use this initialization for any pipeline.
        # I assume (can't say "I understand") that init is doing the following
        # operations:
        # * fill some "common" parameters values (output_directory, SPM
        #   settings...)
        # * check that all mandatory parameters are filled with valid values
        # * check processes requirements
        # * record parameters values in the database
        #
        # I'm sorry I am writing another code for that.

        print('init pipeline...')
        name = os.path.basename(
            self.pipelineEditorTabs.get_current_filename())
        self.main_window.statusBar().showMessage(
            'Pipeline "{0}" is getting initialized. '
            'Please wait.'.format(name))

        QApplication.processEvents()
        # If the initialisation is launch for the main pipeline
        if not pipeline:
            pipeline = get_process_instance(
                self.pipelineEditorTabs.get_current_pipeline())
            main_pipeline = True

        else:
            main_pipeline = False

        init_result = True

        # complete config for completion
        study_config = pipeline.get_study_config()
        study_config.project = self.project

        # Capsul parameters completion
        print('Completion...')
        self.complete_pipeline_parameters(pipeline)
        print('completion done.')

        # check missing inputs
        missing_inputs = pipeline.get_missing_mandatory_parameters()
        if len(missing_inputs) != 0:
            ptype = 'pipeline'
            print('In %s %s: missing mandatory parameters: %s'
                  % (ptype, pipeline.name, ', '.join(missing_inputs)))
            init_result = False

        #missing_inputs = pipeline_tools.nodes_with_missing_inputs(pipeline)
        #if missing_inputs:
            #print('Some input files do not exist:')
            #for name, params in missing_inputs.items():
                #print('node:', name)
                #for pname, fname in params:
                    #print('%s:' % pname, fname)
            #init_result = False

        # check requirements
        req_messages = []
        requirements = pipeline.check_requirements('global',
                                                   message_list=req_messages)
        if requirements is None:
            print('Pipeline requirements are not met')
            print('\n'.join(req_messages))
            print('current configuration:')
            print(study_config.engine.settings.select_configurations('global'))
            init_result = False

        if init_result:
            # add process characteristics in  the database
            # if init is otherwise OK

            nodes_list = [n for n in pipeline.nodes.items()
                          if n[0] != ''
                              and pipeline_tools.is_node_enabled(
                                  pipeline, n[0], n[1])]

            all_nodes = list(nodes_list)
            while nodes_list:
                node_name, node = nodes_list.pop(0)
                if hasattr(node, 'process'):
                    process = node.process

                    if isinstance(node, PipelineNode):
                        new_nodes = [
                            n for n in process.nodes.items()
                            if n[0] != ''
                                and pipeline_tools.is_node_enabled(
                                    process, n[0], n[1])]
                        nodes_list += new_nodes
                        all_nodes += new_nodes

            for node_name, node in all_nodes:
                # Adding the brick to the bricks history
                self.brick_id = str(uuid.uuid4())
                self.brick_list.append(self.brick_id)
                self.project.session.add_document(COLLECTION_BRICK,
                                                  self.brick_id)
                self.project.session.set_value(
                    COLLECTION_BRICK, self.brick_id, BRICK_NAME, node_name)
                self.project.session.set_value(
                    COLLECTION_BRICK, self.brick_id, BRICK_INIT_TIME,
                    datetime.datetime.now())
                self.project.session.set_value(
                    COLLECTION_BRICK, self.brick_id, BRICK_INIT, "Not Done")

                self._register_node_io_in_database(node, pipeline_name)
                self.project.saveModifications()

                # This cannot be done in remote execution
                if hasattr(process, 'manage_brick_before_run'):
                    process.manage_brick_before_run()

        self.project.saveModifications()

        # Updating the node controller
        # Display the updated parameters in right part of
        # the Pipeline Manager (controller)
        if main_pipeline:
            node_controller_node_name = self.nodeController.node_name
            #### Todo: Fix the problem of the controller that
            #### keeps the name of the old brick deleted until
            #### a click on the new one. This can cause a mia
            #### crash during the initialisation, for example.

            if node_controller_node_name in ['inputs', 'outputs']:
                node_controller_node_name = ''

            self.nodeController.display_parameters(
                self.nodeController.node_name,
                pipeline.nodes[node_controller_node_name].process,
                pipeline)


            if not init_result:
                self.msg = QMessageBox()
                self.msg.setIcon(QMessageBox.Critical)
                self.msg.setWindowTitle("MIA configuration warning!")
                message = 'The pipeline could not be initialized properly.'
                self.msg.setText(message)

                yes_button = self.msg.addButton("Open MIA preferences",
                                                QMessageBox.YesRole)

                ok_button = self.msg.addButton(QMessageBox.Ok)

                self.msg.exec()

                if self.msg.clickedButton() == yes_button:
                    self.main_window.software_preferences_pop_up()
                    self.msg.close()

                else:
                    self.msg.close()

                self.main_window.statusBar().showMessage(
                'Pipeline "{0}" was not initialised successfully.'.format(name))

            else:
                for i in range(0, len(self.pipelineEditorTabs)-1):
                    self.pipelineEditorTabs.get_editor_by_index(
                        i).initialized = False
                self.pipelineEditorTabs.get_current_editor().initialized = True

                self.main_window.statusBar().showMessage(
                    'Pipeline "{0}" has been initialised.'.format(name))

        return init_result

    def initialize(self):
        """Clean previous initialization then initialize the current
        pipeline."""

        QApplication.instance().setOverrideCursor(QCursor(Qt.WaitCursor))

        if self.init_clicked:
            for brick in self.brick_list:
                self.main_window.data_browser.table_data.delete_from_brick(
                    brick)
        self.ignore_node = False
        self.key = {}
        self.ignore = {}

        try:
            self.test_init = self.init_pipeline()
        except Exception as e:
            print("\nError during initialisation: ", e)
            self.test_init = False
            import traceback
            traceback.print_exc()
        # If the initialization fail, the run pipeline action is disabled
        # The run pipeline action is enabled only when an initialization is
        # successful
        self.run_pipeline_action.setDisabled(True)

        # When clicking on the Pipeline > Initialize
        # pipeline in the Pipeline Manager tab,
        # this is the first method launched.

        # ** pathway from the self.init_pipeline() command (ex. for the
        #    User_processes Smooth brick):
        #      info1: self is a populse_mia.user_interface.pipeline_manager
        #             .pipeline_manager_tab.PipelineManagerTab object
        #
        # ** populse_mia/user_interface/pipeline_manager/pipeline_manager_tab.py
        #    class PipelineManagerTab(QWidget):
        #    method init_pipeline(self, pipeline=None, pipeline_name=""):
        #      use: initResult_dict = process.list_outputs(
        #                                                 is_plugged=is_plugged)
        #      info1: process is the brick (node, process, etc.)
        #             <User_processes.preprocess.spm.spatial_preprocessing
        #             .Smooth object at ...> object
        
        # ** User_processes/preprocess/spm/spatial_preprocessing.py
        #    class Smooth(Process_Mia)
        #    list_outputs method:
        #      use: super(Smooth, self).list_outputs(). Using the inheritance
        #           to ProcessMIA class, list_outputs method.
        #      info1: here we are in the place where we deal with plugs.
        #
        #** Some characteristics for the pipeline object
        #   (for User_processes Smooth brick):
        #       pipeline is a capsul.pipeline.pipeline.Pipeline object
        #       pipeline.nodes is a dictionary
        #       pipeline.nodes["smooth1"] is a capsul.pipeline.pipeline_nodes
        #         .ProcessNode object
        #       pipeline.nodes["smooth1"].plugs is a dictionary. Each key is a
        #         plug displayed in the Pipeline manager tab
        #       pipeline.nodes["smooth1"].plugs["fwhm"] is a capsul.pipeline
        #         .pipeline_nodes.Plug object
        #       If the plus is not connected,  pipeline.nodes["smooth1"]
        #         .plugs["fwhm"].links_to (in case of output link) : set()
        #       If the plus is connected,  pipeline.nodes["smooth1"]
        #         .plugs["fwhm"].links_to (in case of output link):
        #         {('', 'fwhm', <capsul.pipeline.pipeline_nodes.PipelineNode
        #         object at 0x7f4688109c50>, <capsul.pipeline.pipeline_nodes
        #         .Plug object at 0x7f46691e4888>, False)}
        #       So, it is possble to check if the plug is connected with:
        #         if pipeline.nodes["smooth1"].plugs["fwhm"].links_to: etc ...
        #         or a  if pipeline.nodes["smooth1"].plugs["fwhm"].links_from:
        #         etc ...

        self.init_clicked = True
        self.pipelineEditorTabs.update_current_node()
        self.pipelineEditorTabs.get_current_editor().node_parameters \
            = copy.deepcopy(self.pipelineEditorTabs.get_current_editor(
        ).node_parameters_tmp)
        self.pipelineEditorTabs.update_current_node()

        QApplication.instance().restoreOverrideCursor()

    def layout_view(self):
        """Initialize layout for the pipeline manager tab"""

        self.setWindowTitle("Diagram editor")

        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(self.nodeController)

        # Toolbar
        self.tags_menu.addAction(self.load_pipeline_action)
        self.tags_menu.addAction(self.save_pipeline_action)
        if Config().get_user_mode():
            self.save_pipeline_action.setDisabled(True)
            self.pipelineEditorTabs.get_current_editor(
            ).disable_overwrite = True
        else:
            self.save_pipeline_action.setEnabled(True)
            self.pipelineEditorTabs.get_current_editor(
            ).disable_overwrite = False
        self.tags_menu.addAction(self.save_pipeline_as_action)
        self.tags_menu.addSeparator()
        self.tags_menu.addAction(self.load_pipeline_parameters_action)
        self.tags_menu.addAction(self.save_pipeline_parameters_action)
        self.tags_menu.addSeparator()
        self.tags_menu.addAction(self.init_pipeline_action)
        self.tags_menu.addAction(self.run_pipeline_action)
        self.tags_menu.addAction(self.stop_pipeline_action)
        self.tags_menu.addAction(self.show_pipeline_status_action)

        self.tags_tool_button.setText('Pipeline')
        self.tags_tool_button.setPopupMode(
            QtWidgets.QToolButton.MenuButtonPopup)
        self.tags_tool_button.setMenu(self.tags_menu)

        #self.init_button = QToolButton()
        #self.init_button.setDefaultAction(self.init_pipeline_action)
        #self.run_button = QToolButton()
        #self.run_button.setDefaultAction(self.run_pipeline_action)
        #self.stop_button = QToolButton()
        self.menu_toolbar.addAction(self.init_pipeline_action)
        self.menu_toolbar.addAction(self.run_pipeline_action)
        self.menu_toolbar.addAction(self.stop_pipeline_action)
        self.menu_toolbar.addAction(self.show_pipeline_status_action)
        self.menu_toolbar.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                        QtWidgets.QSizePolicy.Fixed)

        # Layouts

        self.hLayout.addWidget(self.tags_tool_button)
        self.hLayout.addWidget(self.menu_toolbar)
        #self.hLayout.addWidget(self.init_button)
        #self.hLayout.addWidget(self.run_button)
        #self.hLayout.addWidget(self.stop_button)
        self.hLayout.addStretch(1)

        self.splitterRight.addWidget(self.iterationTable)
        self.splitterRight.addWidget(self.scrollArea)
        self.splitterRight.setSizes([400, 400])

        # previewScene = QGraphicsScene()
        # previewScene.setSceneRect(QtCore.QRectF())
        # self.previewDiagram = QGraphicsView()
        # self.previewDiagram.setEnabled(False)

        self.splitter0.addWidget(self.processLibrary)
        self.splitter0.addWidget(self.previewBlock)

        self.splitter1.addWidget(self.splitter0)
        self.splitter1.addWidget(self.pipelineEditorTabs)
        self.splitter1.addWidget(self.splitterRight)
        self.splitter1.setSizes([200, 800, 200])

        # self.splitter2 = QSplitter(Qt.Vertical)
        # self.splitter2.addWidget(self.splitter1)
        # self.splitter2.setSizes([800, 100])

        self.verticalLayout.addLayout(self.hLayout)
        self.verticalLayout.addWidget(self.splitter1)

    def loadPipeline(self):
        """
        Load a pipeline to the pipeline editor

        """

        self.pipelineEditorTabs.load_pipeline()

    def loadParameters(self):
        """
        Load pipeline parameters to the current pipeline of the pipeline editor

        """

        self.pipelineEditorTabs.load_pipeline_parameters()

        self.nodeController.update_parameters()

    def redo(self):
        """
        Redo the last undone action on the current pipeline editor

        Actions that can be redone:
            - add_process
            - delete_process
            - export_plug
            - export_plugs
            - remove_plug
            - update_node_name
            - update_plug_value
            - add_link
            - delete_link

        """

        c_e = self.pipelineEditorTabs.get_current_editor()

        # We can redo if we have an action to make again
        if len(self.pipelineEditorTabs.redos[c_e]) > 0:
            to_redo = self.pipelineEditorTabs.redos[c_e].pop()
            # The first element of the list is the type of action made
            # by the user
            action = to_redo[0]

            if action == "delete_process":
                node_name = to_redo[1]
                class_process = to_redo[2]
                links = to_redo[3]
                c_e.add_process(
                    class_process, node_name, from_redo=True, links=links)

            elif action == "add_process":
                node_name = to_redo[1]
                c_e.del_node(node_name, from_redo=True)

            elif action == "export_plug":
                temp_plug_name = to_redo[1]
                c_e._remove_plug(
                    _temp_plug_name=temp_plug_name, from_redo=True)

            elif action == "export_plugs":
                # No redo possible
                pass

            elif action == "remove_plug":
                temp_plug_name = to_redo[1]
                new_temp_plugs = to_redo[2]
                optional = to_redo[3]
                c_e._export_plug(temp_plug_name=new_temp_plugs[0],
                                 weak_link=False,
                                 optional=optional,
                                 from_redo=True,
                                 pipeline_parameter=temp_plug_name[1])

                # Connecting all the plugs that were connected
                # to the original plugs
                for plug_tuple in new_temp_plugs:
                    # Checking if the original plug is a pipeline
                    # input or output to adapt
                    # the links to add.
                    if temp_plug_name[0] == 'inputs':
                        source = ('', temp_plug_name[1])
                        dest = plug_tuple
                    else:
                        source = plug_tuple
                        dest = ('', temp_plug_name[1])

                    c_e.scene.add_link(source, dest, active=True, weak=False)

                    # Writing a string to represent the link
                    source_parameters = ".".join(source)
                    dest_parameters = ".".join(dest)
                    link = "->".join((source_parameters, dest_parameters))

                    c_e.scene.pipeline.add_link(link)
                    c_e.scene.update_pipeline()

            elif action == "update_node_name":
                node = to_redo[1]
                new_node_name = to_redo[2]
                old_node_name = to_redo[3]
                c_e.update_node_name(
                    node, new_node_name, old_node_name, from_redo=True)

            elif action == "update_plug_value":
                node_name = to_redo[1]
                new_value = to_redo[2]
                plug_name = to_redo[3]
                value_type = to_redo[4]
                c_e.update_plug_value(
                    node_name, new_value, plug_name,
                    value_type, from_redo=True)

            elif action == "add_link":
                link = to_redo[1]
                c_e._del_link(link, from_redo=True)

            elif action == "delete_link":
                source = to_redo[1]
                dest = to_redo[2]
                active = to_redo[3]
                weak = to_redo[4]
                c_e.add_link(source, dest, active, weak, from_redo=True)
                # link = source[0] + "." + source[1]
                # + "->" + dest[0] + "." + dest[1]

            c_e.scene.pipeline.update_nodes_and_plugs_activation()
            self.nodeController.update_parameters()

    def runPipeline(self):
        """Run the current pipeline of the pipeline editor."""

        from soma_workflow import constants as swconstants

        name = os.path.basename(self.pipelineEditorTabs.get_current_filename())
        self.brick_list = []
        self.main_window.statusBar().showMessage(
            'Pipeline "{0}" is getting run. Please wait.'.format(name))
        QApplication.processEvents()
        self.key = {}
        self.ignore = {}
        self.ignore_node = False

        self.last_run_pipeline \
            = self.pipelineEditorTabs.get_current_pipeline()
        self.last_status = swconstants.WORKFLOW_NOT_STARTED
        self.last_run_log = None
        self.last_pipeline_name \
            = self.pipelineEditorTabs.get_current_filename()

        #if self.iterationTable.check_box_iterate.isChecked():
            #iterated_tag = self.iterationTable.iterated_tag
            #tag_values = self.iterationTable.tag_values_list

            #pipeline_progress = dict()
            #pipeline_progress['size'] = len(tag_values)
            #pipeline_progress['counter'] = 1
            #pipeline_progress['tag'] = iterated_tag
            #for tag_value in tag_values:
                #self.brick_list = []
                ## Status bar update
                #pipeline_progress['tag_value'] = tag_value

                #idx_combo_box = self.iterationTable.combo_box.findText(
                    #tag_value)
                #self.iterationTable.combo_box.setCurrentIndex(
                    #idx_combo_box)
                #self.iterationTable.update_table()

                #self.init_pipeline()
                #self.main_window.statusBar().showMessage(
                    #'Pipeline "{0}" is getting run for {1} {2}. '
                    #'Please wait.'.format(name, iterated_tag, tag_value))
                #QApplication.processEvents()
                #self.progress = RunProgress(self, pipeline_progress)
                ##self.progress.show()
                ##self.progress.exec()
                #pipeline_progress['counter'] += 1
                #self.init_clicked = False


                ## # self.init_pipeline(self.pipeline)
                ## idx = self.progress.value()
                ## idx += 1
                ## self.progress.setValue(idx)
                ## QApplication.processEvents()

            #self.main_window.statusBar().showMessage(
                #'Pipeline "{0}" has been run for {1} {2}. Please wait.'.format(
                    #name, iterated_tag, tag_values))

        #else:
            
        self.progress = RunProgress(self)
        self.progress.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                    QtWidgets.QSizePolicy.Fixed)
        self.hLayout.addWidget(self.progress)
        #self.progress.show()
        #self.progress.exec()
        self.stop_pipeline_action.setEnabled(True)
        config = Config()
        sources_images_dir = config.getSourceImageDir()

        mmovie = QMovie(
            os.path.join(sources_images_dir, 'rotatingBrainVISA.gif'))
        self._mmovie = mmovie
        mmovie.stop()
        mmovie.frameChanged.connect(self._set_anim_frame)
        mmovie.start()

        self.progress.worker.finished.connect(self.finish_execution)
        self.progress.start()

        self.init_clicked = False
        self.run_pipeline_action.setDisabled(True)

    def _set_anim_frame(self):
        """
        Callback which sets the animated icon frame to the status action icon
        """
        self.show_pipeline_status_action.setIcon(
            QIcon(self._mmovie.currentPixmap()))

    def stop_execution(self):
        """
        Request interruption of pipeline execution
        """
        print('stop_execution')
        self.progress.stop_execution()

    def finish_execution(self):
        """
        Callback called after a pipeline execution ends (in any way)
        """
        from soma_workflow import constants as swconstants
        self.stop_pipeline_action.setEnabled(False)
        status = self.progress.worker.status
        self.last_status = status
        try:
            engine = self.last_run_pipeline.get_study_config().engine
            if not hasattr(self.progress.worker, 'exec_id'):
                raise RuntimeError('Execution aborted before running')
            engine.raise_for_status(status, self.progress.worker.exec_id)
        except (WorkflowExecutionError, RuntimeError) as e:
            self.last_run_log = str(e)
            print('\n When the pipeline was launched, the following '
                  'exception was raised: {0} ...'.format(e, ))
            self.main_window.statusBar().showMessage(
                'Pipeline "{0}" has not been correctly run.'.format(
                    self.last_pipeline_name))
        else:
            self.last_run_log = None
            self.main_window.statusBar().showMessage(
                'Pipeline "{0}" has been correctly run.'.format(
                    self.last_pipeline_name))
        if status == swconstants.WORKFLOW_DONE:
            icon = 'green_v.png'
        else:
            icon = 'red_cross32.png'
        config = Config()
        sources_images_dir = config.getSourceImageDir()
        self._mmovie.stop()
        self.show_pipeline_status_action.setIcon(
            QIcon(os.path.join(sources_images_dir, icon)))
        del self._mmovie
        del self.progress

    def postprocess_pipeline_execution(self, pipeline=None):
        if not pipeline:
            pipeline = get_process_instance(
                self.pipelineEditorTabs.get_current_pipeline())

        print('postprocess pipeline:', pipeline)

        nodes_list = [n for n in pipeline.nodes.items()
                      if n[0] != ''
                          and pipeline_tools.is_node_enabled(
                              pipeline, n[0], n[1])]

        all_nodes = list(nodes_list)
        while nodes_list:
            node_name, node = nodes_list.pop(0)
            if hasattr(node, 'process'):
                process = node.process

                if isinstance(node, PipelineNode):
                    new_nodes = [
                        n for n in process.nodes.items()
                        if n[0] != ''
                            and pipeline_tools.is_node_enabled(
                                process, n[0], n[1])]
                    nodes_list += new_nodes
                    all_nodes += new_nodes

        for node_name, node in all_nodes:
            if isinstance(node, ProcessNode):
                process = node.process
                # This cannot be done in remote execution
                if hasattr(process, 'manage_brick_after_run'):
                    process.manage_brick_before_run()

    def show_status(self):
        """
        Show the last run status and execution info, errors etc.
        """
        print('show_status')
        log = getattr(self, 'last_run_log', '')
        status_widget = StatusWidget(self)
        status_widget.show()
        self.status_widget = status_widget

    def saveParameters(self):
        """
        Save the pipeline parameters of the the current pipeline of the
        pipeline editor

        """

        self.pipelineEditorTabs.save_pipeline_parameters()

    def savePipeline(self, uncheck=False):
        """
        Save the current pipeline of the pipeline editor

        :param uncheck: a flag to warn (False) or not (True) if a pipeline is
                        going to be overwritten during saving operation

        """

        self.main_window.statusBar().showMessage(
            'The pipeline is getting saved. Please wait.')
        # QApplication.processEvents()
        filename = self.pipelineEditorTabs.get_current_filename()

        # save
        if filename and not uncheck:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("populse_mia - "
                                   "Save pipeline Warning!")
            msg.setText("The following module will be overwritten:\n\n"
                            "{}\n\n"
                            "Do you agree?".format(os.path.abspath(filename)))
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Abort)
            msg.buttonClicked.connect(msg.close)
            retval = msg.exec()

            if retval == QMessageBox.Yes:
                self.pipelineEditorTabs.save_pipeline(new_file_name=filename)
                self.main_window.statusBar().showMessage(
                    "The '{}' pipeline has been "
                    "saved.".format(
                        self.pipelineEditorTabs.get_current_pipeline().name))

            else:
                self.main_window.statusBar().showMessage(
                    "The '{}' pipeline was not "
                    "saved.".format(
                        self.pipelineEditorTabs.get_current_pipeline().name))

        elif filename:
            self.pipelineEditorTabs.save_pipeline(new_file_name=filename)
            self.main_window.statusBar().showMessage(
                    "The '{}' pipeline has been "
                    "saved.".format(
                        self.pipelineEditorTabs.get_current_pipeline().name))

        # save as
        else:
            saveResult = self.pipelineEditorTabs.save_pipeline()

            if saveResult:
                self.main_window.statusBar().showMessage(
                              "The '{}' pipeline has been saved.".format(
                                  os.path.splitext(saveResult)[0].capitalize()))

            else:
                self.main_window.statusBar().showMessage(
                             'The pipeline was not saved.')

    def savePipelineAs(self):
        """
        Save the current pipeline of the pipeline editor under another name

        """

        self.main_window.statusBar().showMessage(
            'The pipeline is getting saved. Please wait.')
        saveResult = self.pipelineEditorTabs.save_pipeline()

        if saveResult:
            self.main_window.statusBar().showMessage(
                "The '{}' pipeline has been saved.".format(
                    os.path.splitext(saveResult)[0].capitalize()))

        else:
            self.main_window.statusBar().showMessage(
                'The pipeline was not saved.')

    def undo(self):
        """
        Undo the last action made on the current pipeline editor

        Actions that can be undone:
            - add_process
            - delete_process
            - export_plug
            - export_plugs
            - remove_plug
            - update_node_name
            - update_plug_value
            - add_link
            - delete_link

        """

        c_e = self.pipelineEditorTabs.get_current_editor()

        # We can undo if we have an action to revert
        if len(self.pipelineEditorTabs.undos[c_e]) > 0:
            to_undo = self.pipelineEditorTabs.undos[c_e].pop()
            # The first element of the list is the type of action made
            # by the user
            action = to_undo[0]

            if action == "add_process":
                node_name = to_undo[1]
                c_e.del_node(node_name, from_undo=True)

            elif action == "delete_process":
                node_name = to_undo[1]
                class_name = to_undo[2]
                links = to_undo[3]
                c_e.add_process(
                    class_name, node_name, from_undo=True, links=links)

            elif action == "export_plug":
                temp_plug_name = to_undo[1]
                c_e._remove_plug(
                    _temp_plug_name=temp_plug_name, from_undo=True)

            elif action == "export_plugs":
                parameter_list = to_undo[1]
                node_name = to_undo[2]
                for parameter in parameter_list:
                    temp_plug_name = ('inputs', parameter)
                    c_e._remove_plug(
                        _temp_plug_name=temp_plug_name,
                        from_undo=True,
                        from_export_plugs=True)
                self.main_window.statusBar().showMessage(
                    "Plugs {0} have been removed.".format(str(parameter_list)))

            elif action == "remove_plug":
                temp_plug_name = to_undo[1]
                new_temp_plugs = to_undo[2]
                optional = to_undo[3]
                c_e._export_plug(temp_plug_name=new_temp_plugs[0],
                                 weak_link=False,
                                 optional=optional, from_undo=True,
                                 pipeline_parameter=temp_plug_name[1])

                # Connecting all the plugs that were connected
                # to the original plugs
                for plug_tuple in new_temp_plugs:
                    # Checking if the original plug is a pipeline
                    # input or output to adapt
                    # the links to add.
                    if temp_plug_name[0] == 'inputs':
                        source = ('', temp_plug_name[1])
                        dest = plug_tuple
                    else:
                        source = plug_tuple
                        dest = ('', temp_plug_name[1])

                    c_e.scene.add_link(source, dest, active=True, weak=False)

                    # Writing a string to represent the link
                    source_parameters = ".".join(source)
                    dest_parameters = ".".join(dest)
                    link = "->".join((source_parameters, dest_parameters))

                    c_e.scene.pipeline.add_link(link)
                    c_e.scene.update_pipeline()

            elif action == "update_node_name":
                node = to_undo[1]
                new_node_name = to_undo[2]
                old_node_name = to_undo[3]
                c_e.update_node_name(node, new_node_name, old_node_name,
                                     from_undo=True)

            elif action == "update_plug_value":
                node_name = to_undo[1]
                old_value = to_undo[2]
                plug_name = to_undo[3]
                value_type = to_undo[4]
                c_e.update_plug_value(node_name, old_value, plug_name,
                                      value_type, from_undo=True)

            elif action == "add_link":
                link = to_undo[1]
                c_e._del_link(link, from_undo=True)

            elif action == "delete_link":
                source = to_undo[1]
                dest = to_undo[2]
                active = to_undo[3]
                weak = to_undo[4]
                c_e.add_link(source, dest, active, weak, from_undo=True)
                # link = source[0] + "." + source[1] +
                # "->" + dest[0] + "." + dest[1]

            c_e.scene.pipeline.update_nodes_and_plugs_activation()
            self.nodeController.update_parameters()

    def update_user_mode(self):
        """
        Update the visibility of widgets/actions depending of the chosen mode

        """

        config = Config()

        # If the user mode is chosen, the process library is not available
        # and the user cannot save a pipeline
        if config.get_user_mode():
            self.save_pipeline_action.setDisabled(True)
            self.pipelineEditorTabs.get_current_editor(
            ).disable_overwrite = True
            self.main_window.action_delete_project.setDisabled(True)
        else:
            self.save_pipeline_action.setDisabled(False)
            self.pipelineEditorTabs.get_current_editor(
            ).disable_overwrite = False
            self.main_window.action_delete_project.setEnabled(True)

        userlevel = config.get_user_level()
        if userlevel \
                != self.pipelineEditorTabs.get_current_editor().userlevel:
            self.pipelineEditorTabs.get_current_editor().userlevel = userlevel
            self.nodeController.process_widget.userlevel = userlevel

        # If the user mode is chosen, the process library is not available
        # and the user cannot save a pipeline
        # if config.get_user_mode() == True:
        #     self.processLibrary.setHidden(True)
        #     self.previewBlock.setHidden(True)
        #     self.save_pipeline_action.setDisabled(True)
        #     self.save_pipeline_as_action.setDisabled(True)
        # else:
        # self.processLibrary.setHidden(False)
        # self.previewBlock.setHidden(False)
        # self.save_pipeline_action.setDisabled(False)
        # self.save_pipeline_as_action.setDisabled(False)

    def update_project(self, project):
        """
        Update the project attribute of several objects

        :param project: current project in the software
        """

        self.project = project
        self.nodeController.project = project
        self.pipelineEditorTabs.project = project
        self.nodeController.visibles_tags = \
            self.project.session.get_shown_tags()
        self.iterationTable.project = project

        # Necessary for using MIA bricks
        ProcessMIA.project = project

    def build_iterated_pipeline(self):
        """
        Build a new pipeline with an iteration node, iterating over the current
        pipeline
        """
        from capsul.attributes.completion_engine import ProcessCompletionEngine

        c_e = self.pipelineEditorTabs.get_current_editor()
        pipeline = c_e.scene.pipeline
        engine = self.get_capsul_engine()
        pipeline_name = 'Iteration_pipeline'
        node_name = 'iteration'
        it_pipeline = engine.get_iteration_pipeline(
            pipeline_name, node_name, pipeline,
            iterative_plugs=None, do_not_export=None,
            make_optional=None)
        compl = ProcessCompletionEngine.get_completion_engine(it_pipeline)
        return it_pipeline

    def update_scans_list(self, iteration_list, all_iterations_list):
        """
        Update the user-selected list of scans

        :param iteration_list: current list of scans in the iteration table
        """

        #if self.check_box_iterate.isChecked():
            #self.run_pipeline_action.setDisabled(False)
            #self.init_pipeline_action.setDisabled(True)
        #else:
        self.run_pipeline_action.setDisabled(True)
        self.init_pipeline_action.setDisabled(False)

        c_e = self.pipelineEditorTabs.get_current_editor()
        pipeline = c_e.scene.pipeline
        has_iteration = ('iteration' in pipeline.nodes)

        if self.iterationTable.check_box_iterate.isChecked():
            if not has_iteration:
                # move to an iteration pipeline
                new_pipeline = self.build_iterated_pipeline()
                c_e.set_pipeline(new_pipeline)
                self.displayNodeParameters('inputs', new_pipeline)

            self.iteration_table_scans_list = all_iterations_list
            self.pipelineEditorTabs.scan_list = all_iterations_list
        else:
            if has_iteration:
                # get the pipeline out from the iteration node
                new_pipeline =  pipeline.nodes['iteration'].process.process
                c_e.set_pipeline(new_pipeline)
                self.displayNodeParameters('inputs', new_pipeline)

            self.iteration_table_scans_list = []
            self.pipelineEditorTabs.scan_list = self.scan_list
        #print('update_scans_list:', all_iterations_list)
        if not self.pipelineEditorTabs.scan_list:
            self.pipelineEditorTabs.scan_list = \
                self.project.session.get_documents_names(COLLECTION_CURRENT)
        self.pipelineEditorTabs.update_scans_list()

    def updateProcessLibrary(self, filename):
        """
        Update the library of processes when a pipeline is saved

        :param filename: file name of the pipeline that has been saved
        """

        filename_folder, file_name = os.path.split(filename)
        module_name = os.path.splitext(file_name)[0]
        class_name = module_name.capitalize()

        tmp_file = os.path.join(filename_folder, module_name + '_tmp')

        # Changing the "Pipeline" class name to the name of file
        with open(filename, 'r') as f:
            with open(tmp_file, 'w') as tmp:
                for line in f:
                    line = line.strip('\r\n')
                    if 'class ' in line:
                        line = 'class {0}(Pipeline):'.format(class_name)
                    tmp.write(line + '\n')

        with open(tmp_file, 'r') as tmp:
            with open(filename, 'w') as f:
                for line in tmp:
                    f.write(line)

        os.remove(tmp_file)
        config = Config()

        if os.path.relpath(filename_folder) != \
                os.path.relpath(os.path.join(
                    config.get_mia_path(), 'processes', 'User_processes')):
            return

        # Updating __init__.py
        init_file = os.path.join(
            config.get_mia_path(), 'processes',
            'User_processes', '__init__.py')

        # Checking that import line is not already in the file
        pattern = 'from .{0} import {1}\n'.format(module_name, class_name)
        file = open(init_file, 'r')
        flines = file.readlines()
        file.close()
        if pattern not in flines:
            with open(init_file, 'a') as f:
                print('from .{0} import {1}'.format(
                    module_name, class_name), file=f)

        package = 'User_processes'
        path = os.path.relpath(os.path.join(filename_folder, '..'))

        # If the pipeline has already been saved
        if 'User_processes.' + module_name in sys.modules.keys():
            # removing the previous version of the module
            del sys.modules['User_processes.' + module_name]
            # this adds the new module version to the sys.modules dictionary
            __import__('User_processes')

        # Adding the module path to the system path
        if path not in sys.path:
            sys.path.insert(0, path)

        self.processLibrary.pkg_library.add_package(package, class_name,
                                                    init_package_tree=True)

        if os.path.relpath(path) not in self.processLibrary.pkg_library.paths:
            self.processLibrary.pkg_library.paths.append(os.path.relpath(path))

        self.processLibrary.pkg_library.save()


#class RunProgress(QProgressDialog):
    #"""Create the pipeline progress bar and launch the thread.

    #The progress bar is closed when the thread finishes.

    #:param diagram_view: A pipelineEditorTabs
    #:param settings: dictionary of settings when the pipeline is iterated
    #"""

    #def __init__(self, diagram_view, settings=None):

        ##super(RunProgress, self).__init__("Please wait while the pipeline is "
                                          ##"running...", "Stop", 0, 0)
        #super(RunProgress, self).__init__()
        ##QApplication.instance().setOverrideCursor(QCursor(Qt.WaitCursor))

        ##if settings:
            ##self.setWindowTitle(
                ##"Pipeline is running ({0}/{1})".format(
                    ##settings["counter"], settings["size"]))
            ##self.setLabelText('Pipeline is running for {0} in {1}. '
                              ##'Please wait.'.format(settings['tag_value'],
                                                    ##settings['tag']))
        ##else:
            ##self.setWindowTitle("Pipeline running")
            
        ##self.setWindowFlags(
            ##Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        ##self.setModal(True)

        #self.diagramView = diagram_view

        #self.setMinimumDuration(0)
        #self.setValue(0)
        #self.setMinimumWidth(350) # For mac OS
        
        #self.worker = RunWorker(self.diagramView)
        #self.worker.finished.connect(self.close)
        ##self.canceled.connect(self.stop_execution)
        ##self.worker.start()

    #def start(self):
        #self.worker.start()

    #def close(self):
        #super().close()
        #self.worker.wait()
        #QApplication.instance().restoreOverrideCursor()
        #if not hasattr(self.worker, 'exec_id'):
            #QMessageBox.critical(self, 'Failure',
                                 #'Execution has failed before running (!)')
        #else:
            #try:
                #pipeline = self.diagramView.get_current_pipeline()
                #engine = pipeline.get_study_config().engine
                #engine.raise_for_status(self.worker.status,
                                        #self.worker.exec_id)
            #except WorkflowExecutionError as e:
                #QMessageBox.critical(self, 'Failure',
                                    #'Pipeline execution has failed:\n%s'
                                    #% str(e))
            #else:
                #QMessageBox.information(self, 'Success',
                                        #'Pipeline execution was OK.')

    #def stop_execution(self):
        #print('*** CANCEL ***')
        #with self.worker.lock:
            #self.worker.interrupt_request = True
        ##self.close()


class RunProgress(QWidget):
    """Create the pipeline progress bar and launch the thread.

    The progress bar is closed when the thread finishes.

    :param pipeline_manager: A PipelineManagerTab
    :param settings: dictionary of settings when the pipeline is iterated
    """

    def __init__(self, pipeline_manager, settings=None):

        super(RunProgress, self).__init__()

        self.pipeline_manager = pipeline_manager

        self.progressbar = QtWidgets.QProgressBar()
        layout = QHBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.progressbar)

        self.progressbar.setRange(0, 0)
        self.progressbar.setValue(0)
        self.progressbar.setMinimumWidth(350) # For mac OS

        self.worker = RunWorker(self.pipeline_manager)
        self.worker.finished.connect(self.close)

    def start(self):
        self.worker.start()
        #self.progressbar.setValue(20)

    def close(self):
        super().close()
        self.worker.wait()
        QApplication.instance().restoreOverrideCursor()

        if not hasattr(self.worker, 'exec_id'):
            mbox_icon = QMessageBox.Critical
            mbox_title = 'Failure'
            mbox_text = 'Execution has failed before running.\n' \
                'Please see details using the status report button'
        else:
            try:
                pipeline = self.pipeline_manager.pipelineEditorTabs. \
                    get_current_pipeline()
                engine = pipeline.get_study_config().engine
                engine.raise_for_status(self.worker.status,
                                        self.worker.exec_id)
            except WorkflowExecutionError as e:
                mbox_icon = QMessageBox.Critical
                mbox_title = 'Failure'
                mbox_text = 'Pipeline execution has failed:\n' \
                    'Please see details using the status report button'
            else:
                mbox_icon = QMessageBox.Information
                mbox_title = 'Success'
                mbox_text = 'Pipeline execution was OK.'
        mbox = QMessageBox(mbox_icon, mbox_title, mbox_text)
        timer = QTimer.singleShot(2000, mbox.accept)
        mbox.exec()

    def stop_execution(self):
        print('*** CANCEL ***')
        with self.worker.lock:
            self.worker.interrupt_request = True
        #self.close()


        engine \
            = self.diagramView.get_current_pipeline().get_study_config().engine
        with engine.study_config.run_lock:
            engine.study_config.run_interruption_request = True
class RunWorker(QThread):
    """Run the pipeline"""

    def __init__(self, pipeline_manager):
        super().__init__()
        self.pipeline_manager = pipeline_manager
        # use this lock to modify the worker state from GUI/other thread
        self.lock = threading.RLock()
        self.status = swconstants.WORKFLOW_NOT_STARTED
        # when interrupt_request is set (within a lock session from a different
        # thread), the worker will interrupt execution and leave the thread.
        self.interrupt_request = False

    def run(self):
        def _check_nipype_processes(pplne):
            for node_name, node in pplne.nodes.items():
                if not hasattr(node, 'process'):
                    continue  # not a process node
                if isinstance(node.process, Pipeline):
                    if node_name != "":
                        _check_nipype_processes(node.process)
                elif isinstance(node.process, NipypeProcess):
                    node.process.activate_copy = False

        with self.lock:
            if self.interrupt_request:
                print('*** INTERRUPT ***')
                return

        pipeline = self.pipeline_manager.pipelineEditorTabs. \
            get_current_pipeline()
        _check_nipype_processes(pipeline)

        with self.lock:
            if self.interrupt_request:
                print('*** INTERRUPT ***')
                return

        # Reading config
        config = Config()
        capsul_config = config.get_capsul_config()

        engine = self.pipeline_manager.get_capsul_engine()

        with self.lock:
            if self.interrupt_request:
                print('*** INTERRUPT ***')
                return

        engine.study_config.reset_process_counter()
        cwd = os.getcwd()

        pipeline = engine.get_process_instance(pipeline)

        with self.lock:
            if self.interrupt_request:
                print('*** INTERRUPT ***')
                return

        print('running pipeline...')

        try:
            exec_id = engine.start(pipeline)
            self.exec_id = exec_id
            while self.status in (swconstants.WORKFLOW_NOT_STARTED,
                                  swconstants.WORKFLOW_IN_PROGRESS):
                #print(self.status)
                with self.lock:
                    self.status = engine.wait(exec_id, 1, pipeline)
                    if self.interrupt_request:
                        print('*** INTERRUPT ***')
                        engine.interrupt(exec_id)
                        #break

            #** pathway from the study_config.run(pipeline, verbose=1) command:
            #   (ex. for the User_processes Smooth brick):
            #     info1: study_config = StudyConfig(...) defined before
            #     info2: from capsul.api import (..., StudyConfig, ...) defined
            #            before
            
            #** capsul/study_config/study_config.py
            #   class StudyConfig(Controller)
            #    run method:
            #     use: result = self._run(process_node.process,
            #                             output_directory,
            #                             verbose) ou
            #          result = self._run(process_node,
            #                             output_directory,
            #                             verbose)
            #     info1: _run() is a private method of the
            #            StudyConfig(Controller) class in the
            #            capsul/study_config/study_config.py module
            #
            #** capsul/study_config/study_config.py
            #   class StudyConfig(Controller)
            #   run method:
            #     use: returncode, log_file = run_process(output_directory,
            #                                             process_instance,
            #                                             cachedir=cachedir,
            #                            generate_logging=self.generate_logging,
            #                            verbose=verbose, **kwargs)
            #     info1: from capsul.study_config.run import run_process defined
            #            in the capsul/study_config/study_config.py module
            
            #** capsul/study_config/run.py; run_process function:
            #     use: returncode = process_instance._run_process()
            #     info1: process_instance is the brick (node, process, etc.)
            #            object (ex.  <User_processes.preprocess.spm
            #            .spatial_preprocessing.Smooth object at ...>)
            #     info2: homemade bricks do not have a mandatory _run_process
            #            method but they inherit the Process_Mia class (module
            #            mia_processes/process_mia.py) that has the
            #            _run_process method
            
            #** mia_processes/process_mia.py
            #   class Process_Mia(ProcessMIA)
            #   _run_process method
            #     use: self.run_process_mia()
            #     info1: self is the brick (node, process, etc.) object
            #            <User_processes.preprocess.spm.spatial_preprocessing
            #            .Smooth object at ...>
            
            #** User_processes/preprocess/spm/spatial_preprocessing.py
            #   class Smooth(Process_Mia)
            #   run_process_mia method:
            #     info1: this is the method where we do what we want when
            #            launching a brick (node, process, etc.).
            #     use1: super(Smooth, self).run_process_mia()
            #     info2: it calls the run_process_mia method of the Process_Mia
            #            class inherited by the Smooth class. run_process_mia
            #            method of the Process_Mia class manages the hidden
            #            matlab parameters (use_mcr, matlab_cmd, etc)
            #     use2: self.process.run()
            #     info3: self.process is a <nipype.interfaces.spm.preprocess
            #            .Smooth> object. This object inherits from the nipype
            #            SPMCommand class, which itself inherits from the nipype
            #            BaseInterface class. The BaseInterface class
            #            (nipype/interfaces/base.core.py module) have the run()
            #            method)
            #     info4: from this method run(), we are outside of mia ...
            #
            #** pipeline object introspection: see initialize method in the
            #                                  PipelineManagerTab class, this
            #                                  module

            # postprocess each node to index outputs
            if self.status == swconstants.WORKFLOW_DONE:
                self.pipeline_manager.postprocess_pipeline_execution(pipeline)
           
        except (OSError, ValueError, Exception) as e:
            print('\n{0} has not been launched:\n{1}\n'.format(pipeline.name,
                                                               e))
            import traceback
            traceback.print_exc()
        except RuntimeError as e:
            print('*** INTERRUPT ***')
            print(e)
            return


        # restore current working directory in case it has been changed
        os.chdir(cwd)


class StatusWidget(QWidget):
    """
    Status widget: displays info about the current or last pipeline execution
    """
    def __init__(self, pipeline_manager):
        super().__init__()
        self.pipeline_manager = pipeline_manager
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.edit = QtWidgets.QTextBrowser()
        log = getattr(pipeline_manager, 'last_run_log', '')
        self.edit.setText(log)

        status_box = QtWidgets.QGroupBox('Status:')
        slayout = QVBoxLayout()
        status_box.setLayout(slayout)
        status = getattr(pipeline_manager, 'last_status',
                         'No pipeline execution')
        slayout.addWidget(QtWidgets.QLabel('<b>status:</b> %s' % status))

        swf_box = QtWidgets.QGroupBox('Soma-Workflow monitoring:')
        wlayout = QVBoxLayout()
        swf_box.setLayout(wlayout)
        swf_box.setCheckable(True)
        swf_box.setChecked(False)
        self.swf_widget = None
        self.swf_box = swf_box
        swf_box.toggled.connect(self.toggle_soma_workflow)

        layout.addWidget(status_box)
        layout.addWidget(swf_box)
        layout.addWidget(QtWidgets.QLabel('Execution log:'))
        layout.addWidget(self.edit)
        self.resize(600, 800)
        self.setWindowTitle('Execution status')

    def toggle_soma_workflow(self, checked):
        if self.swf_widget is not None:
            self.swf_widget.setVisible(checked)
            if not checked:
                return
        else:
            from soma_workflow.gui.workflowGui import ApplicationModel, MainWindow, SomaWorkflowWidget
            model = ApplicationModel()
            sw_widget = MainWindow(
                model,
                None,
                True,
                None,
                None,
                interactive=False)
            self.swf_widget = sw_widget
            self.swf_box.layout().addWidget(sw_widget)




