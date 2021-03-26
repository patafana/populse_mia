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
import os
from traits.trait_base import Undefined
from traits.trait_handlers import TraitListObject

# Capsul imports
from capsul.api import Process

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
        - _run_process: called to run the process
        - get_brick_to_update: give the brick to update given the scan list
           of bricks
        - get_scan_bricks: give the list of bricks given an output value
        - list_outputs: generates the outputs of the process (need to be
           overridden)
        - make_initResult: make the final dictionnary for outputs,
           inheritance and requirement from the initialisation of a brick
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
        - run_process_mia: (need to be overridden)
        - switch_to_scripts_dir: Changes the current working directory to
           the scripts directory
        - switch_to_cur_work_dir: Changes the scripts directory to the
           current working directory

    """

    def __init__(self, *args, **kwargs):
        super(ProcessMIA, self).__init__(*args, **kwargs)
        self.change_dir = False
        self.requirement = None
        self.outputs = {}
        self.inheritance_dict = {}
        # self.filters = {}  # use if the filters are set on plugs

    def _after_run_process(self, run_process_result):
        """Method called after the process being run.

        :param run_process_result: Result of the run process
        :return: the result of the run process
        """
        self.manage_brick_after_run()
        return run_process_result

    def _before_run_process(self):
        """Method called before running the process.

        Add the exec status Not Done and exec time to the process history
        """
        self.manage_brick_before_run()

    def _run_process(self):
        """Called to run the process."""
        if self.change_dir:
            self.switch_to_scripts_dir()

        self.run_process_mia()

        if self.change_dir:
            self.switch_to_cur_work_dir()
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

    def list_outputs(self):
        """Override the outputs of the process."""
        pass

    def make_initResult(self):
        """Make the initResult_dict from initialisation."""        
        if ((self.requirement is None) or
            (not self.inheritance_dict) or
            (not self.outputs)):
            print('\nDuring the {0} process initialisation, some possible '
                   'problems were detected:'.format(self))
             
            if self.requirement is None:
                 print('- requirement attribute was not found ...')

            if not self.inheritance_dict:
                print('- inheritance_dict attribute was not found ...')

            if not self.outputs:
                print('- outputs attribute was not found ...')

            print()

        return {'requirement': self.requirement, 'outputs': self.outputs,
                'inheritance_dict': self.inheritance_dict}

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
        if hasattr(self, "process"):
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

    def run_process_mia(self):
        """
        Implements specific runs for Process_Mia subclasses
        """
        if self.change_dir:
            self.manage_matlab_launch_parameters()

    def switch_to_scripts_dir(self):
        """Method that changes the current working directory to the scripts
           directory.
        """
        try:
            self.cwd = os.getcwd()

        except OSError:
            self.cwd = None

        if (not hasattr(self, 'output_directory') or
              self.output_directory is None or
              self.output_directory is Undefined):
            raise ValueError('output_directory is not set but is mandatory to '
                             'run a Process_Mia')

        print('\nChanging from {0} directory to {1} directory ...\n'
                                       .format(self.cwd, self.output_directory))
        os.chdir(self.output_directory)
        
    def switch_to_cur_work_dir(self):
        """Method that changes the scripts directory to the current
           working directory.
        """
        try:
            cwd1 = os.getcwd()

        except OSError:
            cwd1 = None

        try:
            os.chdir(self.cwd)
            print('Changing from {0} directory to {1} directory ...\n'
                                                        .format(cwd1, self.cwd))

        except Exception as e:
            print('{0}: {1}'.format(e.__class__, e))
