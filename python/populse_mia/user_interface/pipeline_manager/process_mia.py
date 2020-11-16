# -*- coding: utf-8 -*- #
"""
Module used by MIA bricks to run processes.

:Contains:
    :Class:
        - ProcessMIA

"""

##########################################################################
# Populse_mia - Copyright (C) IRMaGe/CEA, 2018
# Distributed under the terms of the CeCILL license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL_V2.1-en.html
# for details.
##########################################################################

import datetime
from traits.trait_base import Undefined
from traits.trait_handlers import TraitListObject
import os

# Capsul imports
from capsul.api import Process
from capsul.pipeline.pipeline_nodes import ProcessNode
from soma.controller.trait_utils import relax_exists_constraint

# Populse_MIA imports
from populse_mia.data_manager.project import (BRICK_EXEC, BRICK_EXEC_TIME,
                                              BRICK_OUTPUTS,COLLECTION_BRICK,
                                              COLLECTION_CURRENT,
                                              COLLECTION_INITIAL, TAG_BRICKS)


class ProcessMIA(Process):
    """Class overriding the default capsul Process class, in order to
    personalise the run for MIA bricks.

   This class is mainly used by MIA bricks.

    .. Methods:
        - _after_run_process: method called after the process being run
        - _before_run_process: method called before running the process
        - get_brick_to_update: give the brick to update given the scan list
           of bricks
        - get_scan_bricks: give the list of bricks given an output value
        - list_outputs: generates the outputs of the process (need to be
           overridden)
        - manage_brick_after_run: update process history after the run
           (Done status)
        - manage_brick_before_run: update process history before running
           the process
        - manage_brick_output_after_run: manage the bricks history before
           the run
        - manage_brick_output_before_run: manage the bricks history before
           the run
        - manage_matlab_launch_parameters: Set the Matlab's config parameters
           when a Nipype process is used
        - remove_brick_output: remove the bricks from the outputs

    """

    
    def __init__(self):
        super(ProcessMIA, self).__init__()
        # self.filters = {}  # use if the filters are set on plugs

    def get_brick_to_update(self, bricks):
        """Give the brick to update, given the scan list of bricks.

        :param bricks: list of scan bricks
        :return: Brick to update
        """
        if bricks is None:
            return

        if len(bricks) == 0:
            return None
        if len(bricks) == 1:
            return bricks[0]
        else:
            brick_to_keep = bricks[len(bricks) - 1]
            for brick in bricks:
                exec_status = self.project.session.get_value(COLLECTION_BRICK,
                                                             brick, BRICK_EXEC)
                exec_time = self.project.session.get_value(COLLECTION_BRICK,
                                                           brick,
                                                           BRICK_EXEC_TIME)
                if (exec_time is None and exec_status is None and brick !=
                        brick_to_keep):
                    # The other bricks not run are removed
                    outputs = self.project.session.get_value(COLLECTION_BRICK,
                                                             brick,
                                                             BRICK_OUTPUTS)
                    if outputs is not None:
                        for output_name in outputs:
                            output_value = outputs[output_name]
                            self.remove_brick_output(brick, output_value)
                    self.project.session.remove_document(COLLECTION_BRICK,
                                                         brick)
                    self.project.saveModifications()
            return brick_to_keep

    def get_scan_bricks(self, output_value):
        """Give the list of bricks, given an output value.

        :param output_value: output value
        :return: list of bricks related to the output
        """
        for scan in self.project.session.get_documents_names(
                COLLECTION_CURRENT):
            if scan in str(output_value):
                return self.project.session.get_value(COLLECTION_CURRENT,
                                                      scan, TAG_BRICKS)
        return []

    def relax_nipype_exists_constraints(self):
        if hasattr(self, 'process'):
            ni_inputs = self.process.inputs
            for name, trait in ni_inputs.traits().items():
                relax_exists_constraint(trait)

    def list_outputs(self):
        """Override the outputs of the process."""
        self.relax_nipype_exists_constraints()

    def manage_brick_after_run(self):
        """Manages the brick history after the run (Done status)."""
        outputs = self.get_outputs()
        for output_name in outputs:
            output_value = outputs[output_name]
            if output_value not in ["<undefined>", Undefined]:
                if type(output_value) in [list, TraitListObject]:
                    for single_value in output_value:
                        self.manage_brick_output_after_run(single_value)
                else:
                    self.manage_brick_output_after_run(output_value)

    def manage_brick_before_run(self):
        """Updates process history, before running the process."""
        outputs = self.get_outputs()
        for output_name in outputs:
            output_value = outputs[output_name]
            if output_value not in ["<undefined>", Undefined]:
                if type(output_value) in [list, TraitListObject]:
                    for single_value in output_value:
                        self.manage_brick_output_before_run(single_value)
                else:
                    self.manage_brick_output_before_run(output_value)

    def manage_brick_output_after_run(self, output_value):
        """Manages the bricks history before the run.

        :param output_value: output value
        """
        scan_bricks_history = self.get_scan_bricks(output_value)
        brick_to_update = self.get_brick_to_update(scan_bricks_history)
        if brick_to_update is not None:
            self.project.session.set_value(COLLECTION_BRICK, brick_to_update,
                                           BRICK_EXEC, "Done")
            self.project.saveModifications()

    def manage_brick_output_before_run(self, output_value):
        """Manages the bricks history before the run.

        :param output_value: output value
        """
        scan_bricks_history = self.get_scan_bricks(output_value)
        brick_to_update = self.get_brick_to_update(scan_bricks_history)
        if brick_to_update is not None:
            self.project.session.set_value(COLLECTION_BRICK, brick_to_update,
                                           BRICK_EXEC_TIME,
                                           datetime.datetime.now())
            self.project.session.set_value(COLLECTION_BRICK, brick_to_update,
                                           BRICK_EXEC, "Not Done")
            self.project.saveModifications()

    def manage_matlab_launch_parameters(self):
        """Set the Matlab's config parameters when a Nipype process is used.

        Called in bricks.
        """
        # Note: this is a non-general trick which should probably not be here.
        if hasattr(self, "process") and hasattr(self.process, 'inputs') \
                and hasattr(self, 'use_mcr'):
            self.process.inputs.use_mcr = self.use_mcr
            self.process.inputs.paths = self.paths
            self.process.inputs.matlab_cmd = self.matlab_cmd
            self.process.inputs.mfile = self.mfile

    def remove_brick_output(self, brick, output):
        """Removes the bricks from the outputs.

        :param output: output
        :param brick: brick
        """
        if type(output) in [list, TraitListObject]:
            for single_value in output:
                self.remove_brick_output(brick, single_value)
            return

        for scan in self.project.session.get_documents_names(
                                                            COLLECTION_CURRENT):

            if scan in output:
                output_bricks = self.project.session.get_value(
                                           COLLECTION_CURRENT, scan, TAG_BRICKS)
                output_bricks.remove(brick)
                self.project.session.set_value(
                            COLLECTION_CURRENT, scan, TAG_BRICKS, output_bricks)
                self.project.session.set_value(
                            COLLECTION_INITIAL, scan, TAG_BRICKS, output_bricks)
                self.project.saveModifications()


# ---- completion system for Capsul ---

from capsul.attributes.completion_engine import (
    ProcessCompletionEngine,
    ProcessCompletionEngineFactory)


class MIAProcessCompletionEngine(ProcessCompletionEngine):
    """
    A specialized :class:`~cpasul.attributes.completion_engine.ProcessCompletionEngine` for
    :class:`ProcessMIA` instances completion.

    Such processes use their method :meth:`ProcessMIA.list_outputs` to perform
    completion from given input parameters. It is currently not based on
    attributes like in capsul completion.

    Processes also get their matlab / SPM settings filled in from the config if
    they need them.

    If the process use it and it is in the study config, their "project"
    parameter is also filled in, as well as the "output_directory" parameter.
    """

    def complete_parameters(self, process_inputs={}):

        self.completion_progress = 0.
        self.completion_progress_total = 1.
        self.set_parameters(process_inputs)
        verbose = False

        node = self.process
        process = node
        if isinstance(node, ProcessNode):
            process = node.process

            is_plugged = {key: (bool(plug.links_to)
                                or bool(plug.links_from))
                                        for key, plug in node.plugs.items()}
        else:
            is_plugged = None  # we cannot get this info
        try:
            initResult_dict = process.list_outputs(is_plugged=is_plugged)
        except Exception as e:
            print(e)
            initResult_dict = {}
        if not initResult_dict:
            return  # the process is not really configured

        outputs = initResult_dict.get('outputs', {})
        for parameter, value in outputs.items():
            if parameter == 'notInDb' \
                    or self.process.is_parameter_protected(parameter):
                continue  # special non-param or set manually
            try:
                setattr(process, parameter, value)
            except Exception as e:
                if verbose:
                    print('Exception:', e)
                    print('param:', pname)
                    print('value:', repr(value))
                    import traceback
                    traceback.print_exc()

        # Test for matlab launch
        if process.trait('use_mcr'):

            from populse_mia.software_properties import Config

            config = Config()
            if config.get_use_spm_standalone():
                process.use_mcr = True
                process.paths \
                    = config.get_spm_standalone_path().split()
                process.matlab_cmd = config.get_matlab_command()

            elif config.get_use_spm():
                process.use_mcr = False
                process.paths = config.get_spm_path().split()
                process.matlab_cmd = config.get_matlab_command()

        # add "project" attribute if the process is using it
        if hasattr(process, 'get_study_config'):
            study_config = process.get_study_config()
            project = getattr(study_config, 'project', None)
            if project:
                if hasattr(process, 'use_project') and process.use_project:
                    process.project = self.project
                # set output_directory
                if process.trait('output_directory') \
                        and process.output_directory in (None, Undefined, ''):
                    out_dir = os.path.abspath(os.path.join(project.folder,
                                                           'scripts'))
                    process.output_directory = out_dir

        self.completion_progress = self.completion_progress_total


class MIAProcessCompletionEngineFactory(ProcessCompletionEngineFactory):
    """
    Completion engine factory specialization for ProcessMIA process instances.
    Its ``factory_id`` is "mia_completion".

    This factory is activated in the
    :class:`~capsul.study_config.study_config.StudyConfig` instance by setting
    2 parameters::

        study_config.attributes_schema_paths = study_config.attributes_schema_paths \
            + ['populse_mia.user_interface.pipeline_manager.process_mia']
        study_config.process_completion =  'mia_completion'

    Once this is done, the completion system will work for all MIA processes.
    """

    factory_id = 'mia_completion'

    def get_completion_engine(self, process, name=None):
        if hasattr(process, 'completion_engine'):
            return process.completion_engine

        in_process = process
        if isinstance(process, ProcessNode):
            in_process = process.process
        if isinstance(in_process, ProcessMIA):
            return MIAProcessCompletionEngine(process, name)

        engine_factory = None
        if hasattr(process, 'get_study_config'):
            study_config = process.get_study_config()
            engine = study_config.engine
            if 'capsul.engine.module.attributes' in engine._loaded_modules:
                try:
                    former_factory = 'builtin'  # TODO how to store this ?
                    engine_factory \
                        = engine._modules_data['attributes'] \
                            ['attributes_factory'].get(
                                'process_completion', former_factory)
                except ValueError:
                    pass # not found
        if engine_factory is None:

            from capsul.attributes.completion_engine_factory \
              import BuiltinProcessCompletionEngineFactory

            engine_factory = BuiltinProcessCompletionEngineFactory()

        return engine_factory.get_completion_engine(process, name=name)


