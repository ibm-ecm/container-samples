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
import platform
import re
import shutil
import subprocess

import requests
import toml
from requests import ConnectTimeout
from rich import print
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from toml.decoder import TomlDecodeError

from .prerequisites_utilites import command_available, check_java_version, \
    get_skopeo_version, filepath_validate, get_ibm_pak_version, get_oc_version, get_mirror_version
from ..property.read_prop import ReadPropImageTag
from ..utilities import kubernetes_utilites as k


# Function to log in to a registry using podman
def login_to_registry_podman(registry, username, password, logger, ssl_enabled=False, ssl_cert_path=''):
    try:
        if ssl_enabled:
            # Allow self-signed certificates
            command = ["podman", "login", registry, "-u", username, "--password-stdin", "--cert-dir", ssl_cert_path,
                       "--tls-verify=false"]
        else:
            command = ["podman", "login", registry, "-u", username, "--password-stdin", "--tls-verify=false"]

        # Using subprocess to run the Podman login command
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate(input=password.encode())

        if process.returncode == 0:
            logger.info("Login succeeded!")
            return True
        else:
            logger.info(f"Login failed. Error: {error.decode()}")
            return False
    except Exception as e:
        logger.info(f"Error: {e}")
        return False


# Function to check oc plugins
def check_oc_plugins(logger, plugin):
    try:
        logger.info("OpenShift CLI available")
        env_vars = {
            'PATH': os.environ["PATH"],
            'HOME': os.environ["HOME"]
        }

        command = f"oc {plugin} --help"
        oc_plugins = subprocess.run(command, env=env_vars, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Get Error code from the command
        if oc_plugins.returncode == 0:
            logger.info(f"{plugin} plugin available")
            return True

        logger.info(f"{plugin} plugin not available")
        return False
    except Exception as e:
        logger.info(f"Error: {e}")
        return


# Function to do the prerequisite checks before the script starts
def prereq_checks(logger, prereqs=None, files=None, fncm_version='5.7.0'):
    logger.info(f"Checking prerequisites ...")
    if prereqs is None:
        prereqs = []

    if files is None:
        files = []
    try:
        missing_tools = []
        missing_files = []

        prereq_summary = {
            "podman": False,
            "java": False,
            "java_version": "",
            "k8s_version": "",
            "connection": False,
            "skopeo": False,
            "skopeo_version": "",
            "oc": False,
            "oc_version": "",
            "mirror": False,
            "mirror_version": "",
            "ibm-pak": False,
            "ibm-pak_version": ""
        }

        platform_type = platform.system()

        if len(files) > 0:
            descriptor_present = []
            prereq_summary["descriptor_files"] = True
            for descriptor in files:
                present = filepath_validate(filepath=descriptor)
                if not present:
                    # Get only the file name
                    descriptor = os.path.basename(descriptor)
                    missing_files.append(descriptor)
                descriptor_present.append(present)
            if not all(descriptor_present):
                logger.info(f"Prerequisites failed -> Descriptor files not present - {missing_files}")
                prereq_summary["descriptor_files"] = False

        if any(x in prereqs for x in ["podman"]):
            logger.info(f"Checking if the 'podman' is available.")
            podman = command_available("podman")

            if podman:

                logger.info("Podman available")
                logger.info("Using Podman Daemon")
                prereq_summary["podman"] = True
            else:
                logger.info("Podman Daemon not present")
                missing_tools.append("Podman CLI")

        if "oc" in prereqs:
            logger.info(f"Checking if the 'oc' command is available.")
            oc = command_available("oc")
            if not oc:
                logger.info("Prerequisites failed -> OpenShift CLI not installed")
                missing_tools.append("OpenShift CLI")
            else:
                logger.info("OpenShift CLI available")
                prereq_summary["oc"] = True
                prereq_summary["oc_version"] = get_oc_version(logger)

                if "mirror" in prereqs:
                    if platform_type.lower() == "windows":
                        missing_tools.append("Windows OS")
                        logger.info("Prerequisites failed -> Windows Machine not supported")

                    elif platform_type.lower() == "darwin":
                        missing_tools.append("Mac OS")
                        logger.info("Prerequisites failed -> Mac OS not supported")

                    else:
                        mirror = check_oc_plugins(logger, "mirror")
                        if not mirror:
                            logger.info("Prerequisites failed -> oc mirror plugin not installed")
                            missing_tools.append("mirror plugin")
                        else:
                            logger.info("oc mirror plugin available")
                            prereq_summary["mirror"] = True
                            prereq_summary["mirror_version"] = get_mirror_version(logger)
                            logger.info(f"Mirror Version: {prereq_summary['mirror_version']}")

                if "ibm-pak" in prereqs:
                    logger.info(f"Checking if the 'ibm-pak' plugin is available.")
                    ibm_pak = check_oc_plugins(logger, "ibm-pak")
                    if not ibm_pak:
                        logger.info("Prerequisites failed -> oc ibm-pak plugin not installed")
                        missing_tools.append("ibm-pak plugin")
                    else:
                        logger.info("oc ibm-pak plugin available")
                        prereq_summary["ibm-pak"] = True
                        prereq_summary["ibm-pak_version"] = get_ibm_pak_version(logger)
                        logger.info(f"IBM PAK Version: {prereq_summary['ibm-pak_version']}")

        if "powershell" in prereqs:
            logger.info(f"Checking if 'PowerShell' is available.")
            powershell_present = command_available("powershell.exe")

            if not powershell_present:
                logger.info("Prerequisites failed -> PowerShell not installed")
                missing_tools.append("PowerShell")
            else:
                logger.info("PowerShell available")
                prereq_summary["powershell"] = True

        if "keytool" in prereqs:
            logger.info(f"Checking if 'keytool' is available.")
            keytool_present = command_available("keytool")

            if not keytool_present:
                logger.info("Prerequisites failed -> keytool not installed")
                missing_tools.append("keytool")
            else:
                logger.info("keytool available")
                prereq_summary["keytool"] = True

        # Java Check
        if "java" in prereqs:

            logger.info(f"Checking if 'Java' is available.")
            java_present = command_available("java")

            if not java_present:
                logger.info("Prerequisites failed -> Java not installed")
                missing_tools.append("Java")
            else:
                logger.info("Java available")
                prereq_summary["java"] = True
                logger.info("Checking Java version")
                java_version = check_java_version(fncm_version)

                # Collect the Java version even if it is incorrect

                if not java_version:
                    logger.info("Prerequisites failed -> Java version not found")
                    missing_tools.append("Java")
                else:
                    logger.info(f"Java version found: {java_version}")
                    prereq_summary["java_version"] = java_version

                if fncm_version == "5.5.8":
                    prereq_summary["expected_java_version"] = "8"
                if fncm_version == "5.5.11":
                    prereq_summary["expected_java_version"] = "11"
                if fncm_version in ("5.5.12", "5.6.0"):
                    prereq_summary["expected_java_version"] = "17"
                if fncm_version == "5.7.0":
                    prereq_summary["expected_java_version"] = "21"
                else:
                    prereq_summary["expected_java_version"] = "21"

                logger.info("Expected Java version: " + prereq_summary["expected_java_version"])

        # check if cluster is logged in
        if "connection" in prereqs:
            try:
                kube = k.KubernetesUtilities(logger)
                logger.info("Checking if user is logged into the OCP console")
                server_version, ocp_logged_in = kube.get_kubernetes_version()

                if not ocp_logged_in:
                    logger.info("Prerequisites failed -> User is not logged into the OCP console")
                    missing_tools.append("connection")
                else:
                    logger.info("User is logged into the OCP console")
                    prereq_summary["connection"] = True
                    prereq_summary["k8s_version"] = server_version

            except (ConnectTimeout, ConnectionError) as e:
                logger.info(f"Could not connect to kubernetes cluster: {e}")
                missing_tools.append("connection")
            except Exception as e:
                logger.info("Prerequisites failed -> User is not logged into the OCP console")
                missing_tools.append("connection")

        if "skopeo" in prereqs:
            logger.info("Checking if skopeo is available")
            if platform_type == "windows":
                missing_tools.append("Windows OS")
                logger.info("Prerequisites failed -> Windows Machine not supported")
            else:
                skopeo_available = command_available("skopeo")
                if not skopeo_available:
                    logger.info("Prerequisites failed -> Skopeo not installed")
                    missing_tools.append("Skopeo CLI")
                else:
                    logger.info("Skopeo CLI available")
                    prereq_summary["skopeo"] = True
                    prereq_summary["skopeo_version"] = get_skopeo_version(logger)

        return missing_tools, prereq_summary, missing_files

    except Exception as e:
        logger.info(
            f"Exception from prerequisites check function -  {str(e)}")


# Function to read a version toml file
def read_version_toml(file_path, logger):
    try:
        logger.info(f"Reading version data from from file: {file_path}")
        version_data = toml.loads(open(file_path, encoding="utf-8").read())
        logger.info(f"Version data read: {version_data}")
        return version_data
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except TomlDecodeError as e:
        logger.error(f"Error reading the toml file: {e}")
        return None
    except Exception as e:
        logger.info(f"Error: {e}")
        return None


# Function to replace namespace variable in different yaml files used
# could be repurposed for other text replacement in the future
def replace_namespace_in_file(project_name, input_file, output_file, resource_type="", private=False):
    # Read the content of the input file
    with open(input_file, 'r') as f:
        content = f.read()

    if resource_type.lower() == "cluster role binding":
        # Replace occurrences of '<NAMESPACE>' with the project_name
        replaced_content = content.replace('<NAMESPACE>', project_name)
    elif resource_type.lower() == "catalog source":
        replaced_content = re.sub(r"namespace: .*", f"namespace: {project_name}", content)
    elif resource_type.lower() == "operator group" or resource_type.lower() == "subscription":
        # Replace occurrences of '<NAMESPACE>' with the project_name
        replaced_content = content.replace('REPLACE_NAMESPACE', project_name)

        replaced_content = re.sub(r'name: .*', f"name: ibm-fncm-operator", replaced_content)
        if private:
            replaced_content = re.sub(r"sourceNamespace: .*", f"sourceNamespace: {project_name}", replaced_content)
    # Write the modified content to the output file
    with open(output_file, 'w') as f:
        f.write(replaced_content)


# Function to recursively search for key value pairs in a yaml
def extract_values(data, key):
    """
    Recursively extract values for a given key from a nested dictionary.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key:
                yield v
            elif isinstance(v, dict):
                yield from extract_values(v, key)
            elif isinstance(v, list):
                for item in v:
                    yield from extract_values(item, key)


# Function to check if key is present in a yaml file
def is_key_present(dictionary, key):
    # Check if the key is in the current level of the dictionary
    if key in dictionary:
        return True

    # Iterate through the values of the dictionary
    for value in dictionary.values():
        # If the value is another dictionary, recursively check if the key is present in it
        if isinstance(value, dict):
            if is_key_present(value, key):
                return True

    # If the key is not found at any level of indentation
    return False


# Function to check if a key is present and return the path
def find_keys_and_structures(dictionary, key, path=[], results=[]):
    # Check if the key is in the current level of the dictionary
    if key in dictionary:
        results.append((dictionary, path, key))

    # Iterate through the items of the dictionary
    for k, v in dictionary.items():
        # If the value is another dictionary, recursively check if the key is present in it
        if isinstance(v, dict):
            find_keys_and_structures(v, key, path + [k], results)

    return results


# Function to create current deployment info
def create_current_operator_info(operator_details):
    # Get Registry
    registry = operator_details["image"].split("/")[0]

    # Get CSV numbers
    if operator_details["type"] == "OLM":
        name, installed_csv = operator_details["installedCSV"].split(".", 1)

        current_details = {
            "deployment": operator_details["deployment"],
            "release": operator_details["release"],
            "type": operator_details["type"],
            "installedCSV": installed_csv,
            "channel": operator_details["channel"],
            "catalogSource": operator_details["catalogSource"],
            "catalogType": operator_details["catalogType"],
            "registry": registry
        }
    else:
        current_details = {
            "deployment": operator_details["deployment"],
            "release": operator_details["release"],
            "type": operator_details["type"],
            "registry": registry
        }
    return current_details


def create_deployment_info(setup, version_data):
    if version_data:
        version = version_data["VERSION"]
        csv = version_data["CSV"]
        channel = version_data["CHANNEL"]
    else:
        version = "5.7.0"
        csv = "57.0.0"
        channel = "25.0.0"

    platform = setup.platform
    if platform == "other":
        type = "YAML"

        if setup.private_registry:
            registry = setup.private_registry_server
        else:
            registry = "icr.io"

    else:
        type = "OLM"
        registry = "icr.io"

    if setup.private_catalog:
        catalog_type = "Private"
    else:
        catalog_type = "Global"
    catalog_source = "ibm-fncm-operator-catalog"

    deployment_details = {
        "deployment": "ibm-fncm-operator",
        "release": version,
        "type": type,
        "installedCSV": csv,
        "channel": channel,
        "catalogSource": catalog_source,
        "catalogType": catalog_type,
        "registry": registry
    }
    return deployment_details


#Function to compare the requests and limits section of CR and return a flag to denote if a update is required or not
def resource_limits_comparison(current_value,upgrade_value,limits=False):
    try:
        # Assumption is that all values that do not have any letters in it are by default in Gigabytes
        # Considering all values having Mi , M , m to be Megabytes and converting them to Gigabytes for comparison
        if "Mi" in current_value or "M" in current_value or "m" in current_value:
            current_gb_value = int(re.sub(r'[a-zA-Z]', '', current_value))/1024
        else:
            current_gb_value = int(re.sub(r'[a-zA-Z]', '', current_value))

        if "Mi" in upgrade_value or "M" in upgrade_value or "m" in upgrade_value:
            upgrade_gb_value = int(re.sub(r'[a-zA-Z]', '', upgrade_value))/1024
        else:
            upgrade_gb_value = int(re.sub(r'[a-zA-Z]', '', upgrade_value))

        #comparison is different for requests and limits.
        if limits:
            if current_gb_value > upgrade_gb_value:
                return True
            else:
                return False
        else:
            if current_gb_value < upgrade_gb_value:
                return True
            else:
                return False
    except Exception as e:
        return True


# Function to update a key value pair using the values present in a another dictionary
# used to update tags and resources if they are present in the cr to be updated
# We use dictionary2 to update values in dictionary1
def update_value_by_path(dictionary1, path, dictionary2, requests=False, limits=False, logger=None):
    # Get the first key in the path
    key = path[0]

    # If there's only one key in the path, update the value
    if len(path) == 1:
        if requests:
            try:
                if resource_limits_comparison(dictionary1[key]["requests"]["cpu"],dictionary2[key]["requests"]["cpu"]):
                    dictionary1[key]["requests"]["cpu"] = dictionary2[key]["requests"]["cpu"]
                if resource_limits_comparison(dictionary1[key]["requests"]["memory"],dictionary2[key]["requests"]["memory"]):
                    dictionary1[key]["requests"]["memory"] = dictionary2[key]["requests"]["memory"]
                if resource_limits_comparison(dictionary1[key]["requests"]["ephemeral_storage"],dictionary2[key]["requests"]["ephemeral_storage"]):
                    dictionary1[key]["requests"]["ephemeral_storage"] = dictionary2[key]["requests"][
                        "ephemeral_storage"]
            except Exception as e:
                logger.info(e)

        elif limits:

            try:
                if resource_limits_comparison(dictionary1[key]["limits"]["cpu"],dictionary2[key]["limits"]["cpu"],limits=True):
                    dictionary1[key]["limits"]["cpu"] = dictionary2[key]["limits"]["cpu"]
                if resource_limits_comparison(dictionary1[key]["limits"]["memory"],dictionary2[key]["limits"]["memory"],limits=True):
                    dictionary1[key]["limits"]["memory"] = dictionary2[key]["limits"]["memory"]
                if resource_limits_comparison(dictionary1[key]["limits"]["ephemeral_storage"],dictionary2[key]["limits"]["ephemeral_storage"],limits=True):
                    dictionary1[key]["limits"]["ephemeral_storage"] = dictionary2[key]["limits"]["ephemeral_storage"]
            except Exception as e:
                logger.info(e)

        else:
            # For image tags and repos we just pop the tag and repo out
            try:

                dictionary1[key] = {}
            except Exception as e:
                logger.info(e)
    else:
        # Recursively update the nested dictionary
        if key in dictionary1 and key in dictionary2:
            update_value_by_path(dictionary1[key], path[1:], dictionary2[key], requests, limits, logger=logger)
        else:
            raise KeyError(f"Key '{key}' not found in dictionary")

def delete_key_by_path(dictionary, path_list, target_key, logger=None):
    """
    Deletes a key from a nested dictionary given a list of keys representing its path.

    Args:
        dictionary (dict): The dictionary to modify.
        path_list (list): A list of keys representing the path to the key to be deleted.
        target_key (str): The key to be deleted.
        logger: Logger object for logging information.
    """
    if not path_list:
        return

    current_dict = dictionary
    # Traverse to the parent dictionary of the key to be deleted
    for key in path_list:
        if not isinstance(current_dict, dict) or key not in current_dict:
            # Handle cases where the path is invalid
            logger.info(f"Path error: Key '{key}' not found or not a dictionary in the path.")
            return
        current_dict = current_dict[key]

    # Delete the target key from its parent dictionary
    if isinstance(current_dict, dict) and target_key in current_dict:
        del current_dict[target_key]
    else:
        logger.info(f"Deletion error: Key '{target_key}' not found at the specified path.")


def parse_yaml_for_keys(yaml_data, keys):
    """
    Parse YAML data for specified keys and extract values.
    """
    parsed_values = {key: list(extract_values(yaml_data, key)) for key in keys}
    return parsed_values


def create_version_info(setup, version_data):
    namespace = setup.namespace

    platform = setup.platform
    if platform == "other":
        platform = "CNCF"

    if version_data:
        appVersion = version_data["APP_VERSION"]
        version = version_data["VERSION"]
    else:
        appVersion = "25.0.0"
        version = "5.7.0"

    version_details = {
        "version": version,
        "namespace": namespace,
        "platform": platform.upper(),
        "appVersion": appVersion
    }

    return version_details


# Create tmp folder
def create_tmp_folder():
    tmp_folder = os.path.join(os.getcwd(), ".tmp")
    if os.path.exists(tmp_folder):
        try:
            # Remove the directory and its contents
            shutil.rmtree(tmp_folder)
        except OSError as e:
            print(f"Failed to delete directory '{tmp_folder}': {e}")
    # Create the directory
    try:
        os.makedirs(tmp_folder)
        return tmp_folder
    except OSError as e:
        print(f"Failed to create directory '{tmp_folder}': {e}")


# image copying mechanism for loadimages.py
def copy_image(source_image, dest_image, progress=None):
    try:
        # Construct Skopeo command to copy image with the same digest
        command = f"skopeo copy docker://{source_image} docker://{dest_image} --all --dest-tls-verify=false --remove-signatures"

        # Execute Skopeo command
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True, stderr=subprocess.PIPE)

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
            progress.log(Text(f"Error copying image to {dest_image}", style="bold red"))
            progress.log()
            return False

        progress.log(Text(f"Image copied to {dest_image} successfully", style="bold green"))
        progress.log()
        return True

    except Exception as e:
        (f"Error: {e}")
        return False


# Function to read all env variables from the airgap variables file
def read_airgap_vars(airgap_details_file):
    airgap_vars = {}
    # Need to ignore comments and "remove" the export keyword
    with open(airgap_details_file, 'r') as file:
        for line in file:
            trimmed = line.strip()
            if trimmed and not trimmed.startswith('#'):
                key, value = trimmed.split("=")
                key = key.replace("export ", "")
                airgap_vars[key] = value

    return airgap_vars


# Parse the airgap details file

# Validate the image tag and repo file details
def validate_airgap_details_file(logger, airgap_details_file: str):
    try:
        # Check if the airgap details file exists
        if not os.path.exists(airgap_details_file):
            print(Panel.fit(f"Issues Found", style="bold red"))
            print(
                f"\n[prompt.invalid]Airgap details file {airgap_details_file} is missing.\n\n"
                f"Please run the script in generate mode to generate the file.\n")

            print(Panel.fit(
                Syntax("python3 loadimages.py --airgap generate", "bash", theme="ansi_dark")
            ))
            exit(1)

        airgap_vars = read_airgap_vars(airgap_details_file)

        if not airgap_vars:
            print(Panel.fit(f"Issues Found", style="bold red"))
            print(
                f"\n[prompt.invalid]Airgap details file {airgap_details_file} is empty.\n\n"
                f"Please run the script in generate mode to generate the file.\n")

            print(Panel.fit(
                Syntax("python3 loadimages.py --airgap generate", "bash", theme="ansi_dark")
            ))
            exit(1)

        # Check all the required variables are present
        required_vars = ["CASE_NAME", "CASE_VERSION", "IBMPAK_HOME", "TARGET_REGISTRY",
                         "REGISTRY_AUTH_FILE", "CASE_INVENTORY_SETUP"]

        missing_vars = [var for var in required_vars if var not in airgap_vars]

        if missing_vars:
            print(Panel.fit(f"Issues Found", style="bold red"))
            print(f"\n[prompt.invalid]Required variables are missing in the airgap details file.\n\n"
                  f"Please add the following variables to the file: {missing_vars}")
            exit(1)

        # Check if the IBM PAK home directory is valid
        ibm_pak_home = os.path.join(airgap_vars["IBMPAK_HOME"], '.ibm-pak')
        if not os.path.exists(ibm_pak_home):
            print(Panel.fit(f"Issues Found", style="bold red"))
            print(f"\n[prompt.invalid]IBM PAK home directory {ibm_pak_home} does not exist.\n\n"
                  f"The IBM PAK directory is populated when the CASE Package is downloaded.\n"
                  f"Please run the script in generate mode to complete the CASE package setup.\n")
            print(Panel.fit(
                Syntax("python3 loadimages.py --airgap generate", "bash", theme="ansi_dark")
            ))
            exit(1)

        return airgap_vars

    except Exception as e:
        logger.exception(
            f"Exception when reading ImageDetails Files\n"
            f"Please Review your Airgap Details file: {e}\n\n")
        exit(1)


# Validate the image tag and repo file details
def validate_image_details_file(logger, image_tag_file):
    try:
        # Load property files if they exist
        if os.path.exists(image_tag_file):
            try:
                image_prop = ReadPropImageTag(image_tag_file, logger)
            except TomlDecodeError:
                print(Panel.fit(f"Issues Found", style="bold red"))
                print(
                    f"\n[prompt.invalid]Exception when reading ImageDetails File\n\n"
                    f"Please Review your Property files for missing quotes and formatting.\n\n")
                exit(1)
            incorrect_keys = image_prop.check_toml()
            if incorrect_keys:
                print(Panel.fit(f"Issues Found", style="bold red"))
                print(f"\n[prompt.invalid]There are certain components which have incorrect format.\n\n"
                      f"Please review the file and correct the following keys: {incorrect_keys}")
                exit(1)

        else:
            print(Panel.fit(f"Issues Found", style="bold red"))
            print(
                f"\n[prompt.invalid]Image details file {image_tag_file} is missing.\n\n"
                f"Please run the script in generate mode to generate the file.\n")

            print(Panel.fit(
                Syntax("python3 loadimages.py generate", "bash", theme="ansi_dark")
            ))

            exit(1)
        # Create dictionaries for property files if not None
        if image_prop:
            image_prop_dict = image_prop.to_dict()
        else:
            image_prop_dict = {}

        return image_prop_dict
    except Exception as e:
        logger.exception(
            f"Exception when reading ImageDetails Files\n"
            f"Please Review your Property files for missing quotes and formatting.{e}\n\n")
        exit(1)


def update_operator_template(input_file, output_file):
    # Define the patterns and replacements
    patterns_replacements = [
        (r'dba_license', r'value:.*', r'value: accept'),
        (r'baw_license', r'value:.*', r'value: accept'),
        (r'fncm_license', r'value:.*', r'value: accept'),
        (r'ier_license', r'value:.*', r'value: accept')
    ]

    # Read input file, apply replacements, and write to output file
    with open(input_file, 'r') as fin, open(output_file, 'w') as fout:
        for line in fin:
            for pattern, search_pattern, replacement in patterns_replacements:
                if re.search(pattern, line):
                    next(fin)  # Skip to the next line
                    line = re.sub(search_pattern, replacement, line)
                    break  # Once a pattern is matched, break out of the loop
            fout.write(line)

