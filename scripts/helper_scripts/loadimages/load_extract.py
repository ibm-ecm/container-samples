###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2024. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################
import os.path
import shutil
import subprocess
from datetime import datetime
from enum import Enum

import jinja2
import requests
import toml
import yaml
from packaging import version
from rich import print
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.text import Text
from tomlkit import comment
from tomlkit import document
from tomlkit import nl
from tomlkit import table
from tomlkit.toml_file import TOMLFile

from ..utilities import kubernetes_utilites as k
from ..utilities.interface import generate_casepackage_results, clear
from ..utilities.prerequisites_utilites import zip_folder, read_json
from ..utilities.utilities import parse_yaml_for_keys, copy_image


# CLass that contains functions to delete the CR as well delete the Operator
class LoadExtract:

    class AirgapChannel:
        Channel = Enum(
            value='Channel',
            names=[("v22.1", "5.5.9"), ("v22.2", "5.5.10"), ("v23.1", "5.5.11"), ("v23.2", "5.5.12"), ("v24.0", "5.6.0"), ("v25.0", "5.7.0")]
        )

        def __init__(self, channel: Channel):
            self._channel = channel

    def __init__(self, console, logger=None, silent=False, dev=False, airgap=False, folder_path="", version_data=None):
        if version_data is None:
            version_data = {}
        self._logger = logger
        self._kubernetes_utilities = k.KubernetesUtilities(logger)
        self._console = console
        self._dev = dev
        self._silent_mode = silent
        self._airgap = airgap

        if 'VERSION' in version_data:
            self._fncm_version = version_data['VERSION']
        else:
            self._fncm_version = '5.7.0'

        if 'ALL_CHANNELS' in version_data:
            self._all_channel = version_data['ALL_CHANNELS']
        else:
            self._all_channel = False

        # CNCF image variables file Details
        self._image_details_folder = folder_path
        self._image_details_file = os.path.join(self._image_details_folder, "imageDetails.toml")

        json_path = os.path.join(os.getcwd(), "helper_scripts", "property")
        self._image_details_template = read_json(json_path, json_file="image_details.json")

        self._apps_v1_api = self._kubernetes_utilities.apps_v1
        self._core_v1_api = self._kubernetes_utilities.core_v1
        self._custom_api = self._kubernetes_utilities.custom_api

        # Repo information
        self._private_registry_server = ""

        # file paths from container samples
        self._content_pattern_path = os.path.join(os.path.dirname(os.getcwd()), "descriptors",
                                                  "ibm_fncm_cr_production_FC_content.yaml")
        self._operator_path = os.path.join(os.path.dirname(os.getcwd()), "descriptors",
                                           "operator.yaml")

        # Variables to store the image details
        self._repo_tag_dict = {}
        self._repo_tag_dict_from_file = {}

        self._image_push_summary = {}
        self._number_of_images = 0

        # Airgap variables file Details
        self._airgap_template = os.path.join(os.getcwd(), "helper_scripts", "loadimages", "templates",
                                             "case_variables_template.j2")
        self._airgap_details_folder = folder_path
        self._airgap_details_file = os.path.join(self._airgap_details_folder, "airgap_variables.sh")
        self._ibmpak_home = os.path.join(os.getcwd())

        # Variables to store casePackage details
        if self._dev:
            self._casepackage_url = "https://raw.githubusercontent.com/IBM/cloud-pak/refs/heads/master/repo/case/ibm-cp-fncm-case/index.yaml"
        else:
            self._casepackage_url = "https://raw.githubusercontent.com/IBM/cloud-pak/master/repo/case/ibm-cp-fncm-case/index.yaml"

        self._case_versions = {}
        self._case_versions_parsed = {}

        self._casepackage_version = "5.7.0"
        self._casename = "ibm-cp-fncm-case"

        self._airgap_vars = {}

    @property
    def ibmpak_home(self):
        return self._ibmpak_home

    @ibmpak_home.setter
    def ibmpak_home(self, value):
        self._ibmpak_home = value

    @property
    def airgap_vars(self):
        return self._airgap_vars

    @airgap_vars.setter
    def airgap_vars(self, value):
        self._airgap_vars = value

    @property
    def case_versions(self):
        return self._case_versions_parsed

    @property
    def number_of_images(self):
        return self._number_of_images

    @property
    def image_push_summary(self):
        return self._image_push_summary

    @property
    def fncm_version(self):
        return self._fncm_version

    @fncm_version.setter
    def fncm_version(self, value):
        self._fncm_version = value

    # Getter for private registry server
    @property
    def private_registry_server(self):
        return self._private_registry_server

    # Setter for private registry server
    @private_registry_server.setter
    def private_registry_server(self, value):
        self._private_registry_server = value

    @staticmethod
    def __write_property_table(section, key, value, note, ):
        section.add(nl())
        for i in note:
            section.add(comment(f'{i}'))
        section.add(key, value)

    # Function to add airgap variables to the dictionary
    def add_airgap_vars(self, key, value):
        self._airgap_vars[key] = value

    # Create the airgap variables file
    def create_airgap_details_file(self):
        # Create the Airgap Details folder
        self.__create_airgap_details_folder()

        # Load the template
        template_loader = jinja2.FileSystemLoader(os.path.dirname(self._airgap_template))
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template('case_variables_template.j2')

        # Convert dictionary to a list of dictionaries
        airgap_vars = list()
        for key, value in self._airgap_vars.items():
            airgap_vars.append({'key': key, 'value': value})

        # Render the template with data
        rendered_template = template.render(airgap_vars=airgap_vars)

        # Write the rendered template to a temporary file
        with open(self._airgap_details_file, 'w') as f:
            f.write(rendered_template)

    # Function to collect Case Versions
    def collect_case_versions(self):

        # Create tmp folder
        if not os.path.exists(os.path.join(os.getcwd(), ".tmp")):
            os.mkdir(os.path.join(os.getcwd(), ".tmp"))

        filename = os.path.join(os.getcwd(), ".tmp", "index.yaml")

        # Download the case package index.yaml file
        # Send a GET request to the URL
        response = requests.get(self._casepackage_url, stream=True, timeout=5)

        # Check if the request was successful
        if response.status_code == 200:
            # Open the file in write-binary mode
            with open(filename, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    # Write each chunk to the file
                    file.write(chunk)
            self._logger.info(f"Downloaded case package index.yaml file to {filename}")
        else:
            self._logger.error(f"Failed to download case package index.yaml file from {self._casepackage_url}")

        # Read the index.yaml file
        with open(filename, 'r') as file:
            case_versions = yaml.safe_load(file)

        # Return the case versions
        self._case_versions = case_versions
        case_versions_parsed = self.__parse_case_versions()
        self._case_versions_parsed = case_versions_parsed
        return case_versions_parsed

    # Function to parse caseVersions
    def __parse_case_versions(self):
        case_versions = self._case_versions
        case_versions_dict = {}

        lowest_version = version.parse("5.5.9")

        # Loop through the caseVersions
        for key, data in case_versions['versions'].items():
            # Get the appVersion
            app_version = data["appVersion"].split("-")[0]

            # Check if the appVersion is greater or equal 5.5.9
            if version.parse(app_version) >= lowest_version:
                # Add the appVersion to the caseVersionsDict
                if app_version not in case_versions_dict:
                    case_versions_dict[app_version] = key
                else:
                    # Check if the casePackageVersion is greater than the current version
                    if version.parse(key) > version.parse(case_versions_dict[app_version]):
                        case_versions_dict[app_version] = key

        self._case_versions_parsed = case_versions_dict
        return case_versions_dict

    # Function to select the casePackageVersion
    def select_case_package_version(self):
        print(Panel.fit("CASE Package Versions"))

        num_version = len(self._case_versions_parsed)
        choices = list(self._case_versions_parsed.keys())

        if self._silent_mode:
            print()
            print("Select a CASE Package Version")
            print("The CASE Package Version determines the version of the CASE package that will be installed.")
            print("The list below shows the latest CASE Package for each version of the FileNet Content Manager.")
            print()
            print("Select a CASE Package Version")
            for i, choice in enumerate(choices, 1):
                print(f"{i}. {self._case_versions_parsed[choice]} ({choice})")

            result = choices.index(self._fncm_version) + 1

            if 1 <= result <= num_version:
                self._casepackage_version = self._case_versions_parsed[choices[result - 1]]
            else:
                print(f"\n[prompt.invalid]Number must be between [[b]1[/b] and [b]{num_version}[/b]]")
                exit()

        else:

            while True:
                print()
                print("Select a CASE Package Version")
                print("The CASE Package Version determines the version of the CASE package that will be installed.")
                print("The list below shows the latest CASE Package for each version of the FileNet Content Manager.")
                print()
                print("Select a CASE Package Version")
                for i, choice in enumerate(choices, 1):
                    print(f"{i}. {self._case_versions_parsed[choice]} ({choice})")

                result = IntPrompt.ask(f'Enter a valid option [[b]1[/b] and [b]{num_version}[/b]]',
                                       default=choices.index(self._fncm_version) + 1)

                if 1 <= result <= num_version:
                    self._casepackage_version = self._case_versions_parsed[choices[result - 1]]
                    break

                print(f"\n[prompt.invalid]Number must be between [[b]1[/b] and [b]{num_version}[/b]]")

        print()
        print(Panel.fit(Text(f"Selected CASE Package Version: {self._casepackage_version}", style="bold green")))
        print()

        return self._casepackage_version

    # Function to create the imageDetails folder
    def __create_cncf_image_details_folder(self):
        if os.path.exists(self._image_details_folder):
            self._logger.info("Backup existing imageDetails folder")
            if not os.path.exists(os.path.join(os.getcwd(), "backups")):
                os.mkdir(os.path.join(os.getcwd(), "backups"))
            now = datetime.now()
            dt_string = now.strftime("%Y-%m-%d_%H-%M")
            zip_folder(os.path.join(os.getcwd(), "backups", "imageDetails_" + dt_string),
                       os.path.join(os.getcwd(), "imageDetails"))
            shutil.rmtree(self._image_details_folder)
            os.mkdir(self._image_details_folder)
        else:
            self._logger.info("Creating imageDetails folder")
            os.mkdir(self._image_details_folder)

    # Function to create the airgap variables file
    def __create_airgap_details_folder(self):
        if os.path.exists(self._airgap_details_folder):
            self._logger.info("Backup existing Airgap folder")
            if not os.path.exists(os.path.join(os.getcwd(), "backups")):
                os.mkdir(os.path.join(os.getcwd(), "backups"))
            now = datetime.now()
            dt_string = now.strftime("%Y-%m-%d_%H-%M")
            zip_folder(os.path.join(os.getcwd(), "backups", "airgapDetails_" + dt_string),
                       os.path.join(os.getcwd(), "airgapDetails"))
            shutil.rmtree(self._airgap_details_folder)
            os.mkdir(self._airgap_details_folder)
        else:
            self._logger.info("Creating Airgap folder")
            os.mkdir(self._airgap_details_folder)

    # Function to retrieve all component tag and repositories
    def parse_content_template(self):
        try:
            with open(self._content_pattern_path, 'r') as file:
                content_template_yaml = yaml.safe_load(file)

        except Exception as e:
            print(f"Error occurred while reading YAML file {self._content_pattern_path}: {e}")

        if content_template_yaml:
            keys_to_parse = ['repository', 'tag']
            self._repo_tag_dict = parse_yaml_for_keys(content_template_yaml, keys_to_parse)
            self._repo_tag_dict["components"] = []
            for repo in self._repo_tag_dict['repository']:
                self._repo_tag_dict["components"].append(repo.split("/")[-1])
            # adding sso images
            if "cpe" in self._repo_tag_dict["components"]:
                self._repo_tag_dict["components"].append("cpe-sso")
                self._repo_tag_dict["repository"].append("cp.icr.io/cp/cp4a/fncm/cpe-sso")
                self._repo_tag_dict["tag"].append(
                    self._repo_tag_dict["tag"][self._repo_tag_dict["repository"].index("cp.icr.io/cp/cp4a/fncm/cpe")])
            if "navigator" in self._repo_tag_dict["components"]:
                self._repo_tag_dict["components"].append("navigator-sso")
                self._repo_tag_dict["repository"].append("cp.icr.io/cp/cp4a/ban/navigator-sso")
                self._repo_tag_dict["tag"].append(self._repo_tag_dict["tag"][self._repo_tag_dict["repository"].index(
                    "cp.icr.io/cp/cp4a/ban/navigator")])
            if self._dev:
                for i in range(len(self._repo_tag_dict["repository"])):
                    self._repo_tag_dict["repository"][i] = self._repo_tag_dict["repository"][i].replace("cp.icr.io",
                                                                                                        "cp.stg.icr.io")

    # Function to parse and retrieve operator image tag and repository
    def parse_operator_template(self):
        try:
            with open(self._operator_path, 'r') as file:
                operator_template_yaml = yaml.safe_load(file)

        except Exception as e:
            print(f"Error occurred while reading YAML file {self._operator_path}: {e}")

        if operator_template_yaml:
            operator_repository, operator_tag = operator_template_yaml["spec"]["template"]["spec"]["containers"][0][
                "image"].split(":")
            if self._dev:
                operator_repository = operator_repository.replace("icr.io/cpopen", "cp.stg.icr.io/cp")
            self._repo_tag_dict["repository"].append(operator_repository)
            self._repo_tag_dict["tag"].append(operator_tag)
            self._repo_tag_dict["components"].append("ibm-fncm-operator")

    # Function to create the TOML file
    def create_image_details_file(self):

        # Create the CNCF Image Details folder
        self.__create_cncf_image_details_folder()

        if (len(self._repo_tag_dict["repository"]) != len(self._repo_tag_dict["tag"])) or len(
                self._repo_tag_dict["repository"]) == 0:
            self._logger.exception(
                "Error with the content pattern template, matching pairs of repositories and tags not found")
            exit(0)
        try:
            image_doc = document()
            image_doc.add(comment("####################################################"))
            image_doc.add(comment("##           FNCM Component Image Details          ##"))
            image_doc.add(comment("####################################################"))

            for i in range(len(self._repo_tag_dict["components"])):
                component_section = table()
                for key, value in self._image_details_template.items():
                    if key.lower() == "repository":
                        self.__write_property_table(section=component_section,
                                                    key=key,
                                                    value=self._repo_tag_dict["repository"][i],
                                                    note=value['comment'])

                    else:
                        self.__write_property_table(section=component_section,
                                                    key=key,
                                                    value=self._repo_tag_dict["tag"][i],
                                                    note=value['comment'])

                component_name = self._repo_tag_dict["components"][i].upper()
                image_doc.add(f"{component_name}", component_section)
                image_doc.add(nl())

            f = TOMLFile(self._image_details_file)
            f.write(image_doc)
            self._logger.info("Generating image details toml file completed successfully")


        except Exception as e:
            self._logger.exception(f"Exception while trying to create image details toml - {e}")

    # Parsing toml file into a dictionary
    def parse_toml_file(self, image_details_dict=None):
        if image_details_dict is None:
            image_details_dict = toml.loads(open(self._image_details_file, encoding="utf-8").read())
        self._repo_tag_dict_from_file["components"] = list(image_details_dict.keys())
        self._number_of_images = len(image_details_dict.keys())

        self._repo_tag_dict_from_file["repository"] = [value['REPOSITORY'].lower() for value in
                                                       image_details_dict.values()]
        self._repo_tag_dict_from_file["tag"] = [value['TAG'] for value in image_details_dict.values()]
        for repository in self._repo_tag_dict_from_file["repository"]:
            if self._dev:
                if "icr.io/cpopen" in repository:
                    repository = repository.replace("icr.io/cpopen", "cp.stg.icr.io/cp")
                if "cp.icr.io" in repository:
                    repository = repository.replace("cp.icr.io", "cp.stg.icr.io")

    # Function to enable generate image mirror config
    def generate_mirror_manifests(self, progress, task):
        try:
            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]

            case_name = env_vars["CASE_NAME"]
            target_registry = env_vars["TARGET_REGISTRY"]
            case_version = env_vars["CASE_VERSION"]

            command = f"oc ibm-pak generate mirror-manifests {case_name} {target_registry} --version {case_version}"

            process = subprocess.run(command, env=env_vars, shell=True, capture_output=True)


            if process.returncode != 0:
                progress.log(Panel.fit(Text("Error enabling generate-mirror", style="bold red")))
                progress.log(process.stderr.decode("utf-8"))
                self._logger.info(f"Error occurred while enabling generate-mirror: {process.stderr.decode('utf-8')}")
                progress.update(task, advance=1)
                return None

            progress.update(task, advance=1)
            return process.stdout.decode("utf-8")

        except Exception as e:
            print(Panel.fit(Text("Error enabling generate-mirror", style="bold red")))
            self._logger.info(f"Error occurred while enabling generate-mirror: {e}")
            return False

    # Private Function to parse channel files
    def __parse_channel_files(self, file_path=None) -> list:
        try:
            with open(file_path, 'r') as file:
                image_set = yaml.safe_load(file)

            parsed_channel_list = []
            # Collect channels from the image-set-config.yaml
            if 'channels' in image_set['mirror']['operators'][0]['packages'][0]:
                channels = image_set['mirror']['operators'][0]['packages'][0]['channels']

                # Parse list of channels
                for channel in channels:
                    parsed_channel_list.append(channel['name'])

            return parsed_channel_list
        except Exception as e:
            self._logger.info(f"Error occurred while reading YAML file {file_path}: {e}")
            return []

    # Function to update channels in the image-set-config.yaml
    def update_image_channels(self, channels=None):
        try:

            env_vars = self._airgap_vars.copy()

            file_path = os.path.join(env_vars['IBMPAK_HOME'], '.ibm-pak', 'data', 'mirror', env_vars['CASE_NAME'],
                                          env_vars['CASE_VERSION'], 'image-set-config.yaml')

            with open(file_path, 'r') as file:
                image_set = yaml.safe_load(file)

            # Build the list of channels
            channels_list = []
            channels.sort()
            for channel in channels:
                channels_list.append({'name': channel})

            # Update channels in the image-set-config.yaml
            if 'channels' in image_set['mirror']['operators'][0]['packages'][0]:
                image_set['mirror']['operators'][0]['packages'][0]['channels'] = channels_list

            with open(file_path, 'w') as file:
                yaml.dump(image_set, file)

            print()
            print(Panel.fit(Text("Channels updated successfully", style="bold green")))
            print()

            return True
        except Exception as e:
            self._logger.info(f"Error occurred while updating YAML file {file_path}: {e}")
            return False

    # Function to select channel for mirror
    def select_channel(self, channels=None):
        try:
            print()
            print(Panel.fit("Airgap Mirror Channels"))

            if self._silent_mode:


                num_channels = len(channels)
                choices_set = set()
                choices_list = channels

                if not self._all_channel:
                    # Calculate channel based on FNCM Version
                    current_channel = self.AirgapChannel.Channel(self._fncm_version).name
                    choices_set.add(current_channel)
                else:
                    choices_set = set(channels)

                print()
                print("Select the channels you want to mirror.")
                print("All images in the selected channels will be mirrored.")
                print("Reducing the number of channels will reduce the size of the total image set.")
                print()
                print("Enter a number to toggle selection")
                print("Enter [[b]0[/b]] to finish selection")
                for i, choice in enumerate(channels, 1):
                    print(f"{i}. {choice} {':heavy_check_mark:' if choice in choices_set else ''}")

            else:

                num_channels = len(channels)
                choices_set = set(channels)
                choices_list = channels

                while True:
                    print()
                    print("Select the channels you want to mirror.")
                    print("All images in the selected channels will be mirrored.")
                    print("Reducing the number of channels will reduce the size of the total image set.")
                    print()
                    print("Enter a number to toggle selection")
                    print("Enter [[b]0[/b]] to finish selection")
                    for i, choice in enumerate(channels, 1):
                        print(f"{i}. {choice} {':heavy_check_mark:' if choice in choices_set else ''}")

                    result = IntPrompt.ask(f'Enter a valid option [[b]1[/b] and [b]{num_channels}[/b]]')

                    if result == 0:
                        if len(choices_set) == 0:
                            print(
                                "\n[prompt.invalid]At least one mirror channel must be selected.")
                            continue
                        break

                    if 1 <= result <= num_channels:
                        # remove from set if already present
                        if choices_list[result-1] in choices_set:
                            choices_set.remove(choices_list[result-1])
                        else:
                            choices_set.add(choices_list[result-1])
                        clear(self._console)
                        print(Panel.fit("Airgap Mirror Channels"))
                    else:
                        print(f'\n[prompt.invalid]Number must be between [[b]1[/b] and [b]{num_channels}[/b]]')

            return list(choices_set)
        except Exception as e:
            self._logger.info(f"Error occurred while selecting channels: {e}")
            return []

    # Function to apply ImageMirrorPolicy to the cluster
    def apply_image_mirror_policy(self, progress, task):
        try:
            progress.log(Panel.fit(Text("Starting Cluster Setup"), style="bold cyan"))
            progress.log()

            progress.log(f"Applying ImageContentSourcePolicy to the cluster")
            progress.log()

            env_vars = self._airgap_vars.copy()

            case_name = env_vars["CASE_NAME"]
            case_version = env_vars["CASE_VERSION"]
            pak_home = env_vars["IBMPAK_HOME"]

            image_mirror_policy_file = os.path.join(pak_home, '.ibm-pak', 'data', 'mirror', case_name, case_version, 'image-content-source-policy.yaml')

            self._kubernetes_utilities.apply_cluster_resource_files(
                resource_file=image_mirror_policy_file,
                resource_type="image policy")

            progress.log(Text(f"ImageContentSourcePolicy applied to the cluster successfully!", style="bold green"))
            progress.log()


            progress.update(task, advance=1)
            return True
        except Exception as e:
            progress.log(Panel(Text(f"Error occurred while applying ImageMirrorPolicy"), style="bold red"))
            progress.log()
            self._logger.info(f"Error occurred while applying ImageMirrorPolicy: {e}")
            return False


    # Function to mirror images to private registry
    def mirror_images(self, progress, task):
        try:
            progress.log(Panel.fit(Text("Starting Airgap Mirror"), style="bold cyan"))
            progress.log()

            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]

            case_name = env_vars["CASE_NAME"]
            target_registry = env_vars["TARGET_REGISTRY"]
            case_version = env_vars["CASE_VERSION"]
            pak_home = env_vars["IBMPAK_HOME"]

            # Construct image path to image-set-config.yaml
            image_set_yaml = os.path.join(pak_home, '.ibm-pak', 'data', 'mirror', case_name, case_version, 'image-set-config.yaml')

            # Construct the command to mirror images
            command = f"oc mirror --config {image_set_yaml} docker://{target_registry} --dest-skip-tls --max-per-registry=6"

            # Execute Image Mirror command
            process = subprocess.Popen(command, stdout=subprocess.PIPE, env=env_vars, shell=True, stderr=subprocess.PIPE)

            while True:
                line = process.stdout.readline().decode('utf-8')
                if not line:
                    break
                progress.log(line)

            error = process.stderr.read().decode('utf-8')
            error_split = error.split("msg=")
            error_msg = error_split[-1]

            if error != '':
                progress.log(Text(error_msg, style="bold red"))
                progress.log(Text(f"Error mirroring images to private registry", style="bold red"))
                progress.log()
                progress.update(task, total=1)
                progress.update(task, advance=1)
                return False

            progress.log(Text(f"All images mirrored to private registry successfully!", style="bold green"))
            progress.log()
            progress.update(task, total=1)
            progress.update(task, advance=1)
            return True

        except Exception as e:
            (f"Error: {e}")
            return False

    # Function to select channel
    def collect_image_channels(self):
        env_vars = self._airgap_vars.copy()

        image_set_yaml = os.path.join(env_vars['IBMPAK_HOME'], '.ibm-pak', 'data', 'mirror', env_vars['CASE_NAME'],
                                      env_vars['CASE_VERSION'], 'image-set-config.yaml')

        channels = self.__parse_channel_files(image_set_yaml)

        selected_channels = self.select_channel(channels)

        # Ff there are differences between the selected channels and the channels in the image-set-config.yaml
        # Update the image-set-config.yaml
        if selected_channels != channels:
            self.update_image_channels(selected_channels)
            # Return true if the channels were updated
            return True

        return False

    # Function to enable oc image mirror
    def enable_oc_image(self, progress, task):
        try:
            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]

            command = "oc ibm-pak config mirror-tools --enabled oc-mirror"

            process = subprocess.run(command, env=env_vars, shell=True, capture_output=True, text=True)

            if process.returncode == 0:
                progress.update(task, advance=1)

            else:
                self._logger.info(f"Error occurred while enabling oc-mirror: {process.stderr}")
                progress.update(task, advance=1)
                return False

            return True

        except Exception as e:
            print(Panel.fit(Text("Error enabling oc-mirror", style="bold red")))
            self._logger.info(f"Error occurred while enabling oc-mirror: {e}")
            return False

    # Function to Download Case
    def download_case(self):
        try:

            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]

            command1 = "oc ibm-pak config repo 'IBM Cloud-Pak OCI registry' -r oci:cp.icr.io/cpopen --enable"

            process1 = subprocess.run(command1, env=env_vars, shell=True, capture_output=True, text=True)

            if process1.returncode == 0:
                repo_enabled = True
            else:
                repo_enabled = False

            command2 = f"oc ibm-pak get {self._casename} --version {self._casepackage_version}"

            process2 = subprocess.run(command2, env=env_vars, shell=True, capture_output=True, text=True)

            if process2.returncode != 0:
                print(Panel(Text("Case Download Failed", style="bold red")))
                print(Text(process2.stderr, style="bold red"))
                self._logger.info(f"Error occurred while downloading case: {process2.stderr}")
                return False

        except Exception as e:
            print(Panel(Text("Case Download Failed", style="bold red")))
            self._logger.info(f"Error occurred while downloading case: {e}")
            return False

        layout = generate_casepackage_results(ibmpak_folder=os.path.join(self.ibmpak_home, '.ibm-pak'),
                                              download_output=process2.stdout,
                                              repo=repo_enabled)

        return layout

    # Function to read all env variables from the airgap variables file
    def read_airgap_vars(self):
        airgap_vars = {}
        # Need to ignore comments and "remove" the export keyword
        with open(self._airgap_details_file, 'r') as file:
            for line in file:
                if line and not line.startswith('#'):
                    key, value = line.strip().split("=")
                    key = key.replace("export ", "")
                    airgap_vars[key] = value

        return airgap_vars

    # Function to copy all images to private registry
    def copy_images(self, progress, task):
        images_not_copied = []
        images_copied = []
        for i in range(len(self._repo_tag_dict_from_file["repository"])):
            tag = self._repo_tag_dict_from_file["tag"][i]
            repository = self._repo_tag_dict_from_file["repository"][i]
            new_image_repo = repository.split("/")[-1]
            src_path = f"{repository}:{tag}"
            if self._repo_tag_dict_from_file["components"][i] == 'IBM-FNCM-OPERATOR':
                dest_path = f"{self._private_registry_server}/cpopen/{new_image_repo}:{tag}"
            else:
                dest_path = f"{self._private_registry_server}/{new_image_repo}:{tag}"
            progress.log(Panel.fit(Text(f"Copying {new_image_repo}:{tag}", style="bold cyan")))
            progress.log()
            image_copied = copy_image(src_path, dest_path, progress)
            if not image_copied:
                images_not_copied.append(f"{new_image_repo}:{tag}")
            else:
                images_copied.append(f"{new_image_repo}:{tag}")

            progress.update(task, advance=1)

        self._image_push_summary["completed"] = images_copied
        self._image_push_summary["failed"] = images_not_copied
        self._image_push_summary["total"] = self._number_of_images
        self._image_push_summary["private_registry"] = self._private_registry_server

        return self._image_push_summary
