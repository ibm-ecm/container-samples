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

import copy
import os

import xmltodict
from tomlkit import comment
from tomlkit import document
from tomlkit import nl
from tomlkit import string
from tomlkit import table
from tomlkit.toml_file import TOMLFile

from ..utilities.prerequisites_utilites import read_json


# Create a class Property that accepts a dictionary of key value pairs
# - Create a java property file
# - Accept a current directory path
# - Create a set of containing folder
# - Backup existing property file if they exist

class Property:

    def __init__(self, gather_obj, path, logger, console):
        self._logger = logger
        self._console = console
        self._gather = gather_obj
        self._working_directory = path
        self._property_folder = os.path.join(self._working_directory, 'propertyFile')
        self._ssl_directory_folder = os.path.join(self._property_folder, 'ssl-certs')
        self._icc_directory_folder = os.path.join(self._property_folder, 'icc')
        self._trusted_certs_directory_folder = os.path.join(self._property_folder, 'ssl-certs', 'trusted-certs')

        # Create a dictionary of properties
        self._json_directory = os.path.dirname(__file__)
        self._db_properties = read_json(self._json_directory, "db_property.json")
        self._ldap_properties = read_json(self._json_directory, "ldap_property.json")
        self._idp_properties = read_json(self._json_directory, "idp_property.json")
        self._common_credentials = read_json(self._json_directory, "common_credentials.json")
        self._p8_credentials = read_json(self._json_directory, "p8_credentials.json")
        self._icn_credentials = read_json(self._json_directory, "icn_credentials.json")
        self._ingress_properties = read_json(self._json_directory, "ingress_property.json")
        self._init_properties = read_json(self._json_directory, "init_properties.json")
        self._os_init_properties = read_json(self._json_directory, "os_init.json")
        self._verify_properties = read_json(self._json_directory, "verify_property.json")
        self._deployment_properties = read_json(self._json_directory, "deployment_property.json")
        self._storage_properties = read_json(self._json_directory, "storage_property.json")
        self._component_properties = read_json(self._json_directory, "component_property.json")
        self._sendmail_custom_properties = read_json(self._json_directory, "sendmail_customproperty.json")
        self._icc_custom_properties = read_json(self._json_directory, "icc_customproperty.json")
        self._tm_custom_properties = read_json(self._json_directory, "tm_customproperty.json")
        self._scim_properties = read_json(self._json_directory, "scim_property.json")

    def move_ldap(self, path, move_dict, ldap_properties_list):
        if move_dict["LDAP"]:
            for i in range(self._gather.ldap_number):
                if i == 0:
                    key = "LDAP"
                else:
                    key = "LDAP{}".format(i + 1)
                self.__parse_ldap_xml(os.path.join(path, move_dict["LDAP"][i]), ldap_properties_list[i])

        return ldap_properties_list

    def __parse_ldap_xml(self, filename, ldap_properties):
        ldap_data = self.__parse_xml(filename)

        for prop in ldap_data['configuration']['property']:
            if prop['@name'] == "LDAPServerHost":
                ldap_properties["LDAP_SERVER"]['value'] = prop['value']

            if prop['@name'] == "LDAPServerPort":
                ldap_properties["LDAP_PORT"]['value'] = prop['value']

            if prop['@name'] == "LDAPBindDN":
                ldap_properties["LDAP_BIND_DN"]['value'] = prop['value']

            if prop['@name'] == "LDAPBaseDN":
                ldap_properties["LDAP_BASE_DN"]['value'] = prop['value']
                ldap_properties["LDAP_GROUP_BASE_DN"]['value'] = prop['value']

            if prop['@name'] == "LDAPUserFilter":
                ldap_properties["LC_USER_FILTER"]['value'] = prop['value']

            if prop['@name'] == "LDAPGroupFilter":
                ldap_properties["LC_GROUP_FILTER"]['value'] = prop['value']

            if prop['@name'] == "LDAPUserIDMap":
                mapping = prop['value']

                if ":" in mapping:
                    ldap_properties["LDAP_USER_NAME_ATTRIBUTE"]['value'] = mapping
                    ldap_properties["LDAP_USER_DISPLAY_NAME_ATTR"]['value'] = mapping.split(":")[1]
                else:
                    ldap_properties["LDAP_USER_NAME_ATTRIBUTE"]['value'] = f"*:{mapping}"
                    ldap_properties["LDAP_USER_DISPLAY_NAME_ATTR"]['value'] = mapping


            if prop['@name'] == "LDAPGroupIDMap":
                ldap_properties["LDAP_GROUP_NAME_ATTRIBUTE"]['value'] = prop['value']
                ldap_properties["LDAP_GROUP_DISPLAY_NAME_ATTR"]['value'] = prop['value'].split(":")[1]

        return ldap_properties

    def move_database(self, path, move_dict, db_properties):
        if move_dict["GCD"]:
            self.__parse_database_xml(os.path.join(path, move_dict["GCD"][0]), "GCD", db_properties)
        if move_dict["OS"]:
            for i in range(self._gather.os_number):
                if i == 0:
                    key = "OS"
                else:
                    key = "OS{}".format(i + 1)
                self.__parse_database_xml(os.path.join(path, move_dict["OS"][i]), key, db_properties)
        if move_dict["ICN"]:
            self.__parse_database_xml(os.path.join(path, move_dict["ICN"][0]), "ICN", db_properties)

        return db_properties

    def __parse_database_xml(self, filename, key, db_properties):
        db_data = self.__parse_xml(filename)

        for prop in db_data['configuration']['property']:
            if prop['@name'] == "DatabaseServerName":
                db_properties[key]["DATABASE_SERVERNAME"]['value'] = prop['value']

            if prop['@name'] == "DatabasePortNumber":
                db_properties[key]["DATABASE_PORT"]['value'] = prop['value']

            if prop['@name'] == "DatabaseName":
                db_properties[key]["DATABASE_NAME"]['value'] = prop['value']

            if prop['@name'] == "DatabaseUsername":
                db_properties[key]["DATABASE_USERNAME"]['value'] = prop['value']

            if prop['@name'] == "JDBCDataSourceName":
                db_properties[key]["DATASOURCE_NAME"]['value'] = prop['value']

            if prop['@name'] == "JDBCDataSourceXAName":
                db_properties[key]["DATASOURCE_NAME_XA"]['value'] = prop['value']

            if prop['@name'] == "TableSpaceName":
                db_properties[key]["TABLESPACE_NAME"]['value'] = prop['value']

            if prop['@name'] == "DatabaseSchema":
                db_properties[key]["SCHEMA_NAME"]['value'] = prop['value']

        if 'ORACLE_JDBC_URL' in db_properties[key]: 
            host_name = db_properties[key]['DATABASE_SERVERNAME']['value']
            db_name = db_properties[key]['DATABASE_NAME']['value'],
            port = db_properties[key]['DATABASE_PORT']['value']
            jdbc_url = self.__create_oracle_jdbc_url(host_name, db_name, port)
            db_properties[key]["ORACLE_JDBC_URL"]['value'] = jdbc_url

        return db_properties

    # Create a method to parse a xml file and return a dictionary
    @staticmethod
    def __parse_xml(filename):
        with open(filename, 'r') as file:
            return xmltodict.parse(file.read())

    # Create a property that gets the property folder
    @property
    def property_folder(self):
        return self._property_folder

    def create_property_structure(self):
        self.__create_property_folder()
        self.__create_ssl_folder()
        self.__create_trusted_certs_folder()
        if self._gather.icc_support:
            self.__create_icc_folder()

    # Create a method that makes a list of directories in the directory path
    def __create_property_folder(self):
        # Create a directory if it does not exist
        if not os.path.exists(self._property_folder):
            os.makedirs(self._property_folder)

    # Create a method that makes a directory path for icc support
    def __create_icc_folder(self):
        # Create a directory if it does not exist
        if not os.path.exists(self._icc_directory_folder):
            os.makedirs(self._icc_directory_folder)

    # Create a method that makes a directory path for icc support
    def __create_trusted_certs_folder(self):
        # Create a directory if it does not exist
        if not os.path.exists(self._trusted_certs_directory_folder):
            os.makedirs(self._trusted_certs_directory_folder)

    # Create a method that creates ssl folders
    def __create_ssl_folder(self):
        # Create a directory if it does not exist
        if not os.path.exists(self._ssl_directory_folder):
            os.makedirs(self._ssl_directory_folder)
        if len(self._gather.ssl_directory_list) > 0:
            for directory in self._gather.ssl_directory_list:
                # Create a directory if it does not exist
                if not os.path.exists(os.path.join(self._ssl_directory_folder, directory)):
                    os.makedirs(os.path.join(self._ssl_directory_folder, directory))
                if "ldap" not in directory:
                    if self._gather.db_type == "postgresql":
                        os.makedirs(os.path.join(self._ssl_directory_folder, directory, 'serverca'))
                        os.makedirs(os.path.join(self._ssl_directory_folder, directory, 'clientcert'))
                        os.makedirs(os.path.join(self._ssl_directory_folder, directory, 'clientkey'))

    def __populate_deployment_dict(self):
        try:
            # Create a copy of the user group dictionary
            deployment_dict = copy.deepcopy(self._deployment_properties)
            deployment_dict['FNCM_Version']['value'] = self._gather.fncm_version
            deployment_dict['LICENSE']['value'] = self._gather.license_model
            deployment_dict['PLATFORM']['value'] = self._gather.platform
            if self._gather.fncm_version in ["5.5.8", "5.5.11"]:
                deployment_dict.pop('FIPS_SUPPORT')
                deployment_dict.pop('RESTRICTED_INTERNET_ACCESS')
            else:
                deployment_dict['FIPS_SUPPORT']['value'] = self._gather.fips_support
                deployment_dict['RESTRICTED_INTERNET_ACCESS']['value'] = self._gather.egress_support
            return deployment_dict

        except Exception as e:
            self._logger.exception(
                "Exception from property script in __populate_deployment_dict function -  {}".format(str(e)))

    def __populate_scim_dict(self):
        try:
            # Create a copy of the user group dictionary
            scim_dict = copy.deepcopy(self._scim_properties)
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support
            scim_dict['SCIM_ENABLE']['value'] = self._gather.scim_support

            return scim_dict

        except Exception as e:
            self._logger.exception(
                "Exception from property script in __populate_scim_dict function -  {}".format(str(e)))

    def __populate_component_dict(self):
        try:
            # Create a copy of the user group dictionary
            component_dict = copy.deepcopy(self._component_properties)

            # for 5.5.8 cpe graphql and ban are a must and hence wont be in the toml files
            if self._gather.fncm_version == "5.5.8":
                if len(self._gather.optional_components) > 0:
                    optional_components = ["css", "cmis", "tm", "es"]
                    for component in optional_components:
                        if component in self._gather.optional_components:
                            component_dict[component.upper()]['value'] = True
                component_dict.pop("CPE")
                component_dict.pop("GRAPHQL")
                component_dict.pop("BAN")
            # for other releases cpe graphql and ban are optional and will be in toml files
            else:
                if len(self._gather.optional_components) > 0:
                    ecm_components = ["cpe", "graphql", "ban", "css", "cmis", "tm", "es", "ier", "iccsap"]
                    for component in ecm_components:
                        if component in self._gather.optional_components:
                            component_dict[component.upper()]['value'] = True

            return component_dict

        except Exception as e:
            self._logger.exception(
                "Exception from property script in __populate_component_dict function -  {}".format(str(e)))

    def create_deployment_propertyfile(self):
        # Create a file
        deployment_doc = document()
        deployment_doc.add(comment("####################################################"))
        deployment_doc.add(comment("##          License , Platform and Version           ##"))
        deployment_doc.add(comment("####################################################"))

        deployment_properties = self.__populate_deployment_dict()

        for key, value in deployment_properties.items():
            if self._gather.fncm_version in ["5.5.8", "5.5.11"] and key in ["FIPS_SUPPORT",
                                                                            "RESTRICTED_INTERNET_ACCESS"]:
                continue
            self.__write_property(doc=deployment_doc,
                                  key=key,
                                  value=value['value'],
                                  note=value['comment'])

        deployment_doc.add(nl())
        deployment_doc.add(comment("####################################################"))
        deployment_doc.add(comment("##              Optional Components               ##"))
        deployment_doc.add(comment("####################################################"))

        component_properties = self.__populate_component_dict()

        for key, value in component_properties.items():
            self.__write_property(doc=deployment_doc,
                                  key=key,
                                  value=value['value'],
                                  note=value['comment'])

        deployment_doc.add(nl())
        deployment_doc.add(comment("####################################################"))
        deployment_doc.add(comment("##                   File Storage                 ##"))
        deployment_doc.add(comment("####################################################"))

        for key, value in self._storage_properties.items():
            self.__write_property(doc=deployment_doc,
                                  key=key,
                                  value=value['value'],
                                  note=value['comment'])

        # Create a file
        f = TOMLFile(os.path.join(self._property_folder, 'fncm_deployment.toml'))
        f.write(deployment_doc)

    def create_ingress_propertyfile(self):
        # Create a file
        ingress_doc = document()
        ingress_doc.add(comment("####################################################"))
        ingress_doc.add(comment("##                CNCF Ingress             ##"))
        ingress_doc.add(comment("####################################################"))

        for key, value in self._ingress_properties.items():
            self.__write_property(doc=ingress_doc,
                                  key=key,
                                  value=value['value'],
                                  note=value['comment'])

        # Create a file
        f = TOMLFile(os.path.join(self._property_folder, 'fncm_ingress.toml'))
        f.write(ingress_doc)

    # method to create the custom component propertyfile
    def create_custom_component_propertyfile(self):
        # Create a file
        custom_property_doc = document()

        ban_features = [self._gather.sendmail_support]

        # compute if header section needs to generated
        # this section of the file is for sendmail support details
        if any(ban_features):
            custom_property_doc.add(comment("####################################################"))
            custom_property_doc.add(comment("##          IBM Content Navigator Options         ##"))
            custom_property_doc.add(comment("####################################################"))

            if self._gather.sendmail_support:
                sendmail_section = table()
                for key, value in self._sendmail_custom_properties.items():
                    self.__write_property_table(section=sendmail_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                custom_property_doc.add(nl())
                custom_property_doc.add("SENDMAIL", sendmail_section)
                custom_property_doc.add(nl())

        # compute if header section needs to generated
        css_features = [self._gather.icc_support]

        # this section of the file is for ICC for Email support details
        if any(css_features):
            custom_property_doc.add(nl())
            custom_property_doc.add(comment("####################################################"))
            custom_property_doc.add(comment("##      IBM Content Search Services Options       ##"))
            custom_property_doc.add(comment("####################################################"))

            if self._gather.icc_support:
                icc_section = table()
                for key, value in self._icc_custom_properties.items():
                    self.__write_property_table(section=icc_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                custom_property_doc.add(nl())
                custom_property_doc.add("ICC", icc_section)
                custom_property_doc.add(nl())

        # compute if header section needs to generated
        tm_features = [self._gather.tm_custom_groups]
        # this section of the file is for taskmanager custom groups support details
        if any(tm_features):
            custom_property_doc.add(comment("####################################################"))
            custom_property_doc.add(comment("##            IBM Task Manager Options            ##"))
            custom_property_doc.add(comment("####################################################"))

            if self._gather.tm_custom_groups:
                custom_groups_section = table()
                for key, value in self._tm_custom_properties.items():
                    self.__write_property_table(section=custom_groups_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                custom_property_doc.add(nl())
                custom_property_doc.add("PERMISSIONS", custom_groups_section)
                custom_property_doc.add(nl())

        # Create a file
        f = TOMLFile(os.path.join(self._property_folder, 'fncm_components_options.toml'))
        f.write(custom_property_doc)

    # Create a method that create a user group file
    def create_user_group_propertyfile(self):
        # Create a file
        user_doc = document()
        user_doc.add(comment("####################################################"))
        user_doc.add(comment("##           Common Credential Properties         ##"))
        user_doc.add(comment("####################################################"))

        for key, value in self._common_credentials.items():
            self.__write_property(doc=user_doc,
                                  key=key,
                                  value=value['value'],
                                  note=value['comment'])

        user_doc.add(nl())
        if self._gather.fncm_version == "5.5.8" or "cpe" in self._gather.optional_components:
            user_doc.add(comment("####################################################"))
            user_doc.add(comment("##           P8 CPE Credential Properties         ##"))
            user_doc.add(comment("####################################################"))

            for key, value in self._p8_credentials.items():
                self.__write_property(doc=user_doc,
                                      key=key,
                                      value=value['value'],
                                      note=value['comment'])

            user_doc.add(nl())
        if self._gather.fncm_version == "5.5.8" or "ban" in self._gather.optional_components:
            user_doc.add(comment("####################################################"))
            user_doc.add(comment("##          Navigator Credential Properties       ##"))
            user_doc.add(comment("####################################################"))

            for key, value in self._icn_credentials.items():
                self.__write_property(doc=user_doc,
                                      key=key,
                                      value=value['value'],
                                      note=value['comment'])
            user_doc.add(nl())

        if self._gather.content_initialize:
            init = self.__populate_init_dict()

            user_doc.add(nl())
            user_doc.add(comment("####################################################"))
            user_doc.add(comment("##         Initialize and Verify Properties       ##"))
            user_doc.add(comment("####################################################"))

            for key, value in init.items():
                self.__write_property(doc=user_doc,
                                      key=key,
                                      value=value['value'],
                                      note=value['comment'])

            verify = self.__populate_verify_dict()

            for key, value in verify.items():
                self.__write_property(doc=user_doc,
                                      key=key,
                                      value=value['value'],
                                      note=value['comment'])

            os_init = self.__populate_os_init_dict()

            # Adjust the db properties for OS
            for i in range(self._gather.os_number):
                if i == 0:
                    suffix = 'OS'
                else:
                    suffix = f"OS{i + 1}"

                os_section = table()
                # loop through the db_properties dictionary
                for key, value in os_init.items():
                    self.__write_property_table(section=os_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                user_doc.add(f"{suffix}", os_section)

        f = TOMLFile(os.path.join(self._property_folder, 'fncm_user_group.toml'))
        f.write(user_doc)

    # Create a private that copy and changes the user group dictionary
    def __populate_init_dict(self):
        try:
            # Create a copy of the user group dictionary
            init_dict = copy.deepcopy(self._init_properties)

            if self._gather.content_initialize:
                init_dict['CONTENT_INITIALIZATION_ENABLE']['value'] = True

            return init_dict

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_db_propertyfile function -  {}".format(str(e)))

    def __populate_verify_dict(self):
        try:
            # Create a copy of the user group dictionary
            verify_dict = copy.deepcopy(self._verify_properties)

            if self._gather.content_verification:
                verify_dict['CONTENT_VERIFICATION_ENABLE']['value'] = True

            return verify_dict

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in populate_verify_dict function -  {}".format(str(e)))

    def __populate_os_init_dict(self):
        try:
            # Create a copy of the user group dictionary
            os_init_dict = copy.deepcopy(self._os_init_properties)

            if "ier" in self._gather.optional_components:
                os_init_dict['CPE_OBJ_STORE_OS_PE_WORKFLOW_ENABLE']['value'] = True

            return os_init_dict

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in populate_os_init_dict function -  {}".format(str(e)))

    # Create a method that creates a db property file
    def create_db_propertyfile(self, db_properties):
        try:

            user_doc = document()
            user_doc.add(comment("####################################################"))
            user_doc.add(comment("##           Common Database Properties           ##"))
            user_doc.add(comment("####################################################"))

            self.__write_property(doc=user_doc,
                                  key='DATABASE_TYPE',
                                  value=db_properties['DATABASE_TYPE']['value'],
                                  note=db_properties['DATABASE_TYPE']['comment'])

            self.__write_property(doc=user_doc,
                                  key='DATABASE_SSL_ENABLE',
                                  value=db_properties['DATABASE_SSL_ENABLE']['value'],
                                  note=db_properties['DATABASE_SSL_ENABLE']['comment'])

            if self._gather.db_type == 'postgresql' and self._gather.db_ssl:
                self.__write_property(doc=user_doc,
                                      key='SSL_MODE',
                                      value=db_properties['SSL_MODE']['value'],
                                      note=db_properties['SSL_MODE']['comment'])

            user_doc.add(nl())
            if self._gather.fncm_version == "5.5.8" or "cpe" in self._gather.optional_components:
                user_doc.add(comment("####################################################"))
                user_doc.add(comment("##         Property Section for GCD database      ##"))
                user_doc.add(comment("####################################################"))

                gcd_section = table()
                for key, value in db_properties['GCD'].items():
                    if self._gather.db_type == 'oracle' and (key in ['DATABASE_SERVERNAME', 'DATABASE_PORT']):
                        continue
                    self.__write_property_table(section=gcd_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                user_doc.add("GCD", gcd_section)

                # Adjust the db properties for OS
                for i in range(self._gather.os_number):
                    if i == 0:
                        suffix = 'OS'
                    else:
                        suffix = f"OS{i + 1}"

                    user_doc.add(nl())
                    user_doc.add(comment("####################################################"))
                    user_doc.add(comment("##         Property Section for {} database      ##".format(suffix)))
                    user_doc.add(comment("####################################################"))

                    os_section = table()
                    # loop through the db_properties dictionary
                    for key, value in db_properties[suffix].items():
                        if self._gather.db_type == 'oracle' and (key in ['DATABASE_SERVERNAME', 'DATABASE_PORT']):
                            continue
                        self.__write_property_table(section=os_section,
                                                    key=key,
                                                    value=value['value'],
                                                    note=value['comment'])

                    user_doc.add(f"{suffix}", os_section)

                user_doc.add(nl())
            if self._gather.fncm_version == "5.5.8" or "ban" in self._gather.optional_components:
                user_doc.add(comment("####################################################"))
                user_doc.add(comment("##         Property Section for ICN database      ##"))
                user_doc.add(comment("####################################################"))

                icn_section = table()
                # loop through the db_properties dictionary
                for key, value in db_properties['ICN'].items():
                    if self._gather.db_type == 'oracle' and (key in ['DATABASE_SERVERNAME', 'DATABASE_PORT']):
                        continue
                    self.__write_property_table(section=icn_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                user_doc.add("ICN", icn_section)

            f = TOMLFile(os.path.join(self._property_folder, 'fncm_db_server.toml'))
            f.write(user_doc)


        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_db_propertyfile function -  {}".format(str(e)))

    def populate_db_propertyfile(self):
        try:

            database_port = {'db2': "50000",
                             'db2HADR': "50000",
                             'oracle': "1521",
                             'oracle_ssl': "2484",
                             'sqlserver': "1433",
                             'postgresql': "5432"}

            # Remove extra DB parameters
            if self._gather.db_type != 'oracle':
                self._db_properties.pop('ORACLE_JDBC_URL')

            if self._gather.db_type != 'db2HADR':
                self._db_properties.pop('HADR_STANDBY_SERVERNAME')
                self._db_properties.pop('HADR_STANDBY_PORT')

            # Create a copy of the db dictionary
            db_properties_dict = {'DATABASE_TYPE': copy.deepcopy(self._db_properties['DATABASE_TYPE']),
                                  'DATABASE_SSL_ENABLE': copy.deepcopy(self._db_properties['DATABASE_SSL_ENABLE']),
                                  'SSL_MODE': copy.deepcopy(self._db_properties['SSL_MODE']),
                                  'GCD': copy.deepcopy(self._db_properties),
                                  'ICN': copy.deepcopy(self._db_properties)}

            if self._gather.db_ssl and self._gather.db_type == 'oracle':
                db_port = database_port['oracle_ssl']
            else:
                db_port = database_port[self._gather.db_type]

            # Add OS to the db_properties_dict
            for i in range(self._gather.os_number):
                if i == 0:
                    db_properties_dict['OS'] = copy.deepcopy(self._db_properties)
                else:
                    db_properties_dict[f"OS{i + 1}"] = copy.deepcopy(self._db_properties)

            # Adjust the db common properties
            db_properties_dict['DATABASE_TYPE']['value'] = self._gather.db_type
            db_properties_dict['DATABASE_SSL_ENABLE']['value'] = self._gather.db_ssl
            db_properties_dict['SSL_MODE']['value'] = "require"

            # Adjust the db properties for GCD
            db_properties_dict['GCD'].pop('DATABASE_TYPE')
            db_properties_dict['GCD'].pop('DATABASE_SSL_ENABLE')
            db_properties_dict['GCD'].pop('OS_LABEL')
            db_properties_dict['GCD'].pop('SSL_MODE')
            db_properties_dict['GCD'].pop('TABLESPACE_NAME')
            db_properties_dict['GCD'].pop('SCHEMA_NAME')
            db_properties_dict['GCD']['DATABASE_PORT']['value'] = db_port
            db_properties_dict['GCD']['DATASOURCE_NAME']['value'] = "FNGCDDS"
            db_properties_dict['GCD']['DATASOURCE_NAME_XA']['value'] = "FNGCDDSXA"
            if self._gather.db_type == 'oracle':
                jdbc_url = self.__create_oracle_jdbc_url()
                db_properties_dict['GCD']['ORACLE_JDBC_URL']['value'] = jdbc_url

            # Adjust the db properties for ICN
            db_properties_dict['ICN'].pop('DATABASE_TYPE')
            db_properties_dict['ICN'].pop('DATABASE_SSL_ENABLE')
            db_properties_dict['ICN'].pop('OS_LABEL')
            db_properties_dict['ICN'].pop('SSL_MODE')
            db_properties_dict['ICN'].pop('DATASOURCE_NAME_XA')
            db_properties_dict['ICN']['TABLESPACE_NAME']['value'] = "ICNDB"
            db_properties_dict['ICN']['SCHEMA_NAME']['value'] = "ICNDB"
            db_properties_dict['ICN']['DATABASE_PORT']['value'] = db_port
            db_properties_dict['ICN']['DATASOURCE_NAME']['value'] = "ECMClientDS"
            if self._gather.db_type == 'oracle':
                jdbc_url = self.__create_oracle_jdbc_url()
                db_properties_dict['ICN']['ORACLE_JDBC_URL']['value'] = jdbc_url

            # Adjust the db properties for OS
            for i in range(self._gather.os_number):
                if i == 0:
                    db_properties_dict['OS'].pop('DATABASE_TYPE')
                    db_properties_dict['OS'].pop('DATABASE_SSL_ENABLE')
                    db_properties_dict['OS']['OS_LABEL']['value'] = 'os'
                    db_properties_dict['OS'].pop('SSL_MODE')
                    db_properties_dict['OS'].pop('TABLESPACE_NAME')
                    db_properties_dict['OS'].pop('SCHEMA_NAME')
                    db_properties_dict['OS']['DATABASE_PORT']['value'] = db_port
                    db_properties_dict['OS']['DATASOURCE_NAME']['value'] = "FNOS1DS"
                    db_properties_dict['OS']['DATASOURCE_NAME_XA']['value'] = "FNOS1DSXA"
                    if self._gather.db_type == 'oracle':
                        jdbc_url = self.__create_oracle_jdbc_url()
                        db_properties_dict['OS']['ORACLE_JDBC_URL']['value'] = jdbc_url
                else:
                    db_properties_dict[f"OS{i + 1}"].pop('DATABASE_TYPE')
                    db_properties_dict[f"OS{i + 1}"].pop('DATABASE_SSL_ENABLE')
                    db_properties_dict[f"OS{i + 1}"]['OS_LABEL']['value'] = f"os{i + 1}"
                    db_properties_dict[f"OS{i + 1}"].pop('SSL_MODE')
                    db_properties_dict[f"OS{i + 1}"].pop('TABLESPACE_NAME')
                    db_properties_dict[f"OS{i + 1}"].pop('SCHEMA_NAME')
                    db_properties_dict[f"OS{i + 1}"]['DATABASE_PORT']['value'] = db_port
                    db_properties_dict[f"OS{i + 1}"]['DATASOURCE_NAME']['value'] = f"FNOS{i + 1}DS"
                    db_properties_dict[f"OS{i + 1}"]['DATASOURCE_NAME_XA']['value'] = f"FNOS{i + 1}DSXA"
                    if self._gather.db_type == 'oracle':
                        jdbc_url = self.__create_oracle_jdbc_url()
                        db_properties_dict[f"OS{i + 1}"]['ORACLE_JDBC_URL']['value'] = jdbc_url

            return db_properties_dict

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_db_propertyfile function -  {}".format(str(e)))

    # Create a private method that creates the jdbc oracle url
    def __create_oracle_jdbc_url(self, host_name = "<Required>", db_name = "<Required>", port_name = "<Required>") -> str:
        try:
            if self._gather.db_ssl and self._gather.db_type == 'oracle':
                jdbc_url = 'jdbc:oracle:thin:@(DESCRIPTION=(ADDRESS=(PROTOCOL=TCPS)(HOST={host})(PORT={port}))(' \
                           'CONNECT_DATA=(SERVICE_NAME={dbname})))'.format(
                    host=host_name,
                    dbname=db_name, 
                    port=port_name)
            else:
                jdbc_url = 'jdbc:oracle:thin:@(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={port}))(' \
                           'CONNECT_DATA=(SERVICE_NAME={dbname})))'.format(
                    host=host_name,
                    dbname=db_name, 
                    port=port_name)
            return jdbc_url

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_oracle_jdbc_url function -  {}".format(str(e)))

    def create_idp_propertyfile(self, idp_properties_list):
        try:

            # Create a file
            idp_doc = document()

            idp_doc.add(nl())
            idp_doc.add(comment("####################################################"))
            idp_doc.add(comment("##                  IDP Properties                ##"))
            idp_doc.add(comment("####################################################"))

            idp_section = table()

            suffix = 'IDP'
            # loop through the ldap_properties dictionary
            for key, value in idp_properties_list[0].items():
                self.__write_property_table(section=idp_section,
                                            key=key,
                                            value=value['value'],
                                            note=value['comment'])

            idp_doc.add(suffix, idp_section)

            for i in range(1, self._gather.idp_number):
                suffix = f"IDP{i + 1}"

                idp_section = table()

                idp_doc.add(nl())
                idp_doc.add(comment("####################################################"))
                idp_doc.add(comment(f"##               {suffix} Properties             ##"))
                idp_doc.add(comment("####################################################"))

                # loop through the db_properties dictionary
                for key, value in idp_properties_list[i].items():
                    self.__write_property_table(section=idp_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                idp_doc.add(suffix, idp_section)

            f = TOMLFile(os.path.join(self._property_folder, 'fncm_identity_provider.toml'))
            f.write(idp_doc)

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_idp_propertyfile function -  {}".format(str(e)))

    # Create a method that creates a ldap property file
    def create_ldap_propertyfile(self, ldap_properties_list):
        try:

            # Create a file
            ldap_doc = document()

            ldap_doc.add(nl())
            ldap_doc.add(comment("####################################################"))
            ldap_doc.add(comment("##                 LDAP Properties                ##"))
            ldap_doc.add(comment("####################################################"))

            ldap_section = table()

            suffix = 'LDAP'

            # loop through the ldap_properties dictionary
            for key, value in ldap_properties_list[0].items():
                self.__write_property_table(section=ldap_section,
                                            key=key,
                                            value=value['value'],
                                            note=value['comment'])

            ldap_doc.add(suffix, ldap_section)

            for i in range(1, self._gather.ldap_number):
                suffix = f"LDAP{i + 1}"

                ldap_section = table()

                ldap_doc.add(nl())
                ldap_doc.add(comment("####################################################"))
                ldap_doc.add(comment(f"##               {suffix} Properties              ##"))
                ldap_doc.add(comment("####################################################"))

                # loop through the db_properties dictionary
                for key, value in ldap_properties_list[i].items():
                    self.__write_property_table(section=ldap_section,
                                                key=key,
                                                value=value['value'],
                                                note=value['comment'])

                ldap_doc.add(suffix, ldap_section)

            f = TOMLFile(os.path.join(self._property_folder, 'fncm_ldap_server.toml'))
            f.write(ldap_doc)

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_ldap_propertyfile function -  {}".format(str(e)))

    # Create a private method that writes properties to a file
    @staticmethod
    def __write_property(doc, key, value, note):

        doc.add(nl())
        for i in note:
            doc.add(comment(f'{i}'))
        cred_list = ['PASSWORD', 'SECRET', 'USERNAME', 'GROUPS_NAME', 'ADMIN_USER', 'LOGIN_USER', 'CLIENT_ID', 'BIND_DN', 'USER_ID', "NAMES"]
        if any(ele in key for ele in cred_list):
            if isinstance(value, list):
                for i in range(len(value)):
                    value[i] = string(value[i], multiline=True)
            else:
                value = string(value, multiline=True)

        doc.add(key, value)

    @staticmethod
    def __write_property_table(section, key, value, note, ):
        section.add(nl())
        for i in note:
            section.add(comment(f'{i}'))
        cred_list = ['PASSWORD', 'SECRET', 'USERNAME', 'GROUPS_NAME', 'ADMIN_USER', 'LOGIN_USER', 'BIND_DN', 'USER_ID', "NAMES"]
        if any(ele in key for ele in cred_list):
            if isinstance(value, list):
                for i in range(len(value)):
                    value[i] = string(value[i], multiline=True)
            else:
                value = string(value, multiline=True)

        section.add(key, value)

    def populate_idp_propertyfile(self):
        try:

            idp_properties_list = []

            for i in range(self._gather.idp_number):
                idp_dict = self._gather.idp_info[i].to_dict()
                idp_prop = copy.deepcopy(self._idp_properties)

                idp_prop['PROVIDER_NAME']['value'] = idp_dict['id']
                idp_prop['DISPLAY_NAME']['value'] = "{} SSO Login".format(idp_dict['id'])

                if idp_dict['discovery_enabled']:
                    idp_prop['DISCOVERY_ENDPOINT']['value'] = idp_dict["discovery_url"]
                else:
                    idp_prop.pop('DISCOVERY_ENDPOINT')

                if idp_dict['token_url']:
                    idp_prop['TOKEN_ENDPOINT']['value'] = idp_dict['token_url']

                if idp_dict["issuer"]:
                    idp_prop['ISSUER']['value'] = idp_dict["issuer"]

                if idp_dict['introspect_url'] and idp_dict['validation_method'] == "introspect":
                    idp_prop['INTROSPECT_ENDPOINT']['value'] = idp_dict['introspect_url']
                    idp_prop.pop('USERINFO_ENDPOINT')

                if idp_dict['userinfo_url'] and idp_dict['validation_method'] == "userinfo":
                    idp_prop['USERINFO_ENDPOINT']['value'] = idp_dict['userinfo_url']
                    idp_prop.pop('INTROSPECT_ENDPOINT')

                if idp_dict['revoke_url']:
                    idp_prop['REVOCATION_ENDPOINT']['value'] = idp_dict['revoke_url']

                idp_prop['VALIDATION_METHOD']['value'] = idp_dict['validation_method']
                idp_prop['USER_IDENTIFIER']['value'] = idp_dict['user_identifier']
                idp_prop['UNIQUE_USER_IDENTIFIER']['value'] = idp_dict['unique_user_identifier']
                idp_prop['USER_IDENTIFIER_TO_CREATE_SUBJECT']['value'] = idp_dict['user_identifier_to_sub']

                idp_properties_list.append(idp_prop)

            return idp_properties_list


        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_ldap_propertyfile function -  {}".format(str(e)))

    def create_scim_propertyfile(self, scim_properties):
        try:

            # Create a file
            scim_doc = document()

            scim_doc.add(nl())
            scim_doc.add(comment("####################################################"))
            scim_doc.add(comment("##                  SCIM Properties               ##"))
            scim_doc.add(comment("####################################################"))

            scim_section = table()

            suffix = 'SCIM'
            # loop through the ldap_properties dictionary
            for key, value in scim_properties.items():
                self.__write_property_table(section=scim_section,
                                            key=key,
                                            value=value['value'],
                                            note=value['comment'])

            scim_doc.add(suffix, scim_section)

            f = TOMLFile(os.path.join(self._property_folder, 'fncm_scim_server.toml'))
            f.write(scim_doc)

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_scim_propertyfile function -  {}".format(str(e)))

    def populate_scim_propertyfile(self):
        try:

            idp_dict = self._gather.idp_info[0].to_dict()
            scim_prop = copy.deepcopy(self._scim_properties)

            scim_prop['DISPLAY_NAME']['value'] = "SCIM"
            scim_prop['SCIM_SSL_ENABLED']['value'] = True
            scim_prop['TOKEN_ENDPOINT']['value'] = idp_dict["token_url"]

            return scim_prop

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in populate_scim_propertyfile function -  {}".format(str(e)))

    def populate_ldap_propertyfile(self):
        try:
            ldap_properties_list = []
            # Create a copy of the ldap properties dictionary
            for i in range(self._gather.ldap_number):
                ldap_dict = self._gather.ldap_info[i].to_dict()
                ldap_prop = copy.deepcopy(self._ldap_properties)

                ldap_prop['LDAP_TYPE']['value'] = ldap_dict['type']
                ldap_prop['LDAP_SSL_ENABLED']['value'] = ldap_dict['ssl']
                ldap_prop['LDAP_ID']['value'] = ldap_dict['id']

                if ldap_dict['type'] != 'Microsoft Active Directory':
                    ldap_prop.pop('LC_AD_GC_HOST')
                    ldap_prop.pop('LC_AD_GC_PORT')

                if ldap_dict['type'] == 'Microsoft Active Directory':
                    default_value = read_json(self._json_directory, "ad_ldap_property.json")
                elif ldap_dict['type'] == 'IBM Security Verify Directory':
                    default_value = read_json(self._json_directory, "tds_ldap_property.json")
                elif ldap_dict['type'] in ['Oracle Internet Directory', 'Oracle Unified Directory',
                                           'Oracle Directory Server Enterprise Edition']:
                    default_value = read_json(self._json_directory, "oracle_ldap_property.json")
                elif ldap_dict['type'] == 'NetIQ eDirectory':
                    default_value = read_json(self._json_directory, "novell_ldap_property.json")
                elif ldap_dict['type'] == 'CA eTrust':
                    default_value = read_json(self._json_directory, "ca_ldap_property.json")

                for key, value in default_value.items():
                    ldap_prop[key]['value'] = value['value']

                if ldap_dict['ssl']:
                    ldap_prop['LDAP_PORT']['value'] = "636"
                else:
                    ldap_prop['LDAP_PORT']['value'] = "389"

                ldap_properties_list.append(ldap_prop)

            return ldap_properties_list

        except Exception as e:
            self._logger.exception(
                "Exception from gather script in create_ldap_propertyfile function -  {}".format(str(e)))
