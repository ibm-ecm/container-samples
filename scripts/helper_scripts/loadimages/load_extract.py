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
from ..utilities.prerequisites_utilites import zip_folder
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

    def __init__(self, console, logger=None, silent=False, dev=False, airgap=False, folder_path="", version_data=None, tls_verify=True):
        if version_data is None:
            version_data = {}
        self._logger = logger
        self._kube = k.KubernetesUtilities(logger)
        self._console = console
        self._dev = dev
        self._silent_mode = silent
        self._airgap = airgap
        self._tls_verify = tls_verify

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

        self._apps_v1_api = self._kube.apps_v1
        self._core_v1_api = self._kube.core_v1
        self._custom_api = self._kube.custom_api

        # Repo information
        self._private_registry_full_server = ""

        # file paths from container samples
        self._content_pattern_path = os.path.join(os.path.dirname(os.getcwd()), "descriptors",
                                                  "ibm_fncm_cr_production_FC_content.yaml")
        self._operator_path = os.path.join(os.path.dirname(os.getcwd()), "descriptors",
                                           "operator.yaml")

        # Variables to store the image details
        self._repo_tag_list = []
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
        self._case_versions_list = []

        self._casepackage_version = "5.7.0"
        self._casename = "ibm-cp-fncm-case"

        self._airgap_vars = {}

    @property
    def casepackage_version(self):
        return self._casepackage_version

    @casepackage_version.setter
    def casepackage_version(self, value):
        self._casepackage_version = value

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
        return self._case_versions_list

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
        return self._private_registry_full_server

    # Setter for private registry server
    @private_registry_server.setter
    def private_registry_server(self, value):
        self._private_registry_full_server = value

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
        self._logger.info(f"Creating the airgap details file: {self._airgap_details_file}")
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
        try:
            self._logger.info(f"Collecting the case versions")
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
                print(Panel.fit(Text(f"Failed to download CASE Package index.yaml file"), style="bold yellow"))
                print()
                self._logger.info(f"Failed to download case package index.yaml file from {self._casepackage_url}")

            # Read the index.yaml file
            with open(filename, 'r') as file:
                case_versions = yaml.safe_load(file)

            # Return the case versions
            self._case_versions = case_versions
            case_versions_parsed = case_versions['versions'].keys()
            self._case_versions_list = case_versions_parsed
        except Exception as e:
            self._logger.info(f"Exception while trying to collect case versions - {e}")
            self._case_versions_list = []


    # Function to parse caseVersions
    def __parse_case_versions(self):
        self._logger.info(f"Parsing the case versions")
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

        self._case_versions_list = case_versions_dict
        return case_versions_dict

    # Function to select the casePackageVersion
    def validate_case_package_version(self, case_version=None):
        print(Panel.fit("CASE Package Version Selection"))
        self._logger.info(f"Selecting the case package versions")

        case_versions_list = self._case_versions_list

        if case_version:
            print()
            print(Panel.fit(Text(f"Selected CASE Package Version: {case_version}", style="bold cyan")))
            print()

        # If case_version is not in the case_versions_list, output warning
        if case_version and case_version not in case_versions_list:
            print()
            print(Panel.fit(Text(f"Warning: The selected CASE Package Version: {case_version} is not in the available versions list.\n"
                                 f"CASEPackage download will proceed without validation"), style="bold yellow"))
            print()

        self._logger.info(f"Selected case package version: {self._casepackage_version}")
        self._casepackage_version = case_version
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
        self._logger.info(f"Retrieving the component tags and repositories")
        try:
            with open(self._content_pattern_path, 'r') as file:
                content_template_yaml = yaml.safe_load(file)

        except Exception as e:
            print(f"Error occurred while reading YAML file {self._content_pattern_path}: {e}")
            self._logger.info(f"Error occurred while reading YAML file {self._content_pattern_path}: {e}")

        if content_template_yaml:
            keys_to_parse = ['repository', 'tag']
            parsed_keys = parse_yaml_for_keys(content_template_yaml, keys_to_parse)

            num_components = len(parsed_keys['repository'])

            for i in range(num_components):
                component_dict = {}

                # Calculate Component Name
                component_name = parsed_keys['repository'][i].split("/")[-1]
                component_dict['components'] = component_name

                # Calculate Tag or Digest
                if "sha256:" in parsed_keys['tag'][i]:
                    component_dict['digest'] = parsed_keys['tag'][i]
                else:
                    component_dict['tag'] = parsed_keys['tag'][i]

                # Calculate Repository
                repository = parsed_keys['repository'][i]
                component_dict['repository'] = repository.lower()

                # Add the component dictionary to the repo_tag_list
                self._repo_tag_list.append(component_dict.copy())

                # Check if the component is cpe or navigator for add the SSO image
                if component_name in ["cpe", "navigator"]:
                    self._logger.info(f"Getting {component_name} SSO repository and tag")
                    component_dict = {}
                    component_dict['components'] = f"{component_name}-sso"
                    if component_name == "cpe":
                        component_dict['repository'] = f"cp.icr.io/cp/cp4a/fncm/{component_name}-sso".lower()
                    else:
                        component_dict['repository'] = f"cp.icr.io/cp/cp4a/ban/{component_name}-sso".lower()
                    if "sha256:" in parsed_keys['tag'][i]:
                        component_dict['digest'] = parsed_keys['tag'][i]
                    else:
                        component_dict['tag'] = parsed_keys['tag'][i]
                    self._repo_tag_list.append(component_dict.copy())

            self._logger.info(self._repo_tag_list)

            # Modify repositories for dev environment
            # Loop through each component dictionary in the repo_tag_list
            # Replace the repository URL with the dev URL
            if self._dev:
                for component_dict in self._repo_tag_list:
                    component_dict["repository"] = component_dict["repository"].replace("cp.icr.io","cp.stg.icr.io")

            # # Add the component dictionary to the repo_tag_list
            # self._repo_tag_list.append(component_dict.copy())

    # Function to parse and retrieve operator image tag and repository
    def parse_operator_template(self):
        self._logger.info(f"Getting operator digest, tag and repository")
        try:
            with open(self._operator_path, 'r') as file:
                operator_template_yaml = yaml.safe_load(file)

        except Exception as e:
            print(f"Error occurred while reading YAML file {self._operator_path}: {e}")
            self._logger.info(f"Error occurred while reading YAML file {self._operator_path}: {e}")


        component_dict = {}

        if operator_template_yaml:
            # Check if operator image is using a tag vs digest
            image = operator_template_yaml["spec"]["template"]["spec"]["containers"][0].get("image", "")
            if "@" in image:
                # If using digest, split by '@' to get the repository and digest
                operator_repository, operator_digest = image.split("@")
                component_dict["digest"] = operator_digest
            else:
                # If using digest, split by ':' to get the repository and tag
                operator_repository, operator_tag = image.split(":")
                component_dict["tag"] = operator_tag
            if self._dev:
                operator_repository = operator_repository.replace("icr.io/cpopen", "cp.stg.icr.io/cp")

            # Add the repository to the component dictionary
            component_dict['repository'] = operator_repository.lower()
            # Add the component name
            component_dict["components"] = "ibm-fncm-operator"

            self._repo_tag_list.append(component_dict)



        # if operator_template_yaml:
        #     operator_repository, operator_tag = operator_template_yaml["spec"]["template"]["spec"]["containers"][0][
        #         "image"].split(":")
        #     if self._dev:
        #         operator_repository = operator_repository.replace("icr.io/cpopen", "cp.stg.icr.io/cp")
        #     self._repo_tag_dict["repository"].append(operator_repository)
        #     self._repo_tag_dict["tag"].append(operator_tag)
        #     self._repo_tag_dict["components"].append("ibm-fncm-operator")

    def create_image_details_file(self):

        self._logger.info(f"Creating file with image details")
        # Create the CNCF Image Details folder
        self.__create_cncf_image_details_folder()

        try:
            image_doc = document()
            image_doc.add(comment("##########################################################"))
            image_doc.add(comment("##  IBM FileNet Content Manager Component Image Details ##"))
            image_doc.add(comment("##########################################################"))

            seen_component_images = set()
            for component in self._repo_tag_list:
                component_name = component.get("components", '').upper()
                repository = component.get("repository", '')
                digest = component.get("digest")
                tag = component.get("tag", '')
                image_identity = (component_name, repository, digest if digest else tag)

                if image_identity in seen_component_images:
                    self._logger.warning(
                        f"Skipping duplicate image details entry for component={component_name}, "
                        f"repository={repository}, reference={digest if digest else tag}"
                    )
                    continue

                seen_component_images.add(image_identity)
                component_section = table()

                self.__write_property_table(section=component_section,
                                            key="REPOSITORY",
                                            value=repository,
                                            note='')

                if digest:
                    self.__write_property_table(section=component_section,
                                                key="DIGEST",
                                                value=digest,
                                                note='')
                else:
                    self.__write_property_table(section=component_section,
                                                key="TAG",
                                                value=tag,
                                                note='')

                image_doc.add(f"{component_name}", component_section)
                image_doc.add(nl())

            f = TOMLFile(self._image_details_file)
            f.write(image_doc)
            self._logger.info("Generating image details toml file completed successfully")


        except Exception as e:
            self._logger.exception(f"Exception while trying to create image details toml - {e}")

    # # Function to create the TOML file
    # def create_image_details_file(self):
    #
    #     # Create the CNCF Image Details folder
    #     self.__create_cncf_image_details_folder()
    #
    #     if (len(self._repo_tag_dict["repository"]) != len(self._repo_tag_dict["tag"])) or len(
    #             self._repo_tag_dict["repository"]) == 0:
    #         self._logger.exception(
    #             "Error with the content pattern template, matching pairs of repositories and tags not found")
    #         exit(0)
    #     try:
    #         image_doc = document()
    #         image_doc.add(comment("####################################################"))
    #         image_doc.add(comment("##           FNCM Component Image Details          ##"))
    #         image_doc.add(comment("####################################################"))
    #
    #         for i in range(len(self._repo_tag_dict["components"])):
    #             component_section = table()
    #             for key, value in self._image_details_template.items():
    #                 if key.lower() == "repository":
    #                     self.__write_property_table(section=component_section,
    #                                                 key=key,
    #                                                 value=self._repo_tag_dict["repository"][i],
    #                                                 note=value['comment'])
    #
    #                 else:
    #                     self.__write_property_table(section=component_section,
    #                                                 key=key,
    #                                                 value=self._repo_tag_dict["tag"][i],
    #                                                 note=value['comment'])
    #
    #             component_name = self._repo_tag_dict["components"][i].upper()
    #             image_doc.add(f"{component_name}", component_section)
    #             image_doc.add(nl())
    #
    #         f = TOMLFile(self._image_details_file)
    #         f.write(image_doc)
    #         self._logger.info("Generating image details toml file completed successfully")
    #
    #
    #     except Exception as e:
    #         self._logger.exception(f"Exception while trying to create image details toml - {e}")

    # Parsing toml file into a dictionary
    def parse_toml_file(self, image_details_dict=None):
        self._logger.info(f"Creating image details dictionary using toml file: {self._image_details_file}")
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
        self._logger.info(f"Generating mirror manifests")
        try:
            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]
            env_vars["HOME"] = os.environ["HOME"]

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
        self._logger.info(f"Getting the channels")
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

            self._logger.info(f"Updating the channels")
            env_vars = self._airgap_vars.copy()
            env_vars["HOME"] = os.environ["HOME"]

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
            self._logger.info(f"Channels updated successfully")

            return True
        except Exception as e:
            self._logger.info(f"Error occurred while updating YAML file {file_path}: {e}")
            return False

    # Function to select channel for mirror
    def select_channel(self, channels=None):
        try:
            print()
            print(Panel.fit("Airgap Mirror Channels"))
            self._logger.info(f"Getting the channels to be mirrored")

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
            self._logger.info(f"Starting the cluster setup")

            progress.log(f"Applying ImageContentSourcePolicy to the cluster")
            progress.log()
            self._logger.info(f"Applying the ICSP to the cluster")

            env_vars = self._airgap_vars.copy()
            env_vars["HOME"] = os.environ["HOME"]

            case_name = env_vars["CASE_NAME"]
            case_version = env_vars["CASE_VERSION"]
            pak_home = env_vars["IBMPAK_HOME"]

            image_mirror_policy_file = os.path.join(pak_home, '.ibm-pak', 'data', 'mirror', case_name, case_version, 'image-content-source-policy.yaml')

            self._kube.apply_cluster_resource_files(
                resource_file=image_mirror_policy_file,
                resource_type="image policy")

            progress.log(Text(f"ImageContentSourcePolicy applied to the cluster successfully!", style="bold green"))
            progress.log()
            self._logger.info(f"ICSP is applied successfully to the cluster")


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
            self._logger.info(f"Starting airgap mirroring")

            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]
            env_vars["HOME"] = os.environ["HOME"]

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
            status_code = process.wait()

            self._logger.info(f"Image Mirror process completed with error: {error_msg}")
            self._logger.info(f"Image Mirror process completed with status code: {status_code}")

            if status_code != 0:
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
            self._logger.info(f"Error: {e}")
            progress.update(task, total=1)
            progress.update(task, advance=1)
            return False

    # Function to select channel
    def collect_image_channels(self):
        self._logger.info(f"Collecting image channels")
        env_vars = self._airgap_vars.copy()
        env_vars["HOME"] = os.environ["HOME"]

        image_set_yaml = os.path.join(env_vars['IBMPAK_HOME'], '.ibm-pak', 'data', 'mirror', env_vars['CASE_NAME'],
                                      env_vars['CASE_VERSION'], 'image-set-config.yaml')

        channels = self.__parse_channel_files(image_set_yaml)

        selected_channels = self.select_channel(channels)

        # If there are differences between the selected channels and the channels in the image-set-config.yaml
        # Update the image-set-config.yaml
        if selected_channels != channels:
            self.update_image_channels(selected_channels)
            # Return true if the channels were updated
            return True

        return False

    # Function to enable oc image mirror
    def enable_oc_image(self, progress, task):
        self._logger.info(f"Enabling oc-mirror")
        try:
            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]
            env_vars["HOME"] = os.environ["HOME"]

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
        self._logger.info(f"Downloading case-package")
        try:

            env_vars = self._airgap_vars.copy()
            env_vars["PATH"] = os.environ["PATH"]
            env_vars["HOME"] = os.environ["HOME"]

            command1 = "oc ibm-pak config repo 'IBM Cloud-Pak OCI registry' -r oci:cp.icr.io/cpopen --enable"

            process1 = subprocess.run(command1, env=env_vars, shell=True, capture_output=True, text=True)

            if process1.returncode == 0:
                repo_enabled = True
            else:
                repo_enabled = False

            command2 = f"oc ibm-pak get {self._casename} --version {self._casepackage_version}"

            process2 = subprocess.run(command2, env=env_vars, shell=True, capture_output=True, text=True)

            if process2.returncode != 0:
                print()
                print(Panel.fit(Text("Case Download Failed\n"
                                     "Please check logs for additional information"), style="bold red"))
                self._logger.info(f"Error occurred while downloading case: {process2.stderr}")
                return False

        except Exception as e:
            print()
            print(Panel.fit(Text("Case Download Failed\n"
                                 "Please check logs for additional information"), style="bold red"))
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
        self._logger.info(f"Copying images to the private registry")
        images_not_copied = []
        images_copied = []
        for i in range(len(self._repo_tag_dict_from_file["repository"])):
            tag = self._repo_tag_dict_from_file["tag"][i]
            repository = self._repo_tag_dict_from_file["repository"][i]
            new_image_repo = repository.split("/")[-1]
            src_path = f"{repository}:{tag}"
            dest_path = f"{self._private_registry_full_server}/{new_image_repo}:{tag}"
            progress.log(Panel.fit(Text(f"Copying {new_image_repo}:{tag}", style="bold cyan")))
            progress.log()
            self._logger.info(f"Copying {new_image_repo}:{tag}")
            image_copied = copy_image(src_path, dest_path, progress)
            if not image_copied:
                images_not_copied.append(f"{new_image_repo}:{tag}")
            else:
                images_copied.append(f"{new_image_repo}:{tag}")

            progress.update(task, advance=1)

        self._image_push_summary["completed"] = images_copied
        self._image_push_summary["failed"] = images_not_copied
        self._image_push_summary["total"] = self._number_of_images
        self._image_push_summary["private_registry"] = self._private_registry_full_server

        return self._image_push_summary
