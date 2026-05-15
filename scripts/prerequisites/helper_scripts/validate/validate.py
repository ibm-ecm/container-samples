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

import base64
import inspect
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
from ipaddress import ip_address, IPv4Address, IPv6Address
from urllib.parse import urlparse, urljoin

import jinja2
import requests
import time
import typer
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from requests import Session
from requests.adapters import HTTPAdapter
from rich import print
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from ..utilities import kubernetes_utilites as k
from ..utilities.interface import idp_token_claim_results, ldap_search_results, scim_entry_types, \
    scim_search_results, scim_admin_group_results, ldap_entry_types, scim_admin_user_results
from ..utilities.prerequisites_utilites import command_available, \
    collect_visible_files, \
    connect_to_server, clean_and_combine_pem_files, create_ssl_context, check_java_version, split_pem

requests.packages.urllib3.disable_warnings()


# Function to remove protocol from URL
def remove_protocol(url):
    hostname = urlparse(url).hostname
    if hostname is None:
        hostname = url
    return hostname


class Validate:

    class CustomHTTPAdapter(HTTPAdapter):
        def __init__(self, ssl_context=None, **kwargs):
            self.ssl_context = ssl_context
            super().__init__(**kwargs)

        def init_poolmanager(self, *args, **kwargs):
            # Pass the custom SSL context to the base class's init_poolmanager
            kwargs['ssl_context'] = self.ssl_context
            super().init_poolmanager(*args, **kwargs)

    _JAR_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "jars")

    # Using the same JDBC jar files for all Versions
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
                 scim_prop=None,
                 component_prop=None,
                 user_group_prop=None,
                 pvc_size='10Mi',
                 namespace=''):

        self._kube = k.KubernetesUtilities(logger)

        self._namespace = namespace

        self.component_prop_present = False
        if db_prop:
            self._db_prop = db_prop
        else:
            self._db_prop = {}

        if ldap_prop:
            self._ldap_prop = ldap_prop
        else:
            self._ldap_prop = {}

        if deploy_prop:
            self._deploy_prop = deploy_prop
        else:
            self._deploy_prop = {}

        if idp_prop:
            self._idp_prop = idp_prop
        else:
            self._idp_prop = {}

        if scim_prop:
            self._scim_prop = scim_prop
        else:
            self._scim_prop = {}

        if component_prop:
            self._component_prop = component_prop
            self.component_prop_present = True

        if user_group_prop:
            self._user_group_prop = user_group_prop
        else:
            self._user_group_prop = {}


        # For DB2 RDS and DB2 RDS HADR we use the same jar as DB2 but we pass the -db2rds flag hence setting the jar and jdbc path to DB2 folder path
        # Using same jar as DB2 for DB2HADR
        if self._db_prop["DATABASE_TYPE"].lower() in ["db2rds", "db2rdshadr", "db2hadr"]:
            self._DB_JDBC_PATH = self.__get_file_from_folder(os.path.join(self._JDBC_DIR, "db2"),
                                                             [".jar"])
            self._DB_CONNECTION_JAR_PATH = self.__get_file_from_folder(
                os.path.join(self._JAR_DIR, "db2"), [".jar"])
        else:
            self._DB_JDBC_PATH = self.__get_file_from_folder(
                os.path.join(self._JDBC_DIR, self._db_prop["DATABASE_TYPE"]),
                [".jar"])
            self._DB_CONNECTION_JAR_PATH = self.__get_file_from_folder(
                os.path.join(self._JAR_DIR, self._db_prop["DATABASE_TYPE"]), [".jar"])

        self._LDAP_JAR_PATH = self.__get_file_from_folder(os.path.join(self._JAR_DIR, "ldap"), [".jar"])

        self._logger = logger
        self._pvc_size = pvc_size

        self.is_validated = {}
        self.ldap_user_groups = {}
        self.roundtriptime = 0

        if ldap_prop:
            self._entries_dict = self.get_entries_ldap()

        if scim_prop:
            self._entries_dict = self.get_entries_scim()
        self.username_userid_map = {}

        if "FIPS_SUPPORT" in self._deploy_prop.keys():
            self._fips_enabled = self._deploy_prop["FIPS_SUPPORT"]
        else:
            self._fips_enabled = False

        # Setting for Truststore
        self.__create_tmp_folder()
        self._alias = "fncmp12Certs"
        self._dnsname = "CN=fncmp12"
        self._storetype = "PKCS12"
        self._truststore_pwd = "changeit"
        self._truststore_folder = os.path.join(self._TMP_DIR, "truststore")
        self._truststore_name = "fncm_truststore.p12"
        self._truststore_path = os.path.join(self._truststore_folder, self._truststore_name)

        self._template_folder = os.path.join(os.getcwd(), "helper_scripts", "validate", "templates")

        self.cleanup_tmp()

        # Load all jinja templates
        self._template_loader = jinja2.FileSystemLoader(self._template_folder)
        self._template_env = jinja2.Environment(loader=self._template_loader, trim_blocks=True)

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
    def scim_prop(self):
        return self._scim_prop

    @scim_prop.setter
    def scim_prop(self, scim_prop):
        self._scim_prop = scim_prop

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

    def cleanup_tmp(self):
        if os.path.exists(self._TMP_DIR):
            shutil.rmtree(self._TMP_DIR)
            self.__recreate_folder(self._TMP_DIR)

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
                "Please see https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.p8.performance.doc/p8ppi308.htm.",
                style="bold green"))
            progress.log(max_transactions)
            progress.log()
        if db_type == "sqlserver":
            xa_enabled = Panel.fit(Text(
                "Ensure XA Transactions have been enabled.\n"
                "Please see https://www.ibm.com/docs/SSNW2F_5.7.0/com.ibm.p8.planprepare.doc/p8ppi027.htm.",
                style="bold green"))
            progress.log(xa_enabled)
            progress.log()

        if self._deploy_prop["FNCM_Version"] == "5.5.8":
            # Check for reachability and authentication of DB Server
            progress.log(Panel.fit(Text("Validating GCD Database Connection"), style="bold cyan"))
            progress.log()
            self.validate_db("GCD", task3, progress)

            for os_id in self._db_prop["_os_ids"]:
                progress.log(Panel.fit(Text(f"Validating {os_id} Database Connection"), style="bold cyan"))
                progress.log()
                self.validate_db(os_id, task3, progress)

            progress.log(Panel.fit(Text("Validating ICN Database Connection"), style="bold cyan"))
            progress.log()
            self.validate_db("ICN", task3, progress)
        else:
            if "CPE" in self._deploy_prop.keys():
                if self._deploy_prop["CPE"]:
                    # Check for reachability and authentication of DB Server
                    progress.log(Panel.fit(Text("Validating GCD Database Connection"), style="bold cyan"))
                    progress.log()
                    self.validate_db("GCD", task3, progress)

                    for os_id in self._db_prop["_os_ids"]:
                        progress.log(Panel.fit(Text(f"Validating {os_id} Database Connection"), style="bold cyan"))
                        progress.log()
                        self.validate_db(os_id, task3, progress)

            if "BAN" in self._deploy_prop.keys():
                if self._deploy_prop["BAN"]:
                    progress.log(Panel.fit(Text("Validating ICN Database Connection"), style="bold cyan"))
                    progress.log()
                    self.validate_db("ICN", task3, progress)

    def parse_shell_command(self, parameter):
        # Create a function to escape any single quotes in the password
        # This is needed for the DB connection jar

        # Escape any single quotes in the password
        parameter = parameter.replace("'", "'\\''")

        return parameter

    def validate_server_name(self, server_name, progress):
        """
        Method_name: validate_server_name
        Description: Validates the server name and returns a boolean indicating whether it is valid.

        Parameters:
            server_name (str): The server name to validate.
            progress (Any): An object that provides a logging method for progress updates.

        Returns:
            bool: True if the server name is valid, False otherwise.
        """
        hostname_pattern = re.compile(
            r"^(?=.{1,253}$)(?!-)[A-Z\d-]{1,63}(?<!-)(\.(?!-)[A-Z\d-]{1,63}(?<!-))*\.?$",
            re.IGNORECASE
        )
        if server_name.startswith("[") and server_name.endswith("]"):
            stripped_server_name = server_name[1:-1]
            try:
                parsed_ip = ip_address(stripped_server_name)
                if isinstance(parsed_ip, IPv6Address):
                    return True
                elif isinstance(parsed_ip, IPv4Address):
                    message = Text(
                        "IPv4 addresses must not be enclosed in brackets."
                        "\nPlease update SERVERNAME in the property files and try again.",
                        style="bold red"
                    )
                    progress.log(message)
                    progress.log()
                    return False
            except ValueError:
                message = Text(
                    "Invalid IPv6 address format inside brackets."
                    "\nPlease update SERVERNAME in the property files and try again.",
                    style="bold red"
                )
                progress.log(message)
                progress.log()
                return False
        try:
            parsed_ip = ip_address(server_name)
            if isinstance(parsed_ip, IPv4Address):
                return True
            else:
                message = Text(
                    "IPv6 addresses must be enclosed in brackets [...]"
                    "\nPlease update SERVERNAME in the property files and try again.",
                    style="bold red"
                )
                progress.log(message)
                progress.log()
                return False
        except ValueError:
            if re.fullmatch(r"[0-9.:]+", server_name):
                message = Text(
                    "IPv4 addresses must be in valid format."
                    "\nPlease update SERVERNAME in the property files and try again.",
                    style="bold red"
                )
                progress.log(message)
                progress.log()
                return False
            if hostname_pattern.fullmatch(server_name):
                return True
            else:
                message = Text(
                    "The hostname contains invalid characters or format."
                    "\nPlease update SERVERNAME in the property files and try again.",
                    style="bold red"
                )
                progress.log(message)
                progress.log()
                return False

    def validate_db(self, db_label, task3, progress):
        db_name = self._db_prop[db_label]['DATABASE_NAME']
        db_user = self._db_prop[db_label]['DATABASE_USERNAME']
        db_pwd = self._db_prop[db_label]['DATABASE_PASSWORD']
        db_type = self._db_prop['DATABASE_TYPE'].lower()
        ssl_enabled = self._db_prop['DATABASE_SSL_ENABLE']
        ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", db_label.lower())

        if db_type == "oracle":
            servername_regex = re.compile(r"(?<=HOST=)[\s]*[^)\s]*")
            db_servername = servername_regex.search(self._db_prop[db_label]['ORACLE_JDBC_URL']).group()
            db_servername = remove_protocol(db_servername)
            port_regex = re.compile(r"(?<=PORT=)[\s]*[^)\s]*")
            db_port = port_regex.search(self._db_prop[db_label]['ORACLE_JDBC_URL']).group()
        else:
            db_servername = remove_protocol(self._db_prop[db_label]['DATABASE_SERVERNAME'])
            db_port = self._db_prop[db_label]['DATABASE_PORT']

        is_valid_name = self.validate_server_name(db_servername, progress)
        if not is_valid_name:
            self.is_validated[db_label] = False
            progress.advance(task3)
            return False

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
                                                 display_rtt=False, cert_path=ssl_cert_folder)

            if not connected:
                progress.log(Panel.fit(
                    Text(f"Reachability over SSL failed. Attempting connection without certificate verification."), style="bold yellow"))
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

        connected_str = Text(f"Successfully connected to database \"{db_name}\"!", style="bold green")
        not_connected_str = Text(f"Unable to connect to database \"{db_name}\" " \
                                 + f"on database server \"{db_servername}\", " \
                                 + "please check database toml file again.", style="bold red")

        jar_cmd = ''
        class_path_delim_char = ''
        if platform.system() == 'Windows':
            class_path_delim_char = ';'
        else:
            class_path_delim_char = ':'

        if ssl_enabled:
            cert_dir = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", db_label.lower())

            if db_type in ["db2", "db2hadr"]:

                self.__add_cert_to_tmp_truststore(cert_dir, db_label.lower(), progress)

                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-D\"javax.net.ssl.trustStoreType={self._storetype}\" "
                           + f"-D\"javax.net.ssl.trustStore={self._truststore_path}\" "
                           + f"-Djavax.net.ssl.trustStorePassword='{self._truststore_pwd}' "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" "
                           + f"DB2Connection -h '{db_servername}' "
                           + f"-p {db_port} -db '{db_name}' "
                           + f"-u '{db_user}' -pwd '{db_pwd}' "
                           + f"-ssl -ca \"{self._truststore_path}\" -capassword '{self._truststore_pwd}'")

            # For DB2 RDS and DB2 RDS HADR we use the same jar as DB2 but we pass the -db2rds flag
            elif db_type in ["db2rds", "db2rdshadr"]:

                self.__add_cert_to_tmp_truststore(cert_dir, db_label.lower(), progress)

                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-D\"javax.net.ssl.trustStoreType={self._storetype}\" "
                           + f"-D\"javax.net.ssl.trustStore={self._truststore_path}\" "
                           + f"-Djavax.net.ssl.trustStorePassword='{self._truststore_pwd}' "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" "
                           + f"DB2Connection -h '{db_servername}' "
                           + f"-p {db_port} -db '{db_name}' "
                           + f"-u '{db_user}' -pwd '{db_pwd}' "
                           + f"-ssl -ca \"{self._truststore_path}\" -capassword '{self._truststore_pwd}' "
                           + "-db2rds")


            elif db_type == "oracle":

                self.__add_cert_to_tmp_truststore(cert_dir, db_label.lower(), progress)

                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-D\"javax.net.ssl.trustStoreType={self._storetype}\" "
                           + f"-D\"javax.net.ssl.trustStore={self._truststore_path}\" "
                           + f"-Djavax.net.ssl.trustStorePassword='{self._truststore_pwd}' "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" "
                           + f"OracleConnection -url '{self._db_prop[db_label]['ORACLE_JDBC_URL']}' "
                           + f"-u '{db_user}' -pwd '{db_pwd}' "
                           + f"-ssl -trustorefile \"{self._truststore_path}\" -trustoretype \"{self._storetype}\" "
                           + f"-trustorePwd '{self._truststore_pwd}'")

            elif db_type == "sqlserver":
                self.__add_cert_to_tmp_truststore(cert_dir, db_label.lower(), progress)

                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-D\"javax.net.ssl.trustStoreType={self._storetype}\" "
                           + f"-D\"javax.net.ssl.trustStore={self._truststore_path}\" "
                           + f"-Djavax.net.ssl.trustStorePassword='{self._truststore_pwd}' "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" "
                           + f"SQLConnection -h '{db_servername}' -p {db_port} -d '{db_name}' "
                           + f"-u '{db_user}' -pwd '{db_pwd}' "
                           + f"-ssl \'encrypt=true;trustServerCertificate=false;"
                           + f"trustStore={self._truststore_path};"
                           + f"trustStorePassword={self._truststore_pwd}\'")

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

                jar_cmd = (
                    f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -D\"com.ibm.jsse2.overrideDefaultTLS=true\" "
                    f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                    f"{self._DB_CONNECTION_JAR_PATH}\" "
                    f"PostgresConnection -h '{db_servername}' -p {db_port} -db '{db_name}' "
                    f"-u '{db_user}' -pwd '{db_pwd}' -sslmode {self._db_prop['SSL_MODE']} "
                    f"{auth_str}")
        else:
            if db_type == "db2":
                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" DB2Connection "
                           + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}'")
            # For DB2 RDS and DB2 RDS HADR we use the same jar as DB2 but we pass the -db2rds flag
            elif db_type in ["db2rds", "db2rdshadr"]:
                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" DB2Connection "
                           + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -db2rds")
            elif db_type == "oracle":
                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" OracleConnection "
                           + f"-url '{self._db_prop[db_label]['ORACLE_JDBC_URL']}' -u '{db_user}' -pwd '{db_pwd}'")
            elif db_type == "sqlserver":
                jar_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" "
                           + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                           + f"{self._DB_CONNECTION_JAR_PATH}\" SQLConnection "
                           + f"-h '{db_servername}' -p {db_port} -d '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -ssl 'encrypt=false'")
            elif db_type == "postgresql":
                jar_cmd = (
                        f"java -D\"semeru.fips={self._fips_enabled}\" -D\"user.language=en\" -D\"user.country=US\" -Dcom.ibm.jsse2.overrideDefaultTLS=true "
                        + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}"
                        + f"{self._DB_CONNECTION_JAR_PATH}\" PostgresConnection "
                        + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -sslmode disable")

        db_is_connected = self.__check_connection_with_jar(jar_cmd, progress)
        if db_is_connected:
            self._logger.info(f"Successfully connected to {db_label} database!")

            progress.log()
            progress.log(Panel.fit(connected_str, style="bold green"))


            self.output_latency(self.roundtriptime, progress, "DB")

        else:
            self._logger.info(f"Failed to connect to {db_label} database!")
            progress.log()
            progress.log(Panel.fit(not_connected_str, style="bold red"))
            progress.log()
            panel = Panel.fit(jar_cmd, title="Execute the following command for more details", style="bold yellow")
            progress.log(panel)
            progress.log()
        self.is_validated[db_label] = db_is_connected
        progress.advance(task3)
        return db_is_connected

    # Returns the first file found in a directory
    # that has one of the extensions provided.
    def __get_file_from_folder(self, file_dir, extensions: list):
        files = self.__files_in_dir(file_dir, extensions)
        if len(files) == 0:
            self._logger.info(f"No files with extension:{str(extensions)} found in {file_dir}!")
            return ''
        return os.path.join(file_dir, files[0])

    # Returns a list of files that has matching extensions
    def __files_in_dir(self, dir_path, extensions: list = []):
        # list to store files
        res = []
        # Iterate directory
        files = collect_visible_files(dir_path)
        for file in files:
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
                f"Exception converting key to DER conversion -  {str(e)}")

        return output_path

    # Function to add a certificate to a trust store
    def __add_cert_to_tmp_truststore(self, folderpath, alias, progress):

        # Collect Truststore variables
        truststore_pwd = self._truststore_pwd
        trustpath = self._truststore_path
        storetype = self._storetype

        ssl_certs = collect_visible_files(folderpath)

        for i, cert in enumerate(ssl_certs):
            if any(ext in cert for ext in [".crt", ".cer", ".pem", ".cert", ".key", ".arm"]):

                progress.log()
                progress.log(Text(f"Adding certificate to truststore: {cert}", style="bold cyan"))

                certfolderpath = os.path.join(folderpath, cert)
                # Split the certificate to separate files
                cert_list = split_pem(self._logger, certfolderpath, self._TMP_DIR, f'{alias}-{i}')

                for k, cert in enumerate(cert_list):
                    try:
                        self._logger.info(f"Adding certificate {i + k}: {cert}")
                        cert_alias = f"{alias}-{i + k}"
                        keystore_cmd = (f"keytool -importcert -alias {cert_alias} -keystore \"{trustpath}\" "
                                        + f"-file \"{cert}\" -storepass {truststore_pwd} "
                                        + f"-noprompt -storetype {storetype}")

                        subprocess.run(keystore_cmd, shell=True, check=True, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)

                    except subprocess.CalledProcessError as error:
                        if "already exists" in error.stderr:
                            continue

    # Function to create a PKC12 trust store
    # This truststore will be used to validate the LDAP and DB connection
    def create_truststore(self, progress):

        # Collect Truststore variables
        dname = self._dnsname
        alias = self._alias
        truststore_pwd = self._user_group_prop["KEYSTORE_PASSWORD"]
        self._truststore_pwd = truststore_pwd
        trustpath = self._truststore_path
        storetype = self._storetype

        if os.path.exists(self._truststore_folder):
            os.remove(self._truststore_folder)

        self.__recreate_folder(self._truststore_folder)

        try:

            if self._fips_enabled:
                fips_str = "true"
                msg = Panel.fit(Text(f"Creating PKCS12 truststore with FIPS support"), style="bold cyan")
            else:
                fips_str = "false"
                msg = Panel.fit(Text(f"Creating PKCS12 truststore"), style="bold cyan")

            progress.log(msg)
            progress.log()

            # Construct Keytool command with FIPS options
            keystore_cmd = (f"keytool -J-Dsemeru.fips={fips_str} -v -genkeypair -alias {alias} "
                            + f"-dname \"{dname}\" -keyalg RSA -keystore \"{trustpath}\" "
                            + f"-storetype {storetype} -storepass {truststore_pwd} -noprompt")

            response = subprocess.run(keystore_cmd, shell=True, check=True, capture_output=True, text=True)
            self._logger.info("PKCS12 truststore created successfully.")
        except subprocess.CalledProcessError as e:
            self._logger.info(f"Failed to create PKCS12 truststore: {str(e)}")
            progress.log(Panel.fit(Text(f"Failed to create PKCS12 truststore: {str(e.stderr.strip())}"), style="bold red"))
            progress.log()
            exit(1)

    # Check every and validate all LDAP found in property file.
    def validate_all_ldap(self, task1, progress):

        # Check Reachability and Authentication of LDAP Server
        ldap_validated_list = []
        for ldap_id in self._ldap_prop["_ldap_ids"]:

            ldap_host = remove_protocol(self._ldap_prop[ldap_id]["LDAP_SERVER"])
            ldap_port = self._ldap_prop[ldap_id]["LDAP_PORT"]
            ssl_enabled = self._ldap_prop[ldap_id]["LDAP_SSL_ENABLED"]
            ldap_type = self._ldap_prop[ldap_id]["LDAP_TYPE"].lower()

            progress.log(Panel.fit(Text(f"LDAP Server Validation: {ldap_id}"), style="bold cyan"))
            progress.log()

            is_valid_name = self.validate_server_name(ldap_host, progress)
            if not is_valid_name:
                progress.advance(task1)
                return all(ldap_validated_list)

            validated = False
            authenticated = False
            check_list = []
            if ssl_enabled:
                cert_folder = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", ldap_id.lower())

                validated = self.validate_server(progress=progress, server=ldap_host,
                                                 port=ldap_port, ssl_enabled=ssl_enabled,
                                                 cert_path=cert_folder, display_rtt=True)

                if not validated:
                    progress.log(Panel.fit(
                        Text(f"Reachability over SSL failed. Attempting connection without certificate verification."), style="bold yellow"))
                    progress.log()

                    validated = self.validate_server(progress=progress, server=ldap_host,
                                                     port=ldap_port, ssl_enabled=False,
                                                     display_rtt=False)

                check_list.append(validated)

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

                    progress.log(Panel.fit(Text(f"MS Active Directory Global Catalog Server Validation: {ldap_id}"), style="bold cyan"))
                    progress.log()

                    # Validate the Global Catalog (GC) port and host
                    validated = self.validate_server(progress=progress, server=gc_host,
                                                        port=gc_port, ssl_enabled=ssl_enabled,
                                                        cert_path=cert_folder, display_rtt=False)

                    if not validated:
                        progress.log(Panel.fit(
                            Text(f"Reachability over SSL failed. Attempting connection without certificate verification."),
                            style="bold yellow"))
                        progress.log()

                        validated = self.validate_server(progress=progress, server=ldap_host,
                                                         port=ldap_port, ssl_enabled=False,
                                                         display_rtt=False)

                    check_list.append(validated)

                if validated:
                    authenticated, valid_users_and_groups = self.authenticate_ldap(ldap_id, progress, True,
                                                                                   cert_path=cert_folder)
                    self.ldap_user_groups[ldap_id] = valid_users_and_groups
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

                    progress.log(Panel.fit(Text(f"MS Active Directory Global Catalog Server Validation: {ldap_id}"), style="bold cyan"))
                    progress.log()

                    # Validate the Global Catalog (GC) port and host
                    validated = self.validate_server(progress=progress, server=gc_host,
                                                     port=gc_port, display_rtt=False)

                check_list.append(validated)

                if validated:
                    authenticated, valid_users_and_groups = self.authenticate_ldap(ldap_id, progress)
                    self.ldap_user_groups[ldap_id] = valid_users_and_groups
                    check_list.append(authenticated)

            self.is_validated[ldap_id] = all(check_list)
            ldap_validated_list.append(all(check_list))

            progress.advance(task1)
        return all(ldap_validated_list)

    # Create a function to check and validate all users and groups in LDAP
    def validate_ldap_users_groups(self, task2, progress):
        try:
            progress.log(Panel.fit(Text("LDAP Users and Groups Validation Check"), style="bold cyan"))
            progress.log()

            # validate the bind dn is present in the ldap
            for ldap_id in self._ldap_prop["_ldap_ids"]:
                server = self._ldap_prop[ldap_id]["LDAP_SERVER"]

                progress.log(Text(f"Searching LDAP: \"{server}\""))
                progress.log()

                self.ldap_search(ldap_id)

            result_panel = ldap_search_results(self._entries_dict)

            progress.log(result_panel)
            progress.log()

            progress.advance(task2)

        except Exception as e:
            self._logger.exception(
                f"Exception from validate_ldap_users_groups function -  {str(e)}")

    def retrieve_token(self, url, payload, progress, cert_path=False, auth=None):

        """ Retrieve token from IDP """
        try:
            response = None

            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            # Add basic auth if only client_basic_auth is provided
            if auth:
                headers.update(auth)

            if cert_path:
                progress.log()
                progress.log("Retrieving access and id_token token over SSL...")

                context = create_ssl_context(client_cert_file=cert_path)
                client_session = Session()
                client_session.mount("https://", self.CustomHTTPAdapter(ssl_context=context))

                response = client_session.post(url, headers=headers, data=payload, timeout=5)

                # Check if "access_token" or 'id_token' is in the response
                if response.status_code == 200:
                    if 'access_token' in response.json() or 'id_token' in response.json():
                        return response.json(), True

                return response, False


            progress.log()
            progress.log("Retrieving access and id_token token...")
            response = requests.post(url, headers=headers, data=payload, verify=False, timeout=5)

            # Check if "access_token" is in the response
            if response.status_code == 200:
                if "access_token" in response.json() or 'id_token' in response.json():
                    return response.json(), True

            return response.json(), False

        # Check for SSL errors
        except requests.exceptions.SSLError as e:
            self._logger.info(f"SSL Error: {e}")
            self._logger.info("Attempting to retrieve token using non-SSL connection...")

            progress.log()
            progress.log(Text("SSL error occurred while retrieving token. Attempting connection without certificate verification.",
                              style="bold yellow"))
            response = requests.post(url, headers=headers, data=payload, verify=False, timeout=5)

            if response.status_code == 200:
                if "access_token" in response.json() or 'id_token' in response.json():
                    return response.json(), True

            return response.json(), False
        except requests.exceptions.RequestException as e:
            return response.json(), False
        except Exception as e:
            return response.json(), False


    def base64url_decode(self, input_str):

        """ Decodes Base64 URL-safe encoded string """

        rem = len(input_str) % 4
        if rem > 0:
            input_str += '=' * (4 - rem)
        return base64.urlsafe_b64decode(input_str.encode('utf-8'))

    def load_jwk_rsa_key(self, jwk):

        """ Loads a RSA public key from a JSON Web Key"""

        # RSA modulus 
        n = int.from_bytes(self.base64url_decode(jwk['n']), 'big')
        # public exponent
        e = int.from_bytes(self.base64url_decode(jwk['e']), 'big')
        # public key
        public_key = rsa.RSAPublicNumbers(e, n).public_key(default_backend())
        return public_key

    def verify_rs256_signature(self, header_b64, payload_b64, signature_b64, public_key):

        """ Verifies an RS256 signature for a given header, payload, and signature """

        signed_data = f'{header_b64}.{payload_b64}'.encode('utf-8')
        signature = self.base64url_decode(signature_b64)
        try:
            public_key.verify(
                signature,
                signed_data,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            self._logger.info(f"Signature verification failed: {e}")
            return False

    def decode_id_token(self, jwks_uri, id_token, client_id, cert_path=None, progress=None):

        """ Validates the id token retrieved from IDP """

        try:
            if cert_path:
                # Getting the public key with SSL verification
                progress.log()
                progress.log("Retrieving public key from JWKS Endpoint over SSL...")
                # Getting the public key
                jwks = requests.get(jwks_uri, verify=cert_path, timeout=5).json()
            else:
                progress.log()
                progress.log("Retrieving public key from JWKS Endpoint...")
                # Getting the public key without SSL verification
                jwks = requests.get(jwks_uri, verify=False, timeout=5).json()

        except requests.exceptions.SSLError as e:
            self._logger.info(f"SSL Error: {e}")
            self._logger.info("Attempting to retrieve public key using non-SSL connection...")
            progress.log()
            progress.log(Text("SSL error occurred while retrieving public key. Attempting connection without certificate verification.",
                              style="bold yellow"))
            jwks = requests.get(jwks_uri, verify=False, timeout=5).json()
        except requests.exceptions.RequestException as e:
            error_text = jwks.text if jwks is not None and hasattr(jwks,
                                                                   "text") else "No response or response not available."
            progress.log()
            progress.log(Panel.fit(
                Text(f"Failed to retrieve public key from \"{jwks_uri}\"! Error: {str(e)}\nResponse Text: {error_text}",
                     style="bold red")))
        except Exception as e:
            progress.log()
            progress.log(Panel.fit(
                Text(f"An unexpected error occurred while retrieving public key from \"{jwks_uri}\"! Error: {str(e)}",
                     style="bold red")))
            self._logger.info(f"An unexpected error occurred: {e}")

        progress.log()
        progress.log("Parsing the token headers")
        header_b64, payload_b64, signature_b64 = id_token.split('.')
        header = json.loads(self.base64url_decode(header_b64))
        payload = json.loads(self.base64url_decode(payload_b64))

        progress.log()
        progress.log("Loading the public key")
        kid = header['kid']
        key = next(k for k in jwks['keys'] if k['kid'] == kid)
        public_key = self.load_jwk_rsa_key(key)

        if not self.verify_rs256_signature(header_b64, payload_b64, signature_b64, public_key):
            progress.log()
            progress.log(Panel.fit(Text("Invalid token signature!"), style="bold red"))
            raise ValueError("Invalid signature")

        progress.log()
        progress.log("Token signature verified successfully!")
        self._logger.info("Token signature verified successfully!")

        now = int(time.time())
        if 'exp' in payload and now > payload['exp']:
            progress.log()
            progress.log(Panel.fit(Text("Token has expired!"), style="bold red"))
            raise ValueError("Token expired")

        progress.log()
        progress.log("Token expiration time is valid!")
        self._logger.info("Token expiration time is valid!")

        return payload

    def validate_all_idps(self, task4, progress):
        idp_ids = self._idp_prop["_idp_ids"]
        validated_idps = []

        if self._scim_prop:
            progress.log()
            progress.log(
                Panel.fit(Text(f"Validating IDP for SCIM Integration"), style="bold cyan"))
            progress.log()
            progress.log(Panel.fit(Text(
                "Validation will test the IDP configuration and retrieve the access token using password flow.\n"
                "Liberty OAuth Jaas module accesses the IDP using the password grant type."), style="bold purple"))
        else:
            progress.log()
            progress.log(Panel.fit(Text("IDP Validation"), style="bold cyan"))
            progress.log()
            progress.log(Panel.fit(Text("IDP Validation is optional.\n"
                                        "During deployment, IBM Liberty will use authorization code flow to retrieve the access token.\n"
                                        "Validation will test the IDP configuration and retrieve the access token using client credentials or password flow.\n"
                                        "Any failures trying to get an access token will be ignored."),
                                   style="bold purple"))



        for idp_id in idp_ids:
            if self._scim_prop:
                validated = self.validate_idp_scim(idp_id, progress)
            else:

                validated = self.validate_idp(idp_id, progress)

            if validated:
                progress.log()
                progress.log(Panel.fit(Text(f"Successfully validated IDP: {idp_id.lower()}"), style="bold green"))

            validated_idps.append(validated)
            self.is_validated[idp_id] = validated
            progress.advance(task4)

        if all(validated_idps):
            progress.log()
            progress.log(Panel.fit(Text("All IDPs validated successfully!"), style="bold green"))
            self._logger.info("All IDPs validated successfully!")
        else:
            progress.log()
            progress.log(Panel.fit(Text("Some IDPs failed the optional validation. IBM Liberty will use the authorization code flow to retrieve the access token.\n"
                                        "Not all IDPs are required to be validated for the deployment to succeed."), style="bold purple"))
        progress.advance(task4)



    def validate_idp(self, idp_id, progress):

        """ Validates IDP """

        try:
            progress.log(Panel.fit(Text(f"Validating IDP: {idp_id.lower()}"), style="bold cyan"))

            idp_config = self._idp_prop[idp_id]
            token_endpoint = idp_config.get("TOKEN_ENDPOINT", "")
            client_id = idp_config.get("CLIENT_ID", "")
            client_secret = idp_config.get("CLIENT_SECRET", "")
            ssl_enabled = idp_config.get("IDP_SSL_ENABLED", False)
            cert_folder = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", idp_id.lower())

            if ssl_enabled:
                # Get the certificate path
                self._logger.info(f"SSL is enabled for IDP: {idp_id.lower()}")
                progress.log()
                progress.log(Text(f"SSL is enabled for IDP: {idp_id.lower()}", style="bold cyan"))

                cert_path, san_list = clean_and_combine_pem_files(self._logger, cert_folder, self._TMP_DIR, idp_id)

                self._logger.info(f"Using certificate path: {cert_path}")

                verify_cert = cert_path
            else:
                verify_cert = False

            # Validate Server Reachability
            progress.log()
            progress.log(f"Validating server reachability for IDP: {idp_id.lower()}\n\n"
                         f"Using token endpoint for validation: {token_endpoint}")
            progress.log()

            # Get Port and Server from the token endpoint
            if not token_endpoint:
                progress.log()
                progress.log(Panel.fit(Text(f"Token endpoint is not provided for {idp_id} IDP!\n\n"
                                            f"Please check the IDP configuration in the fncm_identity_provider.toml file",
                                            style="bold red")))
                self._logger.info(f"Token endpoint is not provided for {idp_id} IDP!")
                return False

            url_parts = urlparse(token_endpoint)
            idp_url = url_parts.hostname
            idp_port = url_parts.port if url_parts.port else (443 if ssl_enabled else 80)

            if ssl_enabled:
                server_reachability = self.validate_server(progress=progress, server=idp_url, port=idp_port,
                                                           ssl_enabled=True, cert_path=cert_folder,
                                                           display_rtt=False)
            else:
                server_reachability = self.validate_server(progress=progress, server=idp_url, port=idp_port,
                                                           display_rtt=False)

            if not server_reachability and ssl_enabled:
                progress.log(
                    Text(f"Reachability over SSL failed. Attempting connection without certificate verification.",
                         style="bold yellow"), style="bold yellow")
                progress.log()

                server_reachability = self.validate_server(progress=progress, server=idp_url, port=idp_port,
                                                           display_rtt=False)

            if not server_reachability:
                return False

            # Validate the password grant type
            # Only check if the discovery URL is provided

            progress.log()
            progress.log(f"Validating client authentication methods")
            discovery_url = idp_config.get("DISCOVERY_ENDPOINT", "")
            if not discovery_url:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Discovery URL is not provided for IDP!\n"
                         f"Additional Validation will be skipped", style="bold yellow")))
                self._logger.info(f"Discovery URL is not provided for {idp_id} IDP!")
                return True

            progress.log()
            progress.log(f"Retrieving discovery document...")
            discovery = requests.get(discovery_url, timeout=5, verify=False).json()


            # Check if the discovery is valid
            if discovery is None:
                progress.log()
                progress.log(Panel.fit(Text(f"Failed to retrieve discovery document\n"
                                            f"Check the DISCOVERY_ENDPOINT in the fncm_identity_provider.toml file",
                                            style="bold red")))
                self._logger.info(f"Failed to retrieve discovery document for {idp_id} IDP!")
                return False

            # Check if "client_credentials" is in the response
            grant_types = discovery.get("grant_types_supported", [])
            if grant_types:
                if "client_credentials" not in grant_types:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"\"client_credentials\" grant type is not supported by IDP: {idp_id.lower()}\n"
                             f"Additional validation will be skipped."),  style="bold yellow"))
                    self._logger.info(f"\"client_credentials\" grant type is not supported by IDP: {idp_id.lower()}")
                    return True
            else:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Unable to determine supported grant types from discovery document.\n"
                         f"Validation will continue to use \"client_credential\" grant"), style="bold yellow"))
                self._logger.info("Unable to determine supported grant types from discovery document.")


            self._logger.info(f"Discovery document retrieved for {idp_id} IDP: {discovery}")
            client_type = ''
            if "token_endpoint_auth_methods_supported" in discovery.keys():
                auth_methods = discovery.get("token_endpoint_auth_methods_supported", [])
                if "client_secret_post" in auth_methods:
                    client_type = 'client_secret_post'
                elif "client_secret_basic" in auth_methods:
                    client_type = 'client_secret_basic'
                else:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"\"client_secret_post\" or \"client_secret_basic\" authentication methods are not supported by IDP: {idp_id.lower()}\n"
                             f"Additional validation will be skipped.", style="bold yellow")))
                    self._logger.info(f"\"client_secret_post\" or \"client_secret_basic\" authentication methods are not supported by IDP: {idp_id.lower()}")
                    return True
            else:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Unable to determine supported authentication methods from discovery document.\n"
                         f"Additional validation will be skipped."), style="bold yellow"))
                self._logger.info("Unable to determine supported authentication methods from discovery document.")
                return True

            progress.log()
            progress.log(Panel.fit(
                Text(f"\"{client_type}\" authentication method is supported!", style="bold green")))
            self._logger.info(f"\"{client_type}\" authentication method is supported!")

            # Retrieving token
            self._logger.info(f"Retrieving id_token from IDP using {client_type}")
            progress.log()
            progress.log("Using \"client_credentials\" grant to retrieve access token from IDP")

            # Azure Entra requires specific scope
            # Will check the Issuer Endpoint to determine if it's Azure Entra
            issuer = idp_config.get("ISSUER", "")
            if 'microsoftonline' in issuer:
                scope = f"{client_id}/.default"
            else:
                scope = "openid profile email"

            if client_type == 'client_secret_post':
                payload = {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": scope
                }
                auth = None
            elif client_type == 'client_secret_basic':
                # For client_secret_basic, we will use the same payload but send it in the headers
                auth = {
                    'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}'
                }
                payload = {
                    "grant_type": "client_credentials",
                    "scope": scope
                }

            response, token_retrieved = self.retrieve_token(token_endpoint, payload, progress, verify_cert, auth)

            self._logger.info(f"Response from IDP: {response}")
            self._logger.info(f"Token retrieved from IDP: {token_retrieved}")

            if not token_retrieved:
                error = response.get("error", "")
                error_description = response.get("error_description", "")

                if error == "unsupported_grant_type":
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"\"client_credentials\" grant type is not supported by IDP: {idp_id.lower()}\n"
                             f"Validation will fall back to \"password\" grant type"), style="bold yellow"))
                    self._logger.info(f"\"client_credentials\" grant type is not supported by IDP: {idp_id.lower()}")

                    # Fallback to password grant type
                    payload["grant_type"] = "password"

                    # Retrieving token
                    progress.log()
                    progress.log("Using \"password\" grant to retrieve access token from IDP")

                    response, token_retrieved = self.retrieve_token(token_endpoint, payload, progress, verify_cert,
                                                                    auth)

                    if token_retrieved:
                        progress.log()
                        progress.log(Panel.fit(
                            Text(f"Access token retrieved successfully from IDP: {idp_id.lower()}"), style="bold green"))
                        self._logger.info(f"Access token retrieved successfully from IDP: {idp_id.lower()}")
                        return True

                else:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"Failed to retrieve token from IDP: {idp_id.lower()}"), style="bold purple"))
                    self._logger.info(f"Failed to retrieve token from IDP: {idp_id.lower()}")

                    if error or error_description:
                        progress.log()
                        progress.log(Panel.fit(Text(f"Error: {error}\nError Description: {error_description}"), style="bold purple"))
                        self._logger.info(f"Error: {error}\nError Description: {error_description}")
                    return True

            progress.log()
            progress.log(Panel.fit(
                Text(f"Access token retrieved successfully from IDP: {idp_id.lower()}"), style="bold green"))
            self._logger.info(f"Access token retrieved successfully from IDP: {idp_id.lower()}")
            return True

        except Exception as e:
            progress.log()
            progress.log(Panel.fit(Text(f"Failed to validate IDP: {idp_id}"), style="bold red"))
            self._logger.info(f"Failed to validate {idp_id} IDP! Error: {str(e)}")
            return False

    def validate_idp_scim(self, idp_id, progress):

        """ Validates IDP """
        progress.log()
        progress.log(Panel.fit(Text(f"Validating IDP for SCIM Integration: {idp_id.lower()}"), style="bold cyan"))

        try:
            idp_config = self._idp_prop[idp_id]
            token_endpoint = idp_config.get("TOKEN_ENDPOINT", "")
            client_id = idp_config.get("CLIENT_ID", "")
            client_secret = idp_config.get("CLIENT_SECRET", "")
            fncm_login_user = self._user_group_prop.get("FNCM_LOGIN_USER", "")
            fncm_login_password = self._user_group_prop.get("FNCM_LOGIN_PASSWORD", "")
            ssl_enabled = idp_config.get("IDP_SSL_ENABLED", False)
            cert_folder = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", idp_id.lower())

            if ssl_enabled:
                # Get the certificate path
                self._logger.info(f"SSL is enabled for IDP: {idp_id.lower()}")
                progress.log()
                progress.log(Text(f"SSL is enabled for IDP: {idp_id.lower()}", style="bold cyan"))

                cert_path, san_list = clean_and_combine_pem_files(self._logger, cert_folder, self._TMP_DIR, idp_id)

                self._logger.info(f"Using certificate path: {cert_path}")

                verify_cert = cert_path
            else:
                verify_cert = False

            # Validate Server Reachability
            progress.log()
            progress.log(f"Validating server reachability for IDP: {idp_id.lower()}\n\n"
                         f"Using token endpoint for validation: {token_endpoint}")
            progress.log()

            # Get Port and Server from the token endpoint
            if not token_endpoint:
                progress.log()
                progress.log(Panel.fit(Text(f"Token endpoint is not provided for {idp_id} IDP!\n\n"
                                            f"Please check the IDP configuration in the fncm_identity_provider.toml file",
                                            style="bold red")))
                self._logger.info(f"Token endpoint is not provided for {idp_id} IDP!")
                return False

            url_parts = urlparse(token_endpoint)
            idp_url = url_parts.hostname
            idp_port = url_parts.port if url_parts.port else (443 if ssl_enabled else 80)

            if ssl_enabled:
                server_reachability = self.validate_server(progress=progress, server=idp_url, port=idp_port,
                                                           ssl_enabled=True, cert_path=cert_folder,
                                                           display_rtt=False)
            else:
                server_reachability = self.validate_server(progress=progress, server=idp_url, port=idp_port,
                                                           display_rtt=False)

            if not server_reachability and ssl_enabled:
                progress.log(Panel.fit(
                    Text(f"Reachability over SSL failed. Attempting connection without certificate verification.",
                         style="bold yellow"), style="bold yellow"))
                progress.log()

                server_reachability = self.validate_server(progress=progress, server=idp_url, port=idp_port,
                                                           display_rtt=False)

            if not server_reachability:
                return False

            # Validate the password grant type
            # Only check if the discovery URL is provided

            progress.log()
            progress.log(f"Validating client authentication methods")
            discovery_url = idp_config.get("DISCOVERY_ENDPOINT", "")
            if not discovery_url:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Discovery URL is not provided for IDP!\n"
                         f"Additional Validation will be skipped"), style="bold yellow"))
                self._logger.info(f"Discovery URL is not provided for {idp_id} IDP!")
                return True

            progress.log()
            progress.log(f"Retrieving discovery document...")
            discovery = requests.get(discovery_url, timeout=5, verify=False).json()


            # Check if the discovery is valid
            if discovery is None:
                progress.log()
                progress.log(Panel.fit(Text(f"Failed to retrieve discovery document\n"
                                            f"Check the DISCOVERY_ENDPOINT in the fncm_identity_provider.toml file",
                                            style="bold red")))
                self._logger.info(f"Failed to retrieve discovery document for {idp_id} IDP!")
                return False

            # Check if "client_credentials" is in the response
            grant_types = discovery.get("grant_types_supported", [])
            if grant_types:
                if "client_credentials" not in grant_types:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"\"client_credentials\" grant type is not supported by IDP: {idp_id.lower()}\n"
                             f"Additional validation will be skipped."),  style="bold yellow"))
                    self._logger.info(f"\"client_credentials\" grant type is not supported by IDP: {idp_id.lower()}")
                    return True
            else:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Unable to determine supported grant types from discovery document.\n"
                         f"Validation will continue to use \"client_credential\" grant"), style="bold yellow"))
                self._logger.info("Unable to determine supported grant types from discovery document.")


            self._logger.info(f"Discovery document retrieved for {idp_id} IDP: {discovery}")
            client_type = ''
            if "token_endpoint_auth_methods_supported" in discovery.keys():
                auth_methods = discovery.get("token_endpoint_auth_methods_supported", [])
                if "client_secret_post" in auth_methods:
                    client_type = 'client_secret_post'
                elif "client_secret_basic" in auth_methods:
                    client_type = 'client_secret_basic'
                else:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"\"client_secret_post\" or \"client_secret_basic\" authentication methods are not supported by IDP: {idp_id.lower()}\n"
                             f"Additional validation will be skipped."), style="bold yellow"))
                    self._logger.info(f"\"client_secret_post\" or \"client_secret_basic\" authentication methods are not supported by IDP: {idp_id.lower()}")
                    return True
            else:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Unable to determine supported authentication methods from discovery document.\n"
                         f"Additional validation will be skipped."), style="bold yellow"))
                self._logger.info("Unable to determine supported authentication methods from discovery document.")
                return True

            progress.log()
            progress.log(Panel.fit(
                Text(f"\"{client_type}\" authentication method is supported!"), style="bold green"))
            self._logger.info(f"\"{client_type}\" authentication method is supported!")

            # Retrieving token
            self._logger.info(f"Retrieving token from IDP using password grant type")
            progress.log()
            progress.log("Using password grant to retrieve access token from IDP")

            # Azure Entra requires specific scope
            # Will check the Issuer Endpoint to determine if it's Azure Entra
            issuer = idp_config.get("ISSUER", "")
            if 'microsoftonline' in issuer:
                scope = f"api://{client_id}/.default"
            else:
                scope = "openid profile email"

            if client_type == 'client_secret_post':
                payload = {
                    "grant_type": "password",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "username": fncm_login_user,
                    "password": fncm_login_password,
                    "scope": scope
                }
                auth = None
            elif client_type == 'client_secret_basic':
                # For client_secret_basic, we will use the same payload but send it in the headers
                auth = {
                    'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}'
                }
                payload = {
                    "grant_type": "password",
                    "scope": scope,
                    "username": fncm_login_user,
                    "password": fncm_login_password,
                }

            response, token_retrieved = self.retrieve_token(token_endpoint, payload, progress, verify_cert, auth)

            self._logger.info(f"Response from IDP: {response}")
            self._logger.info(f"Token retrieved from IDP: {token_retrieved}")

            if not token_retrieved:
                error = response.get("error", "")
                error_description = response.get("error_description", "")

                progress.log()
                progress.log(Panel.fit(
                    Text(f"Failed to retrieve token from IDP: {idp_id.lower()}"), style="bold red"))
                self._logger.info(f"Failed to retrieve token from IDP: {idp_id.lower()}")

                if error or error_description:
                    progress.log()
                    progress.log(
                        Panel.fit(Text(f"Error: {error}\nError Description: {error_description}"),
                                  style="bold red"))
                    self._logger.info(f"Error: {error}\nError Description: {error_description}")
                return False

            if token_retrieved:
                if token_retrieved:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"Token retrieved successfully from IDP: {idp_id.lower()}"), style="bold green"))
                    self._logger.info(f"Token retrieved successfully from IDP: {idp_id.lower()}")

                id_token = response.get("id_token", "")

                if not id_token:
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"ID Token is not present in the response from IDP: {idp_id.lower()}\n"
                             f"Please check the IDP configuration and ensure that the ID Token is being returned.",
                             style="bold red")))
                    self._logger.info(f"ID Token is not present in the response from IDP: {idp_id.lower()}")
                    return False

                progress.log()
                progress.log("Using JWKS URI to decode the IDP ID token")

                jwks_uri = idp_config.get("JWKS_ENDPOINT", "")
                if not jwks_uri:
                    progress.log()
                    progress.log(Panel.fit(Text(f"JWKS URI is not provided for {idp_id} IDP!\n"
                                                f"Add the JWKS_ENDPOINT in the fncm_identity_provider.toml file"
                                                f"This is needed to be able to decode the IDP token",
                                                style="bold red")))
                    self._logger.info(f"JWKS_ENDPOINT is not provided for {idp_id} IDP!")
                    return False

                # Validate token
                decoded_output = self.decode_id_token(jwks_uri, id_token, client_id, verify_cert, progress)

                if decoded_output:
                    self._logger.info(f"Decoded output : {decoded_output}")
                    found_claims = {}
                    missing_claims = []

                    # Create a list of tuples
                    # with expected token claims from the IDP configuration

                    # Create a dictionary with expected token claims from the IDP configuration
                    claim_dict = {"USER_IDENTIFIER": idp_config.get("USER_IDENTIFIER", ""),
                                  "UNIQUE_USER_IDENTIFIER": idp_config.get("UNIQUE_USER_IDENTIFIER", ""),
                                  "USER_IDENTIFIER_TO_CREATE_SUBJECT": idp_config.get(
                                      "USER_IDENTIFIER_TO_CREATE_SUBJECT", "")}

                    self._logger.info(f"Expected claims from IDP: {claim_dict}")

                    for key, value in claim_dict.items():
                        if value in decoded_output:
                            found_claims[key] = (value, decoded_output[value])
                            self._logger.info(f"{key} is present in the decoded output.")
                        else:
                            missing_claims.append(value)
                            self._logger.info(f"{value} is NOT present in the decoded output.")

                    results = idp_token_claim_results(found_claims, missing_claims)

                    progress.log()
                    progress.log(results)

                    if missing_claims:
                        self._logger.info(f"Missing claims in the decoded output: {', '.join(missing_claims)}")
                        self._logger.info(f"Failed to validate token claims from IDP: {idp_id.lower()}!")

                        idp_token_claim_response = Text(
                            f"Failed to validate token claims from IDP: {idp_id.lower()}\n"
                            f"Missing claims in the decoded output: {', '.join(missing_claims)}"
                            f"Review the access token and claim parameters in the fncm_identity_provider.toml file\n"
                            f"Please check the IDP configuration and ensure that the required claims are present.",
                            style="bold red")

                        progress.log()
                        progress.log(Panel.fit(idp_token_claim_response, style="bold red"))
                        return False

                    self._logger.info(f"Successfully validated all token claims from IDP: {idp_id.lower()}!")
                    idp_token_claim_response = Text(
                        f"Successfully validated all token claims from IDP: {idp_id.lower()}")
                    progress.log()
                    progress.log(Panel.fit(idp_token_claim_response, style="bold green"))

                    return True
                else:
                    progress.log()
                    progress.log(Panel.fit(Text(f"Failed to decode IDP ID token: {idp_id.lower()}"), style="bold red"))
                    self._logger.info(f"Failed to decode IDP ID token: {idp_id.lower()}")
                    return False
            else:
                progress.log()
                progress.log(Panel.fit(
                    Text(f"Failed to retrieve token from ID IDP: {idp_id.lower()}"), style="bold red"))
                self._logger.info(f"Failed to retrieve token from IDP: {idp_id.lower()}")
                return False

        except Exception as e:
            progress.log()
            progress.log(Panel.fit(Text(f"Failed to validate IDP: {idp_id}"), style="bold red"))
            self._logger.info(f"Failed to validate {idp_id} IDP! Error: {str(e)}")
            return False

    def query_scim(self, url, access_token, cert_path=None):

        """ Retrieves users/groups from SCIM """

        retrieved_data = False
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/scim+json"
        }

        try:
            if cert_path:
                response = requests.get(url, headers=headers, verify=cert_path, timeout=5)
            else:
                response = requests.get(url, headers=headers, verify=False, timeout=5)

            retrieved_data = True

        except requests.exceptions.SSLError as e:
            self._logger.info(f"SSL Error: {e}")
            self._logger.info("Attempting to retrieve scim query using non-SSL connection...")
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            retrieved_data = True
        except requests.RequestException as e:
            error_text = response.text if response is not None and hasattr(response,
                                                                           "text") else "No response or response not available."
            self._logger.info(f"Failed to retrieve data from SCIM! Error: {str(e)}\nResponse Text: {error_text}")
            retrieved_data = False

        return response.json(), retrieved_data

    def validate_scim_groups(self, scim_endpoint, token, progress, cert_path=None):

        """ Validates all SCIM groups """

        groups_validated = False
        groups = self._entries_dict
        groups_url = urljoin(scim_endpoint, "Groups")

        self._logger.info(f"SCIM Groups: {groups}")

        try:

            for item, value in groups.items():
                if value['type'] in [scim_entry_types.GROUP, scim_entry_types.USER_GROUP]:
                    group_name = item

                    progress.log()
                    progress.log(Text(f"Validating SCIM User or Group: {group_name}", style="bold cyan"))

                    # Query SCIM for each group using Filter
                    groups_url = urljoin(groups_url, f"?filter=displayName eq \"{group_name}\"")

                    fetch_response, retrieved_data = self.query_scim(groups_url, token, cert_path)
                    if not retrieved_data:
                        progress.log()
                        progress.log(Panel.fit(Text(f"Failed to retrieve SCIM group: {group_name}"), style="bold red"))
                        self._logger.info(f"Failed to retrieve SCIM group: {group_name}")
                        continue

                    self._logger.info(f"SCIM Groups response: {fetch_response}")
                    total_results = fetch_response.get("totalResults", 0)
                    if total_results > 0:
                        self._logger.info(f"Successfully retrieved SCIM group: {group_name}")
                        value['count'] += 1
                        if value['type'] == scim_entry_types.USER_GROUP:
                            value['type'] = scim_entry_types.GROUP

            groups_validated = True
            return groups_validated

        except Exception as e:
            progress.log()
            progress.log(Panel.fit(Text(f"Failed to validate SCIM groups! Error: {str(e)}"), style="bold red"))
            self._logger.info(f"Failed to validate SCIM groups! Error: {str(e)}")
            return groups_validated

    def validate_scim_users(self, scim_endpoint, token, progress, cert_path=None):

        """ Validates all SCIM users """

        users_validated = False
        users = self._entries_dict
        users_url = urljoin(scim_endpoint, "Users")

        self._logger.info(f"SCIM Users: {users}")

        try:

            for item, value in users.items():
                if value['type'] in [scim_entry_types.USER, scim_entry_types.USER_GROUP]:
                    username = item

                    progress.log()
                    progress.log(Text(f"Validating SCIM User or Group: {username}", style="bold cyan"))

                    # Query SCIM for each user using Filter
                    users_url = urljoin(users_url, f"?filter=userName eq \"{username}\"")

                    fetch_response, retrieved_data = self.query_scim(users_url, token, cert_path)
                    if not retrieved_data:
                        progress.log()
                        progress.log(Panel.fit(Text(f"Failed to retrieve SCIM user: {username}"), style="bold red"))
                        self._logger.info(f"Failed to retrieve SCIM user: {username}")
                        continue

                    self._logger.info(f"SCIM Users response: {fetch_response}")
                    total_results = fetch_response.get("totalResults", 0)
                    if total_results > 0:
                        self._logger.info(f"Successfully retrieved SCIM user: {username}")
                        value['count'] += 1
                        if value['type'] == scim_entry_types.USER_GROUP:
                            value['type'] = scim_entry_types.USER

            users_validated = True
            return users_validated

        except Exception as e:
            progress.log()
            progress.log(Panel.fit(Text(f"Failed to validate SCIM users! Error: {str(e)}"), style="bold red"))
            self._logger.info(f"Failed to validate SCIM users! Error: {str(e)}")
            return users_validated

    def validate_scim(self, task, progress, scim_id="SCIM", idp_id="IDP"):

        """ Validates SCIM """

        scim_validated_list = []
        self.is_validated[scim_id] = False

        progress.log()
        progress.log(Panel.fit(Text(f"SCIM Validation"), style="bold cyan"))
        progress.log()
        progress.log(Panel.fit(Text("SCIM validation will use the client_credentials grant type to retrieve access token from IDP.\n"
                          "The ID token will be decoded to validate the claims.\n"
                          "Once validated, the SCIM server will be queried for users and groups using an access token."), style="bold purple"))

        progress.log(Panel.fit(Text(f"Validating SCIM: {scim_id.lower()}"), style="bold cyan"))
        progress.log()

        scim_server = self._scim_prop[scim_id].get("SCIM_SERVER", "")
        token_endpoint = self._scim_prop[scim_id].get("TOKEN_ENDPOINT", "")
        scim_context_path = self._scim_prop[scim_id].get("SCIM_CONTEXT_PATH", "")
        client_id = self._scim_prop[scim_id].get("SCIM_CLIENT_ID", "")
        client_secret = self._scim_prop[scim_id].get("SCIM_CLIENT_SECRET", "")
        ssl_enabled = self._scim_prop[scim_id].get("SCIM_SSL_ENABLED", "")
        scim_port = self._scim_prop[scim_id].get("SCIM_PORT", "")
        scim_endpoint = f"https://{scim_server}:{scim_port}/{scim_context_path}/"

        idp_cert_folder = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", idp_id.lower())
        scim_cert_folder = os.path.join(os.getcwd(), "propertyFile", self._namespace, "ssl-certs", scim_id.lower())

        try:

            if ssl_enabled:
                # Get the certificate path
                self._logger.info(f"SSL is enabled for SCIM: {scim_id.lower()}")
                progress.log()
                progress.log(Text(f"SSL is enabled for SCIM: {scim_id.lower()}", style="bold cyan"))

                idp_cert_path, san_list = clean_and_combine_pem_files(self._logger, idp_cert_folder, self._TMP_DIR, scim_id)

                scim_cert_path, san_list = clean_and_combine_pem_files(self._logger, scim_cert_folder, self._TMP_DIR, scim_id)

                self._logger.info(f"SSL cert path: {scim_cert_path}")

                verify_cert = scim_cert_path
            else:
                verify_cert = False

            # Validate Server Reachability
            progress.log()
            progress.log(f"Validating server reachability for SCIM: {scim_id.lower()}\n\n"
                         f"Using SCIM server endpoint for validation: {scim_endpoint}")
            progress.log()

            # Check if the token endpoint is provided
            if not token_endpoint:
                progress.log()
                progress.log(Panel.fit(Text(f"Token endpoint is not provided for SCIM!\n\n"
                                            f"Please check the SCIM configuration in the fncm_scim_server.toml file",
                                            style="bold red")))
                self._logger.info(f"Token endpoint is not provided for SCIM!")
                scim_validated_list.append(False)
                self.is_validated[scim_id] = all(scim_validated_list)
                progress.advance(task)

            # Check if the SCIM server is provided
            if not scim_server:
                progress.log()
                progress.log(Panel.fit(Text(f"SCIM server is not provided for SCIM!\n\n"
                                            f"Please check the SCIM configuration in the fncm_scim_server.toml file",
                                            style="bold red")))
                self._logger.info(f"SCIM server is not provided for SCIM!")
                scim_validated_list.append(False)
                self.is_validated[scim_id] = all(scim_validated_list)
                progress.advance(task)

            # Test reachability of the SCIM server
            if ssl_enabled:
                server_reachability = self.validate_server(progress=progress, server=scim_server, port=scim_port,
                                                           ssl_enabled=True, cert_path=scim_cert_folder,
                                                           display_rtt=False)
            else:
                server_reachability = self.validate_server(progress=progress, server=scim_server, port=scim_port,
                                                           display_rtt=False)

            if not server_reachability and ssl_enabled:
                progress.log(Panel.fit(
                    Text(f"Reachability over SSL failed. Attempting connection without certificate verification.",
                         style="bold yellow"), style="bold yellow"))
                progress.log()

                server_reachability = self.validate_server(progress=progress, server=scim_server, port=scim_port,
                                                           display_rtt=False)

            if not server_reachability:
                scim_validated_list.append(False)
                self.is_validated[scim_id] = all(scim_validated_list)
                progress.advance(task)

            scim_validated_list.append(server_reachability)

            # Retrieve token from IDP

            self._logger.info(f"Retrieving token from IDP using client_credentials grant type")
            progress.log()
            progress.log("Using client_credentials grant to retrieve access token from IDP")
            url = token_endpoint

            payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }

            response, token_retrieved = self.retrieve_token(url, payload, progress, verify_cert)

            self._logger.info(f"Response from IDP: {response}")
            self._logger.info(f"Token retrieved from IDP: {token_retrieved}")

            scim_validated_list.append(token_retrieved)

            if token_retrieved:

                progress.log()
                progress.log(
                    Panel.fit(Text(f"Successfully retrieved token from IDP: {idp_id.lower()}"), style="bold green"))
                self._logger.info(f"Successfully retrieved token from IDP: {idp_id.lower()}")

            else:
                progress.log()
                progress.log(Panel.fit(Text(f"Failed to retrieve tokens from IDP: {idp_id.lower()}"), style="bold red"))
                self._logger.info(f"Failed to retrieve tokens from IDP: {idp_id.lower()}")
                self.is_validated[scim_id] = all(scim_validated_list)
                progress.advance(task)

            if token_retrieved:
                access_token = response.get("access_token", '')

                if not access_token:
                    progress.log()
                    progress.log(Panel.fit(Text(f"Access token is not retrieved from IDP: {idp_id.lower()}\n"
                                                f"Please check the IDP configuration and ensure that the ID Token is being returned.\n"),
                                                style="bold red"))
                    self._logger.info(f"Access token is not retrieved from IDP: {idp_id.lower()}")
                    self.is_validated[scim_id] = all(scim_validated_list)
                    progress.advance(task)
                    return

                progress.log()
                progress.log(Panel.fit(Text("SCIM User and Group Validation"), style="bold cyan"))
                progress.log()
                progress.log("Collecting all admins, users and groups from the property files")
                progress.log()

                # Validate SCIM Admin users
                admin_users_validated = self.validate_scim_admin_users(scim_endpoint=scim_endpoint,
                                                                       token=access_token,
                                                                       progress=progress,
                                                                       ssl_enabled=verify_cert)

                scim_validated_list.extend(admin_users_validated)

                admin_group_validated = self.validate_scim_admin_groups(scim_endpoint=scim_endpoint,
                                                                        token=access_token,
                                                                        progress=progress,
                                                                        ssl_enabled=verify_cert)

                scim_validated_list.extend(admin_group_validated)

                progress.log()
                progress.log(Panel.fit(Text("Validating SCIM Non-Admin Users and Groups"), style="bold cyan"))
                progress.log()
                progress.log("Validation of non-admin users and groups will be done using SCIM Users and Groups endpoints with filters")
                progress.log()

                # Validate the non-admin users
                # This check will only check for existence

                users_validated = self.validate_scim_users(scim_endpoint=scim_endpoint,
                                                           token=access_token,
                                                           progress=progress,
                                                           cert_path=verify_cert)

                scim_validated_list.append(users_validated)

                # Validate SCIM non-admin groups
                # This check will only check for existence

                groups_validated = self.validate_scim_groups(scim_endpoint=scim_endpoint,
                                                             token=access_token,
                                                           progress=progress,
                                                           cert_path=verify_cert)

                scim_validated_list.append(groups_validated)

                result_panel, scim_search_results_validation = scim_search_results(self._entries_dict)
                scim_validated_list.append(scim_search_results_validation)

                progress.log()
                progress.log(result_panel)
                progress.log()

            self.is_validated[scim_id] = all(scim_validated_list)
            progress.advance(task)

        except Exception as e:
            progress.log()
            progress.log(Panel.fit(Text(f"Failed to validate SCIM: {scim_id.lower()}"), style="bold red"))
            self._logger.info(f"Failed to validate {scim_id} SCIM! Error: {str(e)}")
            scim_validated_list.append(False)
            self.is_validated[scim_id] = all(scim_validated_list)
            progress.advance(task)

    def validate_scim_admin_groups(self, scim_endpoint, token, progress, ssl_enabled):

        # Validate the SCIM Admin Groups we need to check that it exists and compare parameters
        progress.log()
        progress.log(Panel.fit(Text("Validating SCIM Admin Groups"), style="bold cyan"))

        progress.log()
        progress.log("Using SCIM Groups endpoint with displayName filter to validate groups")

        # Get the SCIM Admin groups
        scim_admin_groups = self.get_admin_groups_scim()
        self._logger.info(f"SCIM Admin Groups: {scim_admin_groups}")
        if not scim_admin_groups:
            progress.log(Panel.fit(Text("No Admin Groups found in the property files!"), style="bold red"))
            self._logger.info("No Admin groups found in the property files!")
            return False

        validated_groups = []

        for admin_group, admin_data in scim_admin_groups.items():
            try:
                validated = []
                if not admin_data.get("name"):
                    progress.log(Panel.fit(Text(f"Admin group name is not provided!\n"
                                                f"Please check the Admin Groups configuration in the fncm_user_group.toml property file",
                                                style="bold red")))
                    validated.append(False)
                    continue

                name = admin_data.get("name")

                progress.log()
                progress.log(Text(f"Validating SCIM Admin Group: {name}", style="bold cyan"))
                self._logger.info(f"Validating SCIM Admin Group: {name}")

                # Query SCIM for each group using Filter
                users_url = urljoin(scim_endpoint, f"Groups/?filter=displayName eq \"{name}\"")

                scim_group_response, retrieved_data = self.query_scim(url=users_url, access_token=token,
                                                                      cert_path=ssl_enabled)

                self._logger.info(f"SCIM Group response: {scim_group_response}")
                self._logger.info(f"Retrieved data: {retrieved_data}")


                if retrieved_data:
                    scim_group_dict = scim_group_response

                    self._logger.info(f"SCIM Admin Group: {scim_group_dict}")

                    total_results = scim_group_dict.get("totalResults", 0)
                    if total_results == 0:
                        progress.log(Panel.fit(Text(f"No SCIM group data found for Admin Group: {name}",
                                                    style="bold red")))
                        self._logger.info(f"No SCIM group data found for Admin Group: {name}")
                        validated.append(False)
                        continue

                    scim_group_data = scim_group_dict['Resources'][0] if 'Resources' in scim_group_dict else {}

                    progress.log()
                    progress.log(f"SCIM data retrieved for Group: {name}")
                    progress.log()
                    progress.log(f"Validating SCIM Group data...")

                    group_display_name_attribute_mapping = admin_data.get("group_display_name_attribute", '')
                    group_name_attribute_mapping = admin_data.get("group_name_attribute", '')
                    group_unique_id_attribute_mapping = admin_data.get("group_unique_id_attribute", '')

                    group_display_name_attribute = group_display_name_attribute_mapping[0]
                    group_name_attribute = group_name_attribute_mapping[0]
                    group_unique_id_attribute = group_unique_id_attribute_mapping[0]

                    data_mapping = {'scim_key': '', 'scim_value': ''}
                    missing_claims = []
                    found_claims = {}

                    try:

                        if group_display_name_attribute in scim_group_data.keys():
                            data_element = data_mapping.copy()
                            data_element['scim_key'] = group_display_name_attribute
                            data_element['scim_value'] = scim_group_data[group_display_name_attribute]

                            found_claims["GROUP_DISPLAY_NAME"] = data_element.copy()
                        else:
                            progress.log(Panel.fit(Text(
                                f"SCIM group data does not contain {group_display_name_attribute} attribute for Admin Group: {name}",
                                style="bold red")))
                            self._logger.info(
                                f"SCIM group data does not contain {group_display_name_attribute} attribute for Admin Group: {name}")
                            missing_claims.append(group_display_name_attribute)
                            validated.append(False)
                            validated_groups.append(False)
                            continue

                        if group_name_attribute in scim_group_data.keys():
                            data_element = data_mapping.copy()
                            data_element['scim_key'] = group_name_attribute
                            data_element['scim_value'] = scim_group_data[group_name_attribute]

                            found_claims["GROUP_IDENTIFIER"] = data_element.copy()
                        else:
                            progress.log(Panel.fit(Text(
                                f"SCIM group data does not contain {group_name_attribute} attribute for Admin Group: {name}",
                                style="bold red")))
                            self._logger.info(
                                f"SCIM group data does not contain {group_name_attribute} attribute for Admin Group: {name}")
                            missing_claims.append(group_name_attribute)
                            validated.append(False)
                            validated_groups.append(False)
                            continue

                        if group_unique_id_attribute in scim_group_data.keys():
                            data_element = data_mapping.copy()
                            data_element['scim_key'] = group_unique_id_attribute
                            data_element['scim_value'] = scim_group_data[group_unique_id_attribute]

                            found_claims["UNIQUE_GROUP_IDENTIFIER"] = data_element.copy()
                        else:
                            progress.log(Panel.fit(Text(
                                f"SCIM group data does not contain {group_unique_id_attribute} attribute for Admin Group: {name}",
                                style="bold red")))
                            self._logger.info(
                                f"SCIM group data does not contain {group_unique_id_attribute} attribute for Admin Group: {name}")
                            missing_claims.append(group_unique_id_attribute)
                            validated.append(False)
                            validated_groups.append(False)
                            continue

                    except Exception as e:
                        progress.log()
                        progress.log(Panel.fit(Text(f"Failed to validate SCIM group data for Admin group:\n"
                                                    f"SCIM data is not parseable"), style="bold red"))
                        self._logger.info(f"SCIM data is not parseable, Error: {str(e)}")
                        validated.append(False)
                        validated_groups.append(False)
                        continue

                    progress.log()
                    progress.log(scim_admin_group_results(found_claims, missing_claims))

                    if len(missing_claims) > 0:
                        validated.append(False)
                        validated_groups.append(False)
                        progress.log(
                            Panel.fit(Text(f"Missing claims in the SCIM group data: {', '.join(missing_claims)}",
                                           style="bold red")))
                        self._logger.info(f"Missing claims in the SCIM group data: {', '.join(missing_claims)}")
                        continue

                    validated_groups.append(True)
                    progress.log()
                    progress.log(Panel.fit(
                        Text(f"Successfully validated all SCIM group claims for Admin Group: {name}",
                             style="bold green")))
                    self._logger.info(f"Successfully validated all SCIM group claims for Admin Group: {name}")


                else:
                    progress.log(Panel.fit(Text(f"Failed to retrieve SCIM group data for Admin Group: {name}",
                                                style="bold red")))
                    self._logger.info(f"Failed to retrieve SCIM group data for Admin Group: {name}")
                    validated.append(False)
                    validated_groups.append(False)
                    continue

            except Exception as e:
                progress.log()
                progress.log(Panel.fit(Text(f"Failed to validate SCIM Admin Group: {admin_group}\n"
                                            f"Error: {str(e)}"), style="bold red"))
                self._logger.info(f"Failed to validate SCIM Admin Group: {admin_group}!\nError: {str(e)}")
                validated.append(False)
                validated_groups.append(False)
                continue

        if all(validated_groups):
            progress.log()
            progress.log(Panel.fit(Text(f"Successfully validated all SCIM Admin Groups!"), style="bold green"))
            self._logger.info(f"Successfully validated all SCIM Admin Groups!")
        else:
            progress.log()
            progress.log(Panel.fit(Text(f"Failed to validate some SCIM Admin Groups!"), style="bold red"))
            self._logger.info(f"Failed to validate some SCIM Admin Groups!")

        return validated_groups

    def validate_scim_admin_users(self, scim_endpoint, token, progress, ssl_enabled):

        # Obtain Password grant tokens for all admin users
        # Decode the token to get the user ID, Name and Username
        # Use the ID to query the SCIM endpoint for users
        # Compare the 3 user variables

        progress.log(Panel.fit(Text("Validating SCIM Admin Users"), style="bold cyan"))

        # Get the SCIM Admin users
        scim_admin_users = self.get_admin_users_scim()
        self._logger.info(f"SCIM Admin Users: {scim_admin_users}")
        if not scim_admin_users:
            progress.log(Panel.fit(Text("No Admin users found in the property files!"), style="bold red"))
            self._logger.info("No Admin users found in the property files!")
            return False

        validated_users = []

        for admin_user, admin_data in scim_admin_users.items():
            try:
                validated = []
                if not admin_data.get("username") or not admin_data.get("password"):
                    progress.log(
                        Panel.fit(Text(f"{admin_user} does not have username or password defined!"), style="bold red"))
                    self._logger.info(f"{admin_user} does not have username or password defined!")
                    validated.append(False)
                    continue

                username = admin_data.get("username")
                password = admin_data.get("password")

                progress.log()
                progress.log(Text(f"Validating SCIM Admin User Role: {admin_user}"), style="bold cyan")
                progress.log()
                progress.log("Using password grant to retrieve access token from IDP")

                # Only 1 IDP enabled for SCIM, so using the first IDP ID
                idp_id = self._idp_prop["_idp_ids"][0]
                idp_config = self._idp_prop[idp_id]
                token_endpoint = idp_config.get("TOKEN_ENDPOINT", "")
                client_id = idp_config.get("CLIENT_ID", "")
                client_secret = idp_config.get("CLIENT_SECRET", "")

                payload = {
                    "grant_type": "password",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "username": username,
                    "password": password,
                    "scope": "openid profile email"
                }

                # Retrieve token for the admin user
                response, token_retrieved = self.retrieve_token(token_endpoint, payload, progress, ssl_enabled)

                self._logger.info(f"Response from IDP: {response}")
                self._logger.info(f"Token retrieved: {token_retrieved}")


                if token_retrieved:
                    access_token = response.get("access_token", '')
                    if not access_token:
                        progress.log(Panel.fit(
                            Text(f"Access token is not retrieved for Admin user: {admin_user}"), style="bold red"))
                        self._logger.info(f"Access token is not retrieved for Admin user: {admin_user}")
                        validated.append(False)
                        continue

                # Decode the token to get the token claims
                progress.log()
                progress.log("Using JWKS_ENDPOINT to decode the IDP token")
                jwks_uri = idp_config.get("JWKS_ENDPOINT", "")
                if not jwks_uri:
                    progress.log(Panel.fit(Text(f"JWKS URI is not provided for {idp_id} IDP!\n"
                                                f"Add the JWKS_ENDPOINT in the fncm_identity_provider.toml file"
                                                f"This is needed to be able to decode the IDP token",
                                                style="bold red")))
                    self._logger.info(f"JWKS_ENDPOINT is not provided for {idp_id} IDP!")
                    validated.append(False)
                    continue

                decoded_output = self.decode_id_token(jwks_uri, access_token, client_id, ssl_enabled, progress)
                if decoded_output:
                    self._logger.info(f"Decoded output : {decoded_output}")
                    found_claims = {}
                    missing_claims = []

                    # Create a dictionary with expected token claims from the IDP configuration
                    claim_dict = {"USER_IDENTIFIER": {
                        "key": idp_config.get("USER_IDENTIFIER", ""),
                        "value": ''
                    },
                        "UNIQUE_USER_IDENTIFIER": {
                            'key': idp_config.get("UNIQUE_USER_IDENTIFIER", ""),
                            'value': ''},
                        "USER_IDENTIFIER_TO_CREATE_SUBJECT": {
                            'key': idp_config.get("USER_IDENTIFIER_TO_CREATE_SUBJECT", ""),
                            'value': ''}
                    }

                    for claim, mapping in claim_dict.items():
                        if mapping['key'] in decoded_output:
                            found_claims[claim] = (mapping['key'], decoded_output[mapping['key']])
                            claim_dict[claim]['value'] = decoded_output[mapping['key']]
                            self._logger.info(f"{claim} is present in the decoded output.")
                        else:
                            missing_claims.append(mapping['key'])
                            self._logger.info(f"{mapping['key']} is NOT present in the decoded output.")

                    if len(missing_claims) > 0:
                        idp_token_claim_response = Text(
                            f"Missing claims in the decoded output: {', '.join(missing_claims)}")
                        progress.log()
                        progress.log(Panel.fit(idp_token_claim_response), style="bold red")
                        self._logger.info(f"Missing claims in the decoded output: {', '.join(missing_claims)}")
                        validated.append(False)
                        continue
                    else:
                        progress.log()
                        progress.log(Panel.fit(
                            Text(f"Successfully validated all token claims for Admin user role: {admin_user}"
                                 ),style="bold green"))

                    # Use the UNIQUE_USER_IDENTIFIER claim to query the SCIM endpoint for users
                    user_unique_id = claim_dict['UNIQUE_USER_IDENTIFIER']['value']
                    progress.log()
                    progress.log(f"Using UNIQUE_USER_IDENTIFIER to query the SCIM endpoint: {user_unique_id}")

                    users_url = urljoin(scim_endpoint, f"Users/{user_unique_id}")

                    scim_user_response, retrieved_data = self.query_scim(url=users_url, access_token=token,
                                                                         cert_path=ssl_enabled)

                    if retrieved_data:
                        self._logger.info(f"SCIM user data retrieved: {user_unique_id}")
                        self._logger.info(f"SCIM user data retrieved: {scim_user_response}")
                        progress.log()
                        progress.log(f"SCIM data retrieved for ID: {user_unique_id}")
                        progress.log()
                        progress.log(f"Validating SCIM User data...")

                        user_display_name_attribute_mapping = admin_data.get("user_display_name_attribute", '')
                        user_name_attribute_mapping = admin_data.get("user_name_attribute", '')
                        user_unique_id_attribute_mapping = admin_data.get("user_unique_id_attribute", '')

                        user_display_name_attribute = user_display_name_attribute_mapping[0]
                        user_name_attribute = user_name_attribute_mapping[0]
                        user_unique_id_attribute = user_unique_id_attribute_mapping[0]

                        found_claims = {}
                        missing_claims = []
                        unmatched_claims = []
                        data_mapping = {'scim_key': '', 'scim_value': '', 'token_key': '', 'token_value': ''}

                        try:
                            # Check if the user_display_name_attribute, user_name_attribute and user_unique_id_attribute are present in the SCIM user data
                            # Check the user_unique_id_attribute in the scim data
                            if user_unique_id_attribute in scim_user_response.keys():
                                data_element = data_mapping.copy()
                                data_element['scim_key'] = user_unique_id_attribute
                                data_element['scim_value'] = scim_user_response[user_unique_id_attribute]
                                data_element['token_key'] = claim_dict['UNIQUE_USER_IDENTIFIER']['key']
                                data_element['token_value'] = claim_dict['UNIQUE_USER_IDENTIFIER']['value']

                                if data_element['scim_value'] != data_element['token_value']:
                                    unmatched_claims.append(user_unique_id_attribute)
                                    self._logger.info(
                                        f"{user_unique_id_attribute} is present in the SCIM data, but does not match with the token value.")

                                self._logger.info(f"Found {user_unique_id_attribute} in the SCIM data: {data_element}")

                                found_claims["UNIQUE_USER_IDENTIFIER"] = data_element.copy()
                                self._logger.info(f"{user_unique_id_attribute} is present in the SCIM data.")
                            else:
                                missing_claims.append(user_unique_id_attribute)
                                self._logger.info(f"{user_unique_id_attribute} is NOT present in the SCIM data.")

                            # Check the user_name_attribute in the scim data
                            if user_name_attribute in scim_user_response.keys():
                                data_element = data_mapping.copy()
                                data_element['scim_key'] = user_name_attribute
                                data_element['scim_value'] = scim_user_response[user_name_attribute]
                                data_element['token_key'] = claim_dict['USER_IDENTIFIER']['key']
                                data_element['token_value'] = claim_dict['USER_IDENTIFIER']['value']

                                self._logger.info(f"Found {user_name_attribute} in the SCIM data: {data_element}")

                                if data_element['scim_value'] != data_element['token_value']:
                                    unmatched_claims.append(user_name_attribute)
                                    self._logger.info(
                                        f"{user_name_attribute} is present in the SCIM data, but does not match with the token value.")

                                found_claims["USER_IDENTIFIER"] = data_element
                                self._logger.info(f"{user_name_attribute} is present in the SCIM data.")

                            else:
                                missing_claims.append(user_name_attribute)
                                self._logger.info(f"{user_name_attribute} is NOT present in the SCIM data.")

                            # Multiple SCIM attributes can be used for display name, so checking for all
                            name_keys = ['formatted', 'familyName', 'givenName']
                            if user_display_name_attribute in scim_user_response:
                                data_element = data_mapping.copy()
                                data_element['scim_key'] = user_display_name_attribute
                                data_element['scim_value'] = scim_user_response[user_display_name_attribute]
                                data_element['token_key'] = "-"
                                data_element['token_value'] = "-"

                                self._logger.info(
                                    f"Found {user_display_name_attribute} in the SCIM data: {data_element}")

                                found_claims["USER_DISPLAY_NAME"] = data_element
                                self._logger.info(f"{user_display_name_attribute} is present in the SCIM data.")
                            else:
                                for key in name_keys:
                                    if key in scim_user_response['name'].keys():
                                        data_element = data_mapping.copy()
                                        data_element['scim_key'] = f"name.{key}"
                                        data_element['scim_value'] = scim_user_response['name'][key]
                                        data_element['token_key'] = "-"
                                        data_element['token_value'] = "-"

                                        found_claims["USER_DISPLAY_NAME"] = data_element
                                        self._logger.info(f"name.{key} is present in the SCIM data.")
                                        break
                                else:
                                    missing_claims.append(user_display_name_attribute)
                                    self._logger.info(f"{user_display_name_attribute} is NOT present in the SCIM data.")
                        except Exception as e:
                            progress.log()
                            progress.log(Panel.fit(Text(f"Failed to validate SCIM user data for Admin user:\n"
                                                        f"SCIM data is not parseable"), style="bold red"))
                            self._logger.info(f"SCIM data is not parseable, Error: {str(e)}")
                            validated.append(False)
                            continue

                        if len(missing_claims) > 0 or len(unmatched_claims) > 0:
                            validated.append(False)

                        # Check SCIM data for group information
                        progress.log()
                        progress.log(f"Checking SCIM user data for group information...")
                        if 'groups' not in scim_user_response.keys():
                            progress.log()
                            progress.log(Panel.fit(Text(
                                f"SCIM user data does not contain 'groups' information for Admin user: {admin_user}\n"
                                f"Group Membership needs to be present in SCIM data"), style="bold red"))
                            self._logger.info(
                                f"SCIM user data does not contain 'groups' information for Admin user: {admin_user}")
                            validated.append(False)
                            continue
                        else:
                            group_membership = scim_user_response.get('groups', [])

                        progress.log()
                        progress.log(scim_admin_user_results(admin_user, found_claims, missing_claims, group_membership,
                                                             unmatched_claims))


                    else:
                        progress.log()
                        progress.log(Panel.fit(Text(f"Failed to retrieve SCIM user data for Admin user: {admin_user}\n"
                                                    f"Please check the SCIM configuration in the fncm_scim_server.toml file",
                                                    style="bold red")))
                        self._logger.info(f"Failed to retrieve SCIM user data for Admin user: {admin_user}!")
                        continue

                    # If all checks passed, mark the admin user as validated
                    if any(not item for item in validated):
                        progress.log(Panel.fit(Text(f"Failed to validate SCIM Admin User Role: {admin_user}\n"
                                                    f"Please check the SCIM & IDP configuration in the fncm_scim_server.toml and fncm_identity_provider.toml file",
                                                    style="bold red")))
                        self._logger.info(f"Failed to validate SCIM Admin User Role: {admin_user}!")
                        validated_users.append(False)
                    else:
                        validated_users.append(True)
                        progress.log()
                        progress.log(Panel.fit(
                            Text(f"Successfully validated SCIM Admin User Role: {admin_user}"), style="bold green"))
                        self._logger.info(f"Successfully validated SCIM Admin User Role: {admin_user}")

            except Exception as e:
                progress.log(Panel.fit(Text(f"Failed to validate SCIM Admin User Role: {admin_user}\n"
                                            f"Error: {str(e)}"), style="bold red"))
                self._logger.info(f"Failed to validate SCIM Admin user: {admin_user}! Error: {str(e)}")
                validated.append(False)
                continue

        if all(validated_users):
            progress.log()
            progress.log(Panel.fit(Text(f"Successfully validated all SCIM Admin Users!"), style="bold green"))
            self._logger.info(f"Successfully validated all SCIM Admin Users!")

        return validated_users

    def get_entries_ldap(self):
        entries = {**self.get_users_and_groups_ldap(),
                   **self.get_users_ldap(),
                   **self.get_groups_ldap()}

        self._logger.info(f"Entries to be searched in LDAP: {entries}")
        return entries

    def get_entries_scim(self):
        entries = {**self.get_users_scim(),
                   **self.get_groups_scim(),
                   **self.get_users_and_groups_scim()}

        self._logger.info(f"Entries to be searched in SCIM: {entries}")
        return entries

    def get_admin_groups_scim(self):

        # function to get all groups needed to be searched if present in scim
        # SCIM groups need to have both group name and members to be verified
        groups_dict = {}

        # Group Attributes
        ## The SCIM group name attributes
        group_unique_id_attribute = 'id'
        group_display_name_attribute = 'displayName'
        group_name_attribute = 'displayName'

        group_element = {
            'name': '',
            'group_unique_id_attribute': (group_unique_id_attribute, ''),
            'group_display_name_attribute': (group_display_name_attribute, ''),
            'group_name_attribute': (group_name_attribute, ''),
            "members": []
        }

        groups_list = []

        # Collect all groups defined in user_group property file
        if "GCD_ADMIN_GROUPS_NAME" in self._user_group_prop.keys():
            groups_list.extend(self._user_group_prop["GCD_ADMIN_GROUPS_NAME"])

        # remove all duplicate groups from list
        groups_list = list(set(groups_list))

        # Construct a dictionary to store username, count and ldap id
        groups_dict = {}
        for group in groups_list:
            group_entry = group_element.copy()
            group_entry["name"] = group

            groups_dict[group] = group_entry

        return groups_dict

    def get_admin_users_scim(self):
        # function to get all users needed to be searched if present in scim
        # SCIM users need to have both username and password to be verified
        users_dict = {}

        # User Attributes
        # TODO: Make these configurable
        user_unique_id_attribute = "id"
        user_display_name_attribute = "displayName"
        user_name_attribute = "userName"

        user_element = {
            "username": '',
            "password": '',
            "access_token": '',
            'user_display_name_attribute': (user_display_name_attribute, ''),
            'user_name_attribute': (user_name_attribute, ''),
            'user_unique_id_attribute': (user_unique_id_attribute, ''),
            'groups': [],
            'type': scim_entry_types.ADMIN
        }

        # Collect all users defined in user_group property file
        if "FNCM_LOGIN_USER" in self._user_group_prop.keys():
            user = user_element.copy()

            user["username"] = self._user_group_prop["FNCM_LOGIN_USER"]

            if "FNCM_LOGIN_PASSWORD" in self._user_group_prop.keys():
                user["password"] = self._user_group_prop["FNCM_LOGIN_PASSWORD"]

            users_dict["FileNet Admin"] = user

        if "ICN_LOGIN_USER" in self._user_group_prop.keys():
            user = user_element.copy()

            user["username"] = self._user_group_prop["ICN_LOGIN_USER"]

            if "ICN_LOGIN_PASSWORD" in self._user_group_prop.keys():
                user["password"] = self._user_group_prop["ICN_LOGIN_PASSWORD"]

            users_dict["Navigator Admin"] = user

        self._logger.info(f"Users defined in user_group property file: {users_dict}")

        return users_dict

    def get_groups_scim(self):

        # function to get all groups needed to be searched if present in scim
        # SCIM groups need to have both group name and members to be verified

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
            groups_dict[group] = {"type": scim_entry_types.GROUP, "count": 0, "scim_id": []}

        return groups_dict

    def get_users_and_groups_scim(self):
        entry_list = []
        if "CONTENT_INITIALIZATION_ENABLE" in self._user_group_prop.keys():
            if self._user_group_prop["CONTENT_INITIALIZATION_ENABLE"]:
                for os_id in self._db_prop["_os_ids"]:
                    entry_list.extend(self._user_group_prop[os_id]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"])
        entry_dict = {}
        for entry in entry_list:
            entry_dict[entry] = {"type": scim_entry_types.USER_GROUP, "count": 0, "scim_id": []}

        return entry_dict

    # function to get all users needed to be searched if present in ldap
    def get_users_scim(self):
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
            users_dict[user] = {"type": scim_entry_types.USER, "count": 0, "scim_id": []}

        return users_dict

    # function to get all users needed to be searched if present in ldap
    def get_users_ldap(self):
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
            users_dict[user] = {"type": ldap_entry_types.USER, "count": 0, "ldap_id": [], "groups": []}

        return users_dict

    # function to get all groups needed to be searched if present in ldap
    def get_groups_ldap(self):
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
            groups_dict[group] = {"type": ldap_entry_types.GROUP, "count": 0, "ldap_id": [], "members": []}

        return groups_dict

        # Validates if user is present in the LDAP

    def get_users_and_groups_ldap(self):
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

        progress.log()
        progress.log(Text(f"Testing Authentication of \"{server}\" with Bind DN: \"{bind_dn}\""))

        authenticated = False
        authenticated, valid_users_and_groups = self.get_ldap_connection(ldap_id, progress, ssl_enabled, cert_path)

        if authenticated:
            if ssl_enabled:
                progress.log()
                progress.log(Panel.fit(Text(f"Successfully authenticated with \"{bind_dn}\" over SSL!"), style="bold green"))
            else:
                progress.log()
                progress.log(Panel.fit(Text(f"Successfully authenticated with \"{bind_dn}\" over non-SSL!"), style="bold green"))
            progress.log()

        return authenticated, valid_users_and_groups

    def get_user_password_list(self, bind_dn, bind_dn_password):
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

        users = self.get_users_ldap()
        for user in users.keys():
            if user != ldap_username:
                encoded_user = self.encode_base64(user)
                user_password_list = user_password_list + f"username:{encoded_user};"
        return user_password_list

    def get_group_list(self):
        """
        Method name: get_group_list
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Fetch the list of groups from ldap property files as a string to use in the java command
        Parameters: None
        Returns:
           group_list (str) : list of groups separated by commmas
        """
        group_list = ""
        groups = self.get_groups_ldap()
        for group in groups.keys():
            if group not in group_list:
                group_list = group_list + f"{group},"
        return group_list

    def get_usergroup_list(self, group_list):
        """
        Method name: get_usergroup_list
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description: Fetch the list of user-groups from ldap property files as a string to use in the java command
        Parameters:
            group_list (str) : list of groups separated by commmas
        Returns:
           group_list (str) : appended list of groups separated by commmas
        """
        groups = self.get_users_and_groups_ldap()
        for group in groups.keys():
            if group not in group_list:
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
            - If SSL is enabled, the function add the cert into the existing truststore
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

        user_password_list = str(self.get_user_password_list(bind_dn, bind_dn_password))
        initial_group_list = self.get_group_list()
        group_list = str(self.get_usergroup_list(initial_group_list))

        # Validate LDAP Connection
        # FIPS is always set to False. Reference defect : https://jsw.ibm.com/browse/DBACLD-154012.
        fips_enabled = False
        authenticated = False
        valid_users_and_groups = ""

        if ssl_enabled:
            if not os.path.exists(cert_path):
                self._logger.error("LDAP certificate not found")
                return authenticated, valid_users_and_groups

            # Add LDAP cert into truststore
            self.__add_cert_to_tmp_truststore(cert_path, ldap_id.lower(), progress)

            self._logger.info(f"Checking ldap SSL connection test using LdapTest.jar for the server: {server} using Bind DN :{bind_dn}")

            ldap_test_cmd = (f"java -D\"semeru.fips={self._fips_enabled}\" "
                            + f"-D\"javax.net.ssl.trustStoreType={self._storetype}\" "
                            + f"-D\"javax.net.ssl.trustStore={self._truststore_path}\" "
                            + f"-Djavax.net.ssl.trustStorePassword='{self._truststore_pwd}' "
                            + f"-jar \"{self._LDAP_JAR_PATH}\" -u 'ldaps://{server}:{port}' "
                            + f"-b '{base_dn}' -D '{bind_dn}' -w '{bind_dn_password}' "
                            + f"-additionalvalidation -gdn '{group_base_dn}' "
                            + f"-upl '{user_password_list}' -gl '{group_list}' "
                            + f"-uf '{user_filter}' -gf '{group_filter}'")

            java_msg = (f"java -D\"semeru.fips={self._fips_enabled}\" "
                        + f"-D\"javax.net.ssl.trustStoreType={self._storetype}\" "
                        + f"-D\"javax.net.ssl.trustStore={self._truststore_path}\" "
                        + f"-Djavax.net.ssl.trustStorePassword='{self._truststore_pwd}' "
                        + f"-jar \"{self._LDAP_JAR_PATH}\" -u 'ldaps://{server}:{port}' "
                        + f"-b '{base_dn}' -D '{bind_dn}' -w '*****' ")

        else:
            self._logger.info(f"Checking ldap non-SSL connection test using LdapTest.jar for the server: {server} using Bind DN :{bind_dn}")

            ldap_test_cmd = (f"java -D\"semeru.fips={fips_enabled}\" -jar \"{self._LDAP_JAR_PATH}\" "
                             + f"-u 'ldap://{server}:{port}' -b '{base_dn}' "
                             + f"-D '{bind_dn}' -w '{bind_dn_password}' "
                             + f"-additionalvalidation -gdn '{group_base_dn}' "
                             + f"-upl '{user_password_list}' -gl '{group_list}' "
                             + f"-uf '{user_filter}' -gf '{group_filter}'")

            java_msg = (f"java -D\"semeru.fips={self._fips_enabled}\" "
                        + f"-jar \"{self._LDAP_JAR_PATH}\" -u 'ldap://{server}:{port}' "
                        + f"-b '{base_dn}' -D '{bind_dn}' -w '*****' ")

        # Running java command for ldap binding using LdapTest.jar
        self._logger.info(f"Java command for ldap binding using LdapTest.jar : {ldap_test_cmd}")
        try:
            progress.log()
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
                panel = Panel.fit(java_msg, title="Execute the following command for more details",
                                  style="bold yellow")
                progress.log(panel)
                progress.log()
            elif "bind failed" in bind_output or "Error while binding to LDAP" in bind_output:
                progress.log(bind_output)
                progress.log(Panel.fit(Text(
                    f"Unable to connect to LDAP server '{server}' using Bind DN '{bind_dn}', please check configuration in ldap property again."),
                    style="bold red"))
                progress.log()
                panel = Panel.fit(java_msg, title="Execute the following command for more details", style="bold yellow")
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

    def encode_base64(self, data):
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
        try:
            self._logger.info(f"Encoding data : {data}.")
            encoded_data = base64.b64encode(data.encode()).decode()
            self._logger.info(f"Encoded data : {encoded_data}.")
            return encoded_data
        except Exception as e:
            self._logger.error(f"An error occurred during encoded the data : {e}")

    def run_command(self, command):
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
        try:
            self._logger.info(f"Executing command : {command}")
            result = subprocess.run(shlex.split(command), capture_output=True, text=True)
            if result.returncode != 0:
                self._logger.error(
                    f"\nAn error occurred during execution of the command -- stdout : {result.stdout}, stderror : {result.stderr}")
                return result.stderr
            self._logger.info(f"Output of execution : {result.stdout}")
            return result.stdout
        except Exception as e:
            self._logger.error(f"An exception occurred during running the command -- {command} : {e}")
            return str(e)

    def remove_file(self, file_path):
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
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self._logger.info(f"Removed the file : {file_path}")
        except Exception as e:
            self._logger.error(f"An exception occurred during removal of file : {file_path}. Error : {e}")

    def parse_ldap_output(self, output):
        """
        Method name: parse_ldap_output
        Author: Anisha Suresh (anisha-suresh@ibm.com)
        Description:  Retrieves the validated users and groups from the ldap bind output
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
            self._logger.error(f"An exception occurred during fetching valid users and groups: {e}.")
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
        if entry in valid_entry:
            return entry
        else:
            return

    def ldap_search(self, ldap_id):
        """
        Method name: ldap_search
        Description: Authenticates and get valid users and groups from the LDAP server.
                    Then if authenticated successfully, updates the valid entries from dictionary _entries_dict.
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

            authenticated = self.is_validated[ldap_id]
            valid_users_and_groups = self.ldap_user_groups[ldap_id]

            if authenticated:
                for entry, value in self._entries_dict.items():
                    if value['type'] == ldap_entry_types.USER:
                        if self.ldap_item_exists(entry, valid_users_and_groups['users']):
                            value["count"] += 1
                            value["ldap_id"].append(ldap_id)

                    elif value['type'] == ldap_entry_types.GROUP:
                        if self.ldap_item_exists(entry, valid_users_and_groups['groups']):
                            value["count"] += 1
                            value["ldap_id"].append(ldap_id)

                    elif value['type'] == ldap_entry_types.USER_GROUP:
                        if self.ldap_item_exists(entry, valid_users_and_groups['users']):
                            value["type"] = ldap_entry_types.USER
                            value["count"] += 1
                            value["ldap_id"].append(ldap_id)
                            continue
                        if self.ldap_item_exists(entry, valid_users_and_groups['groups']):
                            value["type"] = ldap_entry_types.GROUP
                            value["count"] += 1
                            value["ldap_id"].append(ldap_id)
                            continue
        except Exception as e:
            self._logger.info(f"Error found in ldap_search function in validation script --- {str(e)}")

    # Validates a single LDAP, defaults to the first one by its id: "LDAP"
    def validate_server(self, progress, server, port, ssl_enabled=False, cert_path="", display_rtt=True, pg=False):
        connected = False

        # Test for SSL connections
        # Return a connection object, RTT and a boolean indicating if the connection was successful
        if ssl_enabled:
            progress.log(Text(f"Validating Server \"{server}\" Reachability over SSL"))
            progress.log()
            self._logger.info(f"Validating SSL connection to {server}:{port} with certificate {cert_path}")
            if cert_path:
                cert, san_list  = clean_and_combine_pem_files(self._logger, cert_path, self._TMP_DIR, server)
                self._logger.info(f"Using certificate: {cert}")
            else:
                cert = ''
            conn_result, rtt, connected = connect_to_server(host=server, port=int(port), ssl=True,
                                                            client_cert_file=cert, pg=pg, progress=progress, logger=self._logger)
        else:
            progress.log(Text(f"Validating Server \"{server}\" Reachability"))
            progress.log()
            conn_result, rtt, connected = connect_to_server(host=server, port=int(port), progress=progress, logger=self._logger)

        # Construct the message to be displayed
        # If the SSL connection was successful, display the cipher
        # If connection is successful display the RTT
        # RTT display can be disabled by setting display_rtt to False (RTT for Database is calculated through JDBC driver)
        if connected:
            if ssl_enabled:
                message = Text(f"Reachability to \"{server}\" succeeded over SSL!")
                progress.log()
                progress.log(Panel.fit(message, style="bold green"))

                # If SSL connections were successful, then cipher passed
                self.output_cipher(conn_result.cipher(),
                                   conn_result.version(), progress)
            else:
                message = Text(f"Reachability to \"{server}\" succeeded!")
                progress.log()
                progress.log(Panel.fit(message, style="bold green"))

            if display_rtt:
                self.output_latency(rtt, progress, "LDAP")
        else:
            if not ssl_enabled:
                message = Text(f"Reachability to \"{server}\" failed!\n"
                               f"Please check configuration in Property Files")
                progress.log()
                progress.log(Panel.fit(message, style="bold red"))

        return connected

    # Output cipher for the supplied connection
    @staticmethod
    def output_cipher(cipher, protocol, progress):
        message = Text(f"SSL protocol used: \"{protocol}\", is supported!", style="bold green")
        progress.log()
        progress.log(message)

        message = Text(f"SSL cipher used: \"{cipher[0]}\", is accepted!", style="bold green")
        progress.log()
        progress.log(message)

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

        progress.log()
        progress.log(Panel.fit(Text("Detected Connection Latency: {:.2f}ms \n"
                          "{}".format(rtt, message), style=style), style=style))
        progress.log()

    # Use JAR to test DB connection
    def __check_connection_with_jar(self, jar_cmd, progress):
        try:
            if platform.system() == 'Windows':
                output = subprocess.check_output(["powershell.exe", jar_cmd], shell=True, stderr=subprocess.PIPE,
                                                 universal_newlines=True)
            else:
                output = subprocess.check_output(jar_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            self._logger.info(output)
            if "failure" in output.lower():
                raise subprocess.CalledProcessError(1, jar_cmd, stderr=output)
            round_trip_statement = output.split("Round Trip time:")[1]
            match = re.search(r'([\d.]+)', round_trip_statement)
            if match:
                self.roundtriptime = float(match.group(1))

            return True
        except subprocess.CalledProcessError as error:
            self._logger.info(error.stderr)
            progress.log()
            progress.log(Text(error.stderr, style="bold red"))

            if "PKIX path building failed" in error.stderr or "Connection failure with : TLSv1.3" in error.stderr:
                progress.log()
                progress.log(Text(
                    f"SSL Certificate could not be validated, please check the supplied certificate in propertyFile/{self._namespace}/ssl-certs.",
                    style="bold red"))

            return False

    def get_unique_storageclass(self) -> set:
        sc_set = {self._deploy_prop["SLOW_FILE_STORAGE_CLASSNAME"], self._deploy_prop["MEDIUM_FILE_STORAGE_CLASSNAME"],
                  self._deploy_prop["FAST_FILE_STORAGE_CLASSNAME"]}
        return sc_set

    def validate_all_storage_classes(self, task1, progress):
        # Uses a set to skip checked the same storage class twice
        sc_set = self.get_unique_storageclass()

        for storage_class in sc_set:
            progress.log(Panel.fit(Text(f"Validating storage class: {storage_class}"), style="bold cyan"))
            self.validate_sample_sc(storage_class, "ReadWriteMany", "fncm-test-pvc", task1, progress)

    def __check_pvc_liveliness(self, sample_pvc_name, task1, progress):
        # 30 attempts, 10 seconds each; total ~300 seconds / 5 mins
        TIMEOUT_ATTEMPTS = 30
        SLEEP_TIMER = 10

        for i in range(TIMEOUT_ATTEMPTS):
            progress.log(f"\nChecking for {sample_pvc_name} liveness - Attempt {i + 1}/{TIMEOUT_ATTEMPTS}\n")
            validated = True
            try:
                validated = self._kube.check_pvc_bound(namespace=self._namespace, pvc_name=sample_pvc_name)
                if not validated:
                    progress.log(Text(f"\n\"{sample_pvc_name}\" not yet found, waiting {SLEEP_TIMER} seconds to retry",
                                      style="bold yellow"))
                    progress.log()
                    time.sleep(SLEEP_TIMER)
                else:
                    progress.log(
                        Panel.fit(Text(f"\"{sample_pvc_name}\" is found in Bound state!"), style="bold green"))
                    progress.log()
                    progress.advance(task1)
                    return True
            except Exception as e:
                # If cannot find pvc in bound PVC grep, validation is not complete
                # and will keep waiting
                self._logger.exception(e)
                progress.log(f"Error occurred while when checking \"{sample_pvc_name}\" liveness")
                progress.log()
                progress.log(Syntax(str(e.stderr), "bash", theme="ansi_dark"))
                return False


        # Passed 60 seconds and all attempts, still cannot find PVC
        self._logger.info(f"Failed to allocate the persistent volumes using PVC: \"{sample_pvc_name}\"!")
        progress.log()
        progress.log(Panel.fit(Text(f"Failed to allocate PVC: \"{sample_pvc_name}\"!"), style="bold red"))
        progress.advance(task1)
        return False

    # Creates a storage class yaml to apply
    def validate_sample_sc(self, sc_name, sc_mode, sample_pvc_name, task1, progress):
        # check if storage class is present
        validated = True
        try:
            if self._kube.in_cluster:
                self._logger.info("Running inside cluster, skipping storage class validation")
                progress.log()
                progress.log(Panel.fit(Text(f"Skipping storage class: \"{sc_name}\" validation, running inside cluster", style="bold yellow")))
                self.is_validated[sc_name] = True

            storage_classes = self._kube.list_storage_classes()

            if sc_name in storage_classes:
                validated = True
            else:
                validated = False

            if validated:
                progress.log()
                progress.log(Panel.fit(Text(f"Found storage class: \"{sc_name}\""), style="bold green"))
            if not validated:
                self._logger.info(f"Failed to find storage class: \"{sc_name}\"!\n")
                progress.log()
                progress.log(Panel.fit(Text(f"Storage class: \"{sc_name}\" not found!"), style="bold red"))
                self.is_validated[sc_name] = False
                progress.advance(task1)
                return self.is_validated[sc_name]

        except Exception as e:
            self._logger.info(e)
            progress.log()
            progress.log(Panel.fit(Text(f"Storage classes cannot be retrieved, this is usually caused by cluster permission issues\n"
                         f"Test PVC will still be created, without storage class check!"), style="bold yellow"))
            validated = False

        # remove the existing temp file if previously not removed
        pvc_filename = f"{sc_name}.yaml"
        sample_yaml_path = os.path.join(self._TMP_DIR, pvc_filename)

        data = {
            "sc_name": sc_name,
            "size": self._pvc_size,
            "sc_mode": sc_mode
        }

        rendered_pvc = self.render_pvc_template(data, sample_pvc_name)

        # write the secret data into a yaml
        with open(sample_yaml_path, 'w+') as file:
            file.write(rendered_pvc)
            self._logger.info(f"Created PVC yaml file: {pvc_filename}")

        self._kube.apply_cluster_resource_files(resource_type='pvc', resource_file=sample_yaml_path, namespace=self._namespace)

        progress.log()
        progress.log(f"Sample PVC created with storage class: {sc_name}")
        self.is_validated[sc_name] = self.__check_pvc_liveliness(sample_pvc_name, task1, progress)

        self._kube.delete_pvc(self._namespace, sample_pvc_name)

        return self.is_validated[sc_name]

    def render_pvc_template(self, values, pvc_name):
        # Get the template from the environment
        template = self._template_env.get_template('pvc.j2')

        # Render the template with the provided values
        rendered_pvc = template.render(
            values=values,
            sample_pvc_name=pvc_name
        )

        return rendered_pvc

    # Looks for yaml files in the folder path and applies it with kubectl, will not look int subfolders.
    def auto_apply_all_secrets_in_folder(self, folder_path):
        yaml_ext = [".yaml", ".yml"]
        files = self.__files_in_dir(folder_path, yaml_ext)
        if len(files) == 0:
            self._logger.info(f"No files with extension:{str(yaml_ext)} found in {folder_path}!")

        for f in files:
            # Get name from secret yaml
            self._logger.info(f"Applying secret from file: {f}")
            applied = self._kube.apply_cluster_resource_files("secret", os.path.join(folder_path, f), namespace=self._namespace)
            if applied:
                print(Panel.fit(Text(f"Secret Applied: {f}", style="bold cyan")))
            else:
                print(Panel.fit(Text(f"Failed to apply secret: {f}", style="bold red")))

    def auto_apply_secrets_ssl(self):
        generated_folder = os.path.join(os.getcwd(), "generatedFiles", self._namespace)
        self.auto_apply_all_secrets_in_folder(folder_path=os.path.join(generated_folder, "secrets"))
        # only if ssl secrets folder is present will they be applied
        # Build path where secrets are generated
        secret_directories = [os.path.join(generated_folder,  "ssl"),
                              os.path.join(generated_folder,  "ssl", "trusted-certs")]

        for folder_path in secret_directories:
            if os.path.exists(folder_path):
                self.auto_apply_all_secrets_in_folder(folder_path=folder_path)

    def auto_apply_cr(self):
        generated_folder = os.path.join(os.getcwd(), "generatedFiles", self._namespace)
        applied = self._kube.apply_cluster_resource_files("custom resource", os.path.join(generated_folder, "ibm_fncm_cr_production.yaml"), namespace=self._namespace)
        if applied:
            print(Panel.fit(Text(f"Custom Resource Applied: ibm_fncm_cr_production.yaml", style="bold cyan")))
            return True

        print(Panel.fit(Text(f"Failed to apply custom resource: ibm_fncm_cr_production.yaml", style="bold red")))
        return False
