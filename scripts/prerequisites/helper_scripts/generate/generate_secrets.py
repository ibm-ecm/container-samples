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
import logging
# from helper_scripts.generate.read_prop import *
# import prerequisites_env
import os

import yaml


def represent_str(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    else:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style="'")


def represent_mapping(dumper, data):
    value = []
    for item_key, item_value in data.items():
        node_key = dumper.represent_data(item_key)
        node_value = dumper.represent_data(item_value)
        if isinstance(node_key, yaml.nodes.ScalarNode):
            node_key.style = ''
        if isinstance(node_value, yaml.nodes.ScalarNode):
            node_value.style = "'"
        value.append((node_key, node_value))
    return yaml.nodes.MappingNode('tag:yaml.org,2002:map', value)


yaml.add_representer(str, represent_str)
yaml.add_representer(dict, represent_mapping)


# Class to generate secrets
class GenerateSecrets:

    # Function to XOR password
    def xor_password(self, data, xorkey=0x5F):
        """XORs a password with a key.The key used here is _"""

        # Convert password to bytes
        password_bytes = data.encode()

        # XOR each byte of the password with the key
        xor_result_bytes = bytes([b ^ xorkey for b in password_bytes])

        # Encode the XORed bytes using base64
        xor_encoded_bytes = base64.b64encode(xor_result_bytes)

        # Convert the encoded bytes to a string and prepend with "{xor}"
        xor_result_string = "{xor}" + xor_encoded_bytes.decode()
        return xor_result_string

    # function to create ssl secrets
    # pending case to take care of postgres scenario
    def create_ssl_secrets(self):
        # if any ssl cert folders exists that means ssl was enabled for either ldap or DB
        if os.path.exists(self._ssl_cert_folder):
            ssl_folders = os.listdir(self._ssl_cert_folder)
            ssl_cert_folder = self._ssl_cert_folder
            self._logger.info("Creating ssl secrets")
            ssl_folders = os.listdir(ssl_cert_folder)

            # remove any hidden files that might be picked up
            for folder in ssl_folders:
                if folder.startswith("."):
                    ssl_folders.remove(folder)

            # iterating through folders gcd, os , ldap2 etc
            for item in ssl_folders:
                folderpath = os.path.join(ssl_cert_folder, item)
                ssl_certs = os.listdir(folderpath)

                # processing data to generate ldap ssl secrets
                if "ldap" in item:
                    for cert in ssl_certs:
                        if any(ext in cert for ext in [".crt", ".cer", ".pem", ".cert", ".key"]):
                            certfolderpath = os.path.join(folderpath, cert)
                            # Read binary data from SSL certificate file
                            with open(certfolderpath, "rb") as file:
                                binary_data = file.read()
                            # Encode binary data to base64
                            encoded_data = base64.b64encode(binary_data).decode('utf-8')

                            sslsecret_filepath = os.path.join(self._generate_ssl_secrets_folder,
                                                              "ibm-" + item + "-ssl-secret.yaml")
                            ssl_secret_data = {"apiVersion": "v1", "kind": "Secret",
                                               "metadata": {"name": "ibm-" + item + "-ssl-secret"}, "type": "Opaque",
                                               "data": {"tls.crt": encoded_data}}

                            # write the secret data into a yaml
                            with open(sslsecret_filepath, 'w+') as file:
                                yaml.dump(ssl_secret_data, file)
                                logging.info(
                                    "SSl secret ibm-" + item + "-ssl-secret has been created at---- " + sslsecret_filepath)

                # processing data to generate db ssl secrets
                else:
                    ssl_secret_data = {"apiVersion": "v1", "kind": "Secret",
                                       "metadata": {"name": "ibm-" + item + "-ssl-secret"}, "type": "Opaque"}
                    ssl_secret_data["data"] = {}
                    # if DB type is postgres we need to go through multiple folders which have multiple certs
                    if self._db_properties["DATABASE_TYPE"] == "postgresql":
                        postgres_cert_folders = os.listdir(folderpath)
                        # Use these three variables to decide if certs are present and if all are empty we will use dbpassword to create ssl cert
                        clientkey_present = True
                        clientcert_present = True
                        servercert_present = True

                        # check if we have cert auth or server auth
                        for postgres_folder in postgres_cert_folders:
                            # sometimes there are folders that start with . (hidden folders)
                            if postgres_folder.startswith(".") == True:
                                continue
                            current_postgres_folder = os.path.join(folderpath, postgres_folder)
                            # listing the certs present in the sub folder
                            postgres_cert = os.listdir(current_postgres_folder)
                            sub_folder_cert = ""
                            for folder_item in postgres_cert:
                                if any(ext in folder_item for ext in [".crt", ".cer", ".pem", ".cert", ".key"]):
                                    sub_folder_cert = folder_item
                            # checking to see which subfolders are empty or not
                            if "clientkey" in postgres_folder:
                                if not sub_folder_cert:
                                    clientkey_present = False
                            if "clientcert" in postgres_folder:
                                if not sub_folder_cert:
                                    clientcert_present = False
                            if "serverca" in postgres_folder:
                                if not sub_folder_cert:
                                    servercert_present = False

                        # if client_auth is false that means server auth is true
                        client_auth = False
                        if clientkey_present and clientcert_present:
                            client_auth = True
                        # parsing through the 3 postgres ssl sub folders to generate the secret parameters
                        for postgres_folder in postgres_cert_folders:
                            # skipping hidden folders in case its present
                            if postgres_folder.startswith(".") == True:
                                continue
                            current_postgres_folder = os.path.join(folderpath, postgres_folder)
                            # listing the certs present in the sub folder
                            postgres_cert = os.listdir(current_postgres_folder)
                            sub_folder_cert = ""
                            ssl_secret_data["stringData"] = {}
                            # finding only pem or cert files to use
                            for folder_item in postgres_cert:
                                if any(ext in folder_item for ext in [".crt", ".cer", ".pem", ".cert", ".key"]):
                                    sub_folder_cert = folder_item
                            if client_auth:
                                if "clientkey" in postgres_folder:
                                    # Read binary data from SSL certificate file

                                    if sub_folder_cert:
                                        with open(os.path.join(current_postgres_folder, sub_folder_cert), "rb") as file:
                                            binary_data = file.read()
                                        # Encode binary data to base64
                                        encoded_data = base64.b64encode(binary_data).decode('utf-8')
                                        ssl_secret_data["data"]['clientkey.pem'] = encoded_data

                                if "clientcert" in postgres_folder:
                                    # Read binary data from SSL certificate file
                                    if sub_folder_cert:
                                        with open(os.path.join(current_postgres_folder, sub_folder_cert), "rb") as file:
                                            binary_data = file.read()
                                        # Encode binary data to base64
                                        encoded_data = base64.b64encode(binary_data).decode('utf-8')
                                        ssl_secret_data["data"]['clientcert.pem'] = encoded_data

                                # for modes other thatn require serverca is a must
                                if self._db_properties["SSL_MODE"].lower() != "require":
                                    if "serverca" in postgres_folder:
                                        # Read binary data from SSL certificate file
                                        if sub_folder_cert:
                                            with open(os.path.join(current_postgres_folder, sub_folder_cert),
                                                      "rb") as file:
                                                binary_data = file.read()
                                            # Encode binary data to base64
                                            encoded_data = base64.b64encode(binary_data).decode('utf-8')
                                            ssl_secret_data["data"]['serverca.pem'] = encoded_data

                            else:
                                # server auth is picked so that will be the parameter generated
                                if "serverca" in postgres_folder:
                                    # Read binary data from SSL certificate file
                                    if sub_folder_cert:
                                        with open(os.path.join(current_postgres_folder, sub_folder_cert),
                                                  "rb") as file:
                                            binary_data = file.read()
                                        # Encode binary data to base64
                                        encoded_data = base64.b64encode(binary_data).decode('utf-8')
                                        ssl_secret_data["data"]['serverca.pem'] = encoded_data

                                    dbpass = self._db_properties[item.upper()]["DATABASE_PASSWORD"]
                                    ssl_secret_data["stringData"]["DBPassword"] = str(self.xor_password(dbpass))

                        # adding ssl mode as a parameter for the secret
                        ssl_secret_data["stringData"] = {}
                        ssl_secret_data["stringData"]["sslmode"] = self._db_properties["SSL_MODE"].lower()

                        # write the secret data into a yaml
                        sslsecret_filepath = os.path.join(self._generate_ssl_secrets_folder,
                                                          "ibm-" + item + "db-ssl-secret.yaml")
                        with open(sslsecret_filepath, 'w+') as file:
                            yaml.dump(ssl_secret_data, file)
                            logging.info(
                                "SSl secret ibm-" + item + "-ssl-secret has been created at---- " + sslsecret_filepath)

                    # For all other DB types the ssl secrets are created using the same logic as we did to create ldap ssl secrets
                    else:
                        for cert in ssl_certs:
                            if any(ext in cert for ext in [".crt", ".cer", ".pem", ".cert", ".key"]):
                                certfolderpath = os.path.join(folderpath, cert)
                                # Read binary data from SSL certificate file
                                with open(certfolderpath, "rb") as file:
                                    binary_data = file.read()
                                # Encode binary data to base64
                                encoded_data = base64.b64encode(binary_data).decode('utf-8')

                                sslsecret_filepath = os.path.join(self._generate_ssl_secrets_folder,
                                                                  "ibm-" + item + "db-ssl-secret.yaml")
                                ssl_secret_data = {"apiVersion": "v1", "kind": "Secret",
                                                   "metadata": {"name": "ibm-" + item + "-ssl-secret"},
                                                   "type": "Opaque", "data": {"tls.crt": encoded_data}}

                                # write the secret data into a yaml
                                with open(sslsecret_filepath, 'w+') as file:
                                    yaml.dump(ssl_secret_data, file)
                                    logging.info(
                                        "SSl secret ibm-" + item + "-ssl-secret has been created at---- " + sslsecret_filepath)

    # function to create ban secret
    def create_ban_secret(self):
        self._logger.info("Creating Ban secret")
        bansecret_filepath = os.path.join(self._generate_secrets_folder, "ibm-ban-secret.yaml")
        ban_data = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "ibm-ban-secret"}, "type": "Opaque"}
        stringData = {}
        stringDatafields = ["navigatorDBUsername", "navigatorDBPassword", "ltpaPassword", "keystorePassword",
                            "appLoginUsername", "appLoginPassword"]

        stringDatavalues = [self._db_properties['ICN']['DATABASE_USERNAME'],
                            self.xor_password(self._db_properties['ICN']['DATABASE_PASSWORD']),
                            self._usergroup_properties['LTPA_PASSWORD'],
                            self._usergroup_properties['KEYSTORE_PASSWORD'],
                            self._usergroup_properties['ICN_LOGIN_USER'],
                            self._usergroup_properties['ICN_LOGIN_PASSWORD']]

        string_list = [str(val) for val in stringDatavalues]
        for i in range(len(stringDatafields)):
            stringData[stringDatafields[i]] = string_list[i]
        # check if java sendmail details are present
        if self._customcomponent_properties:
            if "BAN" in self._customcomponent_properties.keys():
                if "JAVAMAIL_USERNAME" in self._customcomponent_properties["BAN"].keys() and "JAVAMAIL_PASSWORD" in \
                        self._customcomponent_properties["BAN"].keys():
                    stringData["jMailUsername"] = self._customcomponent_properties["BAN"]["JAVAMAIL_USERNAME"]
                    stringData["jMailPassword"] = self.xor_password(
                        self._customcomponent_properties["BAN"]["JAVAMAIL_PASSWORD"])
        ban_data["stringData"] = stringData

        with open(bansecret_filepath, 'w+') as file:
            yaml.dump(ban_data, file)
            logging.info("Ban secret ibm-ban-secret.yaml has been created at---- " + bansecret_filepath)

    # Function to generate ldap_secret
    def create_ldap_secret(self):
        self._logger.info("Creating LDAP secret")
        ldapsecret_filepath = os.path.join(self._generate_secrets_folder, "ldap-bind-secret.yaml")
        ldap_data = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "ldap-bind-secret"}, "type": "Opaque"}
        stringData = {}

        for ldap in self._ldap_properties['_ldap_ids']:
            if ldap.lower() == "ldap":
                stringData['ldapUsername'] = self._ldap_properties[ldap]["LDAP_BIND_DN"]
                stringData['ldapPassword'] = self.xor_password(self._ldap_properties[ldap]["LDAP_BIND_DN_PASSWORD"])
            else:
                stringData['ldap' + self._ldap_properties[ldap]["LDAP_ID"] + 'Username'] = self._ldap_properties[ldap][
                    "LDAP_BIND_DN"]
                stringData['ldap' + self._ldap_properties[ldap]["LDAP_ID"] + 'Password'] = self.xor_password(
                    self._ldap_properties[ldap]["LDAP_BIND_DN_PASSWORD"])

        # if '<Required>' in stringData.values():
        #     self._logger.info("Certain fields in your property files which are required to be filled up have not been filled up, please check your ldap property files")
        #     raise Exception("Certain fields in your property files which are required to be filled up have not been filled up, please check your ldap property files")

        ldap_data["stringData"] = stringData
        # writing the data to the ldap secret yaml
        with open(ldapsecret_filepath, 'w+') as file:
            yaml.dump(ldap_data, file)
            logging.info("Ldap secret ldap-bind-secret.yaml has been created at---- " + ldapsecret_filepath)

    # Function to generate fncm_secret
    def create_fncm_secret(self):
        self._logger.info("Creating FNCM secret")
        fncmsecret_filepath = os.path.join(self._generate_secrets_folder, "ibm-fncm-secret.yaml")
        fncm_data = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "ibm-fncm-secret"}, "type": "Opaque"}
        stringData = {}
        stringData["ltpaPassword"] = self._usergroup_properties['LTPA_PASSWORD']
        stringData["keystorePassword"] = self._usergroup_properties['KEYSTORE_PASSWORD']
        stringData["appLoginUsername"] = self._usergroup_properties['FNCM_LOGIN_USER']
        stringData["appLoginPassword"] = self._usergroup_properties['FNCM_LOGIN_PASSWORD']
        stringData["gcdDBUsername"] = self._db_properties["GCD"]["DATABASE_USERNAME"]
        stringData["gcdDBPassword"] = self.xor_password(self._db_properties["GCD"]["DATABASE_PASSWORD"])

        for os_id in self._db_properties["_os_ids"]:
            stringData[self._db_properties[os_id]["OS_LABEL"] + "DBUsername"] = self._db_properties[os_id][
                "DATABASE_USERNAME"]
            stringData[self._db_properties[os_id]["OS_LABEL"] + "DBPassword"] = self.xor_password(
                self._db_properties[os_id]["DATABASE_PASSWORD"])

        # if '<Required>' in stringData.values():
        #     self._logger.info("Certain fields in your property files which are required to be filled up have not been filled up, please check your db and usergroup property files")
        #     raise Exception("Certain fields in your property files which are required to be filled up have not been filled up, please check your db and usergroup property files")

        fncm_data["stringData"] = stringData
        with open(fncmsecret_filepath, 'w+') as file:
            yaml.dump(fncm_data, file)
            logging.info("FNCM secret ibm-fncm-secret.yaml has been created at---- " + fncmsecret_filepath)


    # Function to generate icc related secrets
    def create_icc_secrets(self):
        #function creates the icc-masterkey-txt and ibm-icc-secret
        try:
            self._logger.info("Creating ICC secrets")

            #creating the icc secret
            iccsecret_filepath = os.path.join(self._generate_secrets_folder, "ibm-icc-secret.yaml")
            icc_data = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "ibm-icc-secret"}, "type": "Opaque"}
            stringData = {}
            stringData["archiveUserId"] = self._customcomponent_properties["CSS"]["ARCHIVE_USER_ID"]
            stringData["archivePassword"] = self.xor_password(self._customcomponent_properties["CSS"]["ARCHIVE_PASSWORD"])
            icc_data["stringData"] = stringData
            with open(iccsecret_filepath, 'w+') as file:
                yaml.dump(icc_data, file)
                logging.info("ICC secret ibm-icc-secret.yaml has been created at---- " + iccsecret_filepath)

            #creating the masterkey secret
            iccmasterkey_filepath = os.path.join(self._generate_secrets_folder, "icc-masterkey-txt.yaml")
            file_list = os.listdir(self._icc_folder)
            encoded_data = ""
            for file in file_list:
                if file.endswith('.txt'):
                    masterkeypath = os.path.join(self._icc_folder, file)
                    # Read binary data from SSL certificate file
                    with open(masterkeypath, "rb") as file:
                        binary_data = file.read()
                    # Encode binary data to base64
                    encoded_data = base64.b64encode(binary_data).decode('utf-8')
                    break
            masterkey_secret_data = {"apiVersion": "v1", "kind": "Secret",
                               "metadata": {"name": "icc-masterkey-txt"},
                               "type": "Opaque", "data": {"MasterKey.txt": encoded_data}}
            with open(iccmasterkey_filepath, 'w+') as file:
                yaml.dump(masterkey_secret_data, file)
                logging.info("ICC secret icc-masterkey-txt.yaml has been created at---- " + iccmasterkey_filepath)
        except Exception as e:
            self._logger.exception(f"Error found in create_icc_secrets function in generate_secrets script --- {str(e)}")

    def __init__(self, db_properties=None, ldap_properties=None, usergroup_properties=None,customcomponent_properties=None, logger=None):
        self._logger = logger

        self._db_properties = db_properties
        self._ldap_properties = ldap_properties
        self._usergroup_properties = usergroup_properties
        self._customcomponent_properties = customcomponent_properties

        self._generate_folder = os.path.join(os.getcwd(), "generatedFiles")
        self._ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs")
        self._icc_folder = os.path.join(os.getcwd(), "propertyFile", "icc")
        self._generate_secrets_folder = os.path.join(self._generate_folder, "secrets")
        self._generate_ssl_secrets_folder = os.path.join(self._generate_folder, "ssl")
