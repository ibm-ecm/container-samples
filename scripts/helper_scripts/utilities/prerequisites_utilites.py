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

import yaml
from OpenSSL import SSL
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from rich import print
from rich.text import Text

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
        else:
            print(message)
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

        if progress:
            progress.log(message)
            progress.log()
        else:
            print(message)
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
