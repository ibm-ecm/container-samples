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

import docker
import requests
import toml
import yaml
from .prerequisites_utilites import command_available, check_java_version, get_kubectl_version, \
    kubectl_log_in_check, get_skopeo_version, filepath_validate
from rich import print
from rich.text import Text
from toml.decoder import TomlDecodeError

from ..property.read_prop import ReadPropImageTag


# Function to check if docker is available
def docker_available():
    try:
        client = docker.from_env()
        client.ping()
        return True
    except docker.errors.APIError:
        return False
    except Exception as e:
        return False

# Function to log in to a registry using docker
def login_to_registry_docker(registry, username, password, logger, ssl_enabled=False, ssl_cert_path=''):
    try:

        if ssl_enabled:
            registry_url = f"https://{registry}"

            # Perform Docker login with TLS certificate
            response = requests.get(f"{registry_url}/v2/", auth=(username, password), verify=ssl_cert_path)

            # Check if login was successful
            if response.status_code == 200:
                logger.info("Successfully logged in to the Docker registry.")
                return True
            else:
                logger.error(f"Failed to log in to the Docker registry. Status code: {response.status_code}")
                return False
        else:

            client = docker.from_env()
            client.ping()

            # Log in to the Docker registry

            login_result = client.login(username=username, password=password, registry=registry)
            # Check if the login was successful
            if login_result:
                logger.info(f"Successfully logged in to {registry}")
                return True
            else:
                logger.error(f"Failed to log in to {registry}")
                return False

    except docker.errors.APIError as e:
        logger.info(f"Error: {e}")
        return False

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

# Function to do the prerequisite checks before the script starts
def prereq_checks(logger, prereqs=None, files=None, fncm_version='5.6.0'):
    if prereqs is None:
        prereqs = []

    if files is None:
        files = []
    try:
        missing_tools = []
        missing_files = []

        prereq_summary = {
            "docker": False,
            "podman": False,
            "java": False,
            "java_version": "",
            "kubectl": False,
            "kubectl_version": "",
            "connection": False,
            "skopeo": False,
            "skopeo_version": "",
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

        if any(x in prereqs for x in ["podman", "docker"]):
            podman = command_available("podman")
            docker = docker_available()

            # Either podman or docker needed
            if docker:

                logger.info("Docker Daemon available")
                logger.info("Using Docker Daemon")
                prereq_summary["docker"] = True

            else:

                if podman:

                    logger.info("Podman available")
                    logger.info("Using Podman Daemon")
                    prereq_summary["podman"] = True

                else:
                    logger.info("neither podman or docker daemon present")
                    missing_tools.append("Podman/Docker CLI")

        # Java Check
        if "java" in prereqs:
            java_present = command_available("java")

            if not java_present:
                logger.info("Prerequisites failed -> Java not installed")
                missing_tools.append("Java")
            else:
                logger.info("Java available")
                prereq_summary["java"] = True
                java_version = check_java_version(fncm_version)

                if not java_version:
                    logger.info("Prerequisites failed -> Java version not correct")
                    missing_tools.append("Java Version")
                else:
                    logger.info("Java Version correct")
                    prereq_summary["java_version"] = java_version

        # kubectl check
        if "kubectl" in prereqs:
            kubectl = command_available("kubectl")
            if not kubectl:
                logger.info("Prerequisites failed -> kubectl not installed")
                missing_tools.append("Kubectl CLI")
            else:
                logger.info("Kubectl CLI available")
                prereq_summary["kubectl"] = True
                kubectl_version = get_kubectl_version(logger)
                prereq_summary["kubectl_version"] = kubectl_version

            # check if cluster is logged in
            ocp_logged_in = kubectl_log_in_check(logger)
            if not ocp_logged_in:
                logger.info("Prerequisites failed -> User is not logged into the OCP console")
                missing_tools.append("connection")
            else:
                logger.info("User is logged into the OCP console")
                prereq_summary["connection"] = True

        if "skopeo" in prereqs:
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

# Validate the image tag and repo file details
def validate_image_details_file(logger, image_tag_file):
    try:
        # Load property files if they exist
        if os.path.exists(image_tag_file):
            try:
                image_prop = ReadPropImageTag(image_tag_file, logger)
            except TomlDecodeError:
                print(
                    f"[prompt.invalid]Exception when reading ImageDetails File\n"
                    f"Please Review your Property files for missing quotes and formatting.\n\n")
                exit(1)
            incorrect_keys = image_prop.check_toml()
            if incorrect_keys:
                print(f"[prompt.invalid]There are certain components which have incorrect format.\n"
                      f"Please review the file and correct the following keys: {incorrect_keys}")
                exit(1)

        else:
            print(
                f"[prompt.invalid]Image details file {image_tag_file} is missing.\n"
                f"Please run the script in generate mode to generate the file.")
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

# Function to read a version toml file
def read_version_toml(file_path, logger):
    try:
        version_data = toml.loads(open(file_path, encoding="utf-8").read())
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
        version = "5.6.0"
        csv = "56.0.0"
        channel = "24.0.0"

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
        appVersion = "24.0.0"
        version = "5.6.0"

    version_details = {
        "version": version,
        "namespace": namespace,
        "platform": platform.upper(),
        "appVersion": appVersion
    }

    return version_details

def write_yaml_to_file(content, path):
    if not isinstance(content, dict):
        content = content.to_dict()
    with open(path, 'w') as f:
        yaml.dump(content, f, default_flow_style=False)


def write_log_to_file(content, path):
    with open(path, 'w') as f:
        f.write(content)


def compress_extract_from_pod(command):
    subprocess.run(command, shell=True, check=True)

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


# Validate the image tag and repo file details
def validate_image_details_file(logger, image_tag_file):
    try:
        # Load property files if they exist
        if os.path.exists(image_tag_file):
            try:
                image_prop = ReadPropImageTag(image_tag_file, logger)
            except TomlDecodeError:
                print(
                    f"[prompt.invalid]Exception when reading ImageDetails File\n"
                    f"Please Review your Property files for missing quotes and formatting.\n\n")
                exit(1)
            incorrect_keys = image_prop.check_toml()
            if incorrect_keys:
                print(f"[prompt.invalid]There are certain components which have incorrect format.\n"
                      f"Please review the file and correct the following keys: {incorrect_keys}")
                exit(1)

        else:
            print(
                f"[prompt.invalid]Image details file {image_tag_file} is missing.\n"
                f"Please run the script in generate mode to generate the file.")
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