# -*- coding: utf-8 -*- #
"""
Module to define pipeline manager tab appearance, settings and methods.

Contains:
    Class:
        - PipelineManagerTab
        - RunProgress
        - RunWorker
        - StatusWidget

"""

##########################################################################
# Populse_mia - Copyright (C) IRMaGe/CEA, 2018
# Distributed under the terms of the CeCILL license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL_V2.1-en.html
# for details.
##########################################################################

# Populse_MIA imports
from populse_mia.data_manager.project import (BRICK_EXEC, BRICK_EXEC_TIME,
                                              BRICK_INIT, BRICK_INIT_TIME,
                                              BRICK_INPUTS, BRICK_NAME,
                                              BRICK_OUTPUTS, COLLECTION_BRICK,
                                              COLLECTION_CURRENT,
                                              COLLECTION_INITIAL, TAG_BRICKS,
                                              TAG_CHECKSUM, TAG_EXP_TYPE,
                                              TAG_FILENAME, TAG_TYPE, TYPE_MAT,
                                              TYPE_NII, TYPE_TXT, TYPE_UNKNOWN)
from populse_mia.software_properties import Config
from populse_mia.user_interface.pipeline_manager.iteration_table import (
                                                                 IterationTable)
from populse_mia.user_interface.pipeline_manager.node_controller import (
                                           CapsulNodeController, NodeController)
from populse_mia.user_interface.pipeline_manager.pipeline_editor import (
                                                             PipelineEditorTabs)
from populse_mia.user_interface.pipeline_manager.process_library import (
                                                           ProcessLibraryWidget)
from populse_mia.user_interface.pipeline_manager.process_mia import ProcessMIA
from populse_mia.user_interface.pop_ups import (PopUpInheritanceDict,
                                                PopUpSelectIteration)

# Capsul imports
from capsul.api import (get_process_instance, NipypeProcess, Pipeline,
                        PipelineNode, Process, ProcessNode, Switch)
from capsul.attributes.completion_engine import ProcessCompletionEngine
from capsul.engine import WorkflowExecutionError
from capsul.pipeline.pipeline_workflow import workflow_from_pipeline
from capsul.pipeline import pipeline_tools
from capsul.qt_gui.widgets.pipeline_developper_view import (
    PipelineDeveloperView)


# Soma_workflow import
import soma_workflow.constants as swconstants

# Soma_base import
from soma.controller.trait_utils import is_file_trait
from soma.qt_gui.qtThread import QtThreadCall

# PyQt5 imports
from PyQt5 import Qt
from PyQt5.QtCore import QThread, QTimer, Signal
from PyQt5.QtGui import QCursor, QIcon, QMovie
from PyQt5.QtWidgets import (QAction, QApplication, QHBoxLayout, QMenu,
                             QMessageBox, QProgressDialog, QPushButton,
                             QScrollArea, QSplitter, QToolBar, QVBoxLayout,
                             QWidget)

# Other imports
import copy
import datetime
import inspect
import os
import re
import sys
import threading
import time
import traceback
import uuid
import six
from collections import OrderedDict
from matplotlib.backends.qt_compat import QtWidgets
from traits.api import TraitListObject, Undefined
from traits.trait_errors import TraitError
import traits.api as traits
import functools
import json


class PipelineManagerTab(QWidget):
    """
    Widget that handles the Pipeline Manager tab.

    .. Methods:
        - _register_node_io_in_database: bla bla bla
        - _set_anim_frame: Callback which sets the animated icon frame to
          the status action icon
        - _show_preview:
        - add_plug_value_to_database: add the plug value to the database.
        - add_process_to_preview: add a process to the pipeline
        - build_iterated_pipeline:
        - cleanup_older_init:
        - complete_pipeline_parameters
        - controller_value_changed: update history when a pipeline node is
          changed
        - displayNodeParameters: display the node controller when a node is
          clicked
        - find_process:
        - finish_execution:
        - garbage_collect:
        - get_capsul_engine:
        - get_missing_mandatory_parameters: check on missing parameters for
          each job
        - get_pipeline_or_process:
        - initialize: clean previous initialization then initialize the current
          pipeline
        - init_pipeline: initialize the current pipeline of the pipeline
          editor
        - layout_view : initialize layout for the pipeline manager
        - loadParameters: load pipeline parameters to the current pipeline of
          the pipeline editor
        - loadPipeline: load a pipeline to the pipeline editor
        - postprocess_pipeline_execution:
        - redo: redo the last undone action on the current pipeline editor
        - register_completion_attributes:
        - runPipeline: run the current pipeline of the pipeline editor
        - saveParameters: save the pipeline parameters of the the current
          pipeline of the pipeline editor
        - savePipeline: save the current pipeline of the pipeline editor
        - savePipelineAs: save the current pipeline of the pipeline editor
          under another name
        - show_status:
        - stop_execution:
        - undo: undo the last action made on the current pipeline editor
        - update_auto_inheritance:
        - update_node_list: update the list of nodes in workflow
        - updateProcessLibrary: update the library of processes when a
          pipeline is saved
        - update_project: update the project attribute of several objects
        - update_scans_list: update the user-selected list of scans
        - update_user_buttons_states: Update the visibility of initialize/
          run/save actions according to pipeline state
        - update_user_mode: update the visibility of widgets/actions
          depending of the chosen mode

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

        if not config.isControlV1():
            Node_Controller = CapsulNodeController

        else:
            Node_Controller = NodeController
        
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
        self.node_list = []
        self.workflow = None

        # Used for the inheritance dictionary
        self.key = {}
        self.ignore = {}
        self.ignore_node = False

        QWidget.__init__(self)

        self.verticalLayout = QVBoxLayout(self)
        self.processLibrary = ProcessLibraryWidget(self.main_window)
        self.processLibrary.process_library.item_library_clicked.connect(
            self.item_library_clicked)
        #self.item_library_clicked.connect(self._show_preview)

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
        self.nodeController = Node_Controller(
            self.project, self.scan_list, self, self.main_window)
        self.nodeController.visibles_tags = \
            self.project.session.get_shown_tags()

        self.iterationTable = IterationTable(
            self.project, self.scan_list, self.main_window)
        self.iterationTable.iteration_table_updated.connect(
            self.update_scans_list)

        #self.previewBlock = PipelineDeveloperView(
        #    pipeline=None, allow_open_controller=False,
        #    show_sub_pipelines=True, enable_edition=False)

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
        # commented on January, 4th 2020
        # initialization button was deleted to avoid issues of indexation into the database.
        # initialization is now performed just befor run in run_pipeline_action
        # self.init_pipeline_action = QAction(
        #     QIcon(os.path.join(sources_images_dir, 'init32.png')),
        #     "Initialize pipeline", self)
        # self.init_pipeline_action.triggered.connect(self.initialize)
        # End - commented on January, 4th 2020

        self.run_pipeline_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'run32.png')),
            "Run pipeline", self)
        self.run_pipeline_action.triggered.connect(self.runPipeline)
        # self.run_pipeline_action.setDisabled(True) # commented on January, 4th 2020

        self.stop_pipeline_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'stop32.png')),
            "Stop", self)
        self.stop_pipeline_action.triggered.connect(self.stop_execution)
        self.stop_pipeline_action.setDisabled(True)

        self.show_pipeline_status_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'gray_cross.png')),
            "Status", self)
        self.show_pipeline_status_action.triggered.connect(self.show_status)

        self.garbage_collect_action = QAction(
            QIcon(os.path.join(sources_images_dir, 'garbage_collect.png')),
            "Cleanup", self)
        self.garbage_collect_action.triggered.connect(self.garbage_collect)
        self.garbage_collect_action.setToolTip(
            'cleanup obsolete items in the database (pipeline inits, '
            'obsolete data...). Not needed in normal situations, but useful '
            'after a reconnection (client/server) or application crash.')

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
        self.splitterRight = QSplitter(Qt.Qt.Vertical)
        self.splitter0 = QSplitter(Qt.Qt.Vertical)
        self.splitter1 = QSplitter(Qt.Qt.Horizontal)

        self.layout_view()

        # To undo/redo
        self.nodeController.value_changed.connect(
            self.controller_value_changed)

    def _register_node_io_in_database(self, job, node, pipeline_name=''):
        """bla bla bla"""

        def _serialize_tmp(item):
            import soma_workflow.client as swc
            if item in (Undefined, [Undefined]):
                return '<undefined'
            if isinstance(item, swc.TemporaryPath):
                return '<temp>'
            raise TypeError

        if isinstance(node, (PipelineNode, Pipeline)):
            # only leaf processes produce output data
            return

        process = node
        if isinstance(node, ProcessNode):
            process = node.process
        if isinstance(process, Process):
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
                for param, trait in node.user_traits().items()
                if trait.output}
            inputs = {
                param: node.get_plug_value(param)
                for param, trait in node.user_traits().items()
                if not trait.output}

        # Fill inputs and outputs values with job
        for key in inputs.keys():
            if key in job.param_dict:
                value = job.param_dict[key]
                if isinstance(value, list):
                    for i in range(len(inputs[key])):
                        inputs[key][i] = value[i]
                else:
                    inputs[key] = value

        for key in outputs.keys():
            if key in job.param_dict:
                value = job.param_dict[key]
                if isinstance(value, list):
                    for i in range(len(outputs[key])):
                        outputs[key][i] = value[i]
                else:
                    outputs[key] = value

        # also get completion attributes
        attributes = {}
        completion = ProcessCompletionEngine.get_completion_engine(node)
        if completion:
            attributes = completion.get_attribute_values().export_to_dict()

        # Adding I/O to database history
        for key in inputs:

            # filter Undefined / temp
            # this is an overhead since we convert to/from json, and it will
            # be converted again in the database. But the "default" function
            # for json is not in the database API.
            code = json.dumps(inputs[key], default=_serialize_tmp)
            inputs[key] = json.loads(code)

        for key in outputs:

            # filter Undefined / temp
            # this is an overhead since we convert to/from json, and it will
            # be converted again in the database.
            code = json.dumps(outputs[key], default=_serialize_tmp)
            outputs[key] = json.loads(code)

        node_name = node.name

        # Updating the database with output values obtained from
        # initialisation. If a plug name is in
        # outputs['notInDb'], then the corresponding
        # output value is not added to the database.
        notInDb = set(outputs.get('notInDb', []))

        for plug_name, plug_value in outputs.items():

            if plug_name not in process.traits():
                continue

            if plug_value != "<undefined>":

                if plug_name not in notInDb:

                    if pipeline_name != "":
                        full_name = pipeline_name + "." + node_name

                    else:
                        full_name = node_name

                    trait = process.trait(plug_name)
                    self.add_plug_value_to_database(plug_value,
                                                    job.uuid,
                                                    node_name,
                                                    plug_name,
                                                    full_name,
                                                    job,
                                                    trait,
                                                    inputs,
                                                    attributes)

        # Adding I/O to database history
        # Setting brick init state if init finished correctly
        self.project.session.set_values(
            COLLECTION_BRICK, job.uuid,
            {BRICK_INPUTS: inputs,
             BRICK_OUTPUTS: outputs,
             BRICK_INIT: "Done"})

    def _set_anim_frame(self):
        """
        Callback which sets the animated icon frame to the status action icon
        """

        self.show_pipeline_status_action.setIcon(
            QIcon(self._mmovie.currentPixmap()))        

    #def _show_preview(self, name_item):
    #
    #    self.previewBlock.centerOn(0, 0)
    #    self.find_process(name_item)

    def add_plug_value_to_database(self, p_value, brick_id, node_name,
                                   plug_name, full_name, job, trait, inputs,
                                   attributes):
        """Add the plug value to the database.

        :param p_value: plug value, a file name or a list of file names (any)
        :param brick_id: brick id in the database (str)
        :param node_name: name of the node (str)
        :param plug_name: name of the plug (str)
        :param full_name: full name of the node, including parent
                          brick(s) (str). If there is no parent brick,
                          full_name = node_name.
        :param job: job containing the plug (Job)
        :param trait: handler of the plug trait, or sub-trait if the plug is
                      a list (Trait). It will be used to check the value type
                      (file or not).
        :param inputs: input values for the process/node (dict)
        :param attributes: attributes set coming from Capsul completion engine
                           to be set on all outputs of the node (dict)
        """

        if isinstance(p_value, (list, TraitListObject)):
            inner_trait = trait.handler.inner_traits()[0]
            for i, elt in enumerate(p_value):
                new_attributes = {}
                for k, v in attributes.items():
                    if isinstance(v, list) and v:
                        if len(v) > i:
                            new_attributes[k] = v[i]
                        else:
                            new_attributes[k] = v[-1]
                    else:
                        new_attributes[k] = v
                self.add_plug_value_to_database(elt, brick_id, node_name,
                                                plug_name, full_name, job,
                                                inner_trait, inputs,
                                                new_attributes)
            return

        if (not is_file_trait(trait, allow_dir=True) or
                p_value in ("<undefined>", Undefined, [Undefined])):
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
        already_in_db = False
        if self.project.session.get_document(COLLECTION_CURRENT, p_value):
            already_in_db = True
            print("Path {0} already in database.".format(p_value))
        else:
            self.project.session.add_document(COLLECTION_CURRENT, p_value)
            self.project.session.add_document(COLLECTION_INITIAL, p_value)

        # Adding the new brick to the output files
        bricks = self.project.session.get_value(
            COLLECTION_CURRENT, p_value, TAG_BRICKS)
        if bricks is None:
            bricks = []
        if brick_id not in bricks:
            bricks.append(brick_id)
        # Type tag
        filename, file_extension = os.path.splitext(p_value)
        if file_extension == '.gz':
            filename, file_extension = os.path.splitext(filename)
        ptype = TYPE_UNKNOWN
        if file_extension in (".nii", ".mnc", ".ima", ".img"):
            # (not all nifti but all volumes, image "scans")
            ptype = TYPE_NII
        elif file_extension == ".mat":
            ptype = TYPE_MAT
        elif file_extension == ".txt":
            ptype = TYPE_TXT

        # determine which value the output should inherit its database tags
        # from.
        # Each process may have an "inheritance_dict" (prepared using
        # list_outputs() during completion, if it has this method).
        # If not, or if the parameter value is not found there, we also have
        # an "auto_inheritance_dict" which automatically maps outputs to
        # inputs. If there is no ambiguity, we can process automatically.
        inheritance_dict = getattr(job, 'inheritance_dict', {})
        auto_inheritance_dict = getattr(job, 'auto_inheritance_dict', {})
        parent_files = inheritance_dict.get(old_value)
        own_tags = None
        # the dicts may have several shapes. Keys are output filenames
        # Values may be
        # - an input filenme: get the tags from it
        # - in inheritance_dict only: a dict
        #   {   'parent': input_filename,
        #       'own_tags': dict of additional forceed tags}
        # - in auto_inheritance_dict only: a dict
        #   {   'param_name': input_filename, ... }
        #   when there are ambiguities

        if isinstance(parent_files, dict):
            own_tags = parent_files['own_tags']
            parent_files = {None: parent_files['parent']}

        elif isinstance(parent_files, str):
            parent_files = {None: parent_files}

        if parent_files is None:
            parent_files = auto_inheritance_dict.get(old_value, {})

            if isinstance(parent_files, str):
                parent_files = {None: parent_files}

        db_dir = os.path.join(os.path.abspath(os.path.normpath(
            self.project.folder)), '')
        field_names = self.project.session.get_fields_names(
            COLLECTION_CURRENT)
        all_cvalues = {}
        all_ivalues = {}

        # get all tags values for inputs
        for param, parent_file in parent_files.items():
            database_parent_file = None
            relfile = os.path.abspath(os.path.normpath(parent_file))[
                len(db_dir):]

            if relfile == p_value:
                # output is one of the inputs: OK nothing to be done.
                all_cvalues = {}
                all_ivalues = {}
                break

            scan = self.project.session.get_document(
                COLLECTION_CURRENT, relfile)

            if scan:
                database_parent_file = scan
                #banished_tags = set([TAG_TYPE, TAG_EXP_TYPE, TAG_BRICKS,
                #                TAG_CHECKSUM, TAG_FILENAME])
                banished_tags = set([TAG_TYPE, TAG_BRICKS,
                                TAG_CHECKSUM, TAG_FILENAME])
                cvalues = {field: getattr(scan, field)
                           for field in field_names
                           if field not in banished_tags}
                iscan = self.project.session.get_document(
                    COLLECTION_INITIAL, relfile)
                ivalues = {field: getattr(iscan, field) for field in cvalues}
                all_cvalues[param] = cvalues
                all_ivalues[param] = ivalues

        # If there are several possible inputs: there is more work
        if (not self.ignore_node and len(all_cvalues) >= 2 and
                (node_name not in self.ignore) and
                (node_name + plug_name not in self.ignore)):

            # if all inputs have the same tags set: then pick either of them,
            # they are all the same, there is no ambiguity
            eq = True
            first = None
            for param, cvalues in all_cvalues.items():
                if first is None:
                    first = cvalues
                else:
                    eq = (cvalues == first)
                    if not eq:
                        break
            if eq:
                first = None
                for param, ivalues in all_ivalues.items():
                    if first is None:
                        first = ivalues
                    else:
                        eq = (ivalues == first)
                        if not eq:
                            break
            if eq:
                # all values equal, no ambiguity
                k, v = next(iter(all_cvalues.items()))
                all_cvalues = {k: v}
                k, v = next(iter(all_ivalues.items()))
                all_ivalues = {k: v}

            else:

                # ambiguous inputs -> output
                # ask the user, or use previously setup answers.

                # FIXME:
                # There is a GUI dialog here, involving user interaction.
                # This should probably be avoided here in a processing loop.
                # Some pipelines, especially with iterations, may ask many many
                # questions to users. These should be worked on earlier.

                if node_name in self.key:
                    param = self.key[node_name]
                    value = parent_files[param]
                    inheritance_dict[old_value] = value
                    all_cvalues = {param: all_cvalues[param]}
                    all_ivalues = {param: all_ivalues[param]}
                elif node_name + plug_name in self.key:
                    param = self.key[node_name + plug_name]
                    value = parent_files[param]
                    inheritance_dict[old_value] = value
                    all_cvalues = {param: all_cvalues[param]}
                    all_ivalues = {param: all_ivalues[param]}
                elif not attributes and not already_in_db:
                    # (if there are attributes from completion, use them
                    # without asking)
                    print('no attributes for:', node_name,
                                                plug_name,
                                                full_name,
                                                p_value)
                    pop_up = PopUpInheritanceDict(parent_files,
                                                  full_name,
                                                  plug_name,
                                                  (self.iterationTable.
                                                              check_box_iterate.
                                                              isChecked)())
                    pop_up.exec()
                    self.ignore_node = pop_up.everything
                    if pop_up.ignore:
                        inheritance_dict = None
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
                        inheritance_dict[old_value] = value
                        all_cvalues = {pop_up.key: all_cvalues[pop_up.key]}
                        all_ivalues = {pop_up.key: all_ivalues[pop_up.key]}

        cvalues = {TAG_TYPE: ptype,
                   TAG_BRICKS: bricks}
        ivalues = {TAG_TYPE: ptype,
                   TAG_BRICKS: bricks}

        # from here if we still have several tags sets, we do not assign them
        # at all. Otherwise, set them.

        # Adding inherited tags
        if len(all_cvalues) == 1:
            ivalues.update(next(iter(all_ivalues.values())))
            cvalues.update(next(iter(all_cvalues.values())))

        # use also completion attributes values
        cvalues.update({k: v for k, v in attributes.items()
                        if k in field_names})
        ivalues.update({k: v for k, v in attributes.items()
                        if k in field_names})

        if own_tags:

            # own_tags may insert new fields in the database
            for tag_to_add in own_tags:

                if tag_to_add['name'] not in field_names:
                    (self.project.session.
                                  add_field)(COLLECTION_CURRENT,
                                            tag_to_add['name'],
                                            tag_to_add['field_type'],
                                            tag_to_add['description'],
                                            tag_to_add['visibility'],
                                            tag_to_add['origin'],
                                            tag_to_add['unit'],
                                            tag_to_add['default_value'])


                if (tag_to_add['name'] not in
                      (self.project.session.
                          get_fields_names)(COLLECTION_INITIAL)):
                    (self.project.session.
                                  add_field)(COLLECTION_INITIAL,
                                            tag_to_add['name'],
                                            tag_to_add['field_type'],
                                            tag_to_add['description'],
                                            tag_to_add['visibility'],
                                            tag_to_add['origin'],
                                            tag_to_add['unit'],
                                            tag_to_add['default_value'])

                cvalues[tag_to_add['name']] = tag_to_add['value']
                ivalues[tag_to_add['name']] = tag_to_add['value']

        self.project.session.set_values(
            COLLECTION_CURRENT, p_value, cvalues)
        self.project.session.set_values(
            COLLECTION_INITIAL, p_value, ivalues)

    #def add_process_to_preview(self, class_process, node_name=None):
    #    """Add a process to the pipeline.
    #
    #    :param class_process: process class's name (str)
    #    :param node_name: name of the corresponding node
    #       (using when undo/redo) (str)
    #    """
    #
    #    # pipeline = self.previewBlock.scene.pipeline
    #    pipeline = Pipeline()
    #    if not node_name:
    #        class_name = class_process.__name__
    #        i = 1
    #
    #        node_name = class_name.lower() + str(i)
    #
    #        while node_name in pipeline.nodes and i < 100:
    #            i += 1
    #            node_name = class_name.lower() + str(i)
    #
    #        process_to_use = class_process()
    #
    #    else:
    #        process_to_use = class_process
    #
    #    try:
    #        process = get_process_instance(
    #            process_to_use)
    #    except Exception as e:
    #        return

    #    pipeline.add_process(node_name, process)
    #    self.previewBlock.set_pipeline(pipeline)

    #    # Capsul update
    #    node = pipeline.nodes[node_name]
    #    # gnode = self.scene.add_node(node_name, node)

    #    return node, node_name

    def ask_iterated_pipeline_plugs(self, pipeline):
        """
        Opens a dialog to ask for each pipeline plug, if an iteration should
        iterate over it, or if it should not be iterated, or if it should be
        connected to a database filter (input_filter node)
        """

        def check_db_compat(process, plug):
            trait = process.trait(plug)
            return is_file_trait(trait)

        def iter_clicked(param_btns, p, state):
            if not state and param_btns[p][2] is not None:
                param_btns[p][2].setChecked(False)

        def db_clicked(param_btns, p, state):
            if state:
                param_btns[p][1].setChecked(True)

        dialog = Qt.QDialog()
        buttonbox = Qt.QDialogButtonBox(Qt.QDialogButtonBox.Ok
                                        | Qt.QDialogButtonBox.Cancel)
        layout = Qt.QVBoxLayout()
        param_box = Qt.QGroupBox('Iterate over parameters:')
        pblayout = Qt.QVBoxLayout()
        pblayout.setContentsMargins(0, 0, 0, 0)
        scroll = Qt.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(scroll.NoFrame)
        scroll.setViewportMargins(0, 0, 0, 0)
        pblayout.addWidget(scroll)
        param_lay = Qt.QGridLayout()
        wid = Qt.QWidget()
        scroll.setWidget(wid)
        wid.setLayout(param_lay)
        param_box.setLayout(pblayout)

        layout.addWidget(param_box)
        layout.addWidget(buttonbox)
        dialog.setLayout(layout)

        buttonbox.accepted.connect(dialog.accept)
        buttonbox.rejected.connect(dialog.reject)

        param_lay.addWidget(Qt.QLabel('iter. / database:'), 0, 0, 1, 3)
        param_lay.addWidget(Qt.QLabel('iter.:'), 0, 3, 1, 2)
        param_lay.setColumnStretch(2, 1)
        param_lay.setColumnStretch(4, 1)
        param_lay.setRowStretch(0, 0)

        inputs = pipeline.get_inputs().keys()
        outputs = pipeline.get_outputs().keys()
        params = (inputs, outputs)
        param_btns = [[], []]  # inputs, outputs
        forbidden = set(['nodes_activation', 'selection_changed',
                          'pipeline_steps', 'visible_groups'])

        for i in range(2):
            p = 0
            for plug in params[i]:
                if plug in forbidden:
                    continue
                trait = pipeline.trait(plug)
                it_btn = Qt.QCheckBox()
                db_btn = None
                if i == 0:
                    db_btn = Qt.QCheckBox()
                    if not check_db_compat(pipeline, plug):
                        db_btn.setEnabled(False)
                    c = 2
                else:
                    c = 4

                it_btn.toggled.connect(functools.partial(iter_clicked,
                                                         param_btns[i], p))

                param_lay.addWidget(it_btn, p+1, i*3)
                if db_btn:
                    param_lay.addWidget(db_btn, p+1, i*3 + 1)
                    db_btn.toggled.connect(functools.partial(db_clicked,
                                                             param_btns[i], p))
                param_lay.addWidget(Qt.QLabel(plug), p+1, c)
                param_btns[i].append([plug, it_btn, db_btn])
                it_btn.setChecked(True)
                p += 1
        param_lay.setRowStretch(max(len(inputs), len(outputs)) - 1, 1)

        res = dialog.exec_()
        if res != dialog.Accepted:
            return None

        iterated_plugs = [param[0] for param in param_btns[0] + param_btns[1]
                          if param[1].isChecked()]
        database_plugs = [param[0] for param in param_btns[0] + param_btns[1]
                          if param[2] is not None and param[2].isChecked()]

        return iterated_plugs, database_plugs

    def build_iterated_pipeline(self):
        """
        Build a new pipeline with an iteration node, iterating over the current
        pipeline
        """

        from capsul.attributes.completion_engine import ProcessCompletionEngine

        pipeline = self.get_pipeline_or_process()
        engine = self.get_capsul_engine()
        pipeline_name = 'Iteration_pipeline'
        iteration_name = 'Pipeline'
        if hasattr(pipeline, 'context_name'):
            iteration_name = pipeline.context_name
            if pipeline.context_name.split('.')[0] == 'Pipeline':
                iteration_name = '.'.join(pipeline.context_name.split('.')[1:])

        # get interactively iterated plugs and plugs that should be connected
        # to an input_filter node

        iterated_plugs = self.ask_iterated_pipeline_plugs(pipeline)
        if iterated_plugs is None:
            return  # abort
        iterated_plugs, database_plugs = iterated_plugs

        # if the pipeline is an unconnected inner node, fix it
        if hasattr(pipeline, 'parent_pipeline') and pipeline.parent_pipeline:
            pipeline.parent_pipeline = None
            if hasattr(pipeline, 'update_nodes_and_plugs_activation'):
                # only if it is a pipeline - a single node does not have it
                pipeline.update_nodes_and_plugs_activation()

        # input_filer node outputs a single list. Some processes (before
        # iteration) already take a list as input, which will end up with a
        # double list (list of list) in the iteration pipeline. To overcome
        # this, we use a single input for each iteration (list of one element)
        # before actually building the iterative pipeline. In other words,
        # we insert Reduce nodes before list inputs which will be
        # connected to the database inputs
        for plug in database_plugs:
            trait = pipeline.trait(plug)
            pipeline.trait(plug).forbid_completion = True
            if hasattr(pipeline, 'pipeline_node'):
                # propagate non-completion status
                # (TODO: needs something better)
                for link in pipeline.pipeline_node.plugs[plug].links_to:
                    link[2].get_trait(link[1]).forbid_completion = True

            if not isinstance(pipeline, Pipeline):
                # "pipeline" is actally a single process (or should, if it
                # is not a # pipeline). Get it into a pipeine (with a
                # single node) to  make the workflow.
                new_pipeline = Pipeline()
                new_pipeline.set_study_config(pipeline.study_config)
                if pipeline.context_name.split('.')[0] == 'Pipeline':
                    old_node_name = '.'.join(pipeline.context_name.split('.')[1:])
                else:
                    old_node_name = pipeline.context_name
                new_pipeline.add_process(old_node_name, pipeline)
                new_pipeline.autoexport_nodes_parameters(
                    include_optional=True)
                pipeline = new_pipeline
                iteration_name = old_node_name

            if isinstance(trait.trait_type, traits.List):
                node_name = 'un_list_%s' % plug
                ftol = pipeline.add_custom_node(
                    node_name,
                    'capsul.pipeline.custom_nodes.reduce_node.ReduceNode',
                    parameters={'input_types': ['File']})
                ftol.lengths = [1]

                # reconnect all former connection from this plug to their
                # destination, from the output of the ftol node
                for link in list(pipeline.pipeline_node.plugs[plug].links_to):
                    pipeline.add_link(
                        '%s.outputs->%s.%s' % (node_name, link[0], link[1]))

                # then remove the former pipeline plug, and re-create it by
                # exporting the input of the ftol node
                # keep traits order
                old_traits = list(pipeline.user_traits().keys())
                pipeline.remove_trait(plug)
                pipeline.export_parameter(node_name, 'input_0',
                                          pipeline_parameter=plug)
                pipeline.trait(plug).forbid_completion = True
                pipeline.reorder_traits(old_traits)

        # now replace the pipeline with an iterative node
        iteration_name = 'iterated_%s' % iteration_name
        it_pipeline = engine.get_iteration_pipeline(
            pipeline_name, iteration_name, pipeline,
            iterative_plugs=iterated_plugs, do_not_export=database_plugs,
            make_optional=None)

        # plugs which should be connected to a database filter: add some
        # Input_Filter nodes for them, and connect them to the special
        # database_scans input
        in_filter_not_found = False
        for plug in database_plugs:
            try:
                in_filter = engine.get_process_instance(
                    'mia_processes.bricks.tools.Input_Filter')
            except ValueError:
                in_filter_not_found = True
                print('Input filter not found in library.')
                break
            node_name = '%s_filter' % plug
            it_pipeline.add_process(node_name, in_filter)
            it_pipeline.add_link('%s.output->%s.%s' % (node_name, iteration_name, plug))

            # If database_scans is already a pipeline global input, the plug
            # cannot be exported. A link as to be added between database_scans
            # and the input of the filter.
            if 'database_scans' in it_pipeline.user_traits():
                it_pipeline.add_link('database_scans->%s.input' %node_name)
            else:
                old_traits = list(it_pipeline.user_traits().keys())
                it_pipeline.export_parameter(
                    node_name, 'input', pipeline_parameter='database_scans')
                it_pipeline.reorder_traits(['database_scans'] + old_traits)

        if not in_filter_not_found:
            self.pipelineEditorTabs.get_current_editor().iterated = True
        compl = ProcessCompletionEngine.get_completion_engine(it_pipeline)
        return it_pipeline

    def check_requirements(self, environment='global', message_list=None):
        config = {}
        for node in self.node_list:
            config.update(node.check_requirements(environment, message_list))

        return config

    def cleanup_older_init(self):

        for brick in self.brick_list:
            print('cleanup brick', brick)
            self.main_window.data_browser.table_data.delete_from_brick(
                brick)
        self.project.cleanup_orphan_nonexisting_files()
        self.brick_list = []
        self.node_list = []
        QtThreadCall().push(
            self.main_window.data_browser.table_data.update_table)

    def complete_pipeline_parameters(self, pipeline=None):
        """
        Complete pipeline parameters using Capsul's completion engine
        mechanism.
        This engine works using a set of attributes which can be retreived from
        the database.
        """

        # get a working / configured CapsulEngine
        engine = self.get_capsul_engine()
        if not pipeline:
            pipeline = self.get_pipeline_or_process()
        completion = ProcessCompletionEngine.get_completion_engine(pipeline)
        if completion:
            attributes = completion.get_attribute_values()
            completion.complete_parameters()

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

            if (signal_list[2] in ['protected_parameters',
                                   'protected_parameters_items',
                                   'selection_changed',
                                   'trait_added','user_traits_changed'] or
                                                   signal_list[1] == '' or
                        (signal_list[1] == [] and signal_list[4] is Undefined)):
                return

            history_maker.append("update_plug_value")

            for element in signal_list:

                if element in ['inputs', 'outputs']:
                    element = ''

                history_maker.append(element)

        #For history
        self.pipelineEditorTabs.undos[
            self.pipelineEditorTabs.get_current_editor()].append(history_maker)
        #self.pipelineEditorTabs.redos[
        #    self.pipelineEditorTabs.get_current_editor()].clear()
        # self.run_pipeline_action.setDisabled(True) # commented on January, 4th 2020

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

        """
        config = Config()

        if not config.isControlV1():
            Node_Controller = CapsulNodeController

        else:
            Node_Controller = NodeController

        self.nodeController = Node_Controller(
            self.project, self.scan_list, self, self.main_window)
        self.nodeController.visibles_tags = \
            self.project.session.get_shown_tags()
        """

        self.nodeController.display_parameters(
            node_name, process,
            self.pipelineEditorTabs.get_current_pipeline())
        self.scrollArea.setWidget(self.nodeController)

    #def find_process(self, path):
    #    """
    #    Find the dropped process in the system's paths
    #
    #    :param path: class's path (e.g. "nipype.interfaces.spm.Smooth") (str)
    #    """
    # 
    #    package_name, process_name = os.path.splitext(path)
    #    process_name = process_name[1:]
    #    __import__(package_name)
    #    pkg = sys.modules[package_name]
    #    for name, instance in sorted(list(pkg.__dict__.items())):
    #        if name == process_name and inspect.isclass(instance):
    #            try:
    #                process = get_process_instance(instance)
    #            except Exception as e:
    #                print(e)
    #                return
    #            else:
    #                node, node_name = self.add_process_to_preview(instance)
    #                gnode = self.previewBlock.scene.gnodes[node_name]
    #                gnode.setPos(0, 0)
    #                gnode.updateInfoActived(True)
    #                # gnode.active = True
    #                # gnode.update_node()
    #                rect = gnode.sceneBoundingRect()
    #                self.previewBlock.scene.setSceneRect(rect)
    #                self.previewBlock.fitInView(
    #                    rect.x(), rect.y(), rect.width() * 1.2,
    #                                        rect.height() * 1.2,
    #                    Qt.Qt.KeepAspectRatio)
    #                self.previewBlock.setAlignment(Qt.Qt.AlignCenter)

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

    def garbage_collect(self):
        """
        Index finished brick executions,
        Collect obsolete bricks and data and remove them from the database

        This performs a posptocessing on current and older pipelines, and
        cleans up the database.
        """

        self.postprocess_pipeline_execution()
        self.project.cleanup_orphan_bricks()
        self.project.cleanup_orphan_nonexisting_files()
        self.main_window.data_browser.table_data.update_table()
        if (hasattr(self.pipelineEditorTabs.get_current_editor(),
                    'initialized') and
                self.pipelineEditorTabs.get_current_editor().initialized):
            self.pipelineEditorTabs.get_current_editor().initialized = False
        self.update_user_buttons_states()

    def get_capsul_engine(self):
        """
        Get a CapsulEngine object from the edited pipeline, and set it up from
        MIA config object
        """

        return self.pipelineEditorTabs.get_capsul_engine()

    def get_pipeline_or_process(self, pipeline=None):
        """
        Get either the input pipeline (in the editor GUI), or its unique child
        process, if it only has one unconnected child. It allows to use a
        single process node from the GUI as a pipeline to iterate or run.
        """

        if pipeline is None:
            c_e = self.pipelineEditorTabs.get_current_editor()
            pipeline = c_e.scene.pipeline

        if len(pipeline.nodes) == 2 and len(pipeline.pipeline_node.plugs) == 0:
            for name, node in pipeline.nodes.items():
                if name == '':
                    continue
                if isinstance(node, ProcessNode):
                    return node.process
        return pipeline

    def get_missing_mandatory_parameters(self):
        """check on missing parameters for
          each job"""
        missing_inputs = []
        for node in self.node_list:
            job = None
            for item in node.get_missing_mandatory_parameters():
                # we must also check that the parameter is not a temporary
                # in the workflow
                if job is None:
                    job = [j for j in self.workflow.jobs
                           if hasattr(j, 'process') and j.process() is node]
                    if len(job) != 0:
                        job = job[0]
                    else:
                        job = None
                    if job:
                        value = job.param_dict.get(item)
                        if value not in (None, Undefined, []):
                            # gets a non-null value in the workflow
                            continue
                if node is self.pipelineEditorTabs.get_current_pipeline().pipeline_node:
                    item_name = item
                else:
                    item_name = '%s.%s' % (node.context_name, item)
                missing_inputs.append(item_name)

        return missing_inputs

    def initialize(self):
        """Clean previous initialization then initialize the current
        pipeline."""

        QApplication.instance().setOverrideCursor(QCursor(Qt.Qt.WaitCursor))

        if self.init_clicked:

            self.cleanup_older_init()

        self.ignore_node = False
        self.key = {}
        self.ignore = {}

        try:
            self.test_init = self.init_pipeline()

        except Exception as e:
            name = os.path.basename(
            self.pipelineEditorTabs.get_current_filename())
            if name == '': name = 'NoName'
            print('\nError during initialisation of the "{0}" pipeline '
                  '...!\nTraceback:'.format(name))
            print(''.join(traceback.format_tb(e.__traceback__)), end='')
            print('{0}: {1}\n'.format(e.__class__.__name__, e))
            self.test_init = False
            self.main_window.statusBar().showMessage(
                'Pipeline "{0}" was not initialised successfully.'.format(
                    name))

        # If the initialization fail, the run pipeline action is disabled
        # The run pipeline action is enabled only when an initialization is
        # successful
        # self.run_pipeline_action.setDisabled(True) # commented on January, 4th 2020
        self.init_clicked = True
        self.pipelineEditorTabs.update_current_node()
        self.pipelineEditorTabs.get_current_editor().node_parameters \
            = copy.deepcopy(self.pipelineEditorTabs.get_current_editor(
        ).node_parameters_tmp)
        self.pipelineEditorTabs.update_current_node()

        QApplication.instance().restoreOverrideCursor()

    def init_pipeline(self, pipeline=None, pipeline_name=""):
        """
        Initialize the current pipeline of the pipeline editor

        :param pipeline: not None if this method call a sub-pipeline
        :param pipeline_name: name of the parent pipeline
        """

        print('- Pipeline initialising ...\n')
        t0 = time.time()
        QApplication.processEvents()
        # If the initialisation is launch for the main pipeline
        if not pipeline:
            pipeline = get_process_instance(self.get_pipeline_or_process())
            main_pipeline = True

        else:
            main_pipeline = False

        #name = os.path.basename(
        #    self.pipelineEditorTabs.get_current_filename())
        name = pipeline.name
        if name == 'Pipeline': name= "NoName"
        self.main_window.statusBar().showMessage(
            'Pipeline "{0}" is getting initialized. '
            'Please wait.'.format(name))
        init_result = True

        # complete config for completion
        study_config = pipeline.get_study_config()
        study_config.project = self.project
        self.project.node_inheritance_history = {}

        req_messages = []
        init_messages = []

        # completion / retrieve workflow
        try:

            print('Completion / workflow...')
            self.workflow = workflow_from_pipeline(pipeline,
                                                   complete_parameters=True)
            print('\nWorkflow done.\n')

        except (TypeError, ValueError) as error:
            init_result = False
            ptype = 'pipeline'
            mssg = ('In {0} {1}, initialization error: '
                    '{2}').format(ptype, name, str(error))
            init_messages.append(mssg)
            pass

        # retrieve node list
        self.update_node_list()

        # check missing inputs
        missing_inputs = self.get_missing_mandatory_parameters()

        if len(missing_inputs) != 0:
            ptype = 'pipeline'
            mssg = ('In {0} {1}, missing mandatory '
                   'parameters: {2}').format(ptype,
                                             name,
                                             ', '.join(missing_inputs))
            init_messages.append(mssg)
            init_result = False

        # check requirements
        requirements = self.check_requirements('global',
                                               message_list=req_messages)

        if requirements is None:
            print('Pipeline requirements are not met.')
            print('\n'.join(req_messages))
            print('current configuration:')
            print(study_config.engine.settings.select_configurations('global'))
            init_result = False
            init_messages.append('The pipeline requirements are not met. '
                                 'Please see the standard output for more '
                                 'information.')

        else:
            # QUESTION: Would it be better to write a general method for
            #           testing all modules (currently each module test is
            #           hard coded below)?
            # TODO: Are these tests compatible with remote run?

            # FSL:
            try:
                if requirements['capsul_engine']['uses'].get('capsul.engine.module.'
                                                    'fsl') is None:
                    raise KeyError

            except KeyError:
                # The process don't need FSL
                pass

            else:
                if 'capsul.engine.module.fsl' in requirements:

                    if not requirements['capsul.engine.module.'
                               'fsl'].get('directory',
                                          False):
                        init_result = False
                        init_messages.append('The pipeline requires FSL '
                                             'but it seems FSL is not '
                                             'configured in mia '
                                             'preferences.')

                else:
                    init_result = False
                    init_messages.append('The pipeline requires FSL but it '
                                         'seems FSL is not configured in '
                                         'mia preferences.')

            # Matlab:
            try:

                if (requirements['capsul_engine']['uses'].get('capsul.engine.module.'
                                                     'matlab') is None or
                                         Config().get_use_spm_standalone()):
                    raise KeyError

            except KeyError:
                # The process don't need matlab
                pass

            else:

                if 'capsul.engine.module.matlab' in requirements:

                    if not requirements['capsul.engine.module.'
                               'matlab'].get('executable',
                                             False):
                        init_result = False
                        init_messages.append('The pipeline requires Matlab '
                                             'but it seems Matlab is not '
                                             'configured in mia '
                                             'preferences.')

                else:
                    init_result = False
                    init_messages.append('The pipeline requires Matlab but '
                                         'it seems Matlab is not '
                                         'configured in mia preferences.')

            # SPM
            try:
                if requirements['capsul_engine']['uses'].get('capsul.engine.module.'
                                                    'spm') is None:
                    raise KeyError

            except KeyError:
                # The process don't need spm
                pass

            else:

                if 'capsul.engine.module.spm' in requirements:

                    if not requirements['capsul.engine.module.spm'].get('directory',
                                                               False):
                        init_result = False
                        init_messages.append('The pipeline requires SPM '
                                             'but it seems SPM is not '
                                             'configured in mia '
                                             'preferences.')

                    elif requirements['capsul.engine.module.spm']['standalone']:

                        if Config().get_matlab_standalone_path() is None:
                            init_result = False
                            init_messages.append('The pipeline requires '
                                                 'SPM but it seems that in '
                                                 'mia preferences, SPM has '
                                                 'been configured as '
                                                 'standalone while matlab '
                                                 'Runtime is not '
                                                 'configured.')

                    else:

                        try:
                            requirements['capsul.engine.module.matlab'].get(
                                                               'executable')

                        except KeyError:
                            init_result = False
                            init_messages.append('The pipeline requires '
                                                 'SPM but it seems that in '
                                                 'mia preferences, SPM has '
                                                 'been configured as '
                                                 'non-standalone while '
                                                 'matlab with license is '
                                                 'not configured.')

                else:
                    init_result = False
                    init_messages.append('The pipeline requires SPM but it '
                                         'seems SPM is not configured in '
                                         'mia preferences.')

        # Check that completion for output parameters is fine (for each job)
        if self.workflow is not None:
            for job in self.workflow.jobs:
                if hasattr(job, 'process'):
                    node = job.process()
                    output_names = []
                    for trait_name, trait in six.iteritems(node.traits(output=True, optional=False)):
                        output_names.append(trait_name)

                    if not all(output_name in job.param_dict for output_name in output_names):
                        init_result = False

                        if node.context_name.split('.')[0] == 'Pipeline':
                            node_name = '.'.join(node.context_name.split('.')[1:])

                        else:
                            node_name = node.context_name

                        init_messages.append('It seems that mandatory output parameter(s) '
                                             ' has not been automatically set for the '
                                             '"{0}" brick.'.format(node_name))

        if init_result:
            # add process characteristics in the database
            # if init is otherwise OK
            for job in self.workflow.jobs:
                if hasattr(job, 'process'):
                    node = job.process()
                    process = node
                    if isinstance(node, ProcessNode):
                        process = node.process
                    # trick to eliminate "ReduceJob" in jobs
                    # would it be better to test if process is a ReduceNode ?
                    if hasattr(process, 'context_name'):
                        node_name = getattr(process, 'context_name', node.name)
                        if node_name.split('.')[0] == 'Pipeline':
                            node_name = '.'.join(node_name.split('.')[1:])

                        self.update_auto_inheritance(job, node)
                        self.update_inheritance(job, node)

                        # Adding the brick to the bricks history
                        if not isinstance(node, (PipelineNode, Pipeline)):
                            # check if brick_id has already been assigned
                            brick_id = getattr(job, 'uuid', None)

                            if brick_id is None:
                                brick_id = getattr(node, 'uuid', None)

                            if brick_id is None:
                                brick_id = str(uuid.uuid4())

                            # set brick_id in process
                            job.uuid = brick_id

                            self.brick_list.append(brick_id)
                            try:
                                self.project.session.add_document(COLLECTION_BRICK,
                                                                  brick_id)
                            except ValueError:
                                # # id is not unique. It happens in iterations
                                # # FIXME: we need a better way to handle UUIDs in
                                # # iterated processes
                                # brick_id = str(uuid.uuid4())
                                # job.uuid = brick_id
                                # self.brick_list[-1] = brick_id
                                # # then try again
                                # self.project.session.add_document(COLLECTION_BRICK,
                                #                                   brick_id)
                                init_result = False
                                init_messages.append('Error while setting job uuid on '
                                                     '"{0}" brick.'.format(node_name))

                            self.project.session.set_values(
                                COLLECTION_BRICK, brick_id,
                                {BRICK_NAME: node_name,
                                BRICK_INIT_TIME: datetime.datetime.now(),
                                BRICK_INIT: "Not Done",
                                BRICK_EXEC: "Not Done"})

                            self._register_node_io_in_database(job, node, pipeline_name)

        self.register_completion_attributes(pipeline)
        print('init time:', time.time() - t0)
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

            process = pipeline

            if isinstance(pipeline, Pipeline) \
                    and node_controller_node_name in pipeline.nodes:
                process = pipeline.nodes[node_controller_node_name].process

            self.nodeController.display_parameters(
                self.nodeController.node_name, process,
                self.pipelineEditorTabs.get_current_pipeline())

            if not init_result:
                self.msg = QMessageBox()
                self.msg.setIcon(QMessageBox.Critical)
                self.msg.setWindowTitle("MIA configuration warning!")
                message = 'The pipeline could not be initialised properly.'

                if init_messages:

                    for mssg in init_messages:
                        message = message + '\n- ' + mssg
                
                self.msg.setText(message)
                yes_button = self.msg.addButton("Open MIA preferences",
                                                QMessageBox.YesRole)
                ok_button = self.msg.addButton(QMessageBox.Ok)
                self.msg.exec()

                if self.msg.clickedButton() == yes_button:
                    self.main_window.software_preferences_pop_up()
                    (self.main_window.pop_up_preferences.
                                                  tab_widget.setCurrentIndex)(1)

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
        # self.tags_menu.addAction(self.init_pipeline_action) # commented on January, 4th 2020
        self.tags_menu.addAction(self.run_pipeline_action)
        self.tags_menu.addAction(self.stop_pipeline_action)
        self.tags_menu.addAction(self.show_pipeline_status_action)
        self.tags_menu.addAction(self.garbage_collect_action)

        self.tags_tool_button.setText('Pipeline')
        self.tags_tool_button.setPopupMode(
            QtWidgets.QToolButton.MenuButtonPopup)
        self.tags_tool_button.setMenu(self.tags_menu)

        # self.menu_toolbar.addAction(self.init_pipeline_action) # commented on January, 4th 2020
        self.menu_toolbar.addAction(self.run_pipeline_action)
        self.menu_toolbar.addAction(self.stop_pipeline_action)
        self.menu_toolbar.addAction(self.show_pipeline_status_action)
        self.menu_toolbar.addAction(self.garbage_collect_action)
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
        #self.splitter0.addWidget(self.previewBlock)

        self.splitter1.addWidget(self.splitter0)
        self.splitter1.addWidget(self.pipelineEditorTabs)
        self.splitter1.addWidget(self.splitterRight)
        self.splitter1.setSizes([200, 800, 200])

        # self.splitter2 = QSplitter(Qt.Qt.Vertical)
        # self.splitter2.addWidget(self.splitter1)
        # self.splitter2.setSizes([800, 100])

        self.verticalLayout.addLayout(self.hLayout)
        self.verticalLayout.addWidget(self.splitter1)

    def loadParameters(self):
        """
        Load pipeline parameters to the current pipeline of the pipeline editor
        """

        self.pipelineEditorTabs.load_pipeline_parameters()

        self.nodeController.update_parameters()

    def loadPipeline(self):
        """
        Load a pipeline to the pipeline editor
        """

        self.pipelineEditorTabs.load_pipeline()       

    def postprocess_pipeline_execution(self, pipeline=None):
        """Operations to be performed after a run has been completed.
        It can be called either within the run procedure (the user clicks on
        the "run" button and waits for the results), or after a disconnetion /
        reconnection of the client app: the user clicks on "run" with
        distributed/remote execution activated, then closes the client MIA.
        Processing takes place (possibly remotely) within a soma-workflow
        server. Then the user runs MIA again, and we have to collect the
        outputs of runs which happenned (finished) while we were disconnected.

        Such post-processing includes database indexing of output data, and
        should take into account not only the current pipeline, bu all past
        runs which have not been postprocessed yet.

        When called with a pipeline argument, it only deals with this one.

        The method can be called from within a worker run thread, thus has to
        be thread-safe.

        Question: do we have to postprocess failed runs (pipelines which
        started and failed) ? Probably yes because they may have produced some
        results during the first steps, and failed later.

        Question: how to decide which pipelines / runs have to be posptocessed
        now ? A pipeline may be started, then stopped or could have failed,
        then be postprocessed. But the user can still restart them in
        soma-workflow (or maybe mia one day), thus they should be postprocessed
        again then.
        """

        if not pipeline:
            pipeline = getattr(self, 'last_run_pipeline', None)
            if pipeline is None:
                pipeline = self.pipelineEditorTabs.get_current_pipeline()

        #print('postprocess pipeline:', pipeline)

        to_upate = self.project.finished_bricks(
            self.get_capsul_engine(), pipeline=pipeline, include_done=False)

        outputs = to_upate['outputs']
        bricks = to_upate['bricks']

        # set state of bricks: done + exec date
        for brid, brick in bricks.items():
            swf_status = brick.get('swf_status')
            if swf_status:
                exec_date = swf_status[4][2]
            else:
                # no real info about exec time
                exec_date = datetime.datetime.now()
            print('set exec status on:', brid, exec_date)
            self.project.session.set_values(
                COLLECTION_BRICK, brid,
                {BRICK_EXEC: 'Done', BRICK_EXEC_TIME: exec_date})

        # now cleanup earlier history of data
        obsolete = self.project.update_data_history(outputs)

        # get obsolete bricks (done) referenced from current outputs
        print('obsolete bricks:', obsolete)
        self.project.cleanup_orphan_bricks(obsolete)
        # temporarily disabled 2022/01/13 (Denis) to avoid breaking
        # history graphs
        #self.project.cleanup_orphan_bricks()  # modified on 4th January 2022
        self.project.cleanup_orphan_nonexisting_files()

        QtThreadCall().push(
            self.main_window.data_browser.table_data.update_table)

        self.project.saveModifications()

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
                c_e.add_named_process(
                    class_process, node_name, from_redo=True, links=links)

            elif action == "add_process":
                node_name = to_redo[1]
                c_e.del_node(node_name, from_redo=True)

            elif action == "export_plugs":
                temp_plug_name = ('inputs', to_redo[1])
                c_e._remove_plug(
                    _temp_plug_name=temp_plug_name, from_redo=True)

            elif action == "remove_plug":
                tot_plug_names = to_redo[1]

                if len(tot_plug_names) > 1:
                    tot_pip_plug_name = []
                
                for tot_plug_name in tot_plug_names:
                    pip_plug_name = tot_plug_name[0]
                    node_plug_name = tot_plug_name[1]
                    optional = tot_plug_name[2]

                    if len(tot_plug_names) == 1:
                        multi_export = False

                    else:
                        multi_export = True
                        tot_pip_plug_name.append(tot_plug_name[0][1])

                    c_e._export_plug(temp_plug_name=node_plug_name[0],
                                     weak_link=False,
                                     optional=optional,
                                     from_redo=True,
                                     pipeline_parameter=pip_plug_name[1],
                                     multi_export=multi_export)

                    # Connecting all the plugs that were connected
                    # to the original plugs.
                    
                    # Checking if the original plug is a pipeline
                    # input or output to adapt the links to add.
                    if  tot_plug_name[0][0] == 'inputs':
                        source = ('', tot_plug_name[0][1])
                        dest = tot_plug_name[1][0]

                    else:
                        source = tot_plug_name[1][0]
                        dest = ('', tot_plug_name[0][1])

                    # Writing a string to represent the link
                    source_parameters = ".".join(source)
                    dest_parameters = ".".join(dest)
                    link = "->".join((source_parameters, dest_parameters))

                    c_e.scene.pipeline.add_link(link, allow_export=True)
                    c_e.scene.update_pipeline()

                if multi_export:
                    history_maker = ["export_plugs",
                                     tot_pip_plug_name,
                                     node_plug_name[0][0]]
                    c_e.undos.append(history_maker)

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

    def register_completion_attributes(self, pipeline):
        # get a working / configured CapsulEngine

        engine = self.get_capsul_engine()
        completion = ProcessCompletionEngine.get_completion_engine(
            pipeline)
        if not completion:
            return

        attributes = completion.get_attribute_values().export_to_dict()
        if not attributes:
            return

        proj_dir = os.path.join(os.path.abspath(os.path.normpath(
            self.project.folder)), '')
        pl = len(proj_dir)

        tag_list = set(self.project.session.get_fields_names(
            COLLECTION_CURRENT))
        attributes = {k: v for k, v in attributes.items()
                      if k in tag_list}
        if not attributes:
            return

        for param in pipeline.user_traits():
            value = getattr(pipeline, param)
            todo = []
            values = []
            todo = [value]
            while todo:
                item = todo.pop(0)
                if isinstance(item, list):
                    todo += item
                elif isinstance(item, str):
                    apath = os.path.abspath(os.path.normpath(item))
                    if apath.startswith(proj_dir):
                        values.append(apath[pl:])
            for value in values:
                try:
                    self.project.session.set_values(
                        COLLECTION_CURRENT, value, attributes)
                    self.project.session.set_values(
                        COLLECTION_INITIAL, value, attributes)
                except ValueError:
                    pass  # outputs not used / inactivated

    def runPipeline(self):
        """Run the current pipeline of the pipeline editor."""

        from soma_workflow import constants as swconstants

        # Added on January, 4th 2020
        # Initialize the pipeline
        self.initialize()
        if self.test_init:
            # End - added on January, 4th 2020
            name = os.path.basename(self.pipelineEditorTabs.get_current_filename())
            if name == '': name = 'NoName'
            self.brick_list = []
            self.main_window.statusBar().showMessage(
                'Pipeline "{0}" is getting run. Please wait.'.format(name))
            QApplication.processEvents()
            self.key = {}
            self.ignore = {}
            self.ignore_node = False

            self.last_run_pipeline = self.get_pipeline_or_process()
            self.last_status = swconstants.WORKFLOW_NOT_STARTED
            self.last_run_log = None
            self.last_pipeline_name = self.pipelineEditorTabs.get_current_filename()
            if self.last_pipeline_name == '': self.last_pipeline_name = 'NoName'

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
            # self.run_pipeline_action.setDisabled(True) # Commented on January, 4th 2020

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

    def show_status(self):
        """
        Show the last run status and execution info, errors etc.
        """

        print('show_status')
        log = getattr(self, 'last_run_log', '')
        status_widget = StatusWidget(self)
        status_widget.show()
        self.status_widget = status_widget

    def stop_execution(self):
        """
        Request interruption of pipeline execution
        """

        print('stop_execution')
        self.progress.stop_execution()

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
                c_e.add_named_process(
                    class_name, node_name, from_undo=True, links=links)

            elif action == "export_plugs":
                parameters = to_undo[1]
                node_name = to_undo[2]

                if isinstance(parameters, str):
                    parameters= [parameters]

                temp_plug_name = []

                for parameter in parameters:

                    if c_e.scene.pipeline.nodes[''].plugs[parameter].links_to:
                        pip_plug_name = ('inputs', parameter)

                    else:
                        pip_plug_name = ('outputs', parameter)

                    temp_plug_name.append(pip_plug_name)

                c_e._remove_plug(_temp_plug_name=temp_plug_name,
                                 from_undo=True,
                                 from_export_plugs=False)

                #self.main_window.statusBar().showMessage(
                #    "Plugs {0} have been removed.".format(str(parameters)))

            elif action == "remove_plug":
                tot_plug_names = to_undo[1]

                if len(tot_plug_names) > 1:
                    tot_pip_plug_name = []

                for tot_plug_name in tot_plug_names:
                    pip_plug_name = tot_plug_name[0]
                    node_plug_name = tot_plug_name[1]
                    optional = tot_plug_name[2]

                    if len(tot_plug_names) == 1:
                        multi_export = False

                    else:
                        multi_export = True
                        tot_pip_plug_name.append(tot_plug_name[0][1])

                    c_e._export_plug(temp_plug_name=node_plug_name[0],
                                     weak_link=False,
                                     optional=optional,
                                     from_undo=True,
                                     pipeline_parameter=pip_plug_name[1],
                                     multi_export=multi_export)

                    # Connecting all the plugs that were connected
                    # to the original plugs.

                    if tot_plug_name[1] and tot_plug_name[0]:
                        # Checking if the original plug is a pipeline
                        # input or output to adapt the links to add.
                        if  tot_plug_name[0][0] == 'inputs':
                            source = ('', tot_plug_name[0][1])
                            dest = tot_plug_name[1][0]

                        else:
                            source = tot_plug_name[1][0]
                            dest = ('', tot_plug_name[0][1])

                        # Writing a string to represent the link
                        source_parameters = ".".join(source)
                        dest_parameters = ".".join(dest)
                        link = "->".join((source_parameters, dest_parameters))

                        c_e.scene.pipeline.add_link(link, allow_export=True)

                    c_e.scene.update_pipeline()

                if multi_export:
                    history_maker = ["export_plugs",
                                     tot_pip_plug_name,
                                     node_plug_name[0][0]]

                    c_e.undos.append(history_maker)

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
                c_e.add_link(source, dest, active, weak, from_undo=True,
                             allow_export=True)

            c_e.scene.pipeline.update_nodes_and_plugs_activation()
            self.nodeController.update_parameters()

    def update_auto_inheritance(self, job, node):
        '''
        Try (as best as possible) to assign output parameters to input ones,
        to get database tags for them.

        When a node has only one input with a value (filename) in the database,
        then output filenames are considered to inherit from it.
        When several input parameters have values in the database, then if they
        are all equal, we can fallback to the first case.
        When values are different, and have different database tags, then the
        ambiguity remains, and we keep track of the several possible inputs
        which can provide tags for outputs.

        The process attribute auto_inheritance_dict is filled with these
        values. It's a dict with the shape::

            {output_filename: <input_spec>}

        `output_filename` is the relative filename in the database

        `<input_spec>` can be:

        * a string: filename
        * a dict::

                {input_param: input_filename}

        `auto_inheritance_dict` is built automatically, ans is used as a
        fallback to :class:`ProcessMIA` `inheritance_dict`, built "manually"
        (specialized for each process) in the :meth:`ProcessMIA.list_outputs`
        when the latter does not exist, or does not specify what an output
        inherits from.

        If ambiguities still subsist, the MIA infrastructure will ask the user
        how to solve them, which is not very convenient, and error-prone, thus
        should be avoided.
        '''

        # print('update_auto_inheritance:', node.name)

        process = node
        if isinstance(process, ProcessNode):
            process = process.process

        if not isinstance(process, Process) or isinstance(process, Pipeline):
            # keep only leaf processes that actually produce outputs
            return

        if hasattr(process, 'auto_inheritance_dict'):
            del process.auto_inheritance_dict

        if not hasattr(process, 'get_study_config'):
            return
        study_config = process.get_study_config()

        project = getattr(study_config, 'project', None)
        if not project:
            # no databasing, nothing to be done.
            return

        proj_dir = os.path.join(
            os.path.abspath(os.path.normpath(project.folder)), '')
        pl = len(proj_dir)

        # retrieve inputs and outputs keys in process,
        if isinstance(process, Process):

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
                for param, trait in process.user_traits().items()
                if trait.output}
            inputs = {
                param: node.get_plug_value(param)
                for param, trait in process.user_traits().items()
                if not trait.output}

        # Fill inputs and outputs values with job
        for key in inputs.keys():
            if key in job.param_dict:
                value = job.param_dict[key]
                if isinstance(value, list):
                    for i in range(len(inputs[key])):
                        inputs[key][i] = value[i]
                else:
                    inputs[key] = value

        for key in outputs.keys():
            if key in job.param_dict:
                value = job.param_dict[key]
                if isinstance(value, list):
                    for i in range(len(outputs[key])):
                        outputs[key][i] = value[i]
                else:
                    outputs[key] = value

        # if the process has a single input with a value in the database,
        # then we can deduce its output database tags/attributes from it

        values = {}
        for key, value in inputs.items():

            trait = process.trait(key)
            if not is_file_trait(trait):
                continue

            paths = []
            if isinstance(value, list):
                for val in value:
                    if isinstance(val, str):
                        paths.append(val)
            elif isinstance(value, str):
                paths.append(value)
            for path in paths:
                path = os.path.abspath(os.path.normpath(path))
                if path.startswith(proj_dir):
                    rpath = path[pl:]
                    if project.session.has_document(COLLECTION_CURRENT, rpath):
                        # we'd better use rpath, but inheritance_dict
                        # is using full paths.
                        values[key] = path
                        break
                        # TODO what if several path values are valid ?

        if len(values) == 0:
            # zero inputs are registered in the database: we cannot
            # infer outputs tags automatically. OK we leave.
            return
        elif len(values) == 1:
            main_param = next(iter(values.keys()))
            main_value = values[main_param]
        else:
            # several inputs are registered in the database: we cannot
            # infer outputs tags automatically too, but we mark the ambiguity
            # to ask the user later
            main_value = values

        notInDb = set(outputs.get('notInDb', []))

        auto_inheritance_dict = {}

        for plug_name, plug_value in outputs.items():

            if plug_name in notInDb:
                continue

            trait = process.trait(plug_name)
            if not trait or not is_file_trait(trait):
                continue

            plug_values = set()
            todo = [plug_value]
            while todo:
                value = todo.pop(0)
                if isinstance(value, list):
                    todo += value
                elif isinstance(value, str):
                    path = os.path.abspath(os.path.normpath(value))
                    if path.startswith(proj_dir):
                        #rpath = path[pl:]
                        plug_values.add(value)

            for value in plug_values:
                auto_inheritance_dict[value] = main_value

        if auto_inheritance_dict:
            job.auto_inheritance_dict = auto_inheritance_dict
            # print('auto_inheritance_dict for', node.name, ':', auto_inheritance_dict)

    def update_inheritance(self, job, node):
        if node.context_name.split('.')[0] == 'Pipeline':
            node_name = '.'.join(node.context_name.split('.')[1:])

        else:
            node_name = node.context_name

        new_inheritance_dict = {}
        if node_name in self.project.node_inheritance_history:
            for inherit_dict in self.project.node_inheritance_history[node_name]:
                dict_found = False
                for inheritance_dict_key in inherit_dict.keys():
                    for param_key, param_value in job.param_dict.items():
                        if inheritance_dict_key == param_value and not dict_found:
                            new_inheritance_dict.update(inherit_dict)
                            dict_found = True
        if not new_inheritance_dict:
            process = node
            if isinstance(process, ProcessNode):
                process = process.process
            job.inheritance_dict = getattr(process, 'inheritance_dict', {})
        else:
            job.inheritance_dict = new_inheritance_dict

    def update_node_list(self):
        """
        Update the list of nodes in workflow
        """
        if self.workflow is not None:
            for job in self.workflow.jobs:
                if hasattr(job, 'process'):
                    node = job.process()
                    if node not in self.node_list:
                        self.node_list.append(node)

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

    def update_scans_list(self, iteration_list, all_iterations_list):
        """
        Update the user-selected list of scans

        :param iteration_list: current list of scans in the iteration table
        """

        self.update_user_buttons_states()

        c_e = self.pipelineEditorTabs.get_current_editor()
        pipeline = self.pipelineEditorTabs.get_current_pipeline()
        has_iteration = False
        iteration_name = 'iteration'
        if pipeline and hasattr(pipeline, 'nodes'):
            for key in pipeline.nodes.sortedKeys:
                if 'iterated_' in key:
                    has_iteration = True
                    iteration_name = key

        if self.iterationTable.check_box_iterate.isChecked():
            if not has_iteration:
                # move to an iteration pipeline
                new_pipeline = self.build_iterated_pipeline()
                if new_pipeline is None:
                    # abort
                    self.iterationTable.check_box_iterate.setCheckState(
                        Qt.Qt.Unchecked)
                    return

                c_e.set_pipeline(new_pipeline)
                self.displayNodeParameters('inputs', new_pipeline)

            self.iteration_table_scans_list = all_iterations_list
            self.pipelineEditorTabs.scan_list = sum(all_iterations_list, [])
        else:
            if has_iteration:
                # get the pipeline out from the iteration node
                new_pipeline = pipeline.nodes[iteration_name].process.process
                c_e.set_pipeline(new_pipeline)
                self.displayNodeParameters('inputs', new_pipeline)

            self.iteration_table_scans_list = []
            self.pipelineEditorTabs.scan_list = self.scan_list
        #print('update_scans_list:', sum(all_iterations_list, []))
        if not self.pipelineEditorTabs.scan_list:
            self.pipelineEditorTabs.scan_list = \
                self.project.session.get_documents_names(COLLECTION_CURRENT)
        self.pipelineEditorTabs.update_scans_list()

    def update_user_buttons_states(self):
        """
        Update the visibility of initialize/run/save actions according to pipeline state
        """
        # Commented on January, 4th 2020
        # With disabling of init button, run button is always available
        # if (hasattr(self.pipelineEditorTabs.get_current_editor(),
        #             'initialized') and
        #         self.pipelineEditorTabs.get_current_editor().initialized):
        #     self.run_pipeline_action.setDisabled(False)
        # else:
        #     self.run_pipeline_action.setDisabled(True)
        #
        # self.init_pipeline_action.setDisabled(False)
        self.run_pipeline_action.setDisabled(False)
        # End - Commented on January, 4th 2020

        if (hasattr(self.pipelineEditorTabs.get_current_editor(),
                    'iterated') and
                self.pipelineEditorTabs.get_current_editor().iterated):
            self.save_pipeline_as_action.setDisabled(True)
            self.save_pipeline_action.setDisabled(True)
        else:
            self.save_pipeline_as_action.setDisabled(False)
            self.save_pipeline_action.setDisabled(False)

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
            if self.nodeController.process_widget:
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
                pipeline = self.pipeline_manager.get_pipeline_or_process()
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

    def start(self):

        self.worker.start()
        #self.progressbar.setValue(20)

    def stop_execution(self):

        print('*** CANCEL ***')
        with self.worker.lock:
            self.worker.interrupt_request = True
        #self.close()


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

            if isinstance(pplne, Pipeline):
                for node_name, node in pplne.nodes.items():
                    if not hasattr(node, 'process'):
                        continue  # not a process node
                    if isinstance(node.process, Pipeline):
                        if node_name != "":
                            _check_nipype_processes(node.process)
                    elif isinstance(node.process, NipypeProcess):
                        node.process.activate_copy = False
            elif isinstance(pipeline, NipypeProcess):
                pipeline.activate_copy = False

        with self.lock:
            if self.interrupt_request:
                print('*** INTERRUPT ***')
                return

        pipeline = self.pipeline_manager.get_pipeline_or_process()
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

        print('- Pipeline running ...\n')

        try:
            exec_id, pipeline = engine.start(pipeline, workflow=self.pipeline_manager.workflow, get_pipeline=True)
            self.exec_id = exec_id
            while self.status in (swconstants.WORKFLOW_NOT_STARTED,
                                  swconstants.WORKFLOW_IN_PROGRESS):
                #print(self.status)
                self.status = engine.wait(exec_id, 1, pipeline)
                with self.lock:
                    if self.interrupt_request:
                        print('*** INTERRUPT ***')
                        engine.interrupt(exec_id)
                        #break

            # postprocess each node to index outputs
            # if self.status == swconstants.WORKFLOW_DONE:
            # do it even in case of failure to get partial outputs and clean
            # the remainings
            self.pipeline_manager.postprocess_pipeline_execution(pipeline)
           
        except (OSError, ValueError, Exception) as e:
            print('\n{0} has not run correctly:\n{1}\n'.format(
                      pipeline.name, e))
            import traceback
            traceback.print_exc()

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




