# -*- coding: utf-8 -*- #
"""Module that handle the configuration of the software

Load and save the parameters from the miniviewer and the MIA preferences
pop-up in the config.yml file.

:Contains:
    :Class:
        - Config
    :Function:
        - verCmp

"""

##########################################################################
# Populse_mia - Copyright (C) IRMaGe/CEA, 2018
# Distributed under the terms of the CeCILL license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL_V2.1-en.html
# for details.
##########################################################################

import os
import platform
import yaml
import re
from cryptography.fernet import Fernet

CONFIG = b'5YSmesxZ4ge9au2Bxe7XDiQ3U5VCdLeRdqimOOggKyc='


def verCmp(first_ver, sec_ver, comp):
    """Version comparator.

    The verCmp() function returns a boolean value to indicate whether its
    first argument (first_ver) is equal to, less or equal to, or greater or
    equal to its second argument (sec_ver), as follows:
      - if third argument (comp) is 'eq': when the first argument is equal to the
        second argument, return True (False if not).
      - if third argument (comp) is 'sup': when the first argument is greater
        than the second argument, return True (False if not).
      - if third argument (comp) is 'inf': when the first argument is less than
        the second argument, return True (False if not).

    :param first_ver: the version of a package (a string; ex. '0.13.0')
    :param sec_ver: the version of a package (a string; ex. '0.13.0')
    :param comp: comparator argument (accepted values: 'sup', 'inf' and 'eq' )

    :returns: False or True

    :Contains:
      Private function:
        - normalise

     """

    def normalise(v):
        """Transform a version of a package to a corresponding list of integer.

        :returns: a list of integer (ex. [0, 13, 0])

        """
        v = re.sub("[^0-9\.]", "", v)
        return [int(x) for x in re.sub(r'(\.0+)*$', '', v).split(".")]

    if comp == 'eq':

        if normalise(first_ver) == normalise(sec_ver):
            return True

        else:
            return False

    elif comp == 'sup':

        if (normalise(first_ver) > normalise(sec_ver)) or (
        verCmp(first_ver, sec_ver, 'eq')):
            return True

        else:
            return False

    elif comp == 'inf':

        if (normalise(first_ver) < normalise(sec_ver)) or (
        verCmp(first_ver, sec_ver, 'eq')):
            return True

        else:
            return False


class Config:
    """
    Object that handles the configuration of the software

    .. Methods:
        - get_admin_hash: returns the value of the hash of the admin password
        - get_user_mode: returns the value of "user mode" checkbox
          in the preferences
        - get_matlab_command: returns Matlab command
        - get_matlab_path: returns the path of Matlab's executable
        - get_matlab_standalone_path: returns the path of Matlab Compiler
          Runtime
        - get_max_projects: returns the maximum number of projects displayed in
          the "Saved projects" menu
        - get_mia_path: returns the software's install path
        - get_config_path: returns the configuration file directory
        - get_projects_save_path: returns the folder where the projects are
          saved
        - get_spm_path: returns the path of SPM12 (license version)
        - get_spm_standalone_path: returns the path of SPM12 (standalone
          version)
        - get_use_matlab: returns the value of "use matlab" checkbox in the
          preferences
        - get_use_matlab_standalone: returns the value of "use matlab
          standalone" checkbox in the preferences
        - get_mri_conv_path: sets the MRIManager.jar path
        - get_use_spm: returns the value of "use spm" checkbox in the
          preferences
        - get_use_spm_standalone: returns the value of "use spm standalone"
          checkbox in the preferences
        - getBackgroundColor: returns the background color
        - getChainCursors: returns if the "chain cursors" checkbox of the
          mini viewer is activated
        - getNbAllSlicesMax: returns the maximum number of slices to display in
          the mini viewer
        - get_opened_projects: returns the opened projects
        - getPathData: returns the data's path
        - getPathToProjectsDBFile: returns the already-saved projects's path
        - getPathToProjectsFolder: returns the project's path
        - getShowAllSlices: returns if the "show all slices" checkbox of the
          mini viewer is activated
        - getTextColor: return the text color
        - getThumbnailTag: returns the tag that is displayed in the mini viewer
        - isAutoSave: checks if auto-save mode is activated
        - loadConfig: reads the config in the config.yml file
        - saveConfig: saves the config to the config.yml file
        - setAutoSave: sets the auto-save mode
        - setBackgroundColor: sets the background color
        - set_user_mode: sets the value of "user mode" checkbox in
          the preferences
        - set_matlab_path: sets the path of Matlab's executable
        - set_matlab_standalone_path: sets the path of Matlab Compiler Runtime
        - set_max_projects: sets the maximum number of projects displayed in
          the "Saved projects" menu
        - set_mia_path: sets the software's install path
        - set_mri_conv_path: sets the MRIManager.jar path
        - set_projects_save_path: sets the folder where the projects are saved
        - set_spm_path: sets the path of SPM12 (license version)
        - set_spm_standalone_path: sets the path of SPM12 (standalone version)
        - set_use_matlab: sets the value of "use matlab" checkbox in the
          preferences
        - set_use_matlab_standalone: sets the value of "use matlab standalone"
          checkbox in the preferences
        - set_use_spm: sets the value of "use spm" checkbox in the preferences
        - set_use_spm_standalone: sets the value of "use spm standalone"
          checkbox in the preferences
        - setChainCursors: sets the "chain cursors" checkbox of the mini viewer
        - setNbAllSlicesMax: sets the maximum number of slices to display in
          the mini viewer
        - set_opened_projects: sets the opened projects
        - setPathToData: sets the data's path
        - setShowAllSlices: sets the "show all slices" checkbox of the mini
          viewer
        - setTextColor: sets the text color
        - setThumbnailTag: sets the tag that is displayed in the mini viewer

    """
    def __init__(self, config_path=None, load=True):
        """Initialization of the Config class

        :Parameters:
            - :config_path: str (optional). If provided, the configuration file
               will be loaded/saved from the given directory. Otherwise the
               regular eutristics will be used to determine the config path.
               This option allows to use an alternative config directory (for
               tests for instance).
        """
        self.dev_mode = False
        if config_path is not None:
            self.config_path = config_path
        self.config = self.loadConfig()
        if "mia_user_path" not in self.config.keys():
            self.config["mia_user_path"] = self.get_mia_path()
            self.saveConfig()

    def get_admin_hash(self):
        """Get the value of the hash of the admin password.

        :return: string

        """
        try:
            return self.config["admin_hash"]
        except KeyError:
            return False

    def get_user_mode(self):
        """Get if user mode is disabled or enabled in the preferences.

        :return: boolean

        """
        return self.config.get("user_mode", False)

    def get_mainwindow_maximized(self):
        """Get the maximized (fullscreen) flag
        """

        return self.config.get('mainwindow_maximized', True)

    def get_mainwindow_size(self):
        """Get the main window size
        """

        return self.config.get('mainwindow_size', None)

    def get_matlab_command(self):
        """Get Matlab command.

        :return: Returns path to matlab executable or nothing if matlab
                 path not specified

        """
        if self.config.get("use_spm_standalone"):
            archi = platform.architecture()
            if 'Windows' in archi[1]:
                return ('{0}'.format(self.config["spm_standalone"]) + '/' +
                        'spm12_win' + archi[0][:2] + '.exe')
            else:
                return ('{0}'.format(self.config["spm_standalone"]) + os.sep +
                        'run_spm12.sh {0}'.format(self.config[
                                                    "matlab_standalone"]) +
                                        os.sep + ' script')
        else:
            return self.config.get("matlab", None)

    def get_matlab_path(self):
        """Get the path to the matlab executable.

        :return: String of path

        """
        return self.config.get("matlab", "")

    def get_matlab_standalone_path(self):
        """Get the path to matlab compiler runtime.

        :return: string of path

        """
        return self.config.get("matlab_standalone", "")

    def get_max_projects(self):
        """Get the maximum number of projects displayed in the "Saved
        projects" menu.

        :return: Integer

        """
        try:
            return int(self.config["max_projects"])
        except KeyError as e:
            return 5

    def get_mia_path(self):
        """Get the path to the folder containing the processes, properties
        and resources folders of mia (mia_path).

        During the mia installation, the mia_path is defined and stored in the
        configuration.yml file, located in the .populse_mia folder (himself
        located in the user's home). If mia is launched in admin mode,
        mia path is the cloned git repository. If mia is launched in user
        mode, mia path must compulsorily be returned from the mia_path
        parameter of the configuration.yml

        :return: string of path to mia folder

        """
        mia_path = getattr(self, 'mia_path', None)
        if mia_path:
            return mia_path
        dot_mia_config = os.path.join(os.path.expanduser("~"),
                                      ".populse_mia", "configuration.yml")

        if os.path.isfile(dot_mia_config):

            with open(dot_mia_config, 'r') as stream:

                try:
                    if verCmp(yaml.__version__, '5.1', 'sup'):
                        mia_home_config = yaml.load(stream,
                                                    Loader=yaml.FullLoader)
                    else:
                        mia_home_config = yaml.load(stream)

                    if ("dev_mode" in mia_home_config.keys() and
                            mia_home_config["dev_mode"] == True):
                        # Only for admin mode
                        self.dev_mode = True
                        config_path = os.path.dirname(os.path.realpath(
                            __file__))

                        while "properties" not in os.listdir(config_path):
                            config_path = os.path.dirname(config_path)

                        self.mia_path = config_path
                        return config_path

                    # Only for user mode
                    self.dev_mode = False

                    # mia_path is obsolete. Use mia_user_path instead
                    if "mia_path" in mia_home_config:
                        mia_home_config["mia_user_path"] = \
                                                     mia_home_config["mia_path"]
                        del mia_home_config["mia_path"]

                        with open(dot_mia_config,
                                  'w', encoding='utf8') as configfile:
                            yaml.dump(mia_home_config, configfile,
                                      default_flow_style=False,
                                      allow_unicode=True)

                    self.mia_path = mia_home_config["mia_user_path"]
                    return self.mia_path

                except (yaml.YAMLError, KeyError) as e:
                    print('\nMia path (where is located the processes, '
                          'the properties and resources folders) has not '
                          'been found ...')

        else:  # Only for admin mode

            try:
                self.mia_path = self.config["mia_user_path"]
                return self.mia_path

            except (KeyError, AttributeError):
                config_path = os.path.dirname(os.path.realpath(
                    __file__))

                while "properties" not in os.listdir(config_path):
                    config_path = os.path.dirname(config_path)

                self.mia_path = config_path
                return config_path

    def get_config_path(self):
        """Get the MIA config path (including "properties" directory)
        """
        config_path = getattr(self, 'config_path', None)
        if config_path:
            return config_path
        mia_path = self.get_mia_path()
        return os.path.join(mia_path, 'properties')

    def get_mri_conv_path(self):
        """Get the MRIManager.jar path.

        :return: string of the path

        """
        return self.config.get("mri_conv_path", "")

    def get_opened_projects(self):
        """Get opened projects.

        :return: list of opened projects

        """
        return self.config.get("opened_projects", [])

    def get_projects_save_path(self):
        """Get the path where projects are saved.

        :return: string of path

        """
        try:
            return self.config["projects_save_path"]
        except KeyError:
            if not os.path.isdir(os.path.join(self.get_mia_path(),
                                              'projects')):
                os.mkdir(os.path.join(self.get_mia_path(), 'projects'))
            return os.path.join(self.get_mia_path(), 'projects')

    def get_spm_path(self):
        """Get the path of SPM12.

        :return: string of path

        """
        return self.config.get("spm", "")

    def get_spm_standalone_path(self):
        """Get the path to the SPM12 (standalone version).

        :return: String of path

        """
        return self.config.get("spm_standalone", "")

    def get_use_matlab(self):
        """Get the value of "use matlab" checkbox in the preferences.

        :return: boolean

        """
        return self.config.get("use_matlab", False)

    def get_use_matlab_standalone(self):
        """Get the value of "use matlab standalone" checkbox in the
        preferences.

        :return: boolean

        """
        return self.config.get("use_matlab_standalone", False)

    def get_use_spm(self):
        """Get the value of "use spm" checkbox in the preferences.

        :return: boolean

        """
        return self.config.get("use_spm", False)

    def get_use_spm_standalone(self):
        """Get the value of "use spm standalone" checkbox in the preferences.

        :return: boolean

        """
        return self.config.get("use_spm_standalone", False)

    def getBackgroundColor(self):
        """Get background color.

        :return: string of the background color

        """
        return self.config.get("background_color", "")

    def getChainCursors(self):
        """Get the value of the checkbox 'chain cursor' in miniviewer.

        :return: boolean

        """
        return self.config.get("chain_cursors", False)

    def getNbAllSlicesMax(self):
        """Get number the maximum number of slices to display in the
        miniviewer.

        :return: Integer

        """
        return int(self.config.get("nb_slices_max", "10"))

    def getPathToProjectsFolder(self):
        """Get the project's path.

        :return: string of the path

        """
        return self.config.get("projects_save_path", "")

    def getSourceImageDir(self):
        """Get the source directory for project images."""
        return self.config.get("source_image_dir", "")

    def getShowAllSlices(self):
        """Get whether the show_all_slices parameters was enabled
        or not in the miniviewer.

        :return: boolean

        """
        #Used in MiniViewer
        return self.config.get("show_all_slices", False)

    def getTextColor(self):
        """Get the text color.

        :return: string

        """
        return self.config.get("text_color", "")

    def getThumbnailTag(self):
        """Get the tag of the thumbnail displayed in the miniviewer.

        :return: string

        """
        return self.config.get("thumbnail_tag", "SequenceName")

    def isAutoSave(self):
        """Get if the auto-save mode is enabled or not.

        :return: boolean

        """
        # used only in tests and when the background/text color is changed
        return self.config.get("auto_save", False)

    def loadConfig(self):
        """Read the config in the config.yml file.

        :return: Returns a dictionary of the contents of config.yml

        """
        f = Fernet(CONFIG)
        config_file = os.path.join(self.get_config_path(), 'config.yml')
        if not os.path.exists(config_file):
            return {}
        with open(config_file, 'rb') as stream:
            try:
                stream = b"".join(stream.readlines())
                decrypted = f.decrypt(stream)
                if verCmp(yaml.__version__, '5.1', 'sup'):
                    return yaml.load(decrypted, Loader=yaml.FullLoader)

                else:
                    return yaml.load(decrypted)

            except yaml.YAMLError as exc:
                print(exc)
        # in case of problem, return an empty config
        return {}

    def saveConfig(self):
        """Save the current parameters in the config.yml file."""
        f = Fernet(CONFIG)
        config_file = os.path.join(self.get_config_path(), 'config.yml')
        if not os.path.exists(os.path.dirname(config_file)):
            os.makedirs(os.path.dirname(config_file))
        with open(config_file, 'wb') as configfile:

            stream = yaml.dump(self.config, default_flow_style=False,
                      allow_unicode=True)
            configfile.write(f.encrypt(stream.encode()))

    def set_admin_hash(self, hash):
        """Set the password hash.

        :param: path: string of hash

        """
        self.config["admin_hash"] = hash
        # Then save the modification
        self.saveConfig()

    def set_user_mode(self, user_mode):
        """Enable of disable user mode.

        :param: user_mode: boolean

        """
        self.config["user_mode"] = user_mode
        # Then save the modification
        self.saveConfig()

    def set_mainwindow_maximized(self, enabled):
        """Set the maximized (fullscreen) flag
        """

        self.config['mainwindow_maximized'] = enabled
        self.saveConfig()

    def set_mainwindow_size(self, size):
        """Set main window size
        """

        self.config['mainwindow_size'] = list(size)
        self.saveConfig()

    def set_matlab_path(self, path):
        """Set the path of Matlab's executable.

        :param: path: string of path

        """
        self.config["matlab"] = path
        # Then save the modification
        self.saveConfig()

    def set_matlab_standalone_path(self, path):
        """Set the path of Matlab Compiler Runtime.

        :param: path: string of path

        """
        self.config["matlab_standalone"] = path
        # Then save the modification
        self.saveConfig()

    def set_max_projects(self, nb_max_projects):
        """Set the maximum number of projects displayed in
        the "Saved projects" menu.

        :param: nb_max_projects: Integer

        """
        self.config["max_projects"] = nb_max_projects
        # Then save the modification
        self.saveConfig()

    def set_mri_conv_path(self, path):
        """Set the MRIManager.jar path.

        :param: path: string of the path

        """
        self.config["mri_conv_path"] = path
        # Then save the modification
        self.saveConfig()

    def set_opened_projects(self, new_projects):
        """Set the list of opened projects and saves the modification.

        :param: new_projects: List of path

        """
        self.config["opened_projects"] = new_projects
        # Then save the modification
        self.saveConfig()

    def set_projects_save_path(self, path):
        """Set the folder where the projects are saved.

        :param: path: string of path
        """
        self.config["projects_save_path"] = path
        # Then save the modification
        self.saveConfig()

    def set_spm_path(self, path):
        """Set the path of SPM12 (license version).

        :param: path: string of path

        """
        self.config["spm"] = path
        # Then save the modification
        self.saveConfig()

    def set_spm_standalone_path(self, path):
        """Set the path of SPM12 (standalone version).

        :param: path: string of path

        """
        self.config["spm_standalone"] = path
        # Then save the modification
        self.saveConfig()

    def set_use_matlab(self, use_matlab):
        """Set the value of "use matlab" checkbox in the preferences.

        :param: use_matlab: boolean

        """
        self.config["use_matlab"] = use_matlab
        # Then save the modification
        self.saveConfig()

    def set_use_matlab_standalone(self, use_matlab_standalone):
        """Set the value of "use_matlab_standalone" checkbox in the
        preferences.

        :param: use_matlab: boolean

        """
        self.config["use_matlab_standalone"] = use_matlab_standalone
        # Then save the modification
        self.saveConfig()

    def set_use_spm(self, use_spm):
        """Set the value of "use spm" checkbox in the preferences.

        :param: use_spm: boolean
        """
        self.config["use_spm"] = use_spm
        # Then save the modification
        self.saveConfig()

    def set_use_spm_standalone(self, use_spm_standalone):
        """Set the value of "use spm standalone" checkbox in the preferences.

        :param:use_spm_standalone: boolean

        """
        self.config["use_spm_standalone"] = use_spm_standalone
        # Then save the modification
        self.saveConfig()

    def setAutoSave(self, save):
        """Set auto-save mode.

        :param: save: boolean
        """
        self.config["auto_save"] = save
        # Then save the modification
        self.saveConfig()

    def setBackgroundColor(self, color):
        """Set background color and save configuration.

        :param: color: Color string ('Black', 'Blue', 'Green', 'Grey',
            'Orange', 'Red', 'Yellow', 'White')
        """
        self.config["background_color"] = color
        # Then save the modification
        self.saveConfig()

    def setChainCursors(self, chain_cursors):
        """Set the value of the checkbox 'chain cursor' in the miniviewer.

        :param: chain_cursors: Boolean
        """
        self.config["chain_cursors"] = chain_cursors
        # Then save the modification
        self.saveConfig()

    def setNbAllSlicesMax(self, nb_slices_max):
        """Set the number of slices to display in the miniviewer.

        :param: nb_slices_max: Int

        """
        self.config["nb_slices_max"] = nb_slices_max
        # Then save the modification
        self.saveConfig()

    def setShowAllSlices(self, show_all_slices):
        """Set the show_all_slides setting in miniviewer.

        :param: show_all_slices: Boolean
        """
        self.config["show_all_slices"] = show_all_slices
        # Then save the modification
        self.saveConfig()

    def setSourceImageDir(self, source_image_dir):
        """Set the source directory for project images."""
        self.config["source_image_dir"] = source_image_dir
        # Then save the modification
        self.saveConfig()

    def setTextColor(self, color):
        """Set text color and save configuration.

        :param: color: Color string ('Black', 'Blue', 'Green', 'Grey',
            'Orange', 'Red', 'Yellow', 'White')

        """
        self.config["text_color"] = color
        # Then save the modification
        self.saveConfig()

    def setThumbnailTag(self, thumbnail_tag):
        """Set the tag that is displayed in the mini viewer.

        :param: thumbnail_tag: String

        """
        self.config["thumbnail_tag"] = thumbnail_tag
        # Then save the modification
        self.saveConfig()

    # def set_mia_path(self, path):
    #     """
    #
    #     :param:#         path:
    #
    #     :return:
    #
    #     """
    #     self.config["mia_user_path"] = path
    #     # Then save the modification
    #     self.saveConfig()

    # def getPathData(self):
    #     """
    #     Get the path tp the data directory
    #     :return: returns the path to the data directory
    #
    #     """
    #     return self.config["paths"]["data"]

    # def getPathToProjectsDBFile(self):
    #     """
    #
    #     :return:
    #
    #     """
    #     folder = self.getPathToProjectsFolder()
    #     return os.path.join(folder, 'projects.json')

    # def setPathToData(self,path):
    #     """
    #
    #     :param:#         path:
    #
    #     :return:
    #
    #     """
    #     if path is not None and path != '':
    #         self.config["paths"]["data"] = path
    #         # Then save the modification
    #         self.saveConfig()
