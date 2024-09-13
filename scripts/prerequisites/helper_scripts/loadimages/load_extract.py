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
from datetime import datetime

import toml
import yaml
from rich import print
from rich.panel import Panel
from rich.text import Text
from tomlkit import comment
from tomlkit import document
from tomlkit import nl
from tomlkit import table
from tomlkit.toml_file import TOMLFile

from ..utilities import kubernetes_utilites as k
from ..utilities.prerequisites_utilites import zip_folder, read_json
from ..utilities.utilities import parse_yaml_for_keys, copy_image


# CLass that contains functions to delete the CR as well delete the Operator
class LoadExtract:

    def __init__(self, console, logger=None, silent=False, dev=False, folder_path="", script_mode="generate"):
        self._logger = logger
        self._kubernetes_utilities = k.KubernetesUtilities(logger)
        self._console = console
        self._dev = dev
        self._silent_mode = silent

        self._image_details_folder = folder_path

        if script_mode == "generate":
            # creating folder structure for generate folder
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
        self._repo_tag_dict = {}
        self._repo_tag_dict_from_file = {}

        self._image_push_summary = {}
        self._number_of_images = 0


    @property
    def number_of_images(self):
        return self._number_of_images

    @property
    def image_push_summary(self):
        return self._image_push_summary

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
        if (len(self._repo_tag_dict["repository"]) != len(self._repo_tag_dict["tag"])) or len(
                self._repo_tag_dict["repository"]) == 0:
            self._logger.exception("Error with the content pattern template, matching pairs of repositories and tags not found")
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
