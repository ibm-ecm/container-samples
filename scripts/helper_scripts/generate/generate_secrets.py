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
import os
import shutil

import jinja2

from ..utilities.prerequisites_utilites import collect_visible_files, split_pem, encode_secret_contents


# Class to generate secrets
class GenerateSecrets:
    _TMP_DIR = os.path.join(os.getcwd(), "helper_scripts", "generate", "tmp")

    def __init__(self, namespace, db_properties=None, ldap_properties=None, idp_properties=None, usergroup_properties=None,
                 customcomponent_properties=None, scim_properties=None, deployment_properties=None, logger=None):
        self._logger = logger

        self._db_properties = db_properties
        self._ldap_properties = ldap_properties
        self._usergroup_properties = usergroup_properties
        self._idp_properties = idp_properties
        self._customcomponent_properties = customcomponent_properties
        self._scim_properties = scim_properties
        self._deployment_properties = deployment_properties

        self._ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", namespace, "ssl-certs")
        self._trusted_certs_folder = os.path.join(self._ssl_cert_folder, "trusted-certs")


        self._generate_folder = os.path.join(os.getcwd(), "generatedFiles", namespace)
        self._generate_secrets_folder = os.path.join(self._generate_folder, "secrets")
        self._generate_ssl_secrets_folder = os.path.join(self._generate_folder, "ssl")
        self._generate_trusted_secrets_folder = os.path.join(self._generate_ssl_secrets_folder, "trusted-certs")
        self._icc_folder = os.path.join(self._generate_folder, "icc")

        self._secret_template_folder = os.path.join(os.getcwd(), "helper_scripts", "generate", "templates")


        # Load all jinja templates
        self._template_loader = jinja2.FileSystemLoader(self._secret_template_folder)
        self._template_env = jinja2.Environment(loader=self._template_loader, trim_blocks=True)

        self.__create_tmp_folder()

    def __create_tmp_folder(self):
        try:
            if not os.path.exists(self._TMP_DIR):
                os.makedirs(self._TMP_DIR)
            else:
                self._logger.info(f"The folder {self._TMP_DIR} already exists")
                # Delete and recreate the TMP folder 
                shutil.rmtree(self._TMP_DIR)
                os.makedirs(self._TMP_DIR)
        except Exception as e:
            self._logger.exception(
                f"Exception from validate.py script in function -  {str(e)}")
        return self._TMP_DIR

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

    def render_ssl_secret_template(self, values, secret_name):
        """
        Renders an SSL secret template using the provided values and secret name.

        Parameters:
        values (dict): A dictionary containing the variables to be substituted in the template.
        secret_name (str): The name of the secret to be created.

        Returns:
        str: The rendered secret content for the secret.
        """
        template = self._template_env.get_template('secret.j2')

        # Render the template with the provided values
        rendered_secret = template.render(
            values=values,
            secret_name=secret_name)

        return rendered_secret

    def render_secret_template(self, values, secret_name):
        """
        Renders a Jinja2 template for a secret with the provided values.

        Parameters:
        values (dict): A dictionary containing the variable values to be substituted in the template.
        secret_name (str): The name of the secret to be used in the template.

        Returns:
        str: The rendered secret string.
        """
        # Get the template from the environment
        template = self._template_env.get_template('secret.j2')

        # Render the template with the provided values
        rendered_secret = template.render(
            values=values,
            secret_name=secret_name
        )

        return rendered_secret

    def create_scim_ssl_secrets(self):
        """
        This function creates SSL secrets for SCIM (System for Cross-domain Identity Management) components.
        It checks if the SSL certificate folder exists, collects visible files, and processes each SCIM component
        to create SSL secrets.

        Returns:
        None
        """
        scim_ssl = {}

        for scim in self._scim_properties['_scim_ids']:
            scim_ssl[scim.lower()] = self._scim_properties[scim]["SCIM_SSL_ENABLED"]
        scim_ssl_enabled = any([value for value in scim_ssl.values()])

        if os.path.exists(self._ssl_cert_folder):
            self._logger.info("Creating SCIM ssl secrets")
            ssl_cert_folder = self._ssl_cert_folder
            ssl_folders = collect_visible_files(ssl_cert_folder)

            # remove any hidden files that might be picked up and remove the trusted-certs folder
            for folder in ssl_folders:
                if folder.startswith(".") or folder == "trusted-certs":
                    ssl_folders.remove(folder)

            scim_folders = list(filter(lambda x: "scim" in x, ssl_folders))

            for item in scim_folders:
                folderpath = os.path.join(ssl_cert_folder, item)
                ssl_certs = collect_visible_files(folderpath)

                # processing data to generate ldap ssl secrets
                # only create the ldap ssl secret if ldap ssl is enabled
                # create the ldap ssl secret only if the ldap server has ssl enabled
                if scim_ssl_enabled and "scim" in item:
                    if scim_ssl[item]:
                        self.create_ssl_secret(folderpath=folderpath, ssl_certs=ssl_certs, item=item)


    def create_idp_ssl_secrets(self):
        # if SSL is enabled on the Database or the LDAP server then we need to create ssl secrets

        # if any of the ldap servers have ssl enabled then we need to create ssl secrets
        # Check is any of the ldap server has ssl enabled
        for idp in self._idp_properties['_idp_ids']:
            if self._idp_properties[idp]["IDP_SSL_ENABLED"]:

                if os.path.exists(self._ssl_cert_folder):
                    self._logger.info(f"Creating IDP ssl secrets for ID: {idp}")
                    ssl_cert_folder = self._ssl_cert_folder
                    ssl_folders = collect_visible_files(ssl_cert_folder)

                # remove any hidden files that might be picked up and remove the trusted-certs folder
                for folder in ssl_folders:
                    if folder.startswith(".") or folder == "trusted-certs":
                        ssl_folders.remove(folder)



                folderpath = os.path.join(ssl_cert_folder, idp.lower())
                ssl_certs = collect_visible_files(folderpath)

                self.create_ssl_secret(folderpath=folderpath, ssl_certs=ssl_certs, item=idp.lower())


    def create_ldap_ssl_secrets(self):
        # if SSL is enabled on the Database or the LDAP server then we need to create ssl secrets

        # if any of the ldap servers have ssl enabled then we need to create ssl secrets
        # Check is any of the ldap server has ssl enabled
        ldap_ssl = {}

        for ldap in self._ldap_properties['_ldap_ids']:
            ldap_ssl[ldap.lower()] = self._ldap_properties[ldap]["LDAP_SSL_ENABLED"]
        ldap_ssl_enabled = any([value for value in ldap_ssl.values()])

        if os.path.exists(self._ssl_cert_folder):
            self._logger.info("Creating ssl secrets")
            ssl_cert_folder = self._ssl_cert_folder
            ssl_folders = collect_visible_files(ssl_cert_folder)

            # remove any hidden files that might be picked up and remove the trusted-certs folder
            for folder in ssl_folders:
                if folder.startswith(".") or folder == "trusted-certs":
                    ssl_folders.remove(folder)

            ldap_folders = list(filter(lambda x: "ldap" in x, ssl_folders))

            # iterating through folders gcd, os , ldap2 etc
            for item in ldap_folders:
                folderpath = os.path.join(ssl_cert_folder, item)
                ssl_certs = collect_visible_files(folderpath)

                # processing data to generate ldap ssl secrets
                # only create the ldap ssl secret if ldap ssl is enabled
                # create the ldap ssl secret only if the ldap server has ssl enabled
                if ldap_ssl_enabled and "ldap" in item:
                    if ldap_ssl[item]:
                        self.create_ssl_secret(folderpath=folderpath, ssl_certs=ssl_certs, item=item)

    # function to create ssl secrets
    def create_ssl_db_secrets(self):
        # if SSL is enabled on the Database or the LDAP server then we need to create ssl secrets
        # if any ssl cert folders exists that means ssl was enabled for either ldap or DB

        if os.path.exists(self._ssl_cert_folder):
            self._logger.info("Creating ssl secrets")
            ssl_cert_folder = self._ssl_cert_folder
            ssl_folders = os.listdir(ssl_cert_folder)

            # remove any hidden files that might be picked up and remove the trusted-certs folder
            for folder in ssl_folders:
                if folder.startswith(".") or folder == "trusted-certs":
                    ssl_folders.remove(folder)

            db_folders = list(filter(lambda x: not any(ex in x.lower() for ex in ["ldap", "idp", "scim"]), ssl_folders))

            if "CPE" in self._deployment_properties.keys():
                if not self._deployment_properties["CPE"]:
                    db_folders.remove("gcd")
                    db_folders = list(filter(lambda x: "os" not in x, db_folders))

            if "BAN" in self._deployment_properties.keys():
                if not self._deployment_properties["BAN"]:
                    db_folders = list(filter(lambda x: "icn" not in x, db_folders))

            # processing data to generate db ssl secrets
            for item in db_folders:
                folderpath = os.path.join(ssl_cert_folder, item)
                ssl_certs = collect_visible_files(folderpath)
                ssl_secret_data = {"apiVersion": "v1", "kind": "Secret",
                                   "metadata": {"name": "ibm-" + item + "-ssl-secret"}, "type": "Opaque",
                                   "data": {}}
                # if DB type is postgres we need to go through multiple folders which have multiple certs
                if self._db_properties["DATABASE_TYPE"] == "postgresql":
                    postgres_cert_folders = collect_visible_files(folderpath)
                    # Use these three variables to decide if certs are present and if all are empty we will use dbpassword to create ssl cert
                    clientkey_present = True
                    clientcert_present = True
                    servercert_present = True

                    # check if we have cert auth or server auth
                    for postgres_folder in postgres_cert_folders:
                        # sometimes there are folders that start with . (hidden folders)
                        if postgres_folder.startswith("."):
                            continue
                        current_postgres_folder = os.path.join(folderpath, postgres_folder)
                        # listing the certs present in the sub folder
                        postgres_cert = collect_visible_files(current_postgres_folder)
                        sub_folder_cert = ""
                        for folder_item in postgres_cert:
                            if any(ext in folder_item for ext in [".crt", ".cer", ".pem", ".cert", ".key", ".arm"]):
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
                    if clientkey_present and clientcert_present and self._deployment_properties[
                        "FNCM_Version"] != "5.5.8":
                        client_auth = True
                    # parsing through the 3 postgres ssl sub folders to generate the secret parameters
                    for postgres_folder in postgres_cert_folders:
                        # skipping hidden folders in case its present
                        if postgres_folder.startswith("."):
                            continue
                        current_postgres_folder = os.path.join(folderpath, postgres_folder)
                        # listing the certs present in the sub folder
                        postgres_cert = collect_visible_files(current_postgres_folder)
                        sub_folder_cert = ""
                        ssl_secret_data["stringData"] = {}
                        # finding only pem or cert files to use
                        for folder_item in postgres_cert:
                            if any(ext in folder_item for ext in [".crt", ".cer", ".pem", ".cert", ".key", ".arm"]):
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

                            if self._db_properties["SSL_MODE"].lower() != "require":
                                if "clientcert" in postgres_folder:
                                    # Read binary data from SSL certificate file
                                    if sub_folder_cert:
                                        with open(os.path.join(current_postgres_folder, sub_folder_cert),
                                                  "rb") as file:
                                            binary_data = file.read()
                                        # Encode binary data to base64
                                        encoded_data = base64.b64encode(binary_data).decode('utf-8')
                                        ssl_secret_data["data"]['clientcert.pem'] = encoded_data

                                if "clientkey" in postgres_folder:
                                    # Read binary data from SSL certificate file
                                    if sub_folder_cert:
                                        with open(os.path.join(current_postgres_folder, sub_folder_cert),
                                                  "rb") as file:
                                            binary_data = file.read()
                                        # Encode binary data to base64
                                        encoded_data = base64.b64encode(binary_data).decode('utf-8')
                                        ssl_secret_data["data"]['clientkey.pem'] = encoded_data

                    # adding ssl mode as a parameter for the secret
                    ssl_secret_data["stringData"] = {}
                    ssl_secret_data["stringData"]["sslmode"] = self._db_properties["SSL_MODE"].lower()

                    # write the secret data into a yaml
                    sslsecret_filepath = os.path.join(self._generate_ssl_secrets_folder,
                                                      "ibm-" + item + "db-ssl-secret.yaml")
                    with open(sslsecret_filepath, 'w+') as file:
                        yaml.dump(ssl_secret_data, file)
                        self._logger.info(
                            "SSl secret ibm-" + item + "-ssl-secret has been created at---- " + sslsecret_filepath)

                # For all other DB types the ssl secrets are created using the same logic as we did to create ldap ssl secrets
                else:
                    self.create_ssl_secret(folderpath=folderpath, ssl_certs=ssl_certs, item=item)

    def create_ssl_secret(self, folderpath, ssl_certs, item, prefix="cert-"):
        """
        This function creates an SSL secret from a list of certificate files.

        Parameters:
        folderpath (str): The path to the folder containing the SSL certificate files.
        ssl_certs (list): A list of certificate file names (without extension) to be included in the secret.
        item (str): A unique identifier for the secret.

        Returns:
        None

        The function reads each certificate file in the provided folder, splits multi-file PEM certificates,
        encodes the certificate data in base64, and writes it into a YAML secret file. The secret file is
        named using the format "ibm-<item>-ssl-secret.yaml" and is saved in the directory specified by
        `_generate_ssl_secrets_folder`. The function also logs the creation of the secret.
        """
        data = ""
        for i, cert in enumerate(ssl_certs):
            if any(ext in cert for ext in [".crt", ".cer", ".pem", ".cert", ".key", ".arm"]):
                certfolderpath = os.path.join(folderpath, cert)
                # Split the certificate to separate files
                cert_list = split_pem(self._logger, certfolderpath, self._TMP_DIR, f'{prefix}{i}')

                for k, cert in enumerate(cert_list):
                    self._logger.info("Reading the file " + cert)
                    # Read binary data from SSL certificate file
                    with open(cert, "r") as file:
                        cert_data = file.read()
                    # Append the encoded data to the encoded_data variable
                    data = data + cert_data + '\n'

        # Encode the certificate to base64 
        encoded_data = base64.b64encode(data.encode()).decode('utf-8')
        secret_name = f"ibm-{item}-ssl-secret"
        secret_filename = secret_name + ".yaml"
        sslsecret_filepath = os.path.join(self._generate_ssl_secrets_folder, secret_filename)


        data = {
            'tls.crt': encoded_data,
        }

        rendered_secret = self.render_ssl_secret_template(data, secret_name)

        # write the secret data into a yaml
        with open(sslsecret_filepath, 'w+') as file:
            file.write(rendered_secret)
            self._logger.info(f"Created ssl secret: {secret_name}")

    def create_component_secret(self, data, secret_name,secret_folder):
        """
        Creates a Kubernetes secret from a given dictionary of data and a secret name.

        Args:
        data (dict): A dictionary containing the data to be included in the secret.
        secret_name (str): The name to be given to the created secret.

        Returns:
        None

        The function generates a filename for the secret by appending ".yaml" to the secret name.
        It then constructs the full file path by joining the generated filename with the secrets folder path.

        The function renders a secret template using the provided data and secret name.

        Finally, it writes the rendered secret data into a YAML file at the specified file path.
        A logging message is also printed to indicate the creation of the component secret.
        """
        secret_filename = secret_name + ".yaml"
        secret_filepath = os.path.join(secret_folder, secret_filename)

        # This function makes sure all values are encoded in base64 so that we can create templates with data and not string data
        encoded_secret_data = encode_secret_contents(data)

        rendered_secret = self.render_secret_template(encoded_secret_data, secret_name)

        # write the secret data into a yaml
        with open(secret_filepath, 'w+') as file:
            file.write(rendered_secret)
            self._logger.info(f"Created component secret: {secret_name}")

    # function to create ban secret
    def create_ban_secret(self):
        self._logger.info("Creating BAN secret")

        secret_name = "ibm-ban-secret"

        data = {
            "navigatorDBUsername": self._db_properties['ICN']['DATABASE_USERNAME'],
            "navigatorDBPassword": self.xor_password(self._db_properties['ICN']['DATABASE_PASSWORD']),
            "ltpaPassword": self._usergroup_properties['LTPA_PASSWORD'],
            "keystorePassword": self._usergroup_properties['KEYSTORE_PASSWORD'],
            "appLoginUsername": self._usergroup_properties['ICN_LOGIN_USER'],
            "appLoginPassword": self._usergroup_properties['ICN_LOGIN_PASSWORD']
        }

        # check if java sendmail details are present
        if self._customcomponent_properties:
            if "SENDMAIL" in self._customcomponent_properties.keys():
                self._logger.info("Adding JMAIL parameters")
                data["jMailUsername"] = self._customcomponent_properties["SENDMAIL"]["JAVAMAIL_USERNAME"]
                data["jMailPassword"] = self.xor_password(
                    self._customcomponent_properties["SENDMAIL"]["JAVAMAIL_PASSWORD"])

        self.create_component_secret(data, secret_name, self._generate_secrets_folder)

    # Function to generate ldap_secret
    def create_ldap_secret(self):
        self._logger.info("Creating LDAP secret")

        secret_name = "ldap-bind-secret"

        data = {}

        for ldap in self._ldap_properties['_ldap_ids']:
            if ldap.lower() == "ldap":
                data['ldapUsername'] = self._ldap_properties[ldap]["LDAP_BIND_DN"]
                data['ldapPassword'] = self.xor_password(self._ldap_properties[ldap]["LDAP_BIND_DN_PASSWORD"])
            else:
                data['ldap' + self._ldap_properties[ldap]["LDAP_ID"] + 'Username'] = self._ldap_properties[ldap][
                    "LDAP_BIND_DN"]
                data['ldap' + self._ldap_properties[ldap]["LDAP_ID"] + 'Password'] = self.xor_password(
                    self._ldap_properties[ldap]["LDAP_BIND_DN_PASSWORD"])

        self.create_component_secret(data, secret_name, self._generate_secrets_folder)

    # Function to generate scim_secret
    def create_scim_secret(self):
        for scim in self._scim_properties['_scim_ids']:
            self._logger.info(f"Creating SCIM secret for {scim}")
            secret_name = f"ibm-{scim.lower()}-secret"

            data = {
                'scimPassword': self.xor_password(self._scim_properties[scim]["SCIM_CLIENT_SECRET"]),
                'scimUsername': self._scim_properties[scim]["SCIM_CLIENT_ID"]
            }

            self.create_component_secret(data, secret_name, self._generate_secrets_folder)

    def create_idp_secret(self):

        for idp in self._idp_properties['_idp_ids']:
            self._logger.info(f"Creating IDP secret for {idp}")
            secret_name = f"ibm-{idp.lower()}-oidc-secret"

            data = {
                'client_id': self._idp_properties[idp]["CLIENT_ID"],
                'client_secret': self.xor_password(self._idp_properties[idp]["CLIENT_SECRET"])
            }

            self.create_component_secret(data, secret_name, self._generate_secrets_folder)

    # Function to generate fncm_secret
    def create_fncm_secret(self):
        self._logger.info("Creating FNCM secret")

        secret_name = 'ibm-fncm-secret'

        data = {
            "ltpaPassword": self._usergroup_properties['LTPA_PASSWORD'],
            "keystorePassword": self._usergroup_properties['KEYSTORE_PASSWORD'],
            "appLoginUsername": self._usergroup_properties['FNCM_LOGIN_USER'],
            "appLoginPassword": self._usergroup_properties['FNCM_LOGIN_PASSWORD'],
            "gcdDBUsername": self._db_properties["GCD"]["DATABASE_USERNAME"],
            "gcdDBPassword": self.xor_password(self._db_properties["GCD"]["DATABASE_PASSWORD"])
        }

        for os_id in self._db_properties["_os_ids"]:
            os_label = self._db_properties[os_id]["OS_LABEL"]
            data[f"{os_label}DBUsername"] = self._db_properties[os_id]["DATABASE_USERNAME"]
            data[f"{os_label}DBPassword"] = self.xor_password(self._db_properties[os_id]["DATABASE_PASSWORD"])

        self.create_component_secret(data, secret_name,self._generate_secrets_folder)

    # Function to generate ier secret
    def create_ier_secret(self):
        self._logger.info("Creating IER secret")

        secret_name = 'ibm-ier-secret'

        data = {
            "keystorePassword": self._usergroup_properties['KEYSTORE_PASSWORD']
        }

        self.create_component_secret(data, secret_name,self._generate_secrets_folder)

    # Function to generate iccsap secret
    def create_iccsap_secret(self):
        self._logger.info("Creating ICCSAP secret")

        secret_name = 'ibm-iccsap-secret'

        data = {
            "keystorePassword": self._usergroup_properties['KEYSTORE_PASSWORD']
        }

        self.create_component_secret(data, secret_name,self._generate_secrets_folder)

    # Function to generate icc related secrets
    def create_icc_secrets(self):
        # function creates the icc-masterkey-txt and ibm-icc-secret
        try:
            self._logger.info("Creating ICC secrets")

            secret_name = 'ibm-icc-secret'

            data = {
                'archiveUserId': self._customcomponent_properties["ICC"]["ARCHIVE_USER_ID"],
                'archivePassword': self.xor_password(self._customcomponent_properties["ICC"]["ARCHIVE_PASSWORD"]),

            }

            self.create_component_secret(data, secret_name,self._generate_secrets_folder)

            # creating the masterkey secret
            secret_name = 'icc-masterkey-txt'
            file_name = f"{secret_name}.yaml"
            iccmasterkey_filepath = os.path.join(self._generate_secrets_folder, file_name)
            file_list = collect_visible_files(self._icc_folder)
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

            data = {
                'MasterKey.txt': encoded_data,
            }

            rendered_secret = self.render_ssl_secret_template(data, secret_name)

            # write the secret data into a yaml
            with open(iccmasterkey_filepath, 'w+') as file:
                file.write(rendered_secret)
                self._logger.info(f"Created ICC masterkey secret: {secret_name}")

        except Exception as e:
            self._logger.exception(
                f"Error found in create_icc_secrets function in generate_secrets script --- {str(e)}")

    def create_trusted_secrets(self):
        """
        This function creates Kubernetes secrets for trusted SSL certificates.

        It searches for SSL certificate files in the specified trusted certificates folder.
        It then splits the certificate files into separate files if necessary, reads their binary data,
        encodes the data in base64, and creates a Kubernetes secret for each certificate.

        Parameters:
        self (object): An instance of the class containing the method. It should have the following attributes:
            - _trusted_certs_folder (str): The path to the folder containing trusted SSL certificates.
            - _TMP_DIR (str): The path to a temporary directory.
            - _generate_trusted_secrets_folder (str): The path to the folder where the secrets will be generated.
            - _logger (logging.Logger): A logger object for logging messages.

        Returns:
        None
        """
        try:
            if not os.path.exists(self._trusted_certs_folder):
                return

            trusted_certs = collect_visible_files(self._trusted_certs_folder)

            for i, cert in enumerate(trusted_certs):
                if any(ext in cert for ext in [".crt", ".cer", ".pem", ".cert", ".key", ".arm"]):
                    certfolderpath = os.path.join(self._trusted_certs_folder, cert)
                    # Split the certificate to separate files
                    cert_list = split_pem(self._logger, certfolderpath, self._TMP_DIR, f'trusted-{i}')
                    data = ""
                    for k, split_cert in enumerate(cert_list):
                        self._logger.info("Reading the file " + split_cert)
                        # Read binary data from SSL certificate file
                        with open(split_cert, "r") as file:
                            cert_data = file.read()
                        # Append the encoded data to the encoded_data variable
                        data = data + cert_data + '\n'

                # Encode the certificate to base64 
                encoded_data = base64.b64encode(data.encode()).decode('utf-8')
                secret_name = f"trusted-cert-{i + 1}-secret"
                secret_filename = f"{secret_name}.yaml"
                sslsecret_filepath = os.path.join(self._generate_trusted_secrets_folder, secret_filename)

                data = {
                    'tls.crt': encoded_data,
                }

                rendered_secret = self.render_ssl_secret_template(data, secret_name)

                # write the secret data into a yaml
                with open(sslsecret_filepath, 'w+') as file:
                    file.write(rendered_secret)
                    self._logger.info(f"Created trusted secret: {secret_name}")
        except Exception as e:
            self._logger.exception(
                f"Error found in create_trusted_secrets function in generate_secrets script --- {str(e)}")
