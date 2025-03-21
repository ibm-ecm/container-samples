###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2023. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################

import inspect
import os
import platform
import re
import shutil
import ssl
import string
import subprocess
import time
from urllib.parse import urlparse
import base64
import shlex

import requests
import typer
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from rich import print
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.console import Console

from ..utilities.interface import ldap_search_results, ldap_entry_types
from ..utilities.prerequisites_utilites import command_available, check_java_version, kubectl_log_in_check, \
    collect_visible_files, \
    connect_to_server

requests.packages.urllib3.disable_warnings()


# Function to remove protocol from URL
def remove_protocol(url):
    hostname = urlparse(url).hostname
    if hostname is None:
        hostname = url
    return hostname


class Validate:
    # Is commandline keytool command present in this env?
    # None = Unchecked; True = Present; False = Not present
    _keytool_present = None

    _STORAGE_CLASS_TEMPLATE_YAML = os.path.join(os.getcwd(), "helper_scripts", "validate", "templates",
                                                "storage_class_sample.yaml")

    _JAR_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "jars")

    _JDBC_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "jdbc")

    _TMP_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "tmp")

    _CIPHERS = bytes(
        "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256",
        'utf-8')

    # Cannot default prop to a ReadProp object because Readprop requires a logger to be passed in
    def __init__(self, logger,
                 db_prop=None,
                 ldap_prop=None,
                 deploy_prop=None,
                 idp_prop=None,
                 component_prop=None,
                 user_group_prop=None):

        self.component_prop_present = False
        if db_prop:
            self._db_prop = db_prop

        if ldap_prop:
            self._ldap_prop = ldap_prop

        if deploy_prop:
            self._deploy_prop = deploy_prop

        if idp_prop:
            self._idp_prop = idp_prop

        if component_prop:
            self._component_prop = component_prop
            self.component_prop_present = True

        if user_group_prop:
            self._user_group_prop = user_group_prop

        if self._deploy_prop["FNCM_Version"] == "5.5.8":
            self._JDBC_DIR = os.path.join(self._JDBC_DIR, "java8")

        elif self._deploy_prop["FNCM_Version"] == "5.5.11":
            self._JDBC_DIR = os.path.join(self._JDBC_DIR, "java11")

        else:
            self._JDBC_DIR = os.path.join(self._JDBC_DIR, "java17")

        self._DB_JDBC_PATH = self.__get_file_from_folder(os.path.join(self._JDBC_DIR, self._db_prop["DATABASE_TYPE"]),
                                                         [".jar"])
        self._DB_CONNECTION_JAR_PATH = self.__get_file_from_folder(
            os.path.join(self._JAR_DIR, self._db_prop["DATABASE_TYPE"]), [".jar"])

        self._LDAP_JAR_PATH = self.__get_file_from_folder(os.path.join(self._JAR_DIR, "ldap"), [".jar"])

        self._logger = logger

        self.missing_tools = self.check_env_util()

        self.is_validated = {}
        self.roundtriptime = 0

        self._entries_dict = self.get_entries()

        if "FIPS_SUPPORT" in self._deploy_prop.keys():
            self.fips_enabled = self._deploy_prop["FIPS_SUPPORT"]
        else:
            self.fips_enabled = False

    # Create getters and setters for all properties
    @property
    def db_prop(self):
        return self._db_prop

    @db_prop.setter
    def db_prop(self, db_prop):
        self._db_prop = db_prop

    @property
    def ldap_prop(self):
        return self._ldap_prop

    @ldap_prop.setter
    def ldap_prop(self, ldap_prop):
        self._ldap_prop = ldap_prop

    @property
    def deploy_prop(self):
        return self._deploy_prop

    @deploy_prop.setter
    def deploy_prop(self, deploy_prop):
        self._deploy_prop = deploy_prop

    @property
    def idp_prop(self):
        return self._idp_prop

    @idp_prop.setter
    def idp_prop(self, idp_prop):
        self._idp_prop = idp_prop

    @property
    def component_prop(self):
        return self._component_prop

    @component_prop.setter
    def component_prop(self, component_prop):
        self._component_prop = component_prop

    @property
    def user_group_prop(self):
        return self._user_group_prop

    @user_group_prop.setter
    def user_group_prop(self, user_group_prop):
        self._user_group_prop = user_group_prop

    def check_env_util(self) -> list:
        missing_tools = []

        self._keytool_present = command_available("keytool")
        if not self._keytool_present:
            missing_tools.append("keytool")
        self._java_present = command_available("java")
        if not self._java_present:
            missing_tools.append("java")
        self._powershell_present = command_available("powershell.exe")
        if not self._powershell_present and platform.system() == 'Windows':
            missing_tools.append("powershell")

        if self._java_present:
            self._java_correct_version = check_java_version(self.deploy_prop["FNCM_Version"])
            if not self._java_correct_version:
                missing_tools.append("java_version")

        self._kubectl_present = command_available("kubectl")
        if not self._kubectl_present:
            missing_tools.append("kubectl")

        if self._kubectl_present:
            self._kubectl_logged_in = kubectl_log_in_check(self._logger)
            if not self._kubectl_logged_in:
                missing_tools.append("connection")
        return missing_tools

    def __check_java(self):
        if not self._java_present:
            raise typer.Exit(code=1)

    def __check_keytool(self):
        if not self._keytool_present:
            raise typer.Exit(code=1)

    def __check_kubectl(self):
        if not self._kubectl_present:
            raise typer.Exit(code=1)

    def cleanup_tmp(self):
        if os.path.exists(self._TMP_DIR):
            shutil.rmtree(self._TMP_DIR)

    def __recreate_folder(self, directory):
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.mkdir(directory)
        return directory

    def validate_all_db(self, task3, progress):
        db_type = self._db_prop['DATABASE_TYPE'].lower()
        if db_type == "postgresql":
            max_transactions = Panel.fit(Text(
                "Ensure Postgresql Max Transactions has been configured.\n"
                "Please see https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.p8.performance.doc/p8ppi308.htm.",
                style="bold green"))
            progress.log(max_transactions)
            progress.log()
        if db_type == "sqlserver":
            xa_enabled = Panel.fit(Text(
                "Ensure XA Transactions have been enabled.\n"
                "Please see https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.p8.planprepare.doc/p8ppi027.htm.",
                style="bold green"))
            progress.log(xa_enabled)
            progress.log()

        if self._deploy_prop["FNCM_Version"] == "5.5.8":
            # Check for reachability and authentication of DB Server
            progress.log(Panel.fit(Text("Validating GCD Database Connection", style="bold cyan")))
            progress.log()
            self.validate_db("GCD", task3, progress)

            for os_id in self._db_prop["_os_ids"]:
                progress.log(Panel.fit(Text(f"Validating {os_id} Database Connection", style="bold cyan")))
                progress.log()
                self.validate_db(os_id, task3, progress)

            progress.log(Panel.fit(Text("Validating ICN Database Connection", style="bold cyan")))
            progress.log()
            self.validate_db("ICN", task3, progress)
        else:
            if "CPE" in self._deploy_prop.keys():
                if self._deploy_prop["CPE"]:
                    # Check for reachability and authentication of DB Server
                    progress.log(Panel.fit(Text("Validating GCD Database Connection", style="bold cyan")))
                    progress.log()
                    self.validate_db("GCD", task3, progress)

                    for os_id in self._db_prop["_os_ids"]:
                        progress.log(Panel.fit(Text(f"Validating {os_id} Database Connection", style="bold cyan")))
                        progress.log()
                        self.validate_db(os_id, task3, progress)

            if "BAN" in self._deploy_prop.keys():
                if self._deploy_prop["BAN"]:
                    progress.log(Panel.fit(Text("Validating ICN Database Connection", style="bold cyan")))
                    progress.log()
                    self.validate_db("ICN", task3, progress)

    def parse_shell_command(self, parameter):
        # Create a function to escape any single quotes in the password
        # This is needed for the DB connection jar

        # Escape any single quotes in the password
        parameter = parameter.replace("'", "'\\''")

        return parameter

    def validate_db(self, db_label, task3, progress):
        db_name = self._db_prop[db_label]['DATABASE_NAME']
        db_user = self._db_prop[db_label]['DATABASE_USERNAME']
        db_pwd = self._db_prop[db_label]['DATABASE_PASSWORD']
        db_type = self._db_prop['DATABASE_TYPE'].lower()
        ssl_enabled = self._db_prop['DATABASE_SSL_ENABLE']

        if db_type == "oracle":
            servername_regex = re.compile(r"(?<=HOST=)[\s]*[^)\s]*")
            db_servername = servername_regex.search(self._db_prop[db_label]['ORACLE_JDBC_URL']).group()
            db_servername = remove_protocol(db_servername)
            port_regex = re.compile(r"(?<=PORT=)[\s]*[^)\s]*")
            db_port = port_regex.search(self._db_prop[db_label]['ORACLE_JDBC_URL']).group()
        else:
            db_servername = remove_protocol(self._db_prop[db_label]['DATABASE_SERVERNAME'])
            db_port = self._db_prop[db_label]['DATABASE_PORT']

        # Escape any single quotes in the password & username
        db_pwd = self.parse_shell_command(db_pwd)
        db_user = self.parse_shell_command(db_user)

        connected = False
        # Validates DB server and checks whether postgres pre-SSL packet needs to be sent
        if ssl_enabled:
            if db_type == 'postgresql':
                connected = self.validate_server(progress=progress, server=db_servername, port=db_port,
                                                 ssl_enabled=ssl_enabled,
                                                 display_rtt=False, pg=True)
            else:
                connected = self.validate_server(progress=progress, server=db_servername, port=db_port,
                                                 ssl_enabled=ssl_enabled,
                                                 display_rtt=False)

            if not connected:
                progress.log()
                progress.log(Panel.fit(Text(f"Reachability over SSL failed. Falling back to non-SSL connection.", style="bold yellow")))
                progress.log()

                if db_type == 'postgresql':
                    connected = self.validate_server(progress=progress, server=db_servername, port=db_port,
                                                 ssl_enabled=False,
                                                 display_rtt=False, pg=True)
                else:
                    connected = self.validate_server(progress=progress, server=db_servername, port=db_port,
                                                 ssl_enabled=False, display_rtt=False)

        else:
            if db_type == 'postgresql':
                connected = self.validate_server(progress=progress, server=db_servername, port=db_port,
                                             ssl_enabled=ssl_enabled,
                                             display_rtt=False, pg=True)
            else:
                connected = self.validate_server(progress=progress, server=db_servername, port=db_port,
                                             ssl_enabled=ssl_enabled,
                                             display_rtt=False)

        if not connected:
            self.is_validated[db_label] = connected
            progress.advance(task3)
            return connected

        connected_str = Text("\nChecked DB connection for " \
                             + f"\"{db_name}\" " \
                             + f"on database server \"{db_servername}\", PASSED!\n", style="bold green")
        not_connected_str = Text(f"\nUnable to connect to database \"{db_name}\" " \
                                 + f"on database server \"{db_servername}\", " \
                                 + "please check database toml file again.\n", style="bold red")

        jar_cmd = ''
        class_path_delim_char = ''
        if platform.system() == 'Windows':
            class_path_delim_char = ';'
        else:
            class_path_delim_char = ':'

        if ssl_enabled:
            cert_dir = os.path.join(os.getcwd(), "propertyFile", "ssl-certs", db_label.lower())
            self.__create_tmp_folder()

            if db_type == "db2":
                cert = self.__get_file_from_folder(file_dir=cert_dir,
                                                   extensions=[".crt", ".cer", ".pem", ".cert"])
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -cp " \
                          + f"\"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" " \
                          + f"DB2Connection -h '{db_servername}' " \
                          + f"-p {db_port} -db '{db_name}' " \
                          + f"-u '{db_user}' -pwd '{db_pwd}' " \
                          + f"-ssl -ca \"{cert}\""
            elif db_type == "oracle":
                cert = self.__get_file_from_folder(file_dir=cert_dir,
                                                   extensions=[".crt", ".cer", ".pem", ".cert"])
                truststore_folder = os.path.join(self._TMP_DIR,
                                                 "TRUSTSTORE_" + self._db_prop[db_label]["DATABASE_NAME"])
                self.__recreate_folder(truststore_folder)
                # Create DB .der file
                der_path = self.__crt_to_der_x509(input_cert_path=cert,
                                                  output_path=os.path.join(truststore_folder, f"{db_type}-db-cert.der"))
                # Create truststore
                truststore_pwd = "changeit"
                truststore_type = "PKCS12"
                truststore_path = self.__create_tmp_truststore(der_path=der_path,
                                                               output_path=os.path.join(truststore_folder,
                                                                                        f"{db_type}-db-truststore.p12"),
                                                               alias=f"cp4ba{db_type.upper()}Certs",
                                                               storetype="PKCS12",
                                                               truststore_pwd=truststore_pwd)
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -cp " \
                          + f"\"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" " \
                          + f"OracleConnection -url '{self._db_prop[db_label]['ORACLE_JDBC_URL']}' " \
                          + f"-u '{db_user}' -pwd '{db_pwd}' " \
                          + f"-ssl -trustorefile \"{truststore_path}\" -trustoretype \"{truststore_type}\" " \
                          + f"-trustorePwd \"{truststore_pwd}\""
            elif db_type == "sqlserver":
                cert = self.__get_file_from_folder(file_dir=cert_dir,
                                                   extensions=[".crt", ".cer", ".pem", ".cert"])
                truststore_folder = os.path.join(self._TMP_DIR,
                                                 "TRUSTSTORE_" + self._db_prop[db_label]["DATABASE_NAME"])
                self.__recreate_folder(truststore_folder)
                # Create DB .der file
                der_path = self.__crt_to_der_x509(input_cert_path=cert,
                                                  output_path=os.path.join(truststore_folder, f"{db_type}-db-cert.der"))
                # Create truststore
                truststore_pwd = "changeit"
                truststore_type = "PKCS12"
                truststore_path = self.__create_tmp_truststore(der_path=der_path,
                                                               output_path=os.path.join(truststore_folder,
                                                                                        f"{db_type}-db-truststore.p12"),
                                                               alias=f"cp4ba{db_type.upper()}Certs",
                                                               storetype="PKCS12",
                                                               truststore_pwd=truststore_pwd)
                SSL_CONNECTION_STR = "encrypt=true;trustServerCertificate=false;" \
                                     + f"trustStore=\"{truststore_path}\";" \
                                     + f"trustStorePassword={truststore_pwd}"
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -cp " \
                          + f"\"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" " \
                          + f"SQLConnection -h '{db_servername}' -p {db_port} -d '{db_name}' " \
                          + f"-u '{db_user}' -pwd '{db_pwd}' -ssl \"{SSL_CONNECTION_STR}\""
            elif db_type == "postgresql":
                ca_key_crt_extensions = [".crt", ".cer", ".pem", ".cert", ".key", ".arm"]
                auth_str = ""

                # CLIENT AUTH which uses clientkey and clientcert
                if len(self.__files_in_dir(os.path.join(cert_dir, "clientcert"), ca_key_crt_extensions)) != 0:
                    client_crt = self.__get_file_from_folder(file_dir=os.path.join(cert_dir, "clientcert"),
                                                             extensions=ca_key_crt_extensions)
                    client_key = self.__get_file_from_folder(file_dir=os.path.join(cert_dir, "clientkey"),
                                                             extensions=ca_key_crt_extensions)
                    der_folder = os.path.join(self._TMP_DIR, "DER_" + self._db_prop[db_label]["DATABASE_NAME"])
                    self.__recreate_folder(der_folder)
                    # Create DB .der file
                    der_path = self.__key_to_der_PKCS8(input_key_path=client_key,
                                                       output_path=os.path.join(der_folder, f"{db_type}-db-cert.der"))

                    auth_str = f"-clientkey \"{der_path}\" -clientcert \"{client_crt}\""
                    # NON-require modes always need serverca
                    if self._db_prop['SSL_MODE'].lower() != 'require':
                        server_ca = self.__get_file_from_folder(file_dir=os.path.join(cert_dir, "serverca"),
                                                                extensions=ca_key_crt_extensions)
                        auth_str = f"-ca \"{server_ca}\" " + auth_str

                # SERVER AUTH which uses serverca only
                else:
                    server_ca = self.__get_file_from_folder(file_dir=os.path.join(cert_dir, "serverca"),
                                                            extensions=ca_key_crt_extensions)
                    auth_str = f"-ca \"{server_ca}\""

                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -D\"com.ibm.jsse2.overrideDefaultTLS=true\" " \
                                    f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                                    f"{self._DB_CONNECTION_JAR_PATH}\" " \
                                    f"PostgresConnection -h '{db_servername}' -p {db_port} -db '{db_name}' " \
                                    f"-u '{db_user}' -pwd '{db_pwd}' -sslmode {self._db_prop['SSL_MODE']} " \
                                    f"{auth_str}"
        else:
            if db_type == "db2":
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" DB2Connection " \
                          + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}'"
            elif db_type == "oracle":
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" OracleConnection " \
                          + f"-url '{self._db_prop[db_label]['ORACLE_JDBC_URL']}' -u '{db_user}' -pwd '{db_pwd}'"
            elif db_type == "sqlserver":
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" SQLConnection " \
                          + f"-h '{db_servername}' -p {db_port} -d '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -ssl 'encrypt=false'"
            elif db_type == "postgresql":
                jar_cmd = "java " + f"-D\"semeru.fips={self.fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -Dcom.ibm.jsse2.overrideDefaultTLS=true " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" PostgresConnection " \
                          + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -sslmode disable"

        db_is_connected = self.__check_connection_with_jar(jar_cmd, progress)
        if db_is_connected:
            self._logger.info(f"Successfully connected to {db_label} database!")

            progress.log(connected_str)
            progress.log()

            self.output_latency(self.roundtriptime, progress, "DB")

        else:
            self._logger.info(f"Failed to connect to {db_label} database!")
            progress.log(not_connected_str)
            progress.log()
            panel = Panel.fit(jar_cmd,title="Execute the following command for more details",style="yellow",border_style="cyan")
            progress.log(panel)
            progress.log()
        self.is_validated[db_label] = db_is_connected
        progress.advance(task3)
        return db_is_connected

    # Returns the first file found in a directory
    # that has one of the extensions provided.
    def __get_file_from_folder(self, file_dir, extensions: list):
        # (!!) Will use first file found with listed extension in the directory
        files = self.__files_in_dir(file_dir, extensions)
        if len(files) == 0:
            self._logger.exception(f"No files with extension:{str(extensions)} found in {file_dir}!")
        return os.path.join(file_dir, files[0])

    # Returns a list of files that has matching extensions
    def __files_in_dir(self, dir_path, extensions: list = []):
        # list to store files
        res = []
        # Iterate directory
        for file in collect_visible_files(dir_path):
            # check only text files
            if len(extensions) != 0:
                if file.endswith(tuple(extensions)):
                    res.append(file)
            else:
                res.append(file)
        return res

    def __create_tmp_folder(self):
        try:
            if not os.path.exists(self._TMP_DIR):
                os.makedirs(self._TMP_DIR)
        except Exception as e:
            self._logger.exception(
                f"Exception from validate.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")
        return self._TMP_DIR

    # Converts a .cert file to .der in x509 format
    def __crt_to_der_x509(self, input_cert_path, output_path):
        try:
            # Remove previous temp files
            if os.path.exists(output_path):
                os.remove(output_path)

            # Create LDAP .der file
            with open(input_cert_path, 'rb') as cert_file:
                cert_file = cert_file.read()
            cert_der = x509.load_pem_x509_certificate(cert_file, default_backend())
            with open(output_path, 'wb') as file:
                file.write(cert_der.public_bytes(serialization.Encoding.PEM))

        except Exception as e:
            self._logger.exception(
                f"Exception from validate.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

        return output_path

    # Converts .key files to .der in PKCS8 format
    def __key_to_der_PKCS8(self, input_key_path, output_path):
        try:
            # Remove previous temp files
            if os.path.exists(output_path):
                os.remove(output_path)

            # Create LDAP .der file
            with open(input_key_path, 'rb') as key_data:
                key = serialization.load_pem_private_key(
                    key_data.read(),
                    password=None,
                    backend=default_backend()
                )

            pkcs8_key = key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            with open(output_path, "wb") as outfile:
                outfile.write(pkcs8_key)

        except Exception as e:
            self._logger.exception(
                f"Exception from validate.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

        return output_path

    # der_path is the path to the input .der file needed to create this temp trust store
    # !!truststore_pwd will be defaulted to "changeit"!!
    def __create_tmp_truststore(self, der_path, output_path, alias, storetype, truststore_pwd="changeit"):
        self.__check_keytool()
        if os.path.exists(output_path):
            os.remove(output_path)

        # Create keystore with the .der file
        try:
            keystore_cmd = f"keytool -import -alias {alias} -keystore \"{output_path}\" -file \"{der_path}\" " \
                           + f"-storepass {truststore_pwd} -storetype {storetype} -noprompt"
            subprocess.run(keystore_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self._logger.exception(
                f"Exception creating key store file -  {str(e)}")

        return output_path

    # Check every and validate all LDAP found in property file.
    def validate_all_ldap(self, task1, progress):

        # Check Reachability and Authentication of LDAP Server
        ldap_validated_list = []
        for ldap_id in self._ldap_prop["_ldap_ids"]:

            ldap_host = remove_protocol(self._ldap_prop[ldap_id]["LDAP_SERVER"])
            ldap_port = self._ldap_prop[ldap_id]["LDAP_PORT"]
            ssl_enabled = self._ldap_prop[ldap_id]["LDAP_SSL_ENABLED"]
            ldap_type = self._ldap_prop[ldap_id]["LDAP_TYPE"].lower()

            progress.log(Panel.fit(Text(f"LDAP Server Validation: {ldap_id}", style="bold cyan")))
            progress.log()

            validated = False
            authenticated = False
            check_list = []
            if ssl_enabled:
                self.__create_tmp_folder()
                crt_path = self.__get_file_from_folder(
                    os.path.join(os.getcwd(), "propertyFile", "ssl-certs", ldap_id.lower()),
                    [".crt", ".cer", ".pem", ".cert", ".key", ".arm"])

                validated = self.validate_server(progress=progress, server=ldap_host,
                                                 port=ldap_port, ssl_enabled=ssl_enabled,
                                                 cert_path=crt_path, display_rtt=True)


                if ldap_type == "microsoft active directory":
                    # For Microsoft Active Directory we need to check the Global Catalog (GC) port and host
                    # If GC port or host is defined, we need to take from the toml file else we default

                    try:
                        if self._ldap_prop[ldap_id]["LC_AD_GC_HOST"] != "<Optional>":
                            gc_host = remove_protocol(self._ldap_prop[ldap_id]["LC_AD_GC_HOST"])
                        else:
                            gc_host = ldap_host
                    except KeyError:
                        gc_host = ldap_host

                    try:
                        if self._ldap_prop[ldap_id]["LC_AD_GC_PORT"] != "<Optional>":
                            gc_port = self._ldap_prop[ldap_id]["LC_AD_GC_PORT"]
                        else:
                            gc_port = "3269"
                    except KeyError:
                        gc_port = "3269"

                    progress.log(Panel.fit(Text(f"MS Active Directory Global Catalog Server Validation: {ldap_id}", style="bold cyan")))
                    progress.log()

                    # Validate the Global Catalog (GC) port and host
                    validated = self.validate_server(progress=progress, server=gc_host,
                                                        port=gc_port, ssl_enabled=ssl_enabled,
                                                        cert_path=crt_path, display_rtt=False)

                check_list.append(validated)

                if validated:
                    authenticated = self.authenticate_ldap(ldap_id, progress, True, cert_path=crt_path)
                    check_list.append(authenticated)
            else:

                validated = self.validate_server(progress=progress, server=ldap_host,
                                                 port=ldap_port)

                if ldap_type == "microsoft active directory":
                    # For Microsoft Active Directory we need to check the Global Catalog (GC) port and host
                    # If GC port or host is defined, we need to take from the toml file else we default

                    try:
                        if self._ldap_prop[ldap_id]["LC_AD_GC_HOST"] != "<Optional>":
                            gc_host = remove_protocol(self._ldap_prop[ldap_id]["LC_AD_GC_HOST"])
                        else:
                            gc_host = ldap_host
                    except KeyError:
                        gc_host = ldap_host

                    try:
                        if self._ldap_prop[ldap_id]["LC_AD_GC_PORT"] != "<Optional>":
                            gc_port = self._ldap_prop[ldap_id]["LC_AD_GC_PORT"]
                        else:
                            gc_port = "3268"
                    except KeyError:
                        gc_port = "3268"

                    progress.log(Panel.fit(Text(f"MS Active Directory Global Catalog Server Validation: {ldap_id}", style="bold cyan")))
                    progress.log()

                    # Validate the Global Catalog (GC) port and host
                    validated = self.validate_server(progress=progress, server=gc_host,
                                                     port=gc_port, display_rtt=False)

                check_list.append(validated)

                if validated:
                    authenticated = self.authenticate_ldap(ldap_id, progress)
                    check_list.append(authenticated)

            self.is_validated[ldap_id] = all(check_list)
            ldap_validated_list.append(all(check_list))

            progress.advance(task1)
        return all(ldap_validated_list)

    # Create a function to check and validate all users and groups in LDAP
    def validate_ldap_users_groups(self, task2, progress):
        try:
            progress.log(Panel.fit(Text("LDAP Users and Groups Validation Check", style="bold cyan")))
            progress.log()

            # validate the bind dn is present in the ldap
            for ldap_id in self._ldap_prop["_ldap_ids"]:
                ssl_enabled = self._ldap_prop[ldap_id]["LDAP_SSL_ENABLED"]
                cert_path = ""
                server = self._ldap_prop[ldap_id]["LDAP_SERVER"]

                progress.log(Text(f"Searching LDAP: \"{server}\""))
                progress.log()

                if ssl_enabled:
                    self.__create_tmp_folder()
                    cert_path = self.__get_file_from_folder(
                        os.path.join(os.getcwd(), "propertyFile", "ssl-certs", ldap_id.lower()),
                        [".crt", ".cer", ".pem", ".cert", ".key", ".arm"])

                self.ldap_search(ldap_id, progress, ssl_enabled, cert_path)

            result_panel = ldap_search_results(self._entries_dict)

            progress.log(result_panel)
            progress.log()

            progress.advance(task2)

        except Exception as e:
            self._logger.exception(
                f"Exception from validate_ldap_users_groups function -  {str(e)}")

    def validate_scim(self, task, progress, idp_id="IDP"):

        progress.log(Panel.fit(Text(f"Validating IDP Token: \"{idp_id}\"", style="bold cyan")))
        token_endpoint = self._idp_prop[idp_id]["TOKEN_ENDPOINT"]
        client_id = self._idp_prop[idp_id]["CLIENT_ID"]
        client_secret = self._idp_prop[idp_id]["CLIENT_SECRET"]

        received_token = False

        # Retrieve token from IDP
        try:
            self._logger.info(f"Retrieving token from {idp_id} IDP...")
            progress.log(f"Retrieving token from {idp_id} IDP...")

            url = token_endpoint

            payload = f"grant_type=password&client_id={client_id}&client_secret={client_secret}"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            response = requests.request("POST", url, headers=headers, data=payload, verify=False, timeout=5)

            response.raise_for_status()
            received_token = True

        except Exception as e:
            self._logger.exception(f"Failed to retrieve token from {idp_id} IDP! Error: {str(e)}")

        if received_token:
            self._logger.info(f"Successfully retrieved token from {idp_id} IDP!")
            token_response = Text(f"\nToken received from \"{idp_id}\" IDP successfully, PASSED!\n", style="bold green")
        else:
            self._logger.info(f"Failed to retrieved token from {idp_id} IDP!")
            token_response = Text(f"\nUnable to retrieve token from \"{idp_id}\" IDP, FAILED!\n", style="bold red")

        progress.log(token_response)
        progress.advance(task)

        return received_token

    def get_entries(self):
        return {**self.get_users_and_groups(), **self.get_users(), **self.get_groups()}

    # function to get all users needed to be searched if present in ldap
    def get_users(self):
        users_list = []

        # Collect all users defined in user_group property file
        if "FNCM_LOGIN_USER" in self._user_group_prop.keys():
            users_list.append(self._user_group_prop["FNCM_LOGIN_USER"])

        if "ICN_LOGIN_USER" in self._user_group_prop.keys():
            users_list.append(self._user_group_prop["ICN_LOGIN_USER"])

        # Collect all users for ICC for email
        if self.component_prop_present:
            if "CSS" in self._component_prop.keys():
                users_list.append(self._component_prop["CSS"]["ARCHIVE_USER_ID"])

        # Collect all users for TaskManager
        if self.component_prop_present:
            if "PERMISSIONS" in self._component_prop.keys():
                users_list.extend(self._component_prop["PERMISSIONS"]["TASK_ADMIN_USER_NAMES"])
                users_list.extend(self._component_prop["PERMISSIONS"]["TASK_USER_USER_NAMES"])
                users_list.extend(self._component_prop["PERMISSIONS"]["TASK_AUDITOR_USER_NAMES"])

        if "GCD_ADMIN_USER_NAME" in self._user_group_prop.keys():
            users_list.extend(self._user_group_prop["GCD_ADMIN_USER_NAME"])

        # remove all duplicate users from list
        users_list = list(set(users_list))

        # Construct a dictionary to store username, count and ldap id
        users_dict = {}
        for user in users_list:
            users_dict[user] = {"type": ldap_entry_types.USER, "count": 0, "ldap_id": []}

        return users_dict

    # function to get all groups needed to be searched if present in ldap
    def get_groups(self):
        groups_list = []

        # Collect all groups defined in user_group property file
        if self.component_prop_present:
            if "PERMISSIONS" in self._component_prop.keys():
                groups_list.extend(self._component_prop["PERMISSIONS"]["TASK_ADMIN_GROUP_NAMES"])
                groups_list.extend(self._component_prop["PERMISSIONS"]["TASK_USER_GROUP_NAMES"])
                groups_list.extend(self._component_prop["PERMISSIONS"]["TASK_AUDITOR_GROUP_NAMES"])
        if "GCD_ADMIN_GROUPS_NAME" in self._user_group_prop.keys():
            groups_list.extend(self._user_group_prop["GCD_ADMIN_GROUPS_NAME"])

        # remove all duplicate groups from list
        groups_list = list(set(groups_list))

        # Construct a dictionary to store username, count and ldap id
        groups_dict = {}
        for group in groups_list:
            groups_dict[group] = {"type": ldap_entry_types.GROUP, "count": 0, "ldap_id": []}

        return groups_dict

        # Validates if user is present in the LDAP

    def get_users_and_groups(self):
        entry_list = []
        if "CONTENT_INITIALIZATION_ENABLE" in self._user_group_prop.keys():
            if self._user_group_prop["CONTENT_INITIALIZATION_ENABLE"]:
                for os_id in self._db_prop["_os_ids"]:
                    entry_list.extend(self._user_group_prop[os_id]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"])
        entry_dict = {}
        for entry in entry_list:
            entry_dict[entry] = {"type": ldap_entry_types.USER_GROUP, "count": 0, "ldap_id": []}

        return entry_dict

    def authenticate_ldap(self, ldap_id, progress, ssl_enabled=False, cert_path="") -> bool:
        server = self._ldap_prop[ldap_id]["LDAP_SERVER"]
        bind_dn = self._ldap_prop[ldap_id]["LDAP_BIND_DN"]

        progress.log(Text(f"Testing Authentication of \"{server}\" with Bind DN: \"{bind_dn}\""))
        progress.log()

        authenticated = False
        authenticated, connect = self.get_ldap_connection(ldap_id, progress, ssl_enabled, cert_path)

        if authenticated:
            if ssl_enabled == True :
                progress.log(Text(f"Successfully authenticated with \"{bind_dn}\" over SSL!", style="bold green"))
            else :
                progress.log(Text(f"Successfully authenticated with \"{bind_dn}\" over non-SSL!", style="bold green"))
            progress.log()

        return authenticated

    def get_user_password_list(self,bind_dn,bind_dn_password) :
        """
        Method name: get_user_password_list
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Fetch the encoded (user:password;) list from ldap property files as a string to use in the java command
        Parameters:
            bind_dn (str) : bind_dn of ldap
            bind_dn_password (str) : bind_dn password of ldap
        Returns:
           user_password_list (str) : list of encoded user:password; separated by commmas
        """
        user_password_list = ""
        match = re.search(r"(?i)(CN|UID)=([^,]+)", bind_dn)
        if match:
            ldap_username = match.group(2)
        user1 = self.encode_base64(ldap_username)
        password1 = self.encode_base64(bind_dn_password)
        user_password_list = user_password_list + f"username:{user1},password:{password1};"

        users = self.get_users()
        for user in users.keys() :
            if user != ldap_username :
                encoded_user = self.encode_base64(user)
                user_password_list = user_password_list + f"username:{encoded_user};"
        return user_password_list

    def get_group_list(self) :
        """
        Method name: get_group_list
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Fetch the list of groups from ldap property files as a string to use in the java command
        Parameters: None
        Returns:
           group_list (str) : list of groups separated by commmas
        """
        group_list = ""
        groups = self.get_groups()
        for group in groups.keys() :
            if group not in group_list :
                group_list = group_list + f"{group},"
        return group_list

    def get_usergroup_list(self,group_list) :
        """
        Method name: get_usergroup_list
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Fetch the list of user-groups from ldap property files as a string to use in the java command
        Parameters:
            group_list (str) : list of groups separated by commmas
        Returns:
           group_list (str) : appended list of groups separated by commmas
        """
        groups = self.get_users_and_groups()
        for group in groups.keys() :
            if group not in group_list :
                group_list = group_list + f"{group},"
        return group_list

    def get_ldap_connection(self, ldap_id, progress, ssl_enabled=False, cert_path=""):
        """
        Method name: get_ldap_connection
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Establishes and validates an LDAP connection.
                    This function attempts to connect to an LDAP server using the provided LDAP ID and credentials.
                    It supports both SSL and non-SSL connections and verifies the connection using the LdapTest.jar utility.
        Parameters:
            ldap_id (str): The identifier for the LDAP configuration from self._ldap_prop.
            progress (object): A logging/progress tracking object used for reporting errors and status.
            ssl_enabled (bool, optional): If True, SSL is enabled for the LDAP connection. Defaults to False.
            cert_path (str, optional): The file path to the SSL certificate when SSL is enabled. Defaults to an empty string.
        Returns:
           tuple:
            - authenticated (bool): True if LDAP authentication is successful, False otherwise.
            - valid_users_and_groups (dict): A dictionary containing valid users and groups retrieved from LDAP.
        Raises:
            Exception: If an error occurs while executing the LDAP connection command.
        Notes:
            - If SSL is enabled, the function converts the certificate to DER format and imports it into a Java Keystore (JKS).
            - Uses the LdapTest.jar utility to perform LDAP binding validation.
            - Logs errors and debug information throughout the process.
        """

        server = remove_protocol(self._ldap_prop[ldap_id]["LDAP_SERVER"])
        port = self._ldap_prop[ldap_id]["LDAP_PORT"]
        bind_dn = self._ldap_prop[ldap_id]["LDAP_BIND_DN"]
        bind_dn_password = self._ldap_prop[ldap_id]["LDAP_BIND_DN_PASSWORD"]
        base_dn = self._ldap_prop[ldap_id]["LDAP_BASE_DN"]
        group_base_dn = self._ldap_prop[ldap_id]["LDAP_GROUP_BASE_DN"]
        user_filter = self._ldap_prop[ldap_id]["LC_USER_FILTER"]
        group_filter = self._ldap_prop[ldap_id]["LC_GROUP_FILTER"]

        user_password_list = str(self.get_user_password_list(bind_dn,bind_dn_password))
        initial_group_list = self.get_group_list()
        group_list = str(self.get_usergroup_list(initial_group_list))

        # Validate LDAP Connection
        LDAP_TEST_JAR_PATH = os.getcwd() + "/helper_scripts/validate/jars/ldap/LdapTest.jar"
        # FIPS is always set to False. Reference defect : https://jsw.ibm.com/browse/DBACLD-154012.
        FIPS_FLAG = False
        authenticated = False
        valid_users_and_groups = ""

        if ssl_enabled:
            self._logger.info(f"LDAP certificate path is : {cert_path}")
            if not os.path.exists(cert_path):
                self._logger.error("LDAP certifcate not found.")
                return authenticated, valid_users_and_groups

            # Converting certificate to der format for keytool to import it into JKS
            DER_CERT_PATH = "/tmp/ldap-cert.der"
            self.remove_file(DER_CERT_PATH)
            self._logger.info(f"Converting certificate to der format.")
            self.run_command(f"openssl x509 -outform der -in {cert_path} -out {DER_CERT_PATH}")

            TRUSTSTORE_PATH = "/tmp/ldap-truststore.jks"
            TRUSTSTORE_PASSWORD = "changeit"
            self.remove_file(TRUSTSTORE_PATH)
            keytool_cmd = f"keytool -import -alias fncmLdapCerts -keystore {TRUSTSTORE_PATH} -file {DER_CERT_PATH} -storetype JKS -storepass changeit -noprompt"
            self._logger.info(f"Importing certificate to keystore.")
            self.run_command(keytool_cmd)

            self._logger.info(f"Checking ldap SSL connection test using LdapTest.jar for the server: {server} using Bind DN :{bind_dn}")
            ldap_test_cmd = (
                            f"java -Dsemeru.fips={FIPS_FLAG} -Djavax.net.ssl.trustStore={TRUSTSTORE_PATH} " 
                            f"-Djavax.net.ssl.trustStorePassword={TRUSTSTORE_PASSWORD} "
                            f"-jar {LDAP_TEST_JAR_PATH} -u 'ldaps://{server}:{port}' " 
                            f"-b '{base_dn}' -D '{bind_dn}' -w '{bind_dn_password}' "  
                            f"-additionalvalidation -gdn '{group_base_dn}' " 
                            f"-upl '{user_password_list}' -gl '{group_list}' " 
                            f"-uf '{user_filter}' -gf '{group_filter}'"
                        )
            java_msg = f"java -Dsemeru.fips={FIPS_FLAG} -Djavax.net.ssl.trustStore={TRUSTSTORE_PATH} -Djavax.net.ssl.trustStorePassword={TRUSTSTORE_PASSWORD} -jar {LDAP_TEST_JAR_PATH} -u 'ldaps://{server}:{port}' -b '{base_dn}' -D '{bind_dn}' -w '*****'"

        else :
            self._logger.info(f"Checking ldap non-SSL connection test using LdapTest.jar for the server: {server} using Bind DN :{bind_dn}")
            ldap_test_cmd = (
                            f"java -Dsemeru.fips={FIPS_FLAG} -jar {LDAP_TEST_JAR_PATH} "
                            f"-u 'ldap://{server}:{port}' -b '{base_dn}' " 
                            f"-D '{bind_dn}' -w '{bind_dn_password}' " 
                            f"-additionalvalidation -gdn '{group_base_dn}' " 
                            f"-upl '{user_password_list}' -gl '{group_list}' " 
                            f"-uf '{user_filter}' -gf '{group_filter}'"
                        )
            java_msg = f"java -Dsemeru.fips={FIPS_FLAG} -jar {LDAP_TEST_JAR_PATH} -u 'ldap://{server}:{port}' -b '{base_dn}' -D '{bind_dn}' -w '*****'"

        # Running java command for ldap binding using LdapTest.jar
        self._logger.info(f"Java command for ldap binding using LdapTest.jar : {ldap_test_cmd}")
        try :
            bind_output = self.run_command(ldap_test_cmd)
            self._logger.info(f"Ldap bind output : {bind_output}")
            if "AuthenticationException" in bind_output:
                progress.log(bind_output)
                progress.log(Text(f"LDAP Invalid Credentials", style="bold red"))
                msg = Text(f"Failed to authenticate \"{bind_dn}\"\n"
                            f"Please check the following values in property files:\n"
                            f" - LDAP_BIND_DN \n"
                            f" - LDAP_BIND_DN_PASSWORD\n")
                progress.log(msg, style="bold red")
                progress.log()
                panel = Panel.fit(java_msg, title="Execute the following command for more details", style="yellow", border_style="cyan")
                progress.log(panel)
                progress.log()
            elif "bind failed" in bind_output or "Error while binding to LDAP" in bind_output:
                progress.log(bind_output)
                progress.log(Text(f"Unable to connect to LDAP server '{server}' using Bind DN '{bind_dn}', please check configuration in ldap property again.",style="bold red"))
                progress.log()
                panel = Panel.fit(java_msg, title="Execute the following command for more details", style="yellow", border_style="cyan")
                progress.log(panel)
                progress.log()
            elif "Connected to:" in bind_output:
                authenticated = True
                valid_users_and_groups = self.parse_ldap_output(bind_output)
                self._logger.info(f"Users : {valid_users_and_groups['users']}")
                self._logger.info(f"Groups : {valid_users_and_groups['groups']}")
        except Exception as e:
            self._logger.error(f"An exception occured during validation ldap connection : {e}")
            progress.log(Text(f"LDAP Error: {e}", style="bold red"))
            msg = Text(f"Failed to authenticate \"{bind_dn}\"\n"
                        f"Please check the SSL Certificate", style="bold red")
            progress.log(msg)
            progress.log(Text(f"Failed to connect to LDAP server : '{server}'", style="bold red"))
            progress.log()
        return authenticated, valid_users_and_groups

    def encode_base64(self,data) :
        """
        Method name: encode_base64
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Encodes a string into its base64 format.
        Parameters:
            data (str) : The string to be encoded.
        Returns:
            encoded_data (str): The encoded string.
        Raises:
            Exception: If an error occurs while encoding the string.
        """
        try :
            self._logger.info(f"Encoding data : {data}.")
            encoded_data = base64.b64encode(data.encode()).decode()
            self._logger.info(f"Encoded data : {encoded_data}.")
            return encoded_data
        except Exception as e:
            self._logger.error(f"An error occured during encoded the data : {e}")

    def run_command(self,command):
        """
        Method name: run_command
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description:  Executes shell commands
        Parameters:
            command (str): The command to the to be executed.
        Returns:
            str: The standard output (stdout) if the command runs successfully.
                The standard error (stderr) if an error occurs.
        Raises:
            Exception: If an error occurs while executing the command.
        """
        try :
            self._logger.info(f"Executing command : {command}")
            result = subprocess.run(shlex.split(command),capture_output=True, text=True)
            if result.returncode != 0:
                self._logger.error(f"\nAn error occured during execution of the command -- stdout : {result.stdout}, stderror : {result.stderr}")
                return result.stderr
            self._logger.info(f"Output of execution : {result.stdout}")
            return result.stdout
        except Exception as e :
            self._logger.error(f"An exception occured during running the command -- {command} : {e}")
            return str(e)

    def remove_file(self,file_path) :
        """
        Method name: remove_file
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description:  Removes the file at the given file path.
        Parameters:
            file_path (str): The path to the file to be removed.
        Returns: None
        Raises:
            Exception: If an error occurs while removing the file.
        """
        try :
            if os.path.exists(file_path) :
                os.remove(file_path)
                self._logger.info(f"Removed the file : {file_path}")
        except Exception as e:
            self._logger.error(f"An exception occured during removal of file : {file_path}. Error : {e}")

    def parse_ldap_output(self,output):
        """
        Method name: parse_ldap_output
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description:  Retrives the validated users and groups from the ldap bind output
        Parameters:
            output (str): The ldap bind output
        Returns:
            users_and_groups (dict): The valid users and groups from the ldap bind output
        Raises:
            Exception: If an error occurs while parsing the ldap output.
        """
        try:
            self._logger.info("Fetching valid users and groups from ldap bind output.")
            users_and_groups = {
                "users": [],
                "groups": []
            }

            # Set of all the users
            all_users = set()

            # Extract users and their authentication status
            self._logger.info(f"Extracting users and their authentication status")
            user_pattern = re.compile(r"(?P<username>\S+)\s+\|\s+(?P<valid>true|false)\s+\|\s+(?P<auth>true|false)")
            for match in user_pattern.finditer(output):
                username = match.group("username")
                all_users.add(username)
                if match.group("auth") == "true" and match.group("valid") == "true":
                    users_and_groups["users"].append(username)
            self._logger.info(f"Valid users are : {users_and_groups['users']}")

            # Extract groups and their validity
            self._logger.info(f"Extracting groups and their validity")
            group_pattern = re.compile(r"(?P<groupname>\S+)\s+\|\s+(?P<valid>true)")
            for match in group_pattern.finditer(output):
                groupname = match.group("groupname")
                if groupname not in all_users:
                    users_and_groups["groups"].append(groupname)
            self._logger.info(f"Valid groups are : {users_and_groups['groups']}")
            return users_and_groups
        except Exception as e:
            self._logger.error(f"An exception occured during fetching valid users and groups: {e}.")
            return


    def ldap_item_exists(self, entry, valid_entry):
        """
        Method name: ldap_item_exists
        Description: Checks if the user/group entry from property file is valid.
                    Checks if the property file entry is present in the valid user/groups from the bind output.
        Parameters:
            entry (str): The property file entry
            valid_entry (list): A list containing the valid users or groups from the bind output.
        Returns:
            If the entry is valid, returns the entry (str). Else returns None.
        Raises:
            None
        """
        if entry in valid_entry :
            return entry
        else :
            return

    def ldap_search(self, ldap_id, progress, ssl_enabled=False, cert_path=""):
        """
        Method name: ldap_search
        Description: Authenticates and get valid users and groups from the LDAP server.
                    Then if authenticated usccessfully, updates the valid entries from dictionary _entries_dict.
        Parameters:
            ldap_id (str): The identifier for the LDAP configuration from self._ldap_prop.
            progress (object): A logging/progress tracking object used for reporting errors and status.
            ssl_enabled (bool, optional): If True, SSL is enabled for the LDAP connection. Defaults to False.
            cert_path (str, optional): The file path to the SSL certificate when SSL is enabled. Defaults to an empty string.
        Returns: None
        Raises:
            Exception: If an error occurs while performing ldap search.
        """
        try:
            authenticated, valid_users_and_groups = self.get_ldap_connection(ldap_id, progress, ssl_enabled, cert_path)

            if authenticated:
                for entry, value in self._entries_dict.items():
                    if value['type'] == ldap_entry_types.USER:
                        if self.ldap_item_exists(entry,valid_users_and_groups['users']):
                            self._entries_dict[entry]["count"] += 1
                            self._entries_dict[entry]["ldap_id"].append(ldap_id)

                    elif value['type'] == ldap_entry_types.GROUP:
                        if self.ldap_item_exists(entry,valid_users_and_groups['groups']):
                            self._entries_dict[entry]["count"] += 1
                            self._entries_dict[entry]["ldap_id"].append(ldap_id)

                    elif value['type'] == ldap_entry_types.USER_GROUP:
                        if self.ldap_item_exists(entry,valid_users_and_groups['users']):
                            self._entries_dict[entry]["type"] = ldap_entry_types.USER
                            self._entries_dict[entry]["count"] += 1
                            self._entries_dict[entry]["ldap_id"].append(ldap_id)
                            continue
                        if self.ldap_item_exists(entry,valid_users_and_groups['groups']):
                            self._entries_dict[entry]["type"] = ldap_entry_types.GROUP
                            self._entries_dict[entry]["count"] += 1
                            self._entries_dict[entry]["ldap_id"].append(ldap_id)
                            continue
        except Exception as e:
            self._logger.info(f"Error found in ldap_search function in validation script --- {str(e)}")

    # Validates a single LDAP, defaults to the first one by its id: "LDAP"
    def validate_server(self, progress, server, port, ssl_enabled=False, cert_path="", display_rtt=True, pg=False):
        connected = False

        progress.log(Text(f"Validating Server \"{server}\" Reachability"))
        progress.log()

        # Test for SSL connections
        # Return a connection object, RTT and a boolean indicating if the connection was successful
        if ssl_enabled:
            conn_result, rtt, connected = connect_to_server(host=server, port=int(port), ssl=True, client_cert_file=cert_path, pg=pg,  progress=progress)
        else:
            conn_result, rtt, connected = connect_to_server(host=server, port=int(port), progress=progress)

        # Construct the message to be displayed
        # If the SSL connection was successful, display the cipher
        # If connection is successful display the RTT
        # RTT display can be disabled by setting display_rtt to False (RTT for Database is calculated through JDBC driver)
        if connected:
            if ssl_enabled:
                message = Text(f"\nReachability to \"{server}\" succeeded over SSL!\n", style="bold green")

                progress.log(message)
                progress.log()

                # If SSL connections was successful, then cipher passed
                self.output_cipher(conn_result.get_cipher_name(),
                                   conn_result.get_protocol_version_name(), progress)
            else:
                message = Text(f"\nReachability to \"{server}\" succeeded!\n", style="bold green")
                progress.log(message)
                progress.log()

            if display_rtt:
                self.output_latency(rtt, progress, "LDAP")
        else:
            message = Text(f"\nReachability to \"{server}\" failed!\n"
                           f"Please check configuration server host and port in Property Files", style="bold red")
            progress.log(message)
            progress.log()

        return connected

    # Output cipher for the supplied connection
    @staticmethod
    def output_cipher(cipher, protocol, progress):
        message = Text(f"SSL protocol used: \"{protocol}\", is supported!\n", style="bold green")
        progress.log(message)
        progress.log()

        message = Text(f"SSL cipher used: \"{cipher}\", is accepted!\n", style="bold green")
        progress.log(message)
        progress.log()

    # Output latency for the supplied connection
    @staticmethod
    def output_latency(rtt, progress, type="LDAP"):

        if type == "LDAP":
            max_time = 300
            min_time = 100
        else:
            max_time = 30
            min_time = 10

        if rtt < min_time:
            message = f"Acceptable Latency Range: 0ms - {min_time}ms"
            style = "bold green"
        elif min_time < rtt < max_time:
            message = f"Performance Degradation Latency Range: {min_time}ms - {max_time}ms"
            style = "bold yellow"
        else:
            message = f"Potential Failure Latency Range: > {max_time}ms"
            style = "bold red"

        progress.log(Text("Detected Connection Latency: {:.2f}ms ".format(rtt), style=style))
        progress.log(Text(message, style=style))
        progress.log()

    # Use JAR to test DB connection
    def __check_connection_with_jar(self, jar_cmd, progress):
        self.__check_java()
        try:
            if platform.system() == 'Windows':
                output = subprocess.check_output(["powershell.exe", jar_cmd], shell=True, stderr=subprocess.PIPE,
                                                 universal_newlines=True)
            else:
                output = subprocess.check_output(jar_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            round_trip_statement = output.split("Round Trip time:")[1]
            match = re.search(r'([\d.]+)', round_trip_statement)
            if match:
                self.roundtriptime = float(match.group(1))

            return True
        except subprocess.CalledProcessError as error:
            self._logger.info(error.stderr)
            progress.log()
            progress.log(Text(error.stderr, style="bold red"))

            if "PKIX path building failed" in error.stderr:
                progress.log()
                progress.log(Text("SSL Certificate could not be validated, please check the supplied certificate in propertyFile/ssl-certs.", style="bold red"))

            return False

    def get_unique_storageclass(self) -> set:
        sc_set = {self._deploy_prop["SLOW_FILE_STORAGE_CLASSNAME"], self._deploy_prop["MEDIUM_FILE_STORAGE_CLASSNAME"],
                  self._deploy_prop["FAST_FILE_STORAGE_CLASSNAME"]}
        return sc_set

    def validate_all_storage_classes(self, task2, progress):
        # Uses a set to skip checked the same storage class twice
        sc_set = self.get_unique_storageclass()

        for storage_class in sc_set:
            progress.log(Panel.fit(Text(f"Validating storage class: {storage_class}", style="bold cyan")))
            self.validate_sample_sc(storage_class, "ReadWriteMany", "fncm-test-pvc", task2, progress)

    def __check_pvc_liveliness(self, sample_pvc_name, task2, progress):  # Create new temp yaml sample
        # 30 attempts, 10 seconds each; total ~300 seconds / 5 mins
        TIMEOUT_ATTEMPTS = 30
        SLEEP_TIMER = 10

        if platform.system() == 'Windows':
            kubectl_cmd = f"kubectl get pvc | findstr {sample_pvc_name} | findstr \"Bound\""
        else:
            kubectl_cmd = f"kubectl get pvc | grep {sample_pvc_name}| grep -q -m 1 \"Bound\""

        for i in range(TIMEOUT_ATTEMPTS):
            progress.log(f"\nChecking for {sample_pvc_name} liveness - Attempt {i + 1}/{TIMEOUT_ATTEMPTS}\n")
            validated = True
            try:
                subprocess.check_output(kubectl_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            except subprocess.CalledProcessError as error:
                # If cannot find pvc in bound PVC grep, validation is not complete
                # and will keep waiting
                if "returned non-zero exit status 1" in str(error):
                    validated = False
                    progress.log(Text(f"\n\"{sample_pvc_name}\" not yet found, waiting {SLEEP_TIMER} seconds to retry"))
                    time.sleep(SLEEP_TIMER)
                else:
                    self._logger.exception(error)
                    progress.log()
                    progress.log(f"Error occurred while when checking \"{sample_pvc_name}\" liveness")
                    progress.log()
                    progress.log(Syntax(str(error.stderr), "bash", theme="ansi_dark"))
            if validated:
                progress.log()
                progress.log(Text(f"Verification for PVC: \"{sample_pvc_name}\" PASSED!\n", style="bold green"))
                progress.advance(task2)
                return True
        # Passed 60 seconds and all attempts, still cannot find PVC
        self._logger.info(f"Failed to allocate the persistent volumes using PVC: \"{sample_pvc_name}\"!")
        progress.log()
        progress.log(Text(f"Failed to allocate PVC: \"{sample_pvc_name}\"!", style="bold red"))
        progress.advance(task2)
        return False

    # Creates a storage class yaml to apply
    def validate_sample_sc(self, sc_name, sc_mode, sample_pvc_name, task2, progress):
        # check if storage class is present
        kubectl_cmd = f"kubectl get storageclasses -o custom-columns=:metadata.name"
        validated = True
        try:
            output = subprocess.check_output(kubectl_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            storage_classes = output.strip().split('\n')
            if sc_name in storage_classes:
                validated = True
            else:
                validated = False

            if validated:
                progress.log()
                progress.log(Text(f"Verification for Storage Class: \"{sc_name}\" PASSED!\n", style="bold green"))
            if not validated:
                self._logger.info(f"Failed to find storage class: \"{sc_name}\"!\n")
                progress.log()
                progress.log(Text(f"Failed to find storage class: \"{sc_name}\"!\n", style="bold red"))
                self.is_validated[sc_name] = False
                progress.advance(task2)
                return self.is_validated[sc_name]

        except subprocess.CalledProcessError as error:
            self._logger.info(error)
            progress.log()
            progress.log(f"Error occurred while validating \"{sc_name}\"\n"
                         f"Sample PVC will still be created, without storage class check!", style="bold yellow")
            validated = False

        # remove existing temp file if previously not removed
        sample_yaml_path = os.path.join(self.__create_tmp_folder(), sc_name + ".yaml")

        if os.path.exists(sample_yaml_path):
            self._logger.info("Temporary yaml file exists and will be removed before a new file is created")
            os.remove(sample_yaml_path)

        # Writing storage class vars to sample file
        sc_template = string.Template((open(self._STORAGE_CLASS_TEMPLATE_YAML, encoding='UTF-8')).read())
        finished_output = sc_template.safe_substitute(sc_name=sc_name,
                                                      sc_mode=sc_mode,
                                                      sample_pvc_name=sample_pvc_name)
        with open(sample_yaml_path, "w", encoding='UTF-8') as output:
            output.write(finished_output)

        self.kubectl_apply(sample_yaml_path)
        progress.log()
        progress.log(f"Sample PVC created with storage class: {sc_name}")
        self.is_validated[sc_name] = self.__check_pvc_liveliness(sample_pvc_name, task2, progress)
        self.kubectl_delete(sample_yaml_path)

        os.remove(sample_yaml_path)

        return self.is_validated[sc_name]

    def kubectl_apply(self, yaml_path):
        self.__check_kubectl()
        kubectl_cmd = "kubectl apply -f \"" + yaml_path + "\""
        response = None
        try:
            response = subprocess.check_output(kubectl_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
        except subprocess.CalledProcessError as error:
            if "metadata.resourceVersion" in str(error.stderr):
                kubectl_cmd = "kubectl replace -f \"" + yaml_path + "\""
                response = subprocess.check_output(kubectl_cmd, shell=True, stderr=subprocess.PIPE,
                                                   universal_newlines=True)
            else:
                self._logger.exception(
                    f"Exception applying '{yaml_path}' -  {str(error.stderr)}")
        return response

    def kubectl_delete(self, yaml_path):
        self.__check_kubectl()
        kubectl_cmd = "kubectl delete -f \"" + yaml_path + "\""
        response = None
        try:
            response = subprocess.check_output(kubectl_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
        except subprocess.CalledProcessError as error:
            self._logger.exception(
                f"Exception deleting '{yaml_path}' -  {str(error.stderr)}")
        return response

    # Looks for yaml files in the folder path and applies it with kubectl, will not look int subfolders.
    def auto_apply_all_in_folder(self, folder_path):
        yaml_ext = [".yaml", ".yml"]
        files = self.__files_in_dir(folder_path, yaml_ext)
        if len(files) == 0:
            self._logger.info(f"No files with extension:{str(yaml_ext)} found in {folder_path}!")

        for f in files:
            response = self.kubectl_apply(os.path.join(folder_path, f))
            print(Panel.fit(Text(response.strip(), style="bold cyan")))

    def auto_apply_secrets_ssl(self):
        self.auto_apply_all_in_folder(folder_path=os.path.join(os.getcwd(), "generatedFiles", "secrets"))
        # only if ssl secrets folder is present will they be applied
        # Build path where secrets are generated
        secret_directories = [os.path.join(os.getcwd(), "generatedFiles", "ssl"),
                              os.path.join(os.getcwd(), "generatedFiles", "ssl", "trusted-certs")]

        for folder_path in secret_directories:
            if os.path.exists(folder_path):
                self.auto_apply_all_in_folder(folder_path=folder_path)

    def auto_apply_cr(self):
        # Applying FNCM CR
        response = self.kubectl_apply(os.path.join(os.getcwd(), "generatedFiles", "ibm_fncm_cr_production.yaml"))
        print(Panel.fit(Text(response.strip(), style="bold cyan")))
        return True
