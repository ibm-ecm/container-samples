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

import inspect
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import time
from socket import socket, gaierror

import docker
import requests
import toml
import yaml
from OpenSSL import SSL
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from rich import print
from rich.text import Text
from toml.decoder import TomlDecodeError

from ..property.read_prop import ReadPropImageTag

_CIPHERS = bytes(
    "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256",
    'utf-8')


# create a private method that reads in json into a dictionary
def read_json(directory, json_file):
    path = os.path.join(directory, json_file)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Create a method to zip a folder and return the path to the zip file
def zip_folder(zip_file_name: str, folder_path: str) -> str:
    """Zip a folder and return the path to the zip file."""
    zip_file = shutil.make_archive(zip_file_name, "zip", folder_path, )
    return zip_file


# Create a method to create the generatedfiles folder structure and zip it up if it is present
def create_generate_folder(trusted_certs_present) -> None:
    generate_folder = os.path.join(os.getcwd(), "generatedFiles")
    generate_secrets_folder = os.path.join(generate_folder, "secrets")
    generate_ssl_secrets_folder = os.path.join(generate_folder, "ssl")
    generate_trusted_secrets_folder = os.path.join(generate_folder, "ssl", "trusted-certs")
    os.mkdir(generate_folder)
    os.mkdir(generate_secrets_folder)
    os.mkdir(generate_ssl_secrets_folder)
    if trusted_certs_present:
        os.mkdir(generate_trusted_secrets_folder)


def parse_required_fields(required_fields):
    parsed_fields = {}
    for entry in required_fields:
        section = entry[0][0]
        paramter = entry[0][1]
        # check if section exists
        if section not in parsed_fields:
            parsed_fields[section] = []
        parsed_fields[section].append(paramter)
    return parsed_fields


# Function to check if private key is of pem format
def check_pem_key_format(ssl_cert):
    try:
        with open(ssl_cert, 'rb') as file:
            data = file.read()
        # Attempt to load it as a private key
        serialization.load_pem_private_key(data, password=None, backend=default_backend())
        # If successful, it's a valid PEM file
        return True
    except Exception as e:
        try:
            # Attempt to load it as a public key
            serialization.load_pem_public_key(data, backend=default_backend())
            # If successful, it's a valid PEM file
            return True
        except Exception:
            # Not a valid PEM file
            return False


# Function to check if ssl cert is of pem format
def check_pem_cert_format(ssl_cert):
    try:
        with open(ssl_cert, 'rb') as file:
            data = file.read()
        x509.load_pem_x509_certificate(data, default_backend())
        return True
    except Exception as e:
        return False


# Function to check all cert formats recursively for postgres SSL
def check_ssl_certs_postgres(folder_list, cert_path):
    for cert in folder_list:
        if cert.startswith("."):
            os.remove(os.path.join(cert_path, cert))
        else:
            pem_cert_check = check_pem_cert_format(os.path.join(cert_path, cert))
            if not pem_cert_check:
                pem_key_check = check_pem_key_format(os.path.join(cert_path, cert))
                if not pem_key_check:
                    return False
                else:
                    return True
            else:
                return True


# Function to check if ssl certs are added to the respective folders
def check_ssl_folders(db_prop=None, ldap_prop=None, ssl_cert_folder=None, deploy_prop=None) -> tuple:
    missing_cert = {}
    incorrect_cert = {}
    # if any ssl cert folders exists that means ssl was enabled for either ldap or DB
    if os.path.exists(ssl_cert_folder):
        ssl_folders = collect_visible_files(ssl_cert_folder)

        # remove any hidden files that might be picked up and remove the trusted-certs folder
        for folder in ssl_folders.copy():
            if folder == "trusted-certs":
                ssl_folders.remove(folder)

        # checking to see if any changes to ssl value have been made after folders were created
        ldap_folders = list(filter(lambda x: "ldap" in x, ssl_folders))
        db_folders = list(filter(lambda x: "ldap" not in x, ssl_folders))

        # if db type is not postgres we have a standard folder structure of ssl certs
        if db_prop["DATABASE_SSL_ENABLE"]:
            if db_prop["DATABASE_TYPE"].lower() != "postgresql":
                for folder in db_folders:
                    ssl_certs = collect_visible_files(os.path.join(ssl_cert_folder, folder))
                    if not ssl_certs:
                        missing_cert[folder] = ["certificate"]
                    # logic to check if the cert is the right pem format
                    else:
                        for cert in ssl_certs:
                            if cert.startswith("."):
                                os.remove(os.path.join(ssl_cert_folder, folder, cert))
                            else:
                                pem_cert_check = check_pem_cert_format(os.path.join(ssl_cert_folder, folder, cert))
                                if not pem_cert_check:
                                    pem_key_check = check_pem_key_format(os.path.join(ssl_cert_folder, folder, cert))
                                    if not pem_key_check:
                                        incorrect_cert[folder] = ["certificate"]
            else:
                # if db type is postgres we have three sub folders inside the db ssl cert folders which need to be checked for ssl certs
                for folder in db_folders:

                    sub_folder_path = os.path.join(ssl_cert_folder, folder)
                    sub_folders = collect_visible_files(sub_folder_path)

                    server_ca = False
                    clientkey = False
                    clientcert = False
                    for sub_folder in sub_folders:
                        if "serverca" in sub_folder.lower():
                            server_ca_items = collect_visible_files(os.path.join(sub_folder_path, sub_folder))
                            if server_ca_items:
                                server_ca = True
                                incorrect_cert_present = check_ssl_certs_postgres(server_ca_items,
                                                                                  os.path.join(sub_folder_path,
                                                                                               sub_folder))
                                if not incorrect_cert_present:
                                    if folder not in incorrect_cert:
                                        incorrect_cert[folder] = []
                                        incorrect_cert[folder].append("serverca")
                                    else:
                                        incorrect_cert[folder].append("serverca")

                        if "clientkey" in sub_folder.lower():
                            clientkey_items = collect_visible_files(os.path.join(sub_folder_path, sub_folder))
                            if clientkey_items:
                                clientkey = True
                                incorrect_cert_present = check_ssl_certs_postgres(clientkey_items,
                                                                                  os.path.join(sub_folder_path,
                                                                                               sub_folder))
                                if not incorrect_cert_present:
                                    if folder not in incorrect_cert:
                                        incorrect_cert[folder] = []
                                        incorrect_cert[folder].append("clientkey")
                                    else:
                                        incorrect_cert[folder].append("clientkey")
                        if "clientcert" in sub_folder.lower():
                            clientcert_items = collect_visible_files(os.path.join(sub_folder_path, sub_folder))
                            if clientcert_items:
                                clientcert = True
                                incorrect_cert_present = check_ssl_certs_postgres(clientcert_items,
                                                                                  os.path.join(sub_folder_path,
                                                                                               sub_folder))
                                if not incorrect_cert_present:
                                    if folder not in incorrect_cert:
                                        incorrect_cert[folder] = []
                                        incorrect_cert[folder].append("clientcert")
                                    else:
                                        incorrect_cert[folder].append("clientcert")
                    if db_prop["DATABASE_SSL_ENABLE"]:
                        if db_prop["SSL_MODE"].lower() == "verify-full":
                            # All certs are required for "verify-full" mode
                            if not server_ca:
                                if folder not in missing_cert:
                                    missing_cert[folder] = []
                                    missing_cert[folder].append("serverca")
                                else:
                                    missing_cert[folder].append("serverca")
                            if not clientkey:
                                if folder not in missing_cert:
                                    missing_cert[folder] = []
                                    missing_cert[folder].append("clientkey")
                                else:
                                    missing_cert[folder].append("clientkey")
                            if not clientcert:
                                if folder not in missing_cert:
                                    missing_cert[folder] = []
                                    missing_cert[folder].append("clientcert")
                                else:
                                    missing_cert[folder].append("clientcert")
                        elif db_prop["SSL_MODE"].lower() == "require":
                            # Require mode can be either Client or Server Authentication
                            # Selected Client Authentication
                            if (clientcert or clientkey) and deploy_prop["FNCM_Version"] != "5.5.8":
                                if not clientkey:
                                    if folder not in missing_cert:
                                        missing_cert[folder] = []
                                        missing_cert[folder].append("clientkey")
                                    else:
                                        missing_cert[folder].append("clientkey")
                                if not clientcert:
                                    if folder not in missing_cert:
                                        missing_cert[folder] = []
                                        missing_cert[folder].append("clientcert")
                                    else:
                                        missing_cert[folder].append("clientcert")
                            # Selected Server Authentication
                            elif not server_ca:
                                if folder not in missing_cert:
                                    missing_cert[folder] = []
                                    missing_cert[folder].append("serverca")
                                else:
                                    missing_cert[folder].append("serverca")
                        elif db_prop["SSL_MODE"].lower() == "verify-ca" and folder != "ldap":
                            # Verify-ca mode requires a server-ca cert
                            if clientcert or clientkey:
                                if not server_ca:
                                    if folder not in missing_cert:
                                        missing_cert[folder] = []
                                        missing_cert[folder].append("serverca")
                                    else:
                                        missing_cert[folder].append("serverca")

                                if not clientkey:
                                    if folder not in missing_cert:
                                        missing_cert[folder] = []
                                        missing_cert[folder].append("clientkey")
                                    else:
                                        missing_cert[folder].append("clientkey")

                                if not clientcert:
                                    if folder not in missing_cert:
                                        missing_cert[folder] = []
                                        missing_cert[folder].append("clientcert")
                                    else:
                                        missing_cert[folder].append("clientcert")
                            else:
                                if not server_ca:
                                    if folder not in missing_cert:
                                        missing_cert[folder] = []
                                        missing_cert[folder].append("serverca")
                                    else:
                                        missing_cert[folder].append("serverca")

        # base logic for ldap cert folder
        for folder in ldap_folders:
            if ldap_prop[folder.upper()]["LDAP_SSL_ENABLED"]:
                ssl_certs = collect_visible_files(os.path.join(ssl_cert_folder, folder))
                if not ssl_certs:
                    if folder not in missing_cert:
                        missing_cert[folder] = []
                        missing_cert[folder].append("certificate")
                    else:
                        missing_cert[folder].append("certificate")
                else:
                    for cert in ssl_certs:
                        if cert.startswith("."):
                            os.remove(os.path.join(ssl_cert_folder, folder, cert))
                        else:
                            pem_cert_check = check_pem_cert_format(os.path.join(ssl_cert_folder, folder, cert))
                            if not pem_cert_check:
                                pem_key_check = check_pem_key_format(os.path.join(ssl_cert_folder, folder, cert))
                                if not pem_key_check:
                                    incorrect_cert[folder] = ["certificate"]

    return missing_cert, incorrect_cert


# Function to check if icc masterkey file is present
def check_icc_masterkey(custom_component_prop, icc_folder):
    # if custom component property file is empty then we know icc is not present and we can skip the check
    if not custom_component_prop:
        return True
    if custom_component_prop and "ICC" not in custom_component_prop.keys():
        return True
    # the file to create the secret has to be in .txt format
    if os.path.exists(icc_folder):
        file_list = collect_visible_files(icc_folder)
        if not file_list:
            return False
        else:
            for file in file_list:
                if file.endswith('.txt'):
                    return True
            return False


# Function to check if there are certs in the trusted cert folder
def check_trusted_certs(trusted_certs_folder):
    # the certs have to be in .pem , .crt , .cert
    invalid_certs = []
    if os.path.exists(trusted_certs_folder):
        file_lists = collect_visible_files(trusted_certs_folder)
        if len(file_lists) > 0:
            # some certs have been added
            for file in file_lists:
                if file.startswith("."):
                    continue
                if not (file.endswith('.pem') or file.endswith('.crt') or file.endswith('.cert')):
                    invalid_certs.append(file)
            return True, invalid_certs
        else:
            return False, invalid_certs
    else:
        return True, invalid_certs


def check_dbname(db_prop):
    incorrect_naming_convention = []
    if db_prop["DATABASE_TYPE"].lower() == "db2":
        for db in db_prop["db_list"]:
            if len(db_prop[db]["DATABASE_NAME"]) > 8:
                incorrect_naming_convention.append(db)
    return incorrect_naming_convention


# Function to check if keystore password is atleast 16characters long for FIPS enabled
def check_keystore_password_length(user_group_prop, deploy_prop):
    # checking if fips support is enabled
    if "FIPS_SUPPORT" in deploy_prop.keys():
        if deploy_prop["FIPS_SUPPORT"]:
            if len(user_group_prop["KEYSTORE_PASSWORD"]) < 16:
                return False
    return True


# Function to check if db password is atleast 16 characters long for FIPS enabled
def check_db_password_length(db_prop, deploy_prop):
    # checking if fips support is enabled
    incorrect_password_dbs = []
    if "FIPS_SUPPORT" in deploy_prop.keys():
        if deploy_prop["FIPS_SUPPORT"] and db_prop["DATABASE_TYPE"].lower() == "postgresql":
            for db in db_prop["db_list"]:
                if len(db_prop[db]["DATABASE_PASSWORD"]) < 16:
                    incorrect_password_dbs.append(db)
    return incorrect_password_dbs


# Function to check if db ssl mode is require for postgres for FIPS enabled
def check_db_ssl_mode(db_prop, deploy_prop):
    # checking if fips support is enabled
    correct_ssl_mode = True
    if "FIPS_SUPPORT" in deploy_prop.keys():
        if deploy_prop["FIPS_SUPPORT"] and db_prop["DATABASE_TYPE"].lower() == "postgresql" and db_prop[
            "DATABASE_SSL_ENABLE"]:
            if db_prop["SSL_MODE"].lower() != "require":
                correct_ssl_mode = False
    return correct_ssl_mode


def collect_visible_files(folder_path: str) -> [str]:
    return [file for file in os.listdir(folder_path) if not file.startswith('.')]


def get_kubectl_version(logger):
    try:
        # Get the kubectl version
        kubectl_version = subprocess.check_output(["kubectl", "version", "--output=json"],
                                                  stderr=subprocess.DEVNULL,
                                                  timeout=5).decode("utf-8")
        kubectl_version = json.loads(kubectl_version)["clientVersion"]["gitVersion"]
        logger.info(f"Kubectl Version: {kubectl_version}")
        return kubectl_version
    except subprocess.TimeoutExpired:
        logger.info("Error: Timeout while getting kubectl version")
        return ""
    except Exception as e:
        logger.info(f"Error: {e}")
        return ""


def get_skopeo_version(logger):
    try:
        # Get the skopeo version
        skopeo_version = subprocess.check_output(["skopeo", "--version"]).decode("utf-8")
        skopeo_version = skopeo_version.split()[2]
        logger.info(f"Skopeo Version: {skopeo_version}")
        return skopeo_version
    except Exception as e:
        logger.info(f"Error: {e}")
        return None


def check_java_version(fncm_version):
    try:
        java_version_output = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True)
        version_match = re.search(r'"(\d+\.\d+\.\d+)', java_version_output)
        java_version = version_match.group(1) if version_match else "Unknown"
        if java_version != 'Unknown':
            if fncm_version == "5.5.8":
                if int(java_version.split(".")[1]) != 8:
                    return False
            if fncm_version == "5.5.11":
                if int(java_version.split(".")[0]) != 11:
                    return False

            if fncm_version in ("5.5.12", "5.6.0"):
                if int(java_version.split(".")[0]) != 17:
                    return False
        return True
    except subprocess.CalledProcessError as e:
        # If 'java -version' returns a non-zero exit code, print the error
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


def connect_to_server(host, port, ssl=False, client_cert_file=None, pg=False, progress=None):
    # If SSL is enabled, create an SSL socket
    # Create an SSL context
    if ssl:
        context = SSL.Context(SSL.SSLv23_METHOD)
        context.set_cipher_list(_CIPHERS)
        context.set_min_proto_version(SSL.TLS1_2_VERSION)
        if client_cert_file:
            context.use_certificate_file(client_cert_file)

        # Create an SSL socket
        sock = socket()
        conn = SSL.Connection(context, sock)
    else:
        conn = socket()

    connected = False
    try:
        start_time = time.time()
        conn.connect((host, port))
        end_time = time.time()

        if ssl:
            # Postgres requires protocol negotiation before SSL since everything's on same port
            # https://www.postgresql.org/docs/current/protocol-flow.html#PROTOCOL-FLOW-SSL
            if pg:
                version_ssl = struct.pack('!I', 1234 << 16 | 5679)
                length = struct.pack('!I', 8)
                packet = length + version_ssl
                sock.sendall(packet)
                sock.recv(1)
            conn.do_handshake()
        connected = True

    # Now you can perform LDAP operations using 'conn' if needed
    except gaierror as e:
        message = Text(
            f"Hostname \"{host}\" is not known.\n"
            f"Please review the Property Files for all SERVERNAME parameters", style="bold red")
        if progress:
            progress.log(message)
            progress.log()
        return conn, 0, connected
    except Exception as e:
        if type(e.args) == list:
            if e.args[0][0][0] == 'SSL routines' and e.args[0][0][2] == 'sslv3 alert handshake failure':
                message = Text(
                    f"SSL protocol used: \"{conn.get_protocol_version_name()}\", is not supported by the server!\n"
                    f"Please review below list of supported protocols:\n"
                    f" - \"TLSv1.2\"\n"
                    f" - \"TLSv1.3\"", style="bold red")
        else:
            message = Text(f"Connection Error: {e}", style="bold red")
            print(message)

        if progress:
            progress.log(message)
            progress.log()
        return conn, 0, connected

    # Calculate RTT and format to milliseconds
    rtt = (end_time - start_time) * 1000

    return conn, rtt, connected


# Function to check if podman, oc and other commands are available
def command_available(command):
    try:
        if platform.system() == 'Windows':
            subprocess.check_output("where " + command, stderr=subprocess.PIPE, shell=True)
        else:
            subprocess.check_output("which " + command, stderr=subprocess.PIPE, shell=True)
        return True
    except subprocess.CalledProcessError as error:
        return False


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


# Checks whether we are properly logged into a Kubernetes/OCP cluster
# 'kubectl config current-context' is not sufficient it will show most recent cluster,
# but we cannot apply yaml which is needed to test storage classes
# (!!!) DOES NOT WORK WHEN INSIDE OPERATOR POD
def kubectl_log_in_check(logger):
    try:
        subprocess.check_output("kubectl get pods", shell=True, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                                universal_newlines=True, timeout=5)
        return True
    except subprocess.TimeoutExpired:
        return False
    except subprocess.CalledProcessError as error:
        logger.info("Kubectl is not logged into any cluster and " \
                    + f"will cause errors when checking storage classes; error")
        return False


# method to check to if value in property file is valid
def valid_check(prop_key, prop_value, valid_values, _error_list, _logger):
    try:
        # For sets and boolean validity check
        if type(valid_values) is list:
            if prop_value not in valid_values:
                # Just extra formatting to match what is visible in toml file for strings
                if type(prop_value) is str:
                    prop_value = f"\"{prop_value}\""

                error = f"Incorrect/missing parameter set in silent install file -  {prop_key}={prop_value} | Valid values - {valid_values}"
                _error_list.append(error)
                return False

        # For range of integers check
        elif type(valid_values) is tuple:
            if valid_values[0] > prop_value >= valid_values[1]:
                error = f"Incorrect/missing parameter set in silent install file -  {prop_key}={prop_value} | Valid values - {valid_values}"
                _error_list.append(error)
                return False

        # For boolean values check
        elif type(valid_values) is bool:
            if type(prop_value) is not bool:
                valid_values = "[true,false]"
                error = f"Incorrect/missing parameter set in silent install file -  {prop_key}={prop_value} | Valid values - {valid_values}"
                _error_list.append(error)
                return False

        elif type(valid_values) is str:
            if valid_values == "url":
                # Check if the url is valid
                if prop_value is None or not prop_value.endswith(".well-known/openid-configuration"):
                    error = f"URL is empty or invalid in silent install file -  {prop_key}={prop_value} | Valid values - ends with .well-known/openid-configuration"
                    _error_list.append(error)
                    return False

        return True

    except Exception as e:
        _logger.info(
            f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # method to return variables in correct type for a given key from config file
    # Currently can only read one table layer deep


def gather_var(key, _logger, _envfile, _error_list, section_header='', valid_values=True):
    try:
        if section_header == '':
            value = _envfile.get(key)
        else:
            value = _envfile[section_header][key]
            section_header = "[" + section_header + "]"
        # Check that the user/property file input is valid
        if valid_check(prop_key=section_header + key, prop_value=value, valid_values=valid_values, _logger=_logger,
                       _error_list=_error_list):
            return value
        return None

    except Exception as e:
        _logger.info(
            f"Exception from utilities.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")


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
    else:
        type = "OLM"

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
        "registry": "icr.io"
    }
    return deployment_details


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


# Function to check if a specific file path is present
def filepath_validate(filepath):
    if not os.path.exists(filepath):
        return False
    else:
        return True


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


# Clear console based on system OS
def clear(console):
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        console.clear()
