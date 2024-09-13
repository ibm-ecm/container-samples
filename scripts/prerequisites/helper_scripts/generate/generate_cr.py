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
import os
from urllib.parse import urlparse

from ruamel.yaml import CommentedMap
from ruamel.yaml import YAML

from ..utilities.prerequisites_utilites import collect_visible_files


# Function to remove protocol from URL
def remove_protocol(url):
    hostname = urlparse(url).hostname
    if hostname is None:
        hostname = url
    return hostname


# Class to generate the CR
class GenerateCR:

    # read to yaml function
    def load_cr_template(self, filepath):
        # load the YAML file with comments
        # read the source YAML file with comments
        with open(filepath, 'r') as file:
            data = YAML().load(file)
        return data

    # write to yaml function
    def write_cr_template(self):
        # write the updated YAML file with preserved comments
        with open(self._generated_cr, 'w') as file:
            yaml = YAML()
            yaml.representer.ignore_aliases = lambda *args: True
            yaml.dump(self._merged_data, file)

    def __init__(self, db_properties=None, ldap_properties=None, usergroup_properties=None, deployment_properties=None,
                 ingress_properties=None, customcomponent_properties=None, idp_properties=None, scim_properties=None,
                 logger=None):
        self._logger = logger

        self._db_properties = db_properties
        self._ldap_properties = ldap_properties
        self._usergroup_properties = usergroup_properties
        self._idp_properties = idp_properties
        self._deployment_properties = deployment_properties
        self._ingress_properties = ingress_properties
        self._customcomponent_properties = customcomponent_properties
        self._scim_properties = scim_properties

        self._generate_folder = os.path.join(os.getcwd(), "generatedFiles")
        # Navigate up two levels to the parent directory
        self._base_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "base.yaml")
        self._database_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                               self._deployment_properties["FNCM_Version"], "database.yaml")
        self._ldap_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "ldap.yaml")
        self._idp_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                          self._deployment_properties["FNCM_Version"], "idp.yaml")
        self._ingress_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                              self._deployment_properties["FNCM_Version"], "ingress.yaml")
        self._init_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "init.yaml")
        self._multi_ldap_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                                 self._deployment_properties["FNCM_Version"], "ldap-multi.yaml")
        self._verify_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                             self._deployment_properties["FNCM_Version"], "verify.yaml")
        self._scim_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "scim.yaml")

        self._generated_cr = os.path.join(self._generate_folder, "ibm_fncm_cr_production.yaml")
        self._merged_data = CommentedMap()
        if os.path.exists(self._generated_cr):
            os.remove(self._generated_cr)

    def generate_cr(self):
        self._logger.info("generating CR")
        # call function to generate shared configuration section of CR
        self.generate_base_section()

        if self._idp_properties:
            self.populate_idp_section()

        self.populate_ingress_section()

        if self._ldap_properties:
            ldap_dict = self.load_cr_template(self._ldap_template)
            self.populate_ldap_section(ldap_dict, "ldap_configuration")
            self.populate_multi_ldap_section()

        if self._db_properties:
            self.populate_db_section()

        # call function to generate init configuration of CR if required
        if "CONTENT_INITIALIZATION_ENABLE" in self._usergroup_properties:
            if self._usergroup_properties["CONTENT_INITIALIZATION_ENABLE"]:
                self.populate_init_section()

                if not self._ldap_properties and self._scim_properties:
                    self._merged_data["spec"]["initialize_configuration"].pop("ic_ldap_creation")
                    self.populate_scim_section()

        # call function to generate verify configuration of CR if required
        if "CONTENT_VERIFICATION_ENABLE" in self._usergroup_properties:
            if self._usergroup_properties["CONTENT_VERIFICATION_ENABLE"]:
                self.populate_verify_section()

        # calculate custom feature list:
        feature_dict = self.generate_custom_feature_dict()

        # call function to generate custom component properties if required
        self.populate_custom_property_section(feature_dict)

        self.write_cr_template()

    # Create a function to populate the SCIM section
    def populate_scim_section(self):
        self._logger.info("generating SCIM section")
        try:
            scim_section = self.load_cr_template(self._scim_template)
            num_scim = len(self._scim_properties["_scim_ids"])

            # Adding the SCIM section to the CR
            # First section already exists in the template
            # Loop to add additional sections
            while len(scim_section["spec"]["initialize_configuration"]["scim_configuration"]) < num_scim:
                new_scim_dict = scim_section["spec"]["initialize_configuration"]["scim_configuration"][0].copy()
                scim_section["spec"]["initialize_configuration"]["scim_configuration"].append(new_scim_dict)

            # Populate the SCIM section
            # Loop through scim_properties and populate the SCIM section
            for idx, key in enumerate(self._scim_properties["_scim_ids"]):
                secret_name = f"ibm-{key.lower()}-secret"

                # Create SCIM secret section

                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["name"] = key

                # Get First IDP Key
                idp_key = self._idp_properties["_idp_ids"][0]
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["auth_url"] = \
                    self._idp_properties[idp_key]["TOKEN_ENDPOINT"]

                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["ssl_enabled"] = \
                    self._scim_properties[key]["SCIM_SSL_ENABLED"]

                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "group_name_attribute"] = "displayName"
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "group_display_name_attribute"] = "displayName"
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "group_unique_id_attribute"] = "id"

                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "user_unique_id_attribute"] = "id"
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "user_display_name_attribute"] = "displayName"
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "user_name_attribute"] = "userName"

                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["host"] = \
                    remove_protocol(self._scim_properties[key]["SCIM_SERVER"])
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["port"] = \
                    self._scim_properties[key]["SCIM_PORT"]
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["context_path"] = \
                    self._scim_properties[key]["SCIM_CONTEXT_PATH"]
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "scim_secret_name"] = secret_name
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx][
                    "service_type"] = "AUTO_DETECT"

                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["admin_users"] = \
                    self._usergroup_properties["GCD_ADMIN_USER_NAME"]
                scim_section["spec"]["initialize_configuration"]["scim_configuration"][idx]["admin_groups"] = \
                    self._usergroup_properties["GCD_ADMIN_GROUPS_NAME"]

            self._merged_data["spec"]["initialize_configuration"].update(
                scim_section["spec"]["initialize_configuration"])

        except Exception as e:
            self._logger.exception(f"Error found in populate-scim function in generate_cr script --- {str(e)}")

    # function to populate the ldap sections
    def populate_ldap_section(self, ldap_dict, cr_key, key=None):
        self._logger.info("Generating Ldap section")
        try:
            # Build LDAPType to sections mapping
            ldap_type_to_section = {
                "IBM Security Verify Directory": "tds",
                "IBM Security Directory Server": "tds",
                "Microsoft Active Directory": "ad",
                "NetIQ eDirectory": "ed",
                "Oracle Internet Directory": "oracle",
                "Oracle Directory Server Enterprise Edition": "oracle",
                "Oracle Unified Directory": "oracle",
                "CA eTrust": "caet"
            }

            if cr_key == "ldap_configuration":
                key = "LDAP"
            # populating the base ldap section and also removing keys not required
            if self._ldap_properties[key]["LDAP_TYPE"] == "IBM Security Verify Directory":
                ldap_dict["spec"][cr_key]["lc_selected_ldap_type"] = "IBM Security Directory Server"
            else:
                ldap_dict["spec"][cr_key]["lc_selected_ldap_type"] = self._ldap_properties[key]["LDAP_TYPE"]
            ldap_dict["spec"][cr_key]["lc_ldap_group_member_id_map"] = self._ldap_properties[key][
                "LDAP_GROUP_MEMBERSHIP_ID_MAP"]

            # check if ssl is enabled otherwise remove those keys and values

            if self._ldap_properties[key]["LDAP_SSL_ENABLED"]:
                ldap_dict["spec"][cr_key]["lc_ldap_ssl_secret_name"] = "ibm-" + key.lower() + "-ssl-secret"
            else:
                ldap_dict["spec"][cr_key].pop('lc_ldap_ssl_secret_name')
                ldap_dict["spec"][cr_key]['lc_ldap_ssl_enabled'] = False

            if self._ldap_properties[key]["LDAP_TYPE"] == "IBM Security Verify Directory":
                ldap_dict["spec"][cr_key]["lc_selected_ldap_type"] = "IBM Security Directory Server"
            else:
                ldap_dict["spec"][cr_key]["lc_selected_ldap_type"] = self._ldap_properties[key]["LDAP_TYPE"]

            for ldap_property in self._ldap_properties["LDAP"]:
                if "lc_" + ldap_property.lower() in list(
                        ldap_dict["spec"][cr_key].keys()):
                    if 'server' in ldap_property.lower():
                        ldap_dict["spec"][cr_key]["lc_" + ldap_property.lower()] = remove_protocol(
                            self._ldap_properties[key][ldap_property])
                    else:
                        ldap_dict["spec"][cr_key]["lc_" + ldap_property.lower()] = self._ldap_properties[key][
                            ldap_property]

            ldap_acronym = ldap_type_to_section[self._ldap_properties[key]["LDAP_TYPE"]]

            ldap_dict["spec"][cr_key][ldap_acronym]["lc_user_filter"] = self._ldap_properties[key]["LC_USER_FILTER"]
            ldap_dict["spec"][cr_key][ldap_acronym]["lc_group_filter"] = self._ldap_properties[key]["LC_GROUP_FILTER"]

            # populating the additional AD GC section if defined and not "optional"
            if "LC_AD_GC_HOST" in self._ldap_properties[key]:
                if self._ldap_properties[key]["LC_AD_GC_HOST"].lower() != "<optional>":
                    ldap_dict["spec"][cr_key]["ad"]["lc_ad_gc_host"] = self._ldap_properties[key]["LC_AD_GC_HOST"]
                else:
                    ldap_dict["spec"][cr_key]["ad"].pop("lc_ad_gc_host")
            else:
                ldap_dict["spec"][cr_key]["ad"].pop("lc_ad_gc_host")
            if "LC_AD_GC_PORT" in self._ldap_properties[key]:
                if self._ldap_properties[key]["LC_AD_GC_PORT"].lower() != "<optional>":
                    ldap_dict["spec"][cr_key]["ad"]["lc_ad_gc_port"] = self._ldap_properties[key]["LC_AD_GC_PORT"]
                else:
                    ldap_dict["spec"][cr_key]["ad"].pop("lc_ad_gc_port")
            else:
                ldap_dict["spec"][cr_key]["ad"].pop("lc_ad_gc_port")

            # Remove optional keys based on the LDAP type
            for optional_key in list(ldap_dict["spec"][cr_key].keys()):
                if not optional_key.startswith("lc_") and not optional_key.startswith(ldap_acronym):
                    ldap_dict["spec"][cr_key].pop(optional_key)

            self._merged_data["spec"].update(ldap_dict["spec"])

        except Exception as e:
            self._logger.exception(f"Error found in populate_ldap_section function in generate_cr script --- {str(e)}")

    # Create a function to generate the OIDC section
    def populate_idp_section(self):
        self._logger.info("generating OIDC section")
        try:
            idp_section = self.load_cr_template(self._idp_template)
            num_idp = len(self._idp_properties["_idp_ids"])

            # Adding the OIDC section to the CR
            # First section already exists in the template
            # Loop to add additional sections
            while len(idp_section["spec"]["shared_configuration"]["open_id_connect_providers"]) < num_idp:
                new_idp_dict = idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][0].copy()
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"].append(new_idp_dict)

            # Populate the OIDC section
            # Loop through idp_properties and populate the OIDC section
            for idx, key in enumerate(self._idp_properties["_idp_ids"]):
                secret_name = "ibm-" + key.lower() + "-oidc-secret"

                # Create OIDC secret section

                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx]["provider_name"] = key
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx]["display_name"] = \
                    self._idp_properties[key]["DISPLAY_NAME"]
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx]["issuer_identifier"] = \
                    self._idp_properties[key]["ISSUER"]

                secret_section = {"cpe": secret_name, "nav": secret_name}
                if self._deployment_properties["FNCM_Version"] == "5.5.8":
                    secret_section["es"] = secret_name
                    secret_section["graphql"] = secret_name

                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx][
                    "client_oidc_secret"] = secret_section
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx]["validation_method"] = \
                    self._idp_properties[key]["VALIDATION_METHOD"]
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx]["user_identifier"] = \
                    self._idp_properties[key]["USER_IDENTIFIER"]
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx][
                    "unique_user_identifier"] = \
                    self._idp_properties[key]["UNIQUE_USER_IDENTIFIER"]
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx][
                    "user_identity_to_create_subject"] = \
                    self._idp_properties[key]["USER_IDENTIFIER_TO_CREATE_SUBJECT"]
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx]["token_endpoint_url"] = \
                    self._idp_properties[key]["TOKEN_ENDPOINT"]

                if "DISCOVERY_ENDPOINT" in self._idp_properties[key]:
                    idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx][
                        "discovery_endpoint_url"] = \
                        self._idp_properties[key]["DISCOVERY_ENDPOINT"]
                else:
                    idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx].pop(
                        "discovery_endpoint_url")

                # Build custom user-defined parameters
                parameter_list = []
                if self._idp_properties[key]["VALIDATION_METHOD"] == "userinfo":
                    parameter = "DELIM=;userinfoEndpointUrl;" + self._idp_properties[key]["USERINFO_ENDPOINT"]
                    parameter_list.append(parameter)
                    parameter = "DELIM=;userinfo;true"
                    parameter_list.append(parameter)
                else:
                    parameter = "DELIM=;introspectEndpointUrl;" + self._idp_properties[key]["INTROSPECT_ENDPOINT"]
                    parameter_list.append(parameter)

                parameter = "DELIM=;revokeEndpointUrl;" + self._idp_properties[key]["REVOCATION_ENDPOINT"]
                parameter_list.append(parameter)

                # Add custom user-defined parameters to the OIDC section
                idp_section["spec"]["shared_configuration"]["open_id_connect_providers"][idx][
                    "oidc_ud_param"] = parameter_list

            self._merged_data["spec"]["shared_configuration"].update(idp_section["spec"]["shared_configuration"])

        except Exception as e:
            self._logger.exception(f"Error found in populate-idp function in generate_cr script --- {str(e)}")

    # function to populate the db section
    def populate_db_section(self):
        self._logger.info("generating Database Section")
        try:
            db_dict = self.load_cr_template(self._database_template)
            db_dict["spec"]["datasource_configuration"]["dc_ssl_enabled"] = self._db_properties["DATABASE_SSL_ENABLE"]
            # for 5.5.11 and above all three datasource sections are not a must.
            cr_db_keys = []
            if self._deployment_properties["FNCM_Version"] != "5.5.8":
                if self._deployment_properties["CPE"]:
                    cr_db_keys.append("dc_gcd_datasource")
                    cr_db_keys.append("dc_os_datasources")
                if self._deployment_properties["BAN"]:
                    cr_db_keys.append("dc_icn_datasource")
            else:
                cr_db_keys = ["dc_gcd_datasource", "dc_icn_datasource", "dc_os_datasources"]
            for cr_key in cr_db_keys:
                if cr_key == "dc_gcd_datasource":
                    db_key = "GCD"
                elif cr_key == "dc_icn_datasource":
                    db_key = "ICN"
                else:
                    db_key = self._db_properties["_os_ids"]
                # populating GCD and ICN section
                if cr_key in ["dc_gcd_datasource", "dc_icn_datasource"]:
                    db_dict["spec"]["datasource_configuration"][cr_key]["dc_database_type"] = self._db_properties[
                        "DATABASE_TYPE"]
                    if self._db_properties["DATABASE_SSL_ENABLE"]:
                        db_dict["spec"]["datasource_configuration"][cr_key][
                            "database_ssl_secret_name"] = "ibm-" + db_key.lower() + "-ssl-secret"
                    else:
                        db_dict["spec"]["datasource_configuration"][cr_key].pop("database_ssl_secret_name")

                    for prop_key in self._db_properties[db_key]:
                        if prop_key.lower() in db_dict["spec"]["datasource_configuration"][cr_key].keys():
                            if 'server' in prop_key.lower():
                                db_dict["spec"]["datasource_configuration"][cr_key][prop_key.lower()] = \
                                    remove_protocol(self._db_properties[db_key][prop_key])
                            else:
                                db_dict["spec"]["datasource_configuration"][cr_key][prop_key.lower()] = \
                                    self._db_properties[db_key][prop_key]

                    # populating the datasource name
                    if cr_key == "dc_gcd_datasource":
                        db_dict["spec"]["datasource_configuration"][cr_key]["dc_common_gcd_datasource_name"] = \
                            self._db_properties["GCD"][
                                "DATASOURCE_NAME"]
                        db_dict["spec"]["datasource_configuration"][cr_key]["dc_common_gcd_xa_datasource_name"] = \
                            self._db_properties["GCD"][
                                "DATASOURCE_NAME_XA"]
                    else:
                        db_dict["spec"]["datasource_configuration"][cr_key]["dc_common_icn_datasource_name"] = \
                            self._db_properties["ICN"][
                                "DATASOURCE_NAME"]

                    # removing hadr and oracle parameters if they aren't selected as DB type
                    for datasource_key in list(db_dict["spec"]["datasource_configuration"][cr_key].keys()):
                        if self._db_properties["DATABASE_TYPE"].lower() != "db2hadr":
                            if datasource_key.startswith("dc_hadr") and datasource_key != "dc_hadr_validation_timeout":
                                db_dict["spec"]["datasource_configuration"][cr_key].pop(datasource_key)
                        else:
                            db_dict["spec"]["datasource_configuration"][cr_key]["dc_hadr_standby_servername"] = \
                                remove_protocol(self._db_properties[db_key]['HADR_STANDBY_SERVERNAME'])
                            db_dict["spec"]["datasource_configuration"][cr_key]["dc_hadr_standby_port"] = \
                                self._db_properties[db_key]['HADR_STANDBY_PORT']
                        if self._db_properties["DATABASE_TYPE"].lower() != "oracle":
                            if "oracle" in datasource_key:
                                db_dict["spec"]["datasource_configuration"][cr_key].pop(datasource_key)
                        else:
                            db_dict["spec"]["datasource_configuration"][cr_key][
                                "dc_oracle_" + db_key.lower() + "_jdbc_url"] = self._db_properties[db_key][
                                'ORACLE_JDBC_URL']
                            db_dict["spec"]["datasource_configuration"][cr_key].pop("database_servername", None)
                            db_dict["spec"]["datasource_configuration"][cr_key].pop("database_port", None)
                            db_dict["spec"]["datasource_configuration"][cr_key].pop("database_name", None)

                # populating the OS section
                else:
                    while len(db_dict["spec"]["datasource_configuration"]["dc_os_datasources"]) < len(db_key):
                        new_os_dict = db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][0].copy()
                        db_dict["spec"]["datasource_configuration"]["dc_os_datasources"].append(new_os_dict)
                    for os_number in range(len(db_dict["spec"]["datasource_configuration"]["dc_os_datasources"])):
                        prop_key = db_key[os_number]
                        db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                            "dc_database_type"] = self._db_properties["DATABASE_TYPE"]
                        db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number]["dc_os_label"] = \
                            self._db_properties[prop_key]["OS_LABEL"]
                        if self._db_properties["DATABASE_SSL_ENABLE"]:
                            # if it is the first section that we know it will be the base OS, so we can use ibm-osdb-ssl-secret
                            secret_name = "ibm-os-ssl-secret"
                            if os_number > 0:
                                secret_name = "ibm-os" + str(os_number + 1) + "-ssl-secret"
                            db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                "database_ssl_secret_name"] = secret_name
                        else:
                            db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                "database_ssl_secret_name")

                        # Populate the datasource name and XA datasource name
                        db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                            "dc_common_os_datasource_name"] = self._db_properties[prop_key]["DATASOURCE_NAME"]
                        db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                            "dc_common_os_xa_datasource_name"] = self._db_properties[prop_key]["DATASOURCE_NAME_XA"]

                        for property in list(self._db_properties[prop_key].keys()):
                            if property.lower() in dict(
                                    db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number]).keys():
                                if 'server' in property.lower():
                                    db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                        property.lower()] = remove_protocol(
                                        self._db_properties[prop_key][property])
                                else:
                                    db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                        property.lower()] = self._db_properties[prop_key][property]

                        # removing hadr and oracle parameters if they aren't selected as DB type
                        for datasource_key in list(
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].keys()):
                            if self._db_properties["DATABASE_TYPE"].lower() != "db2hadr":
                                if datasource_key.startswith(
                                        "dc_hadr") and datasource_key != "dc_hadr_validation_timeout":
                                    db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                        datasource_key)
                            else:
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                    "dc_hadr_standby_servername"] = remove_protocol(self._db_properties[prop_key][
                                                                                        'HADR_STANDBY_SERVERNAME'])
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                    "dc_hadr_standby_port"] = self._db_properties[prop_key]['HADR_STANDBY_PORT']
                            if self._db_properties["DATABASE_TYPE"].lower() != "oracle":
                                if "oracle" in datasource_key:
                                    db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                        datasource_key)
                            else:
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                    "dc_oracle_os_jdbc_url"] = self._db_properties[prop_key]['ORACLE_JDBC_URL']
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                    "database_servername", None)
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                    "database_port", None)
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                    "database_name", None)

            # based on the component deployed, certain sections of the CR can be removed.
            if self._deployment_properties["FNCM_Version"] != "5.5.8":
                if not self._deployment_properties["CPE"]:
                    db_dict["spec"]["datasource_configuration"].pop("dc_os_datasources")
                    db_dict["spec"]["datasource_configuration"].pop("dc_gcd_datasource")
                if not self._deployment_properties["BAN"]:
                    db_dict["spec"]["datasource_configuration"].pop("dc_icn_datasource")

            # merge the db section into the main yaml
            self._merged_data["spec"].update(db_dict["spec"])

        except Exception as e:
            self._logger.exception(f"Error found in populate_db_section function in generate_cr script --- {str(e)}")

    # function to generate the Database , shared and ldap section
    def generate_base_section(self):
        self._logger.info("Generating Base section")
        try:
            base_dict = self.load_cr_template(self._base_template)
            if self._deployment_properties["FNCM_Version"] == "5.5.8":
                base_dict["spec"]["ibm_license"] = "accept"
            else:
                base_dict["spec"]["license"]["accept"] = True
            if self._deployment_properties["FNCM_Version"] == "5.5.8":
                optional_components_list = ["css", "tm", "cmis"]
                optional_components_present = []
                for component in optional_components_list:
                    if self._deployment_properties[component.upper()]:
                        optional_components_present.append(component)
                base_dict["spec"]["shared_configuration"]["sc_optional_components"] = ",".join(
                    optional_components_present)
            else:
                for optional_component in base_dict["spec"]["content_optional_components"].keys():
                    for prop_key in self._deployment_properties.keys():
                        if optional_component.lower() == prop_key.lower():
                            base_dict["spec"]["content_optional_components"][optional_component] = \
                                self._deployment_properties[prop_key]
            base_dict["spec"]["shared_configuration"]["sc_deployment_platform"] = \
                self._deployment_properties["PLATFORM"]

            # removing sc_deployment_patterns:content if one of cpe, graphql,ban is not selected (5.5.11 and above only)
            if self._deployment_properties["FNCM_Version"] != "5.5.8":
                component_check_list = ["cpe", "graphql", "ban"]
                for component in component_check_list:
                    if not base_dict["spec"]["content_optional_components"][component]:
                        base_dict["spec"]["shared_configuration"].ca.items['root_ca_secret'][2] = None
                        base_dict["spec"]["shared_configuration"].pop("sc_deployment_patterns")
                        base_dict["spec"]["shared_configuration"].yaml_set_comment_before_after_key(
                            "sc_deployment_type",
                            before="\n# The deployment type as selected.",
                            indent=4)
                        break
            # update trusted certificates parameter if we have secrets generated
            if os.path.exists(os.path.join(self._generate_folder, "ssl", "trusted-certs")):
                trusted_cert_secrets = collect_visible_files(
                    os.path.join(self._generate_folder, "ssl", "trusted-certs"))
                for secret in trusted_cert_secrets:
                    secret_name = secret.split(".")[0]
                    base_dict["spec"]["shared_configuration"]["trusted_certificate_list"].append(
                        secret_name)

            # when roks is enabled we need to have an ingress parameter set to false
            if self._deployment_properties["PLATFORM"].lower() == "roks":
                base_dict["spec"]["shared_configuration"]["sc_ingress_enable"] = False
            base_dict["spec"]["shared_configuration"]["sc_fncm_license_model"] = \
                self._deployment_properties["LICENSE"]
            base_dict["spec"]["shared_configuration"]["storage_configuration"][
                "sc_slow_file_storage_classname"] = self._deployment_properties["SLOW_FILE_STORAGE_CLASSNAME"]
            base_dict["spec"]["shared_configuration"]["storage_configuration"][
                "sc_medium_file_storage_classname"] = self._deployment_properties["MEDIUM_FILE_STORAGE_CLASSNAME"]
            base_dict["spec"]["shared_configuration"]["storage_configuration"][
                "sc_fast_file_storage_classname"] = self._deployment_properties["FAST_FILE_STORAGE_CLASSNAME"]
            if "CONTENT_INITIALIZATION_ENABLE" in self._usergroup_properties and self._usergroup_properties[
                "CONTENT_INITIALIZATION_ENABLE"]:
                base_dict["spec"]["shared_configuration"]["sc_content_initialization"] = \
                    self._usergroup_properties["CONTENT_INITIALIZATION_ENABLE"]
            if "CONTENT_VERIFICATION_ENABLE" in self._usergroup_properties and self._usergroup_properties[
                "CONTENT_VERIFICATION_ENABLE"]:
                base_dict["spec"]["shared_configuration"]["sc_content_verification"] = \
                    self._usergroup_properties["CONTENT_VERIFICATION_ENABLE"]

            # populating fips enable parameter if required
            if self._deployment_properties["FNCM_Version"] not in ["5.5.8", "5.5.11"]:
                base_dict["spec"]["shared_configuration"]["enable_fips"] = self._deployment_properties[
                    "FIPS_SUPPORT"]
                base_dict["spec"]["shared_configuration"]["sc_egress_configuration"][
                    "sc_restricted_internet_access"] = \
                    self._deployment_properties[
                        "RESTRICTED_INTERNET_ACCESS"]

            self._merged_data.update(base_dict)


        except Exception as e:
            self._logger.exception(
                f"Error found in generate_base_section function in generate_cr script --- {str(e)}")

    # function to generate the ingress section
    def populate_ingress_section(self):
        # populate ingress section
        # if ingress properties are created then we populate them
        if self._ingress_properties:
            ingress_dict = self.load_cr_template(self._ingress_template)
            ingress_dict["spec"]["shared_configuration"]["sc_service_type"] = self._ingress_properties[
                "SERVICE_TYPE"]
            ingress_dict["spec"]["shared_configuration"]["sc_ingress_enable"] = \
                self._ingress_properties["INGRESS_ENABLED"]
            if self._ingress_properties["INGRESS_TLS_ENABLED"]:
                if 'INGRESS_TLS_SECRET_NAME' in self._ingress_properties and self._ingress_properties[
                    "INGRESS_TLS_SECRET_NAME"].lower() != "<optional>":
                    ingress_dict["spec"]["shared_configuration"]["sc_ingress_tls_secret_name"] = \
                        self._ingress_properties["INGRESS_TLS_SECRET_NAME"]
                else:
                    ingress_dict["spec"]["shared_configuration"].pop("sc_ingress_tls_secret_name")
            else:
                ingress_dict["spec"]["shared_configuration"].pop("sc_ingress_tls_secret_name")
            ingress_dict["spec"]["shared_configuration"]["sc_ingress_annotations"] = []
            if self._ingress_properties["INGRESS_ANNOTATIONS"]:
                for item in self._ingress_properties["INGRESS_ANNOTATIONS"]:
                    item_key = item.split(":", 1)[0]
                    item_value = item.split(":", 1)[1]
                    # Remove leading/trailing whitespace and single quotes from the key and value
                    item_key = item_key.strip()
                    item_value = item_value.strip().strip('"').strip("\\'")
                    item_dict = {item_key: item_value}
                    ingress_dict["spec"]["shared_configuration"]["sc_ingress_annotations"].append(
                        item_dict)
            ingress_dict["spec"]["shared_configuration"]["sc_deployment_hostname_suffix"] = \
                remove_protocol(self._ingress_properties["INGRESS_HOSTNAME"])

            self._merged_data["spec"]["shared_configuration"].update(ingress_dict["spec"]["shared_configuration"])

        else:
            ingress_params = ["sc_service_type", "sc_ingress_enable", "sc_ingress_tls_secret_name",
                              "sc_deployment_hostname_suffix", "sc_ingress_annotations"]
            for param in ingress_params:
                if param in self._merged_data["spec"]["shared_configuration"].keys():
                    self._merged_data["spec"]["shared_configuration"].pop(param)

    # function to generate the additional ldap section (multi ldap case)
    def populate_multi_ldap_section(self):
        try:
            self._logger.info("generating multi ldap section")
            # counting the number of ldaps in the property file
            if len(self._ldap_properties["_ldap_ids"]) > 1:
                for key in self._ldap_properties["_ldap_ids"]:
                    if key != "LDAP":
                        mutli_ldap_dict = self.load_cr_template(self._multi_ldap_template)
                        mutli_ldap_dict["spec"][
                            'ldap_configuration_' + self._ldap_properties[key]["LDAP_ID"]] = mutli_ldap_dict[
                            "spec"].pop("ldap_configuration_<id_name>")
                        cr_key = 'ldap_configuration_' + self._ldap_properties[key]["LDAP_ID"]
                        self.populate_ldap_section(mutli_ldap_dict, cr_key, key)

        except Exception as e:
            self._logger.exception(
                f"Error found in generate_multi_ldap_section function in generate_cr script --- {str(e)}")

    # function to generate the init section
    def populate_init_section(self):
        try:
            self._logger.info("generating init section")
            init_dict = self.load_cr_template(self._init_template)
            init_dict["spec"]["initialize_configuration"]["ic_ldap_creation"][
                "ic_ldap_admin_user_name"] = self._usergroup_properties["GCD_ADMIN_USER_NAME"]
            init_dict["spec"]["initialize_configuration"]["ic_ldap_creation"][
                "ic_ldap_admins_groups_name"] = self._usergroup_properties["GCD_ADMIN_GROUPS_NAME"]
            init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"]["object_stores"][0][
                "oc_cpe_obj_store_admin_user_groups"] = []
            for admin_user_group in self._usergroup_properties["OS"]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"]:
                init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"]["object_stores"][
                    0]["oc_cpe_obj_store_admin_user_groups"].append(admin_user_group)
            if self._usergroup_properties["FNCM_LOGIN_USER"] not in \
                    init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"][
                        "object_stores"][0]["oc_cpe_obj_store_admin_user_groups"]:
                init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"]["object_stores"][
                    0]["oc_cpe_obj_store_admin_user_groups"].append(self._usergroup_properties["FNCM_LOGIN_USER"])

            # Populating the PE WorkFlow Section if required
            if "OS" in self._usergroup_properties.keys():
                if "CPE_OBJ_STORE_OS_PE_WORKFLOW_ENABLE" in self._usergroup_properties["OS"]:
                    if self._usergroup_properties["OS"]["CPE_OBJ_STORE_OS_PE_WORKFLOW_ENABLE"]:
                        pe_workflow_dict = {}
                        pe_workflow_dict["oc_cpe_obj_store_enable_workflow"] = True
                        pe_workflow_dict["oc_cpe_obj_store_workflow_region_name"] = "os_region"
                        pe_workflow_dict["oc_cpe_obj_store_workflow_region_number"] = 1
                        pe_workflow_dict["oc_cpe_obj_store_workflow_data_tbl_space"] = self._db_properties["OS"][
                            "DATA_TABLESPACE"]
                        pe_workflow_dict["oc_cpe_obj_store_workflow_admin_group"] = \
                        self._usergroup_properties["OS"]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"][0]
                        pe_workflow_dict["oc_cpe_obj_store_workflow_config_group"] = \
                        self._usergroup_properties["OS"]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"][0]
                        pe_workflow_dict["oc_cpe_obj_store_workflow_date_time_mask"] = "mm/dd/yy hh:tt am"
                        pe_workflow_dict["oc_cpe_obj_store_workflow_locale"] = "en"
                        pe_workflow_dict["oc_cpe_obj_store_workflow_pe_conn_point_name"] = "os_pe_conn_point"

                        init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"]["object_stores"][0].update(
                            pe_workflow_dict)

            os_list = list(self._db_properties["_os_ids"])
            for os_number in range(1, len(os_list)):
                obj_store = {}
                obj_store["oc_cpe_obj_store_display_name"] = "OS" + str(os_number + 1).zfill(2)
                obj_store["oc_cpe_obj_store_symb_name"] = "OS" + str(os_number + 1).zfill(2)
                obj_store["oc_cpe_obj_store_conn"] = {}
                obj_store["oc_cpe_obj_store_conn"]["name"] = "OS" + str(os_number + 1).zfill(2) + "_dbconnection"
                obj_store["oc_cpe_obj_store_conn"]["dc_os_datasource_name"] = "FNOS" + str(os_number + 1) + "DS"
                obj_store["oc_cpe_obj_store_conn"]["dc_os_xa_datasource_name"] = "FNOS" + str(os_number + 1) + "DSXA"
                obj_store["oc_cpe_obj_store_admin_user_groups"] = []
                # incase there is a mismatch in os labels from the user group prop file and the db prop file
                if os_list[os_number] in list(self._usergroup_properties.keys()):
                    for admin_user_group in self._usergroup_properties[os_list[os_number]][
                        "CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"]:
                        obj_store["oc_cpe_obj_store_admin_user_groups"].append(admin_user_group)
                    if self._usergroup_properties["FNCM_LOGIN_USER"] not in obj_store[
                        "oc_cpe_obj_store_admin_user_groups"]:
                        obj_store["oc_cpe_obj_store_admin_user_groups"].append(
                            self._usergroup_properties["FNCM_LOGIN_USER"])

                    if os_list[os_number] in self._usergroup_properties.keys():
                        if "OS" in self._usergroup_properties.keys():
                            if "CPE_OBJ_STORE_OS_PE_WORKFLOW_ENABLE" in self._usergroup_properties[os_list[os_number]]:
                                if self._usergroup_properties[os_list[os_number]]["CPE_OBJ_STORE_OS_PE_WORKFLOW_ENABLE"]:
                                    pe_workflow_dict = {}
                                    pe_workflow_dict["oc_cpe_obj_store_enable_workflow"] = True
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_region_name"] = f"{os_list[os_number].lower()}_region"
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_region_number"] = 1
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_data_tbl_space"] = \
                                        self._db_properties[os_list[os_number]]["DATA_TABLESPACE"]
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_admin_group"] = \
                                        self._usergroup_properties[os_list[os_number]]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"][0]
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_config_group"] = \
                                        self._usergroup_properties[os_list[os_number]]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"][0]
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_date_time_mask"] = "mm/dd/yy hh:tt am"
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_locale"] = "en"
                                    pe_workflow_dict["oc_cpe_obj_store_workflow_pe_conn_point_name"] = f"{os_list[os_number].lower()}_pe_conn_point"

                                    obj_store.update(pe_workflow_dict)

                init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"][
                    "object_stores"].append(obj_store)

            self._merged_data["spec"].update(init_dict["spec"])
        except Exception as e:
            self._logger.exception(f"Error found in generate_init_section function in generate_cr script --- {str(e)}")

    # function to generate the verify section
    def populate_verify_section(self):
        self._logger.info("generating verify section")
        try:
            verify_dict = self.load_cr_template(self._verify_template)
            self._merged_data["spec"].update(verify_dict["spec"])
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_verify_section function in generate_cr script --- {str(e)}")

    # function to generate custom component css properties if required
    def populate_css_section(self, feature_list):
        self._logger.info("generating custom property section for css")
        try:
            self._merged_data['spec']["ecm_configuration"]["css"] = CommentedMap()
            self._merged_data['spec']["ecm_configuration"].yaml_set_comment_before_after_key("css",
                                                                                             before='####################################\n## Start of configuration for CSS ##\n####################################',
                                                                                             indent=4)

            if "ICC" in feature_list:
                self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"] = CommentedMap()
                self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"] = CommentedMap()
                self._merged_data["spec"]["ecm_configuration"]["css"][
                    "css_production_setting"].yaml_set_comment_before_after_key("icc",
                                                                                before='## Use the icc section below to enable IBM Content Collector P8 Content Search Services Support.  Refer to IBM Documentation for details.',
                                                                                indent=8)

                self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                    "icc_enabled"] = True
                self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                    "icc_secret_name"] = "ibm-icc-secret"
                self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                    "p8domain_name"] = self._customcomponent_properties["ICC"]["P8_DOMAIN_NAME"]
                self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                    "secret_masterkey_name"] = "icc-masterkey-txt"

        except Exception as e:
            self._logger.exception(
                f"Error found in generate_css_section function in generate_cr script --- {str(e)}")

    # function to generate custom component navigator properties if required
    def populate_navigator_section(self, feature_list):
        self._logger.info("generating custom property section for navigator")
        try:
            self._merged_data["spec"]["navigator_configuration"] = CommentedMap()
            self._merged_data['spec'].yaml_set_comment_before_after_key("navigator_configuration",
                                                                        before='########################################################################\n########   IBM Business Automation Navigator configuration      ########\n########################################################################',
                                                                        indent=2)
            if "SENDMAIL" in feature_list:
                self._merged_data["spec"]["navigator_configuration"]["java_mail"] = CommentedMap()
                self._merged_data["spec"]["navigator_configuration"].yaml_set_comment_before_after_key("java_mail",
                                                                                                       before="send mail",
                                                                                                       indent=4)
                self._merged_data["spec"]["navigator_configuration"]["java_mail"]["host"] = \
                    remove_protocol(self._customcomponent_properties["SENDMAIL"]["JAVA_MAIL_HOST"])
                self._merged_data["spec"]["navigator_configuration"]["java_mail"]["port"] = \
                    self._customcomponent_properties["SENDMAIL"]["JAVA_MAIL_PORT"]
                self._merged_data["spec"]["navigator_configuration"]["java_mail"]["sender"] = \
                    self._customcomponent_properties["SENDMAIL"]["JAVAMAIL_SENDER"]
                self._merged_data["spec"]["navigator_configuration"]["java_mail"]["ssl_enabled"] = bool(
                    self._customcomponent_properties["SENDMAIL"]["JAVAMAIL_SSL"])

            if "DATASOURCE" in feature_list:
                if "icn_production_setting" not in self._merged_data["spec"]["navigator_configuration"].keys():
                    self._merged_data["spec"]["navigator_configuration"]["icn_production_setting"] = CommentedMap()

                self._merged_data["spec"]["navigator_configuration"]["icn_production_setting"]["icn_jndids_name"] = \
                    self._db_properties["ICN"]["DATASOURCE_NAME"]
                self._merged_data["spec"]["navigator_configuration"][
                    "icn_production_setting"].yaml_set_comment_before_after_key(
                    "icn_jndids_name",
                    before="Datasource name",
                    indent=6)

            if "SCHEMA" in feature_list:
                if "icn_production_setting" not in self._merged_data["spec"]["navigator_configuration"].keys():
                    self._merged_data["spec"]["navigator_configuration"]["icn_production_setting"] = CommentedMap()

                self._merged_data["spec"]["navigator_configuration"]["icn_production_setting"]["icn_schema"] = \
                    self._db_properties["ICN"]["SCHEMA_NAME"]
                self._merged_data["spec"]["navigator_configuration"][
                    "icn_production_setting"].yaml_set_comment_before_after_key("icn_schema",
                                                                                before="Database schema",
                                                                                indent=6)
            if "TABLESPACE" in feature_list:
                if "icn_production_setting" not in self._merged_data["spec"]["navigator_configuration"].keys():
                    self._merged_data["spec"]["navigator_configuration"]["icn_production_setting"] = CommentedMap()

                self._merged_data["spec"]["navigator_configuration"]["icn_production_setting"]["icn_table_space"] = \
                    self._db_properties["ICN"]["TABLESPACE_NAME"]
                self._merged_data["spec"]["navigator_configuration"][
                    "icn_production_setting"].yaml_set_comment_before_after_key(
                    "icn_table_space",
                    before="Database tablespace",
                    indent=6)

            if "EXTERNAL_SHARE" in feature_list:
                self._merged_data["spec"]["navigator_configuration"]["enable_ldap"] = True
                self._merged_data["spec"]["navigator_configuration"].yaml_set_comment_before_after_key(
                    "enable_ldap",
                    before="Enabling this will give the user the option to sign-in using the LDAP.",
                    indent=4)

        except Exception as e:
            self._logger.exception(
                f"Error found in generate_navigator_section function in generate_cr script --- {str(e)}")

    # function to generate custom component task manager properties if required
    def populate_tm_section(self, feature_list):
        self._logger.info("generating custom property section for task manager")
        try:
            self._merged_data["spec"]["ecm_configuration"]["tm"] = CommentedMap()
            self._merged_data['spec']["ecm_configuration"].yaml_set_comment_before_after_key("tm",
                                                                                             before='####################################\n## Start of configuration for Task Manager ##\n####################################',
                                                                                             indent=4)

            if "PERMISSIONS" in feature_list:
                self._merged_data["spec"]["ecm_configuration"]["tm"]["tm_production_setting"] = CommentedMap()
                self._merged_data["spec"]["ecm_configuration"]["tm"]["tm_production_setting"][
                    "security_roles_to_group_mapping"] = CommentedMap()
                self._merged_data['spec']["ecm_configuration"]["tm"][
                    "tm_production_setting"].yaml_set_comment_before_after_key("security_roles_to_group_mapping",
                                                                               before='## All users/groups belong to one of three roles (Admin, User, or Auditor) that are specific to Task Manager.\n## Each role takes a list of users/groups (e.g., groups: [taskAdmins, taskAdmins2]).  Refer to IBM Documentation for details.',
                                                                               indent=8)
                security_roles_settings = {}
                security_roles_settings["task_admins"] = {}
                security_roles_settings["task_admins"]["groups"] = self._customcomponent_properties["PERMISSIONS"][
                    "TASK_ADMIN_GROUP_NAMES"]
                security_roles_settings["task_admins"]["users"] = self._customcomponent_properties["PERMISSIONS"][
                    "TASK_ADMIN_USER_NAMES"]
                security_roles_settings["task_users"] = {}
                security_roles_settings["task_users"]["groups"] = self._customcomponent_properties["PERMISSIONS"][
                    "TASK_USER_GROUP_NAMES"]
                security_roles_settings["task_users"]["users"] = self._customcomponent_properties["PERMISSIONS"][
                    "TASK_USER_USER_NAMES"]
                security_roles_settings["task_auditors"] = {}
                security_roles_settings["task_auditors"]["groups"] = self._customcomponent_properties["PERMISSIONS"][
                    "TASK_AUDITOR_GROUP_NAMES"]
                security_roles_settings["task_auditors"]["users"] = self._customcomponent_properties["PERMISSIONS"][
                    "TASK_AUDITOR_USER_NAMES"]
                self._merged_data["spec"]["ecm_configuration"]["tm"]["tm_production_setting"][
                    "security_roles_to_group_mapping"] = security_roles_settings

        except Exception as e:
            self._logger.exception(
                f"Error found in generate_tm_section function in generate_cr script --- {str(e)}")

    # function to generate custom component properties if required
    def populate_custom_property_section(self, feature_dict):
        self._logger.info("generating custom component section")

        try:
            if len(feature_dict["BAN"]) != 0:
                self.populate_navigator_section(feature_dict["BAN"])

            if len(feature_dict["TM"]) != 0 or len(feature_dict["CSS"]) != 0:
                self._merged_data["spec"]["ecm_configuration"] = CommentedMap()
                self._merged_data['spec'].yaml_set_comment_before_after_key("ecm_configuration",
                                                                            before='########################################################################\n########   IBM FileNet Content Manager configuration      ########\n########################################################################',
                                                                            indent=2)

            if len(feature_dict["CSS"]) != 0:
                self.populate_css_section(feature_dict["CSS"])

            if len(feature_dict["TM"]) != 0:
                self.populate_tm_section(feature_dict["TM"])

        except Exception as e:
            self._logger.exception(
                f"Error found in generate_custom_property_section function in generate_cr script --- {str(e)}")

    def generate_custom_feature_dict(self):
        self._logger.info("generating custom feature list")
        try:
            feature_dict = {}
            ban_features = []
            css_features = []
            tm_features = []

            # separate the features into the different components
            # add to the list of features for each component
            if "ICC" in self._customcomponent_properties.keys():
                css_features.append("ICC")

            if "SENDMAIL" in self._customcomponent_properties.keys():
                ban_features.append("SENDMAIL")

            if "ICN" in self._db_properties.keys() or self._deployment_properties["FNCM_Version"] == "5.5.8":

                if "TABLESPACE_NAME" in self._db_properties["ICN"].keys():
                    if self._db_properties["ICN"]["TABLESPACE_NAME"] != "ICNDB":
                        ban_features.append("TABLESPACE")

                if "SCHEMA_NAME" in self._db_properties["ICN"].keys():
                    if self._db_properties["ICN"]["SCHEMA_NAME"] != "ICNDB":
                        ban_features.append("SCHEMA")

                if "DATASOURCE_NAME" in self._db_properties["ICN"].keys():
                    if self._db_properties["ICN"]["DATASOURCE_NAME"] != "ECMClientDS":
                        ban_features.append("DATASOURCE")

            if "ES" in self._deployment_properties.keys():
                if self._deployment_properties["ES"] and self._idp_properties and self._ldap_properties:
                    ban_features.append("EXTERNAL_SHARE")

            if "PERMISSIONS" in self._customcomponent_properties.keys():
                tm_features.append("PERMISSIONS")

            # add all lists to the feature dictionary
            feature_dict["BAN"] = ban_features
            feature_dict["CSS"] = css_features
            feature_dict["TM"] = tm_features

            return feature_dict
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_custom_feature_dict function in generate_cr script --- {str(e)}")
