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

import os
from enum import Enum
from urllib.parse import urlparse

from rich import print
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.syntax import Syntax
from rich.text import Text

from ..utilities.interface import clear
from ..utilities.kubernetes_utilites import KubernetesUtilities
from ..utilities.prerequisites_utilites import check_pem_cert_format, \
    connect_to_server
from ..utilities.utilities import login_to_registry_podman


# create a class to gather all deployment options from the user for the cleanup deployment script
class GatherOptions:
    class OptionalComponents(Enum):
        cpe = 1
        graphql = 2
        ban = 3
        css = 4
        cmis = 5
        tm = 6
        es = 7
        ier = 8
        iccsap = 9
    # Create an enum for all platform types
    class Platform(Enum):
        OCP = 1
        other = 2

    class Version:
        FNCMVersion = Enum(
            value='FNCMVersion',
            names=[("5.5.9", 1), ("5.5.10", 2), ("5.5.11", 3), ("5.5.12", 4), ("5.6.0", 5), ("5.7.0", 6)]
        )

        def __init__(self, fncm_version: FNCMVersion):
            self._fncm_version = fncm_version

    # Script type options are cleanup,deploy,load_extract and upgrade
    def __init__(self, logger, console, script_type="cleanup", dev=False, tls_verify=True):
        self._script_type = script_type
        self._ocp_logged_in = False
        self._namespace = None
        self._podman_available = False
        self._skopeo_available = False
        self._sensitive_collect = False
        self._logger = logger
        self._console = console
        self._platform = self.Platform(1).name
        self._missing_tools = []
        self._fncm_version = "5.7.0"
        self._accept_license = False
        self._entitlement_key_valid = False
        self._entitlement_key = ''
        self._private_registry = False
        self._private_registry_valid = False
        self._private_registry_host = ''
        self._private_registry_port = 5000
        self._private_registry_username = ''
        self._private_registry_password = ''
        self._private_registry_ssl_enabled = False
        self._private_registry_ssl_cert = ''
        self._private_registry_full_server = ''
        self._private_registry_path = ''
        self._private_catalog = True
        self._all_channels = False
        self._components = set()
        self._current_namespace = None
        if dev:
            self._runtime_mode = "dev"
            self._registry = "cp.stg.icr.io"
        else:
            self._runtime_mode = "prod"
            self._registry = "cp.icr.io"
        self._silent_mode = False
        # Initialize Kubernetes client
        self._k = KubernetesUtilities(self._logger)
        self._tls_verify = tls_verify

    @property
    def fncm_version(self):
        return self._fncm_version

    @property
    def all_channels(self):
        return self._all_channels

    @property
    def accept_license(self):
        return self._accept_license

    @property
    def sensitive_collect(self):
        return self._sensitive_collect

    @property
    def components(self):
        return self._components

    @components.setter
    def components(self, value):
        self._components = set(value)

    @property
    def namespace(self):
        return self._namespace

    @property
    def podman_available(self):
        return self._podman_available

    @podman_available.setter
    def podman_available(self, value):
        self._podman_available = value

    @property
    def private_registry(self):
        return self._private_registry

    @private_registry.setter
    def private_registry(self, value):
        self._private_registry = value

    @property
    def private_registry_full_server(self):
        return self._private_registry_full_server

    @private_registry_full_server.setter
    def private_registry_full_server(self, value):
        self._private_registry_full_server = value

    @property
    def private_registry_server(self):
        return self._private_registry_full_server

    @property
    def platform(self):
        return self._platform

    @platform.setter
    def platform(self, value):
        self._platform = value

    @property
    def private_catalog(self):
        return self._private_catalog

    @property
    def private_registry_valid(self):
        return self._private_registry_valid

    @property
    def runtime_mode(self):
        return self._runtime_mode.lower()

    @property
    def silent_mode(self):
        return self._silent_mode

    @property
    def registry(self):
        return self._registry.lower()

    @property
    def entitlement_key_valid(self):
        return self._entitlement_key_valid

    @property
    def entitlement_key(self):
        return self._entitlement_key


    @property
    def private_registry_port(self):
        return self._private_registry_port

    @property
    def private_registry_username(self):
        return self._private_registry_username

    @property
    def private_registry_password(self):
        return self._private_registry_password

    # Create a function to gather platform from user
    def collect_platform(self):
        try:
            self._logger.info("Collecting Platform details")
            print()
            print(Panel.fit("Platform"))
            while True:
                print()
                print("Select a Platform Type")
                print("1. OCP")
                print("2. CNCF")
                print()
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]2[/b]]')

                if 1 <= result <= 2:
                    self._platform = self.Platform(result).name
                    self._logger.info(f"Platform selected: {self._platform}")
                    break

                print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]2[/b]]")
                self._logger.debug(f"Invalid prompt. Number must be between [1 and 2]")
        except Exception as e:
            self._logger.exception(
                f"Exception from utility script in collect_platform function -  {str(e)}")

    def __parse_optional_components__(self, choices=None):
        try:
            components = set()
            if choices is None:
                print("No optional components chosen")
            else:
                # loop through choices and add to optional components list based on Enum value
                for choice in choices:
                    components.add(self.OptionalComponents(choice).name)

            self._components =  list(components)

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in set_optional_components function -  {str(e)}")

        # Create a function to gather optional components from the user
    def collect_mustgather_components(self, component_list, version="5.7.0"):
        try:
            # Convert component list to enum values
            component_list = [self.OptionalComponents[component].value for component in component_list]
            choices = set(component_list)

            if version in ["5.6.0", "5.7.0"]:
                print()
                print(Panel.fit("Deployed Components"))
                print()

                print("In addition to the deployment artifacts, the FNCM MustGather can collect components specific logs and configuration files.\n"
                      "This includes the following components:\n\n"
                      "- Component Logs\n"
                      "- Component Version\n"
                      "- Java Version\n"
                      "- Liberty Version\n")

                num_components = 9

                while True:
                    print()
                    print("Select zero or more FileNet Content Management Components")
                    print("Enter a number to toggle selection")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CPE {":heavy_check_mark:" if 1 in choices else ""}')
                    print(f'2. GraphQL {":heavy_check_mark:" if 2 in choices else ""}')
                    print(f'3. Navigator {":heavy_check_mark:" if 3 in choices else ""}')
                    print(f'4. CSS {":heavy_check_mark:" if 4 in choices else ""}')
                    print(f'5. CMIS {":heavy_check_mark:" if 5 in choices else ""}')
                    print(f'6. Task Manager {":heavy_check_mark:" if 6 in choices else ""}')
                    print(f'7. External Share {":heavy_check_mark:" if 7 in choices else ""}')
                    print(f'8. IER {":heavy_check_mark:" if 8 in choices else ""}')
                    print(f'9. ICCSAP {":heavy_check_mark:" if 9 in choices else ""}')

                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]{}[/b]]'.format(num_components))

                    if result == 0:
                        break

                    if 1 <= result <= num_components:
                        # remove from set if already present
                        if result in choices:
                            choices.remove(result)
                        else:
                            choices.add(result)
                        clear(self._console)
                        print()
                        print(Panel.fit("Deployed Components"))
                        print()
                        print(
                            "In addition to the deployment artifacts, the FNCM MustGather can collect components specific logs and configuration files.\n"
                            "This includes the following components:\n\n"
                            "- Component Logs\n"
                            "- Component Version\n"
                            "- Java Version\n"
                            "- Liberty Version\n")
                    else:
                        print(f'\n[prompt.invalid]Number must be between [[b]1[/b] and [b]{num_components}[/b]]')
            else:
                print()
                print(Panel.fit("Deployed Components"))
                print()

                print("In addition to the deployment artifacts, the FNCM MustGather can collect components specific logs and configuration files.\n"
                      "This includes the following components:\n\n"
                      "- Component Logs\n"
                      "- Component Version\n"
                      "- Java Version\n"
                      "- Liberty Version\n")

                num_components = 7

                while True:
                    print()
                    print("Select zero or more FileNet Content Management Components")
                    print("Enter a number to toggle selection")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CPE {":heavy_check_mark:" if 1 in choices else ""}')
                    print(f'2. GraphQL {":heavy_check_mark:" if 2 in choices else ""}')
                    print(f'3. Navigator {":heavy_check_mark:" if 3 in choices else ""}')
                    print(f'4. CSS {":heavy_check_mark:" if 4 in choices else ""}')
                    print(f'5. CMIS {":heavy_check_mark:" if 5 in choices else ""}')
                    print(f'6. Task Manager {":heavy_check_mark:" if 6 in choices else ""}')
                    print(f'7. External Share {":heavy_check_mark:" if 7 in choices else ""}')

                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]{}[/b]]'.format(num_components))

                    if result == 0:
                        break

                    if 1 <= result <= num_components:
                        # remove from set if already present
                        if result in choices:
                            choices.remove(result)
                        else:
                            choices.add(result)
                        clear(self._console)
                        print(Panel.fit("Deployed Components"))
                        print()
                        print(
                            "In addition to the deployment artifacts, the FNCM MustGather can collect components specific logs and configuration files.\n"
                            "This includes the following components:\n\n"
                            "- Component Logs\n"
                            "- Component Version\n"
                            "- Java Version\n"
                            "- Liberty Version\n")
                    else:
                        print(f'\n[prompt.invalid]Number must be between [[b]1[/b] and [b]{num_components}[/b]]')

            self.__parse_optional_components__(choices)

        except Exception as e:
            # Create log for exception
            self._logger.exception(
                f"Exception from gather script in optional_components_menu function -  {str(e)}")

    def collect_sensitive_data(self, collect=None):
        try:
            if collect is None:
                print()
                print(Panel.fit("Collect Sensitive Data"))
                print()
                print("The FileNet Content Manager MustGather would like to collect sensitive configuration data to help diagnose and troubleshoot issues.\n"
                      "This includes configuration files, logs and secrets with unencrypted values.")
                print()

                self._sensitive_collect = Confirm.ask("Do you want to collect sensitive data?")
            else:
                self._sensitive_collect = collect
        except Exception as e:
            self._logger.exception(
                f"Exception from utility script in collect_sensitive_data function -  {str(e)}")


    def collect_namespace(self, namespace=None):
        # namespace parameter is none when silent mode is NOT selected, hence the conditions to skip conditions if silent mode is selected
        try:
            self._logger.info("Gathering namespace information")
            if namespace is None:
                print()
                print(Panel.fit("Namespace"))
                print()
                try:
                    self._current_namespace = self._k.current_namespace
                except Exception as e:
                    self._current_namespace = None


            if self._platform in ["OCP"]:
                invalid_namespaces = ["services", "default", "calico-system", "ibm-cert-store", "ibm-observe",
                                      "ibm-system", "ibm-odf-validation-webhook"]
                invalid_namespace_to_start_with = ["openshift-", "kube-"]
            else:
                invalid_namespaces = ["services", "default", "calico-system"]
                invalid_namespace_to_start_with = ["kube-"]

            while True:
                if namespace is None:
                    answer = Prompt.ask("Enter your namespace", default=self._current_namespace)
                    if self._script_type != "deploy":
                        namespace_exists = self._k.check_namespace_exists(namespace=answer)
                        if not namespace_exists:
                            print()
                            print(Panel.fit(f"Namespace '{answer}' does not exist.\n"
                                            f"Enter a valid namespace for script to proceed.", style="bold red"))
                            print()
                            continue
                else:
                    # silent install check for namespace will not loop more than once if invalid namespace is provided
                    if self._script_type != "deploy":
                        self._logger.info(f"Checking if namespace: {namespace} exists.")
                        namespace_exists = self._k.check_namespace_exists(namespace=namespace)
                        if not namespace_exists:
                            self._logger.info(f"Namespace '{namespace}' does not exist.")
                            print()
                            print(Panel.fit(f"Namespace '{namespace}' does not exist.\n"
                                            f"Enter a valid namespace for script to proceed.", style="bold red"))
                            print()
                            exit(1)
                    answer = namespace

                answer = answer.strip()
                # Start of namespace validation
                # Check if the answer is not empty after stripping whitespace
                if answer == '':
                    self._logger.debug(f"Namespace cannot be empty. Please try again")
                    print()
                    print("[prompt.invalid]Namespace cannot be empty. Please try again")
                    print()
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if the answer is not in the list of invalid namespaces
                if any(answer in value for value in invalid_namespaces):
                    invalid_msg = ""
                    for value in invalid_namespaces:
                        invalid_msg += f"- {value}\n"
                    invalid_msg.strip()

                    print()
                    print(f"[prompt.invalid]Namespace cannot be any of the following. Please try again.\n{invalid_msg}")
                    print()
                    self._logger.debug(f"Namespace cannot be any of the following: {invalid_msg}")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                if any(answer.startswith(value) for value in invalid_namespace_to_start_with):
                    invalid_msg = ""
                    for value in invalid_namespace_to_start_with:
                        invalid_msg += f"- {value}\n"
                    invalid_msg = invalid_msg.strip()
                    print()
                    print(
                        f"[prompt.invalid]Namespace cannot start with any of the following. Please try again.\n{invalid_msg}")
                    print()
                    self._logger.debug(f"Namespace cannot start with any of the following: {invalid_msg}")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if namespace is only numbers
                if answer.isnumeric():
                    print()
                    print("[prompt.invalid]Namespace cannot be a number. Please try again.")
                    print()
                    self._logger.debug(f"Namespace cannot be a number. Please try again.")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if the answer has any uppercase letters
                if any(char.isupper() for char in answer):
                    print()
                    print("[prompt.invalid]Namespace cannot contain uppercase letters. Please try again.")
                    print()
                    self._logger.debug(f"Namespace cannot contain uppercase letters. Please try again.")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if namespace is more than 1 word
                if " " in answer:
                    print()
                    print("[prompt.invalid]Namespace cannot contain spaces. Use '-'. Please try again.")
                    print()
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if namespace has an underscore
                if "_" in answer:
                    print()
                    print("[prompt.invalid]Namespace cannot contain '_'. Use '-'. Please try again.")
                    print()
                    self._logger.debug(f"Namespace cannot be a number. Please try again.")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # for all scripts using this function other than deploy operator we need to check if namespace exists
                self._namespace = answer
                self._logger.info(f"Namespace entered: {self._namespace}")
                break

        except Exception as e:
            self._logger.exception(
                f"Exception from gathering deployment details in collect namespace function -  {str(e)}")

    # Create a function to gather db_type from the user
    def collect_license_model(self, version_data, license_accept=None):
        try:
            self._logger.info("Gathering license model details")
            print(Panel.fit("License and Version"))
            print()

            version = version_data.get("VERSION", '5.7.0')
            self._fncm_version = version.split('-')[0]
            self._logger.info(f"IBM FileNet Content Manager Version detected: {self._fncm_version}")

            print(Panel.fit(Text(f"Detected IBM FileNet Content Manager Version: {version}"), style="bold cyan"))
            print()

            if self._fncm_version == "5.5.8":
                fncm_license_url = Text("https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KPMK",
                                        style="link https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KPMK")
                icf_license_url = Text("https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KQ34",
                                       style="link https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KQ34")

                print(Panel.fit(
                    f"IMPORTANT: Review the license  information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}"))

            elif self._fncm_version == "5.5.11":
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_5_11",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_5_11")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_5_11",
                                       style="link https://ibm.biz/CPE_ICF_License_5_5_11")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_11",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_11")

                print(Panel.fit(
                    f"IMPORTANT: Review the license information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}"))

            elif self._fncm_version == "5.5.12":
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_5_12",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_5_12")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_5_12",
                                       style="link https://ibm.biz/CPE_ICF_License_5_5_12")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_12",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_12")
                cp4ba_license_url = Text("https://ibm.biz/cp4ba_license_2302",
                                       style="link https://ibm.biz/cp4ba_license_2302")

                print(Panel.fit(
                    f"IMPORTANT: Review the license  information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}\n"
                    f"IBM Cloud Pak for Business Automation license information here: {cp4ba_license_url}"))

            elif self._fncm_version == "5.6.0":
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_6_0",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_6_0")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_6_0",
                                       style="link https://ibm.biz/CPE_ICF_License_5_6_0")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_6_0",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_6_0")
                ier_license_url = Text("https://ibm.biz/ier_license_521",
                                       style="link https://ibm.biz/ier_license_521")
                iccsap_license_url = Text("https://ibm.biz/iccsap_license_4002",
                                       style="link https://ibm.biz/iccsap_license_4002")
                cp4ba_license_url = Text("https://ibm.biz/cp4ba_license_2400",
                                       style="link https://ibm.biz/cp4ba_license_2400")

                print(Panel.fit(
                    f"IMPORTANT: Review the license information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}\n"
                    f"IBM Enterprise Records information here: {ier_license_url}\n"
                    f"IBM Content Collector for SAP license information here: {iccsap_license_url}\n"
                    f"IBM Cloud Pak for Business Automation license information here: {cp4ba_license_url}"))
            else:
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_7_0",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_7_0")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_7_0",
                                       style="link https://ibm.biz/CPE_ICF_License_5_7_0")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_7_0",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_7_0")
                ier_license_url = Text("https://ibm.biz/ier_license_521",
                                       style="link https://ibm.biz/ier_license_521")
                iccsap_license_url = Text("https://ibm.biz/iccsap_license_4002",
                                       style="link https://ibm.biz/iccsap_license_4002")
                cp4ba_license_url = Text("https://ibm.biz/cp4ba_license_2500",
                                       style="link https://ibm.biz/cp4ba_license_2500")

                print(Panel.fit(
                    f"IMPORTANT: Review the license information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}\n"
                    f"IBM Enterprise Records information here: {ier_license_url}\n"
                    f"IBM Content Collector for SAP license information here: {iccsap_license_url}\n"
                    f"IBM Cloud Pak for Business Automation license information here: {cp4ba_license_url}"))

            print()

            if license_accept is None:
                self._accept_license = Confirm.ask("Do you accept the International Program License?")
            else:
                self._accept_license = license_accept

            if not self._accept_license:
                self._logger.debug("International Program License is not accepted. You must accept the International Program License to continue.")
                print("\n[prompt.invalid]You must accept the International Program License to continue.")
                exit(1)

            self._logger.info("International Program License is accepted.")

        except Exception as e:
            self._logger.exception(
                f"Exception from gather Class in license model function -  {str(e)}")

    # Function to collect and validate the entitlement key
    def collect_verify_entitlement_key(self):
        try:
            self._logger.info("Collecting and validating the IBM Entitlement Registry key")
            print()
            print(Panel.fit("Validate Entitlement Key"))
            print()
            if not self._silent_mode:
                entitlement_key_kc = Text(
                    "https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.dba.install/op_topics/tsk_images_enterp_entitled.html",
                    style="link https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.dba.install/op_topics/tsk_images_enterp_entitled.html")
                print(
                    f"To get access to the container images from the IBM Entitled Registry, you must have a key to pull the images from the IBM registry.\n"
                    f"For more information, see {entitlement_key_kc}.\n")
                self._entitlement_key_present = Confirm.ask("Do you have an IBM Entitlement Registry key?",
                                                            default=True)

                # For the loadimages script the entitlement key is mandatory
                if self._script_type.lower() == "load_extract" and not self._entitlement_key_present:
                    print()
                    print(
                        "[prompt.invalid]An IBM Entitlement Key is required to pull images.\n"
                        "Configure an IBM Entitlement Key and re-run the script")
                    exit()
            # For silent mode we have the entitlement key present so we can set this variable to true
            else:
                self._entitlement_key_present = True
            if not self._entitlement_key_present:
                if not self._silent_mode:
                    self.collect_verify_private_registry()
            else:
                while True:
                    # No need to ask for an entitlement key if silent install is enabled

                    if not self._silent_mode:
                        print()
                        answer  = Prompt.ask("Enter your IBM Entitlement Registry key", password=True)
                        if ':' in answer:
                            username = answer.split(':')[0]
                            password = answer.split(':')[1]
                            self._entitlement_key = password
                        else:
                            username = "cp"
                            self._entitlement_key = answer
                    else:
                        username = "cp"

                    if not self._entitlement_key:
                        print()
                        print("[prompt.invalid]IBM Entitlement Registry key cannot be empty. Please try again.")
                        self._logger.debug(f"IBM Entitlement Registry key cannot be empty. Please try again.")
                        continue
                    else:
                        self._logger.info("Collected IBM Entitlement Registry key.")
                        self._entitlement_key_valid = login_to_registry_podman(registry_host=self._registry,
                                                                               username=username,
                                                                               password=self._entitlement_key,
                                                                               logger=self._logger,
                                                                               tls_verify=False)

                    if not self._entitlement_key_valid:
                        print()
                        self._logger.debug(f"IBM Entitlement key could not be validated.")
                        print("[prompt.invalid]IBM Entitlement key could not be validated. Please try again.")
                        if not self._silent_mode:
                            continue
                        else:
                            exit()

                    break

                self._logger.info("Successfully authenticated with IBM Entitled Registry")
                msg_panel = Panel.fit("Successfully authenticated with IBM Entitled Registry", style="bold green")
                print()
                print(msg_panel)

        except Exception as e:
            self._logger.exception(
                f"Exception from gather Class in entitlement key function -  {str(e)}")

    # Function to collect and validate private registry details
    # This function is used for script type load_extract and deploy_operator

    def verify_private_registry(self):
        if not self._silent_mode:
            while True:
                while True:
                    print()
                    self._private_registry_username = Prompt.ask("Enter the private registry username")
                    if self._private_registry_username == "":
                        print()
                        print("[prompt.invalid]Private registry Username can't be empty. Please try again.")
                        self._logger.debug(f"Private registry username cannot be empty. Please try again.")
                    else:
                        break

                while True:
                    print()
                    self._private_registry_password = Prompt.ask(
                        "Enter the private registry password", password=True)
                    if self._private_registry_password == "":
                        print()
                        print("[prompt.invalid]Private registry password can't be empty. Please try again.")
                        self._logger.debug(f"Private registry password cannot be empty. Please try again.")
                    else:
                        break

                # podman needs the cert path directory for authentication
                if self._private_registry_ssl_enabled:
                    ssl_folder = os.path.dirname(self._private_registry_ssl_cert)
                else:
                    ssl_folder = ""
                self._private_registry_valid = login_to_registry_podman(registry_host=self._private_registry_host,
                                                                        registry_port=self._private_registry_port,
                                                                        registry_path=self._private_registry_path,
                                                                        username=self._private_registry_username,
                                                                        password=self._private_registry_password,
                                                                        logger=self._logger,
                                                                        ssl_enabled=self._private_registry_ssl_enabled,
                                                                        ssl_cert_path=ssl_folder,
                                                                        tls_verify=self._tls_verify)

                if not self._private_registry_valid:
                    print()
                    print("[prompt.invalid]Private registry credentials could not be authenticated. Please try again")
                    self._logger.debug(f"Private registry credentials could not be authenticated. Please try again.")
                    if not self._silent_mode:
                        continue
                    else:
                        exit()

                msg = "Successfully Authenticated with Private Registry"
                self._private_registry = True
                if self._private_registry_ssl_enabled:
                    msg = f"{msg} over SSL"
                self._logger.info(f"{msg}")
                msg_panel = Panel.fit(msg, style="bold green")
                print()
                print(msg_panel)

                break

        else:
            # podman needs the cert path directory for authentication
            if self._private_registry_ssl_enabled:
                ssl_folder = os.path.dirname(self._private_registry_ssl_cert)
            else:
                ssl_folder = ""
            self._private_registry_valid = login_to_registry_podman(registry_host=self._private_registry_host,
                                                                    registry_port=self._private_registry_port,
                                                                    registry_path=self._private_registry_path,
                                                                    username=self._private_registry_username,
                                                                    password=self._private_registry_password,
                                                                    logger=self._logger,
                                                                    ssl_enabled=self._private_registry_ssl_enabled,
                                                                    ssl_cert_path=ssl_folder,
                                                                    tls_verify=self._tls_verify)

            if not self._private_registry_valid:
                print()
                print("[prompt.invalid]Private registry credentials could not be authenticated. Please try again")
                self._logger.debug(f"Private registry credentials could not be authenticated. Please try again.")
                exit(1)

            msg = "Successfully authenticated with Private Registry"
            self._private_registry = True
            if self._private_registry_ssl_enabled:
                msg = f"{msg} over SSL"
            self._logger.info(f"{msg}")
            msg_panel = Panel.fit(msg, style="bold green")
            print()
            print(msg_panel)

    def collect_verify_private_registry(self):
        try:
            self._logger.info("Collecting and validating the Private registry")
            print()
            print(Panel.fit("Validate Private Registry"))
            # Menu based logic required only for silent mode
            if not self._silent_mode:
                while True:
                    # Different menu questions for the script type
                    if self._script_type == "load_extract":
                        print()
                        print(
                            "A private image registry must be used to store all images used in an offline (Airgap) deployment.")
                        print()
                        self._private_registry_ready = Confirm.ask(
                            "Do you have access to a private registry where you can store images?", default=True)
                        if not self._private_registry_ready:
                            print()
                            print(
                                "[prompt.invalid]A Private Registry is required to store images.\n"
                                "Configure a Private Registry and re-run the script")
                            exit(1)
                    elif self._script_type == "deploy":
                        if self._platform.lower() == "other":
                            private_registry_kc = Text(
                                "https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.dba.install/filenet_containers_install_topics/containers_airgap.html",
                                style="link https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.dba.install/filenet_containers_install_topics/containers_airgap.html")
                            print()
                            print(f"A private image registry must be used to store all images in your local environment.\n"
                                f"Please ensure that all required images are pushed to the private registry before proceeding.\n\n"
                                f"For more information, see {private_registry_kc}.")
                            print()
                            self._private_registry_ready = Confirm.ask(
                                "Have you pushed all required images to a private registry?", default=True)
                            if not self._private_registry_ready:
                                print()
                                print("[prompt.invalid]Use loadimages.py to push operator images to a private registry and re-run the script")
                                print(Panel.fit(Syntax("python3 loadimages.py", "python")))
                                exit(1)
                        else:
                            private_registry_kc = Text(
                                "https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.dba.install/op_topics/tsk_airgap_parent.html",
                                style="link https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.dba.install/op_topics/tsk_airgap_parent.html")
                            print()
                            print(f"A private image registry must be used to store all images in your local environment.\n"
                                f"Please ensure that all required images are mirrored to the private registry before proceeding.\n\n"
                                f"For more information, see {private_registry_kc}.")
                            print()
                            self._private_registry_ready = Confirm.ask(
                                "Have you mirrored all required images to a private registry?", default=True)
                            if not self._private_registry_ready:
                                print()
                                print("[prompt.invalid]Use loadimages.py in airgap mode to mirror operator images to a private registry and re-run the script")
                                print(Panel.fit(Syntax("python3 loadimages.py --airgap", "python")))
                                exit(1)

                    print()
                    print(Text("Tip: To disable the SSL verification set the --no-tls-verify flag", style="cyan"))
                    print()

                    while True:
                        print()
                        private_reg_hostname_full = Prompt.ask(
                            "Enter the private registry URL")
                        if private_reg_hostname_full == "":
                            print()
                            print("[prompt.invalid]Private registry hostname can't be empty. Please try again.")
                            continue

                        # Split hostname into scheme, server, context and port using urlparse
                        # Following the syntax specifications in RFC 1808, urlparse recognizes a netloc only if it is properly introduced by ‘//’.
                        if "://" not in private_reg_hostname_full:
                            private_reg_hostname_full_shema = "//" + private_reg_hostname_full
                        else:
                            private_reg_hostname_full_shema = private_reg_hostname_full

                        private_reg_parts = urlparse(url=private_reg_hostname_full_shema, scheme="https")
                        self._logger.info(f"Private registry URL parts: {private_reg_parts}")
                        if not private_reg_parts.hostname:
                            print()
                            print("[prompt.invalid]Private registry URL must include a hostname. Please try again.")
                            continue

                        self._private_registry_host = private_reg_parts.hostname

                        # If no port is provided, default to 443 for https and 80 for http
                        # Use 443 if no schema is provided
                        private_reg_scheme = private_reg_parts.scheme
                        if private_reg_parts.port is None:
                            if private_reg_parts.scheme == "http":
                                self._private_registry_port = 80
                            else:
                                self._private_registry_port = 443
                        else:
                            self._private_registry_port = private_reg_parts.port

                        # Ask if SSL is to be used for private registry
                        if private_reg_scheme == "https":
                            self._private_registry_ssl_enabled = True
                        else:
                            # Query user if they want to use SSL
                            print()
                            self._private_registry_ssl_enabled = Confirm.ask(
                                "Do you want to use SSL to connect to the private registry?", default=False)

                        self._private_registry_full_server = f"{private_reg_hostname_full}"
                        if private_reg_parts.path != "":
                            self._private_registry_path = private_reg_parts.path.lstrip('/')

                        print()
                        # Ask if SSL is to be used for private registry
                        # If tls_verify is False we wont ask for the SSL certificate
                        if self._private_registry_ssl_enabled:
                            if not self._tls_verify:
                                print()
                                print(Text("TLS verification is disabled. Podman login will attempt without supplying an SSL certificate", style="yellow"))
                                print()
                            else:
                                self.collect_private_registry_ssl_details()

                        # Test for SSL connections
                        # Return a connection object, RTT and a boolean indicating if the connection was successful
                        if self._private_registry_ssl_enabled and self._tls_verify:
                            conn_result, rtt, connected = connect_to_server(self._private_registry_host, int(self._private_registry_port),
                                                                            True, self._private_registry_ssl_cert, logger=self._logger)
                        else:
                            conn_result, rtt, connected = connect_to_server(self._private_registry_host, int(self._private_registry_port), logger=self._logger)

                        if not connected:
                            print()
                            print(
                                f"[prompt.invalid]Private registry could not be reached. Please check the hostname and port and try again.")
                            continue

                        msg = "Successfully Validated Private Registry Server Reachability"
                        if self._private_registry_ssl_enabled:
                            msg = f"{msg} over SSL"
                        msg_panel = Panel.fit(msg, style="bold green")
                        print()
                        print(msg_panel)
                        break

                    self.verify_private_registry()
                    break
            else:
                if self._private_registry_ssl_enabled:
                    self._logger.info(f"TLS verification is set to {self._tls_verify} for private registry SSL connection")
                    if not self._tls_verify:
                        print()
                        print(Text("TLS verification is disabled. Podman login will attempt without supplying an SSL certificate", style="yellow"))
                        print()
                    else:
                        self.collect_private_registry_ssl_details()

                # Test for SSL connections
                # Return a connection object, RTT and a boolean indicating if the connection was successful
                if self._private_registry_ssl_enabled and self._tls_verify:
                    conn_result, rtt, connected = connect_to_server(self._private_registry_host,
                                                                    int(self._private_registry_port), True,
                                                                    self._private_registry_ssl_cert, logger=self._logger)
                else:
                    conn_result, rtt, connected = connect_to_server(self._private_registry_host,
                                                                    int(self._private_registry_port), logger=self._logger)

                if not connected:
                    print()
                    print(
                        f"[prompt.invalid]Private registry could not be reached. Please check the hostname and port and try again.")
                    exit(1)

                msg = "Successfully Validated Private Registry Server Reachability"
                if self._private_registry_ssl_enabled:
                    msg = f"{msg} over SSL"
                msg_panel = Panel.fit(msg, style="bold green")
                print()
                print(msg_panel)

                self.verify_private_registry()

        except Exception as e:
            self._logger.exception(
                f"Exception from gather Class in private registry function -  {str(e)}")

    def collect_private_registry_ssl_details(self):
        self._logger.info("Collecting private registry SSL details")
        if not self._silent_mode:
            while True:
                # Menu based logic not required for silent mode
                if not self._silent_mode:
                    print()
                    self._private_registry_ssl_cert = Prompt.ask(
                        "Enter the file path to the private registry SSL certificate")

                if self._private_registry_ssl_cert == "":
                    print()
                    print(
                        "[prompt.invalid]Private registry SSL certificate file path can't be empty. Please try again.")
                    self._logger.debug("Private registry SSL certificate file path can't be empty. Please try again.")
                    continue

                if not os.path.exists(self._private_registry_ssl_cert):
                    print()
                    print("[prompt.invalid]Private Registry SSL certificate can't be found. Please try again.")
                    self._logger.debug("Private registry SSL certificate can't be found. Please try again.")
                    continue

                if not check_pem_cert_format(self._private_registry_ssl_cert):
                    print()
                    print("[prompt.invalid]Private registry SSL certificate is not in PEM format. Please try again.")
                    self._logger.debug("Private registry SSL certificate is not in PEM format. Please try again.")
                    continue

                break
        else:
            if not os.path.exists(self._private_registry_ssl_cert):
                print()
                print("[prompt.invalid]Private Registry SSL certificate can't be found. Please try again.")
                self._logger.debug("Private Registry SSL certificate can't be found. Please try again.")
                exit(1)

            if not check_pem_cert_format(self._private_registry_ssl_cert):
                print()
                print("[prompt.invalid]Private registry SSL certificate is not in PEM format. Please try again.")
                self._logger.debug("Private registry SSL certificate is not in PEM format. Please try again.")
                exit(1)

    # Function to check if private catalog is being used
    def collect_private_catalog(self):
        self._logger.info("Collecting catalog information")
        if self._platform != "other":
            print()
            print(Panel.fit("Private Catalog"))
            print()
            print("The FileNet Content Manager Operator Catalog Source can be installed with the follow options:\n"
                  "1. Private Catalog - Install the catalog in the same target namespace\n"
                  "2. Global Catalog - Install the catalog in the openshift-marketplace namespace")
            print()
            print("A private catalog can only be used by operator instances in the same namespace.\n"
                  "A global catalog can be used by operator instances in any namespace.")
            print()
            print("Note: Private catalog is the default and recommended option.")
            self._private_catalog = not (Confirm.ask(
                "Do you want to deploy FileNet Content Manager Operator using a global catalog?", default=False))
            
            if self._private_catalog:
                self._logger.info("Selected Private catalogue")
            else:
                self._logger.info("Selected global catalogue")

    # Display preupgrade steps to be done
    # TBD for Jason to add more content to display
    def display_preupgrade_steps(self):
        print(Panel.fit("Pre Upgrade Checklist"))
        print()
        upgrade_link = Text(
            "https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.p8.containers.doc/containers_upgrading_licenseV559.htm",
            style="link https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.p8.containers.doc/containers_upgrading_licenseV559.htm")
        while True:
            print(
                f"Please see FileNet Content Manager Documentation for important upgrade prerequisites: {upgrade_link}")
            self._preupgrade_steps = Confirm.ask(
                "Have you completed FileNet Content Manager Operator upgrade prerequisites")
            if not self._preupgrade_steps:
                print("Please complete upgrade prerequisites before continuing")
                exit(1)
            else:
                break

    # Create a function to print all the deployment options
    def print_deployment_options(self):
        self._logger.info("namespace-", self._namespace)
        self._logger.info("platform-", self._platform)
        self._logger.info("podman present-", self._podman_available)
        self._logger.info("oc logged in", self._ocp_logged_in)
        return_dict = {}
        if self._script_type.lower() == "cleanup":
            return_dict = {
                "namespace": self._namespace,
                "platform": self._platform,
                "podman present": self._podman_available,
                "Cluster connection": self._ocp_logged_in
            }
        print(return_dict)
