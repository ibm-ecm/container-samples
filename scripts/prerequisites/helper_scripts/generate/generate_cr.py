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

import ruamel.yaml
import yaml
from ruamel.yaml.comments import CommentedMap


# Class to generate the CR
class GenerateCR:

    # read to yaml function
    def load_cr_template(self, filepath):
        # load the YAML file with comments
        # read the source YAML file with comments
        with open(filepath, 'r') as file:
            data = ruamel.yaml.YAML().load(file)
        return data

    # write to yaml function
    def write_cr_template(self):
        # write the updated YAML file with preserved comments
        with open(self._generated_cr, 'w') as file:
            ruamel.yaml.YAML().dump(self._merged_data, file)

    def __init__(self, db_properties, ldap_properties=None, usergroup_properties=None, deployment_properties=None,
                 ingress_properties=None, customcomponent_properties=None, logger=None):
        self._logger = logger

        self._db_properties = db_properties
        self._ldap_properties = ldap_properties
        self._usergroup_properties = usergroup_properties
        self._deployment_properties = deployment_properties
        self._ingress_properties = ingress_properties
        self._customcomponent_properties = customcomponent_properties
        self._generate_folder = os.path.join(os.getcwd(), "generatedFiles")
        # Navigate up two levels to the parent directory
        self._base_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "base.yaml")
        self._ingress_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                              self._deployment_properties["FNCM_Version"], "ingress.yaml")
        self._init_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "init.yaml")
        self._ldap_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                           self._deployment_properties["FNCM_Version"], "ldap.yaml")
        self._verify_template = os.path.join(os.getcwd(), "helper_scripts", "generate", "cr_templates",
                                             self._deployment_properties["FNCM_Version"], "verify.yaml")
        self._generated_cr = os.path.join(self._generate_folder, "ibm_fncm_cr_production.yaml")
        if os.path.exists(self._generated_cr):
            os.remove(self._generated_cr)
        data = {}
        with open(self._generated_cr, 'w') as file:
            yaml.dump(data, file)
        self._generated_cr_dict = self.load_cr_template(self._generated_cr)

    # function to populate the ldap sections
    def populate_ldap_section(self, ldap_dict, cr_key, key=None):
        self._logger.info("generating base ldap section")
        try:
            if cr_key == "ldap_configuration":
                key = "LDAP"
            # populating the base ldap section and also removing keys not required
            ldap_dict["spec"][cr_key]["lc_selected_ldap_type"] = self._ldap_properties[key]["LDAP_TYPE"]
            ldap_dict["spec"][cr_key]["lc_ldap_group_member_id_map"] = self._ldap_properties[key][
                "LDAP_GROUP_MEMBERSHIP_ID_MAP"]

            # check if ssl is enabled otherwise remove those keys and values

            if self._ldap_properties[key]["LDAP_SSL_ENABLED"]:
                ldap_dict["spec"][cr_key]["lc_ldap_ssl_secret_name"] = "ibm-" + key.lower() + "-ssl-secret"
            else:
                ldap_dict["spec"][cr_key].pop('lc_ldap_ssl_secret_name')
                ldap_dict["spec"][cr_key]['lc_ldap_ssl_enabled'] = False

            ldap_dict["spec"][cr_key]["lc_selected_ldap_type"] = self._ldap_properties[key]["LDAP_TYPE"]
            for ldap_property in self._ldap_properties["LDAP"]:
                if "lc_" + ldap_property.lower() in list(
                        ldap_dict["spec"][cr_key].keys()):
                    ldap_dict["spec"][cr_key]["lc_" + ldap_property.lower()] = self._ldap_properties[key][ldap_property]

            if self._ldap_properties[key]["LDAP_TYPE"] == "IBM Security Directory Server":
                for optional_key in list(ldap_dict["spec"][cr_key].keys()):
                    if not optional_key.startswith("lc_") and not optional_key.startswith("tds"):
                        ldap_dict["spec"][cr_key].pop(optional_key)
            if self._ldap_properties[key]["LDAP_TYPE"] == "Microsoft Active Directory":
                for optional_key in list(ldap_dict["spec"][cr_key].keys()):
                    if not optional_key.startswith("lc_") and not optional_key.startswith("ad"):
                        ldap_dict["spec"][cr_key].pop(optional_key)
                # making sure if the value is optional for gc port and host we dont populate that value and we remove it
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

            return ldap_dict
        except Exception as e:
            self._logger.exception(f"Error found in populate_ldap_section function in generate_cr script --- {str(e)}")

    # function to populate the db section
    def populate_db_section(self, db_dict):
        self._logger.info("generating Database Section")
        try:
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
                                self._db_properties[db_key]['HADR_STANDBY_SERVERNAME']
                            db_dict["spec"]["datasource_configuration"][cr_key]["dc_hadr_standby_port"] = \
                                self._db_properties[db_key]['HADR_STANDBY_PORT']
                        if self._db_properties["DATABASE_TYPE"].lower() != "oracle":
                            if "oracle" in datasource_key:
                                db_dict["spec"]["datasource_configuration"][cr_key].pop(datasource_key)
                        else:
                            db_dict["spec"]["datasource_configuration"][cr_key][
                                "dc_oracle_" + db_key.lower() + "_jdbc_url"] = self._db_properties[db_key][
                                'ORACLE_JDBC_URL']
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
                            # if its the first section that we know it will be the base OS so we can use ibm-osdb-ssl-secret
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
                                    "dc_hadr_standby_servername"] = self._db_properties[prop_key][
                                    'HADR_STANDBY_SERVERNAME']
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                    "dc_hadr_standby_port"] = self._db_properties[prop_key]['HADR_STANDBY_PORT']
                            if self._db_properties["DATABASE_TYPE"].lower() != "oracle":
                                if "oracle" in datasource_key:
                                    db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number].pop(
                                        datasource_key)
                            else:
                                db_dict["spec"]["datasource_configuration"]["dc_os_datasources"][os_number][
                                    "dc_oracle_os_jdbc_url"] = self._db_properties[prop_key]['ORACLE_JDBC_URL']

            # based on the component deployed, certain sections of the CR can be removed.
            if self._deployment_properties["FNCM_Version"] != "5.5.8":
                if not self._deployment_properties["CPE"]:
                    db_dict["spec"]["datasource_configuration"].pop("dc_os_datasources")
                    db_dict["spec"]["datasource_configuration"].pop("dc_gcd_datasource")
                if not self._deployment_properties["BAN"]:
                    db_dict["spec"]["datasource_configuration"].pop("dc_icn_datasource")
            return db_dict

        except Exception as e:
            self._logger.exception(f"Error found in populate_db_section function in generate_cr script --- {str(e)}")

    # function to generate the Database , shared and ldap section
    def generate_base_section(self):
        self._logger.info("generating shared section")
        try:
            self._generated_base_dict = self.load_cr_template(self._base_template)
            if self._deployment_properties["FNCM_Version"] == "5.5.8":
                self._generated_base_dict["spec"]["ibm_license"] = "accept"
            else:
                self._generated_base_dict["spec"]["license"]["accept"] = True
            if self._deployment_properties["FNCM_Version"] == "5.5.8":
                optional_components_list = ["css", "tm", "cmis"]
                optional_components_present = []
                for component in optional_components_list:
                    if self._deployment_properties[component.upper()]:
                        optional_components_present.append(component)
                self._generated_base_dict["spec"]["shared_configuration"]["sc_optional_components"] = ",".join(
                    optional_components_present)
            else:
                for optional_component in self._generated_base_dict["spec"]["content_optional_components"].keys():
                    for prop_key in self._deployment_properties.keys():
                        if optional_component.lower() == prop_key.lower():
                            self._generated_base_dict["spec"]["content_optional_components"][optional_component] = \
                                self._deployment_properties[prop_key]
            self._generated_base_dict["spec"]["shared_configuration"]["sc_deployment_platform"] = \
                self._deployment_properties["PLATFORM"]
            # when roks is enabled we need to have a ingress parameter set to false
            if self._deployment_properties["PLATFORM"].lower() == "roks":
                self._generated_base_dict["spec"]["shared_configuration"]["sc_ingress_enable"] = False
            self._generated_base_dict["spec"]["shared_configuration"]["sc_fncm_license_model"] = \
                self._deployment_properties["LICENSE"]
            self._generated_base_dict["spec"]["shared_configuration"]["storage_configuration"][
                "sc_slow_file_storage_classname"] = self._deployment_properties["SLOW_FILE_STORAGE_CLASSNAME"]
            self._generated_base_dict["spec"]["shared_configuration"]["storage_configuration"][
                "sc_medium_file_storage_classname"] = self._deployment_properties["MEDIUM_FILE_STORAGE_CLASSNAME"]
            self._generated_base_dict["spec"]["shared_configuration"]["storage_configuration"][
                "sc_fast_file_storage_classname"] = self._deployment_properties["FAST_FILE_STORAGE_CLASSNAME"]
            if "CONTENT_INITIALIZATION_ENABLE" in self._usergroup_properties and self._usergroup_properties[
                "CONTENT_INITIALIZATION_ENABLE"]:
                self._generated_base_dict["spec"]["shared_configuration"]["sc_content_initialization"] = \
                    self._usergroup_properties["CONTENT_INITIALIZATION_ENABLE"]
            if "CONTENT_VERIFICATION_ENABLE" in self._usergroup_properties and self._usergroup_properties[
                "CONTENT_VERIFICATION_ENABLE"]:
                self._generated_base_dict["spec"]["shared_configuration"]["sc_content_verification"] = \
                    self._usergroup_properties["CONTENT_VERIFICATION_ENABLE"]

            # populate ingress section
            # if ingress properties are created then we populate them
            if self._ingress_properties:
                self._generated_base_dict["spec"]["shared_configuration"]["sc_service_type"] = self._ingress_properties[
                    "SERVICE_TYPE"]
                self._generated_base_dict["spec"]["shared_configuration"]["sc_ingress_enable"] = \
                self._ingress_properties["INGRESS_ENABLED"]
                if self._ingress_properties["INGRESS_TLS_ENABLED"]:
                    if 'INGRESS_TLS_SECRET_NAME' in self._ingress_properties and self._ingress_properties[
                        "INGRESS_TLS_SECRET_NAME"].lower() != "<optional>":
                        self._generated_base_dict["spec"]["shared_configuration"]["sc_ingress_tls_secret_name"] = \
                        self._ingress_properties["INGRESS_TLS_SECRET_NAME"]
                    else:
                        self._generated_base_dict["spec"]["shared_configuration"].pop("sc_ingress_tls_secret_name")
                else:
                    self._generated_base_dict["spec"]["shared_configuration"].pop("sc_ingress_tls_secret_name")
                self._generated_base_dict["spec"]["shared_configuration"]["sc_ingress_annotations"] = []
                if self._ingress_properties["INGRESS_ANNOTATIONS"]:
                    for item in self._ingress_properties["INGRESS_ANNOTATIONS"]:
                        item_key = item.split(":", 1)[0]
                        item_value = item.split(":", 1)[1]
                        # Remove leading/trailing whitespace and single quotes from the key and value
                        item_key = item_key.strip()
                        item_value = item_value.strip().strip('"').strip("\\'")
                        item_dict = {item_key: item_value}
                        self._generated_base_dict["spec"]["shared_configuration"]["sc_ingress_annotations"].append(
                            item_dict)
                self._generated_base_dict["spec"]["shared_configuration"]["sc_deployment_hostname_suffix"] = \
                    self._ingress_properties["INGRESS_HOSTNAME"]
            else:
                ingress_params = ["sc_service_type", "sc_ingress_enable", "sc_ingress_tls_secret_name",
                                  "sc_deployment_hostname_suffix", "sc_ingress_annotations"]
                for param in ingress_params:
                    if param in self._generated_base_dict["spec"]["shared_configuration"].keys():
                        self._generated_base_dict["spec"]["shared_configuration"].pop(param)

            # populating the base ldap section and also removing keys not required
            self._generated_base_dict = self.populate_ldap_section(self._generated_base_dict, "ldap_configuration")

            # populating the db section
            self._generated_base_dict = self.populate_db_section(self._generated_base_dict)

            # merge the shared section into the main yaml
            self._merged_data = ruamel.yaml.comments.CommentedMap()
            self._merged_data.update(self._generated_base_dict)
            self._merged_data.update(self._generated_cr_dict)
            self.write_cr_template()

        except Exception as e:
            self._logger.exception(f"Error found in generate_base_section function in generate_cr script --- {str(e)}")

    # function to generate the additional ldap section (multi ldap case)
    def generate_ldap_section(self):
        try:
            self._logger.info("generating multi ldap section")
            self._generated_cr_dict = self.load_cr_template(self._generated_cr)
            # counting the number of ldaps in the property file
            if len(self._ldap_properties["_ldap_ids"]) > 1:
                for key in self._ldap_properties["_ldap_ids"]:
                    if key != "LDAP":
                        self._generated_ldap_dict = self.load_cr_template(self._ldap_template)
                        self._generated_ldap_dict["spec"][
                            'ldap_configuration_' + self._ldap_properties[key]["LDAP_ID"]] = self._generated_ldap_dict[
                            "spec"].pop("ldap_configuration_<id_name>")
                        cr_key = 'ldap_configuration_' + self._ldap_properties[key]["LDAP_ID"]
                        self._generated_ldap_dict = self.populate_ldap_section(self._generated_ldap_dict, cr_key, key)
                        # appending/merging the new section to the exsisting template
                        self._generated_cr_dict["spec"].update(self._generated_ldap_dict["spec"])
                        self._merged_data.update(self._generated_cr_dict)
            self.write_cr_template()
        except Exception as e:
            self._logger.exception(f"Error found in generate_ldap_section function in generate_cr script --- {str(e)}")

    # function to generate the init section
    def generate_init_section(self):
        try:
            self._logger.info("generating init section")
            self._generated_cr_dict = self.load_cr_template(self._generated_cr)
            self._generated_init_dict = self.load_cr_template(self._init_template)
            self._generated_init_dict["spec"]["initialize_configuration"]["ic_ldap_creation"][
                "ic_ldap_admin_user_name"] = self._usergroup_properties["GCD_ADMIN_USER_NAME"]
            self._generated_init_dict["spec"]["initialize_configuration"]["ic_ldap_creation"][
                "ic_ldap_admins_groups_name"] = self._usergroup_properties["GCD_ADMIN_GROUPS_NAME"]
            self._generated_init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"]["object_stores"][0][
                "oc_cpe_obj_store_admin_user_groups"] = []
            for admin_user_group in self._usergroup_properties["OS"]["CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"]:
                self._generated_init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"]["object_stores"][
                    0]["oc_cpe_obj_store_admin_user_groups"].append(admin_user_group)
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
                # incase there is a mis match in os labels from the user group prop file and the db prop file
                if os_list[os_number] in list(self._usergroup_properties.keys()):
                    for admin_user_group in self._usergroup_properties[os_list[os_number]][
                        "CPE_OBJ_STORE_OS_ADMIN_USER_GROUPS"]:
                        obj_store["oc_cpe_obj_store_admin_user_groups"].append(admin_user_group)

                self._generated_init_dict["spec"]["initialize_configuration"]["ic_obj_store_creation"][
                    "object_stores"].append(obj_store)
            self._generated_cr_dict["spec"].update(self._generated_init_dict["spec"])
            self._merged_data.update(self._generated_cr_dict)
            self.write_cr_template()
        except Exception as e:
            self._logger.exception(f"Error found in generate_init_section function in generate_cr script --- {str(e)}")

    # function to generate the verify section
    def generate_verify_section(self):
        self._logger.info("generating verify section")
        try:
            self._generated_cr_dict = self.load_cr_template(self._generated_cr)
            self._generated_verify_dict = self.load_cr_template(self._verify_template)
            self._generated_cr_dict["spec"].update(self._generated_verify_dict["spec"])
            self._merged_data.update(self._generated_cr_dict)
            self.write_cr_template()
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_verify_section function in generate_cr script --- {str(e)}")

    # function to generate custom component css properties if required
    def generate_css_section(self):
        self._logger.info("generating custom property section for css")
        try:
            if "ecm_configuration" not in self._merged_data["spec"].keys():
                self._merged_data["spec"]["ecm_configuration"] = CommentedMap(dict())
                self._merged_data['spec'].yaml_set_comment_before_after_key("ecm_configuration",
                                                                    before='########################################################################\n########   IBM FileNet Content Manager configuration      ########\n########################################################################',
                                                                    indent=2)
            self._merged_data["spec"]["ecm_configuration"]["css"] = CommentedMap(dict())
            self._merged_data['spec']["ecm_configuration"].yaml_set_comment_before_after_key("css",
                                                                        before='####################################\n## Start of configuration for CSS ##\n####################################',
                                                                        indent=4)
            self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"] = CommentedMap(dict())
            self._merged_data['spec']["ecm_configuration"]["css"].yaml_set_comment_before_after_key("css_production_setting",
                                                                                             before='## CSS Production setting',
                                                                                             indent=6)
            self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"] = CommentedMap(dict())
            self._merged_data['spec']["ecm_configuration"]["css"]["css_production_setting"].yaml_set_comment_before_after_key("icc",
                                                                                             before='## Use the icc section below to enable IBM Content Collector P8 Content Search Services Support.  Refer to IBM Documentation for details.',
                                                                                             indent=8)

            self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"]["icc_enabled"] = True
            self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"]["icc_secret_name"] = "ibm-icc-secret"
            self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"]["p8domain_name"] = self._customcomponent_properties["CSS"]["P8_DOMAIN_NAME"]
            self._merged_data["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"]["secret_masterkey_name"] = "icc-masterkey-txt"
            self.write_cr_template()
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_css_section function in generate_cr script --- {str(e)}")

    # function to generate custom component navigator properties if required
    def generate_navigator_section(self):
        self._logger.info("generating custom property section for navigator")
        try:
            self._merged_data["spec"]["navigator_configuration"] = CommentedMap(dict())
            self._merged_data['spec'].yaml_set_comment_before_after_key("navigator_configuration",
                                                                        before='########################################################################\n########   IBM Business Automation Navigator configuration      ########\n########################################################################',
                                                                        indent=2)
            self._merged_data["spec"]["navigator_configuration"]["java_mail"] = CommentedMap(dict())
            self._merged_data["spec"]["navigator_configuration"].yaml_set_comment_before_after_key("java_mail",
                                                                                                   before="send mail",
                                                                                                   indent=4)
            self._merged_data["spec"]["navigator_configuration"]["java_mail"]["host"] = \
            self._customcomponent_properties["BAN"]["JAVA_MAIL_HOST"]
            self._merged_data["spec"]["navigator_configuration"]["java_mail"]["port"] = \
            self._customcomponent_properties["BAN"]["JAVA_MAIL_PORT"]
            self._merged_data["spec"]["navigator_configuration"]["java_mail"]["sender"] = \
            self._customcomponent_properties["BAN"]["JAVAMAIL_SENDER"]
            self._merged_data["spec"]["navigator_configuration"]["java_mail"]["ssl_enabled"] = bool(
                self._customcomponent_properties["BAN"]["JAVAMAIL_SSL"])
            self.write_cr_template()
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_navigator_section function in generate_cr script --- {str(e)}")

    # function to generate custom component task manager properties if required
    def generate_tm_section(self):
        self._logger.info("generating custom property section for task manager")
        try:
            if "ecm_configuration" not in self._merged_data["spec"].keys():
                self._merged_data["spec"]["ecm_configuration"] = CommentedMap(dict())
                self._merged_data['spec'].yaml_set_comment_before_after_key("ecm_configuration",
                                                                            before='########################################################################\n########   IBM FileNet Content Manager configuration      ########\n########################################################################',
                                                                            indent=2)
            self._merged_data["spec"]["ecm_configuration"]["tm"] = CommentedMap(dict())
            self._merged_data['spec']["ecm_configuration"].yaml_set_comment_before_after_key("tm",before='####################################\n## Start of configuration for Task Manager ##\n####################################',indent=4)
            self._merged_data["spec"]["ecm_configuration"]["tm"]["tm_production_setting"] = CommentedMap(dict())
            self._merged_data['spec']["ecm_configuration"]["tm"].yaml_set_comment_before_after_key("tm_production_setting",before='## ## Below are the default TM Production settings.  Make the necessary changes as you see fit.  Refer to IBM Documentation for details.',indent=6)
            self._merged_data["spec"]["ecm_configuration"]["tm"]["tm_production_setting"]["security_roles_to_group_mapping"] = CommentedMap(dict())
            self._merged_data['spec']["ecm_configuration"]["tm"]["tm_production_setting"].yaml_set_comment_before_after_key("security_roles_to_group_mapping",before='## All users/groups belong to one of three roles (Admin, User, or Auditor) that are specific to Task Manager.\n## Each role takes a list of users/groups (e.g., groups: [taskAdmins, taskAdmins2]).  Refer to IBM Documentation for details.',indent=8)
            security_roles_settings = {}
            security_roles_settings["task_admins"] = {}
            security_roles_settings["task_admins"]["groups"] = self._customcomponent_properties["TM"]["TASK_ADMIN_GROUP_NAMES"]
            security_roles_settings["task_admins"]["users"] = self._customcomponent_properties["TM"]["TASK_ADMIN_USER_NAMES"]
            security_roles_settings["task_users"] = {}
            security_roles_settings["task_users"]["groups"] = self._customcomponent_properties["TM"]["TASK_USER_GROUP_NAMES"]
            security_roles_settings["task_users"]["users"] = self._customcomponent_properties["TM"]["TASK_USER_USER_NAMES"]
            security_roles_settings["task_auditors"] = {}
            security_roles_settings["task_auditors"]["groups"] = self._customcomponent_properties["TM"]["TASK_AUDITOR_GROUP_NAMES"]
            security_roles_settings["task_auditors"]["users"] = self._customcomponent_properties["TM"]["TASK_AUDITOR_USER_NAMES"]
            self._merged_data["spec"]["ecm_configuration"]["tm"]["tm_production_setting"]["security_roles_to_group_mapping"] = security_roles_settings
            self.write_cr_template()
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_tm_section function in generate_cr script --- {str(e)}")


    # function to generate custom component properties if required
    def generate_custom_property_section(self):
        # adding javasendmail section to the CR
        self._logger.info("generating custom component section")
        try:
            if "BAN" in self._customcomponent_properties.keys():
                self.generate_navigator_section()
            if "CSS" in self._customcomponent_properties.keys():
                self.generate_css_section()
            if "TM" in self._customcomponent_properties.keys():
                self.generate_tm_section()
        except Exception as e:
            self._logger.exception(
                f"Error found in generate_custom_property_section function in generate_cr script --- {str(e)}")

    def generate_cr(self):
        self._logger.info("generating CR")
        # call function to generate shared configuration section of CR
        self.generate_base_section()
        # call function to generate multi ldap configuration section of CR if required
        self.generate_ldap_section()
        # call function to generate init configuration of CR if required
        if "CONTENT_INITIALIZATION_ENABLE" in self._usergroup_properties:
            if self._usergroup_properties["CONTENT_INITIALIZATION_ENABLE"]:
                self.generate_init_section()
        # call function to generate verify configuration of CR if required
        if "CONTENT_VERIFICATION_ENABLE" in self._usergroup_properties:
            if self._usergroup_properties["CONTENT_VERIFICATION_ENABLE"]:
                self.generate_verify_section()
        # call function to generate custom component properties if required
        if self._customcomponent_properties:
            self.generate_custom_property_section()
