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
import shutil
import string
import subprocess
import time

import typer
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from rich.panel import Panel
from rich import print
from rich.syntax import Syntax
from rich.text import Text

from helper_scripts.property.read_prop import *
from helper_scripts.utilities.utilites import collect_visible_files


class Validate:
    # Is commandline keytool command present in this env?
    # None = Unchecked; True = Present; False = Not present
    _keytool_present = None

    # Default paths for property files
    # Used for validating property files in their preset location
    # without passing in an ReadProp dictionary object in init
    _DEFAULT_DB_PROP_PATH = os.path.join(os.getcwd(), "propertyFile", "fncm_db_server.toml")
    _DEFAULT_LDAP_PROP_PATH = os.path.join(os.getcwd(), "propertyFile", "fncm_ldap_server.toml")
    _DEFAULT_DEPLOY_PROP_PATH = os.path.join(os.getcwd(), "propertyFile", "fncm_deployment.toml")

    _STORAGE_CLASS_TEMPLATE_YAML = os.path.join(os.getcwd(), "helper_scripts", "validate", "templates",
                                                "storage_class_sample.yaml")

    _JAR_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "jars")

    _JDBC_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "jdbc")

    _TMP_DIR = os.path.join(os.getcwd(), "helper_scripts", "validate", "tmp")

    # Cannot default prop to a ReadProp object because Readprop requires a logger to be pased in
    def __init__(self, logger, db_prop=None,
                 ldap_prop=None,
                 deploy_prop=None):
        prop_obj = None
        if db_prop:
            self._db_prop = db_prop
        else:
            prop_obj = ReadPropDb(self._DEFAULT_DB_PROP_PATH, logger)
            self._db_prop = prop_obj.to_dict()

        if ldap_prop:
            self._ldap_prop = ldap_prop
        else:
            prop_obj = ReadPropLdap(self._DEFAULT_LDAP_PROP_PATH, logger)
            self._ldap_prop = prop_obj.to_dict()

        if deploy_prop:
            self._deploy_prop = deploy_prop
        else:
            prop_obj = ReadProp(self._DEFAULT_DEPLOY_PROP_PATH, logger)
            self._deploy_prop = prop_obj.to_dict()

        self.required_fields = prop_obj.required_fields

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

    def check_env_util(self) -> list:
        missing_tools = []

        self._keytool_present = self.__is_cmd_present("keytool")
        if not self._keytool_present:
            missing_tools.append("keytool")
        self._java_present = self.__is_cmd_present("java")
        if not self._java_present:
            missing_tools.append("java")

        self._kubectl_present = self.__is_cmd_present("kubectl")
        if not self._kubectl_present:
            missing_tools.append("kubectl")

        if self._kubectl_present:
            self._kubectl_logged_in = self.__is_kubectl_logged_in()
            if not self._kubectl_logged_in:
                missing_tools.append("connection")
        return missing_tools

    # Check keytool,kubernetes,java
    def __is_cmd_present(self, cmd):
        try:
            # TODO: Add windows support if where is missing
            if platform.system() == 'Windows':
                subprocess.check_output("where " + cmd, stderr=subprocess.PIPE, shell=True)
            else:
                subprocess.check_output("which " + cmd, stderr=subprocess.PIPE, shell=True)
            return True
        except subprocess.CalledProcessError as error:
            self._logger.info(
                f"{cmd} is not found on this machine, please install the necessary dependencies. Error: {error}")
            return False

    def __check_java(self):
        if not self._java_present:
            raise typer.Exit(code=1)

    def __check_keytool(self):
        if not self._keytool_present:
            raise typer.Exit(code=1)

    def __check_kubectl(self):
        if not self._kubectl_present:
            raise typer.Exit(code=1)

    # Checks whether or not we are properly logged into a Kubernetes/OCP cluster
    # 'kubectl config current-context' is not sufficient it will show most recent cluster
    # but we cannot apply yaml which is needed to test storage classes
    # (!!!) DOES NOT WORK WHEN INSIDE OPERATOR POD
    def __is_kubectl_logged_in(self):
        try:
            subprocess.check_output("kubectl get pods </dev/null", shell=True, stderr=subprocess.PIPE,
                                    universal_newlines=True)
            return True
        except subprocess.CalledProcessError as error:
            self._logger.info("Kubectl is not logged into any cluster and " \
                              + f"will cause errors when checking storage classes; error")
            return False

    def cleanup_tmp(self):
        if os.path.exists(self._TMP_DIR):
            shutil.rmtree(self._TMP_DIR)

    def __recreate_folder(self, directory):
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.mkdir(directory)
        return directory

    def validate_all_db(self, task3, progress):
        progress.log(Panel.fit(Text("Validating GCD Database Connection", style="bold cyan")))
        self.validate_db("GCD", task3, progress)

        progress.log(Panel.fit(Text("Validating ICN Database Connection", style="bold cyan")))
        self.validate_db("ICN", task3, progress)

        for os_id in self._db_prop["_os_ids"]:
            progress.log(Panel.fit(Text(f"Validating {os_id} Database Connection", style="bold cyan")))
            self.validate_db(os_id, task3, progress)

    def parse_shell_command (self, parameter):
        # Create a function to escape any single quotes in the password
        # This is needed for the DB connection jar

        # Escape any single quotes in the password
        parameter = parameter.replace("'", "'\\''")

        return parameter

    def validate_db(self, db_label, task3, progress):
        db_servername = self._db_prop[db_label]['DATABASE_SERVERNAME']
        db_port = self._db_prop[db_label]['DATABASE_PORT']
        db_name = self._db_prop[db_label]['DATABASE_NAME']
        db_user = self._db_prop[db_label]['DATABASE_USERNAME']
        db_pwd = self._db_prop[db_label]['DATABASE_PASSWORD']
        db_type = self._db_prop['DATABASE_TYPE']

        # Escape any single quotes in the password & username
        db_pwd = self.parse_shell_command(db_pwd)
        db_user = self.parse_shell_command(db_user)

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

        if self._db_prop['DATABASE_SSL_ENABLE']:
            cert_dir = os.path.join(os.getcwd(), "propertyFile", "ssl-certs", db_label.lower())
            self.__create_tmp_folder()

            if db_type == "db2":
                cert = self.__get_file_from_folder(file_dir=cert_dir,
                                                   extensions=[".crt", ".cer", ".pem", ".cert"])
                jar_cmd = "java -Duser.language=en -Duser.country=US -cp " \
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
                jar_cmd = "java -Duser.language=en -Duser.country=US -cp " \
                          + f"\"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" " \
                          + f"OracleConnection -url \"{self._db_prop[db_label]['ORACLE_JDBC_URL']}\" " \
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
                SSL_CONNECTION_STR = "encrypt=true;trustServerCertificate=true;" \
                                     + f"trustStore=\"{truststore_path}\";" \
                                     + f"trustStorePassword={truststore_pwd}"
                jar_cmd = "java -Duser.language=en -Duser.country=US -cp " \
                          + f"\"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" " \
                          + f"SQLConnection -h '{db_servername}' -p {db_port} -d '{db_name}' " \
                          + f"-u '{db_user}' -pwd '{db_pwd}' -ssl \"{SSL_CONNECTION_STR}\""
            elif db_type == "postgresql":
                ca_key_crt_extensions = [".crt", ".cer", ".pem", ".cert", ".key"]
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

                jar_cmd = "java -Duser.language=en -Duser.country=US -Dcom.ibm.jsse2.overrideDefaultTLS=true " \
                          f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          f"{self._DB_CONNECTION_JAR_PATH}\" " \
                          f"PostgresConnection -h '{db_servername}' -p {db_port} -db '{db_name}' " \
                          f"-u '{db_user}' -pwd '{db_pwd}' -sslmode {self._db_prop['SSL_MODE']} " \
                          f"{auth_str}"
        else:
            if db_type == "db2":
                jar_cmd = "java -Duser.language=en -Duser.country=US " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" DB2Connection " \
                          + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}'"
            elif db_type == "oracle":
                jar_cmd = "java -Duser.language=en -Duser.country=US " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" OracleConnection " \
                          + f"-url {self._db_prop[db_label]['ORACLE_JDBC_URL']} -u '{db_user}' -pwd '{db_pwd}'"
            elif db_type == "sqlserver":
                jar_cmd = "java -Duser.language=en -Duser.country=US " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" SQLConnection " \
                          + f"-h '{db_servername}' -p {db_port} -d '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -ssl 'encrypt=false'"
            elif db_type == "postgresql":
                jar_cmd = "java -Duser.language=en -Duser.country=US -Dcom.ibm.jsse2.overrideDefaultTLS=true " \
                          + f"-cp \"{self._DB_JDBC_PATH}{class_path_delim_char}" \
                          + f"{self._DB_CONNECTION_JAR_PATH}\" PostgresConnection " \
                          + f"-h '{db_servername}' -p {db_port} -db '{db_name}' -u '{db_user}' -pwd '{db_pwd}' -sslmode disable"

        db_is_connected = self.__check_connection_with_jar(jar_cmd, progress)
        if db_is_connected:
            self._logger.info(f"Successfully connected to {db_label} database!")
            progress.log(connected_str)
            progress.log()
        else:
            self._logger.info(f"Failed to connect to {db_label} database!")
            progress.log(not_connected_str)
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
        for ldap_id in self._ldap_prop["_ldap_ids"]:
            self.validate_ldap(task1, progress, ldap_id)

    # Validates a single LDAP, defaults to the first one by its id: "LDAP"
    def validate_ldap(self, task1, progress, ldap_id="LDAP"):
        # This is just for readability
        ldap_server = self._ldap_prop[ldap_id]["LDAP_SERVER"]
        ldap_bind_dn = self._ldap_prop[ldap_id]["LDAP_BIND_DN"]
        ldap_bind_dn_pwd = self._ldap_prop[ldap_id]["LDAP_BIND_DN_PASSWORD"]
        ldap_base_dn = self._ldap_prop[ldap_id]["LDAP_BASE_DN"]
        ldap_port = self._ldap_prop[ldap_id]["LDAP_PORT"]

        ldap_bind_dn_pwd = self.parse_shell_command(ldap_bind_dn_pwd)
        ldap_bind_dn = self.parse_shell_command(ldap_bind_dn)

        ldap_is_connected = None
        jar_cmd = ""

        connected_str = Text(f"\nConnected to LDAP \"{ldap_server}\" using BindDN:\"{ldap_bind_dn}\"" \
                             + " successfuly, PASSED!\n", style="bold green")

        not_connected_str = Text(f"\nUnable to connect to LDAP server \"{ldap_server}\" " \
                                 + f"using Bind DN \"{ldap_bind_dn}\", " \
                                 + "please check configuration in ldap toml file again.\n", style="bold red")

        progress.log(Panel.fit(Text(f"Validating LDAP server \"{ldap_server}\"", style="bold cyan")))

        # Test for non-SSL connections
        if not self._ldap_prop[ldap_id]["LDAP_SSL_ENABLED"]:
            jar_cmd = f"java -jar '{self._LDAP_JAR_PATH}' -u 'ldap://{ldap_server}:{ldap_port}' " \
                      + f"-b '{ldap_base_dn}' -D '{ldap_bind_dn}' -w '{ldap_bind_dn_pwd}'"

        # Test for SSL connections
        else:
            # Create .der and truststore file needed for validation
            self.__create_tmp_folder()
            crt_path = self.__get_file_from_folder(
                os.path.join(os.getcwd(), "propertyFile", "ssl-certs", ldap_id.lower()),
                [".crt", ".cer", ".cert", ".key", ".pem"])
            der_path = self.__crt_to_der_x509(input_cert_path=crt_path,
                                              output_path=os.path.join(self._TMP_DIR, "ldap.der"))
            truststore_pwd = "changeit"
            truststore_path = self.__create_tmp_truststore(der_path=der_path,
                                                           output_path=os.path.join(self._TMP_DIR,
                                                                                    "ldap-truststore.jks"),
                                                           alias="cp4baLdapCerts",
                                                           storetype="JKS",
                                                           truststore_pwd=truststore_pwd)
            # Validate LDAP connection over SSL
            jar_cmd = f"java -Djavax.net.ssl.trustStore='{truststore_path}' " \
                      + f"-Djavax.net.ssl.trustStorePassword={truststore_pwd} -jar '{self._LDAP_JAR_PATH}' " \
                      + f"-u 'ldaps://{ldap_server}:{ldap_port}' -b '{ldap_base_dn}' -D '{ldap_bind_dn}' " \
                      + f"-w '{ldap_bind_dn_pwd}'"
        ldap_is_connected = self.__check_connection_with_jar(jar_cmd, progress)
        self.is_validated[ldap_id] = ldap_is_connected
        if ldap_is_connected:
            self._logger.info(connected_str)
            progress.log(connected_str)
        else:
            self._logger.info(not_connected_str)
            progress.log(not_connected_str)
        progress.advance(task1)
        return ldap_is_connected

    # Returns true if we can connect to LDAP using given jar_cmd
    def __check_connection_with_jar(self, jar_cmd, progress):
        self.__check_java()
        try:
            subprocess.check_output(jar_cmd, shell=True, stderr=subprocess.PIPE, universal_newlines=True)
            return True
        except subprocess.CalledProcessError as error:
            self._logger.info(error.stderr)
            progress.log()
            progress.log((Syntax(str(error.stderr), "java", theme="ansi_dark")))
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
        self._logger.error(f"Failed to allocate the persistent volumes using PVC: \"{sample_pvc_name}\"!")
        progress.log()
        progress.log(Text(f"Failed to allocate PVC: \"{sample_pvc_name}\"!", style="bold red"))
        progress.advance(task2)
        return False

    # Creates a storage class yaml to apply
    def validate_sample_sc(self, sc_name, sc_mode, sample_pvc_name, task2, progress):
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
        if os.path.exists(os.path.join(os.getcwd(), "generatedFiles", "ssl")):
            self.auto_apply_all_in_folder(folder_path=os.path.join(os.getcwd(), "generatedFiles", "ssl"))

    def auto_apply_cr(self):
        # comp_list will have labels for all components, if these components have not yet
        # passed validation, CR will not by applied
        comp_list = ["GCD", "ICN"] + self._db_prop["_os_ids"] + self._ldap_prop["_ldap_ids"]
        sc_list_set = list(
            {self._deploy_prop["SLOW_FILE_STORAGE_CLASSNAME"], self._deploy_prop["MEDIUM_FILE_STORAGE_CLASSNAME"],
             self._deploy_prop["FAST_FILE_STORAGE_CLASSNAME"]})
        comp_list = comp_list + sc_list_set
        for c in comp_list:
            if c not in self.is_validated:
                self._logger.info("Have not yet ran validation for all components. Skipped applying CR.")
                return False

        response = self.kubectl_apply(os.path.join(os.getcwd(), "generatedFiles", "ibm_fncm_cr_production.yaml"))
        print(Panel.fit(Text(response.strip(), style="bold cyan")))
        return True
    