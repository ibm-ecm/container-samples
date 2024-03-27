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

# Create a class to silently set variables from config file
#  - the class should have a constructor that takes the filename as an argument
#  - the class should have a method to parse the file

import inspect
import os

import toml
import typer

from helper_scripts.gather.gather import GatherOptions


# create a class to silently set variables from config file
class SilentGather(GatherOptions):
    # Default path for env file
    _envfile_path = os.path.join(os.getcwd(), "helper_scripts", "gather", "silent_config", "silent_install.toml")
    _error_list = []

    def __init__(self, logger, envfile_path=_envfile_path):

        super().__init__(logger, console=None)

        self._envfile_path = envfile_path

        try:
            self._envfile = toml.loads(open(self._envfile_path, encoding="utf-8").read())
        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script - error loading {self._envfile_path} file -  {str(e)}")

    # method to parse the file
    def parse_envfile(self):
        try:
            self.silent_platform()
            self.silent_fips_support()
            self.silent_auth_type()
            self.silent_idp()
            self.silent_optional_components()
            self.silent_sendmail_support()
            self.silent_icc_support()
            self.silent_tm_support()
            self.silent_db()
            self.silent_license_model()
            self.silent_ldap()
            self.silent_initverify()
            self.silent_storage()
            self.silent_egress_support()

            # self.error_check()

        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    def error_check(self):
        if len(self._error_list) > 0:
            for error in self._error_list:
                self._logger.exception(error)

            raise typer.Exit(code=1)
        return len(self._error_list)

    def silent_platform(self):
        platform = self.__gather_var("PLATFORM", valid_values=[1, 2, 3])
        if platform is not None:
            self.platform = self.Platform(platform).name
            if self.platform == 'other' and self.__gather_var("INGRESS") is not None and self.Version.FNCMVersion(
                    self.__gather_var("FNCM_VERSION", valid_values=[1, 2])).name != "5.5.8":
                self.ingress = self.__gather_var("INGRESS")

    def silent_version(self):
        version = self.__gather_var("FNCM_VERSION", valid_values=[1, 2, 3])
        if version:
            self._fncm_version = self.Version.FNCMVersion(version).name

    def silent_sendmail_support(self):
        sendmail_support = self.__gather_var("SENDMAIL_SUPPORT")
        if sendmail_support is not None:
            self._sendmail_support = sendmail_support
        else:
            self._sendmail_support = False
        if "ban" not in self._optional_components:
            self._sendmail_support = False


    def silent_egress_support(self):
        egress_support = self.__gather_var("RESTRICTED_INTERNET_ACCESS")
        if egress_support is not None:
            self._egress_support = egress_support
        else:
            self._egress_support = False
        if self._fncm_version in ["5.5.8", "5.5.11"]:
            self._egress_support = False

    def silent_fips_support(self):
        fips_support = self.__gather_var("FIPS_SUPPORT")
        if fips_support is not None:
            self._fips_support = fips_support
        else:
            self._fips_support = False
        if self._fncm_version in ["5.5.8","5.5.11"]:
            self._fips_support = False

    def silent_icc_support(self):
        icc_support = self.__gather_var("ICC_SUPPORT")
        if icc_support is not None:
            self._icc_support = icc_support
        else:
            self._icc_support = False
        if "css" not in self._optional_components:
            self._icc_support = False

    def silent_tm_support(self):
        tm_support = self.__gather_var("TM_CUSTOM_GROUP_SUPPORT")
        if tm_support is not None:
            self._tm_custom_groups = tm_support
        else:
            self._tm_custom_groups = False
        if "tm" not in self._optional_components:
            self._tm_custom_groups = False

    def silent_optional_components(self):
        self._optional_components = ["cpe", "graphql", "ban"]
        cmis = self.__gather_var("CMIS")
        css = self.__gather_var("CSS")
        tm = self.__gather_var("TM")
        es = self.__gather_var("ES")

        if cmis is not None and cmis is True:
            self._optional_components.append("cmis")
        if css is not None and css is True:
            self._optional_components.append("css")
        if tm is not None and tm is True:
            self._optional_components.append("tm")
        if es is not None and es is True:
            self._optional_components.append("es")
        if self._fncm_version != "5.5.8":
            cpe = self.__gather_var("CPE")
            graphql = self.__gather_var("GRAPHQL")
            ban = self.__gather_var("BAN")
            if cpe is None or cpe is False:
                self._optional_components.remove("cpe")
            if graphql is None or graphql is False:
                self._optional_components.remove("graphql")
            if ban is None or ban is False:
                self._optional_components.remove("ban")

            if ("graphql" in self._optional_components or "cmis" in self._optional_components) and "cpe" not in self._optional_components:
                print("Note - CPE is required to deploy graphql or CMIS and will be added as a component to this deployment")
                self._optional_components.append("cpe")
            if "tm" in self._optional_components and "ban" not in self._optional_components:
                print("Note - Navigator is required to deploy Task Manager and will be added as a component to this deployment")
                self._optional_components.append("ban")
            if "es" in self._optional_components and "ban" not in self._optional_components:
                if self._auth_type in ("LDAP", "SCIM_IDP"):
                    print("Note - External Share requires an LDAP_IDP Authentication type to be configured")
                    self._auth_type = "LDAP_IDP"
                print("Note - Navigator is required to deploy External Share and will be added as a component to this deployment")
                self._optional_components.append("ban")


    def silent_ldap(self):
        self._ldap_number = self.__find_ldap_count()
        for i in range(self._ldap_number):
            ldap_id = f"LDAP{str(i + 1) if i > 0 else ''}"
            ldap_type = self.__gather_var("LDAP_TYPE", section_header=ldap_id, valid_values=[1, 2, 3, 4, 5, 6, 7])
            ldap_ssl = self.__gather_var("LDAP_SSL_ENABLE", section_header=ldap_id)
            if ldap_ssl:
                self._ssl_directory_list.append(ldap_id.lower())
            if ldap_type is not None and ldap_ssl is not None:
                self._ldap_info.append((self.Ldap(self.Ldap.ldapTypes(ldap_type), ldap_ssl, ldap_id)))

    def silent_idp(self):
        self._idp_number = self.__find_idp_count()
        for i in range(self._idp_number):
            idp_id = f"IDP{str(i + 1) if i > 0 else ''}"
            idp_discovery_enabled = self.__gather_var("DISCOVERY_ENABLED", section_header=idp_id)
            if idp_discovery_enabled:
                idp_discovery_url = self.__gather_var("DISCOVERY_URL", section_header=idp_id, valid_values="url")
            else:
                idp_discovery_url = None

            if idp_discovery_enabled is not None:
                idp = self.Idp(idp_discovery_enabled, idp_id, idp_discovery_url)
                if idp.parse_discovery_url():
                    self._idp_info.append(idp)
                else:
                    error = ("Discovery URL is invalid\n"
                             "Make sure your discovery URL ends with \".well-known/openid-configuration\"")
                    self._error_list.append(error)

    def silent_auth_type(self):
        auth_type = self.__gather_var("AUTHENTICATION", valid_values=[1, 2, 3])
        if auth_type is not None:
            self._auth_type = self.AuthType(auth_type).name

    def silent_db(self):
        if self._fips_support:
            db_type = self.__gather_var("DATABASE_TYPE", valid_values=[1, 2, 3, 4])
        else:
            db_type = self.__gather_var("DATABASE_TYPE", valid_values=[1, 2, 3, 4, 5])
        if db_type is not None:
            # self.db_type = self.__gather_var("DATABASE.TYPE",["db2", "db2HADR", "oracle", "sqlserver", "postgresql"])
            self.db_type = self.DatabaseType(db_type).name

        os_number = self.__gather_var("DATABASE_OBJECT_STORE_COUNT", valid_values=(1, float('inf')))
        # self.db_ssl = self.__gather_var("DATABASE.SSL_ENABLE",["True","False"]) in ["True"]
        if os_number is not None:
            self.os_number = os_number

        db_ssl = self.__gather_var("DATABASE_SSL_ENABLE")
        if db_ssl:
            self._db_ssl = db_ssl
            if "cpe" in self._optional_components or self._fncm_version == "5.5.8":
                self._ssl_directory_list.append("gcd")
                self._ssl_directory_list.append("os")
                for i in range(1, os_number):
                    self._ssl_directory_list.append(f"os{i + 1}")
            if "ban" in self._optional_components or self._fncm_version == "5.5.8":
                self._ssl_directory_list.append("icn")

    def silent_license_model(self):
        license_model = self.__gather_var("LICENSE", valid_values=["ICF.PVUNonProd", "ICF.PVUProd", "ICF.UVU", "ICF.CU",
                                                                   "FNCM.PVUNonProd", "FNCM.PVUProd", "FNCM.UVU",
                                                                   "FNCM.CU", "CP4BA.NonProd", "CP4BA.Prod",
                                                                   "CP4BA.User"])
        if license_model is not None:
            self._license_model = license_model

    def silent_initverify(self):
        content_initialize = self.__gather_var("CONTENT_INIT")
        if content_initialize is not None:
            self.content_initialize = content_initialize
        content_verification = self.__gather_var("CONTENT_VERIFY")
        if content_verification is not None:
            self.content_verification = content_verification
        if self._fncm_version != "5.5.8" and "cpe" not in self._optional_components:
            self.content_initialize = False
            self.content_verification = False

    # method to return variables in correct type for a given key from config file
    # Currently can only read one table layer deep
    def __gather_var(self, key, section_header='', valid_values=True):
        try:
            if section_header == '':
                value = self._envfile.get(key)
            else:
                value = self._envfile[section_header][key]
                section_header = "[" + section_header + "]"
            # Check that the user/property file input is valid
            if self.__valid_check(section_header + key, value, valid_values):
                return value
            return None

        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # method to check to if value in property file is valid
    def __valid_check(self, prop_key, prop_value, valid_values):
        try:
            # For sets and boolean validity check
            if type(valid_values) is list:
                if prop_value not in valid_values:

                    # Just extra formatting to match what is visible in toml file for strings
                    if type(prop_value) is str:
                        prop_value = f"\"{prop_value}\""

                    error = f"Incorrect/missing parameter set in silent install file -  {prop_key}={prop_value} | Valid values - {valid_values}"
                    self._error_list.append(error)
                    return False

            # For range of integers check
            elif type(valid_values) is tuple:
                if prop_value < valid_values[0] and prop_value >= valid_values[1]:
                    error = f"Incorrect/missing parameter set in silent install file -  {prop_key}={prop_value} | Valid values - {valid_values}"
                    self._error_list.append(error)
                    return False

            # For boolean values check
            elif type(valid_values) is bool:
                if type(prop_value) is not bool:
                    valid_values = "[true,false]"
                    error = f"Incorrect/missing parameter set in silent install file -  {prop_key}={prop_value} | Valid values - {valid_values}"
                    self._error_list.append(error)
                    return False

            elif type(valid_values) is str:
                if valid_values == "url":
                    # Check if the url is valid
                    if prop_value is None or not prop_value.endswith(".well-known/openid-configuration"):
                        error = f"URL is empty or invalid in silent install file -  {prop_key}={prop_value} | Valid values - ends with .well-known/openid-configuration"
                        self._error_list.append(error)
                        return False

            return True

        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Return the count of ldap to use
    def __find_ldap_count(self):
        num_ldap = 0
        for key in self._envfile:
            # Parse the keys with more than 4 characters ie. LDAP2; LDAP3
            if "LDAP" in key:
                num_ldap += 1
        return num_ldap

    def __find_idp_count(self):
        num_idp = 0
        for key in self._envfile:
            # Parse the keys with more than 4 characters ie. IDP2; IDP3
            if "IDP" in key:
                num_idp += 1
        return num_idp
