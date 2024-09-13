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

from ..gather.gather_prerequisites import GatherPrereqOptions
from ..utilities.prerequisites_utilites import gather_var


# create a class to silently set variables from config file
class SilentGatherPrereqOptions(GatherPrereqOptions):
    # Default path for env file
    _envfile_path = os.path.join(os.getcwd(), "silent_config",
                                 "silent_install_prerequisites.toml")
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
            self.silent_egress_support()

            # self.error_check()

        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    def error_check(self):
        if len(self._error_list) > 0:
            for error in self._error_list:
                self._logger.warning(error)

            raise typer.Exit(code=1)
        return len(self._error_list)

    def silent_platform(self):
        platform = gather_var(key="PLATFORM", valid_values=[1, 2, 3], _logger=self._logger, _envfile=self._envfile,
                              _error_list=self._error_list)
        if platform is not None:
            self.platform = self.Platform(platform).name
            if self.platform == 'other' and gather_var(key="INGRESS", _logger=self._logger, _envfile=self._envfile,
                                                       _error_list=self._error_list) is not None and self.Version.FNCMVersion(
                gather_var(key="FNCM_VERSION", valid_values=[1, 2, 3, 4], _logger=self._logger, _envfile=self._envfile,
                           _error_list=self._error_list)).name != "5.5.8":
                self.ingress = gather_var(key="INGRESS", _logger=self._logger, _envfile=self._envfile,
                                          _error_list=self._error_list)

    def silent_version(self):
        version = gather_var(key="FNCM_VERSION", valid_values=[1, 2, 3, 4], _logger=self._logger,
                             _envfile=self._envfile,
                             _error_list=self._error_list)
        if version:
            self._fncm_version = self.Version.FNCMVersion(version).name

    def silent_sendmail_support(self):
        sendmail_support = gather_var(key="SENDMAIL_SUPPORT", _logger=self._logger, _envfile=self._envfile,
                                      _error_list=self._error_list)
        if sendmail_support is not None:
            self._sendmail_support = sendmail_support
        else:
            self._sendmail_support = False
        if "ban" not in self._optional_components:
            self._sendmail_support = False

    def silent_egress_support(self):
        egress_support = gather_var(key="RESTRICTED_INTERNET_ACCESS", _logger=self._logger, _envfile=self._envfile,
                                    _error_list=self._error_list)
        if egress_support is not None:
            self._egress_support = egress_support
        else:
            self._egress_support = False
        if self._fncm_version in ["5.5.8", "5.5.11"]:
            self._egress_support = False

    def silent_fips_support(self):
        fips_support = gather_var(key="FIPS_SUPPORT", _logger=self._logger, _envfile=self._envfile,
                                  _error_list=self._error_list)
        if fips_support is not None:
            self._fips_support = fips_support
        else:
            self._fips_support = False
        if self._fncm_version in ["5.5.8", "5.5.11"]:
            self._fips_support = False

    def silent_icc_support(self):
        icc_support = gather_var(key="ICC_SUPPORT", _logger=self._logger, _envfile=self._envfile,
                                 _error_list=self._error_list)
        if icc_support is not None:
            self._icc_support = icc_support
        else:
            self._icc_support = False
        if "css" not in self._optional_components:
            self._icc_support = False

    def silent_tm_support(self):
        tm_support = gather_var(key="TM_CUSTOM_GROUP_SUPPORT", _logger=self._logger, _envfile=self._envfile,
                                _error_list=self._error_list)
        if tm_support is not None:
            self._tm_custom_groups = tm_support
        else:
            self._tm_custom_groups = False
        if "tm" not in self._optional_components:
            self._tm_custom_groups = False

    def silent_optional_components(self):
        if self._fncm_version == "5.5.8":
            self._optional_components = {"cpe", "graphql", "ban"}
            cmis = gather_var(key="CMIS", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            css = gather_var(key="CSS", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            tm = gather_var(key="TM", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            es = gather_var(key="ES", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)

            if cmis is not None and cmis is True:
                self._optional_components.add("cmis")
            if css is not None and css is True:
                self._optional_components.add("css")
            if tm is not None and tm is True:
                self._optional_components.add("tm")
            if es is not None and es is True:
                self._optional_components.add("es")
        if self._fncm_version in ["5.5.11", "5.5.12"]:
            cpe = gather_var(key="CPE", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            graphql = gather_var(key="GRAPHQL", _logger=self._logger, _envfile=self._envfile,
                                 _error_list=self._error_list)
            ban = gather_var(key="BAN", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            cmis = gather_var(key="CMIS", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            css = gather_var(key="CSS", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            tm = gather_var(key="TM", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            es = gather_var(key="ES", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)

            if cpe is not None and cpe is True:
                self._optional_components.add("cpe")
            if graphql is not None and graphql is True:
                self._optional_components.add("graphql")
            if ban is not None and ban is True:
                self._optional_components.add("ban")
            if cmis is not None and cmis is True:
                self._optional_components.add("cmis")
            if css is not None and css is True:
                self._optional_components.add("css")
            if tm is not None and tm is True:
                self._optional_components.add("tm")
            if es is not None and es is True:
                self._optional_components.add("es")

            if (
                    "graphql" in self._optional_components or "cmis" in self._optional_components) and "cpe" not in self._optional_components:
                print("CPE is required to deploy graphql or CMIS and will be added as a component to this deployment")
                self._optional_components.add("cpe")
            if "tm" in self._optional_components and "ban" not in self._optional_components:
                print(
                    "Navigator is required to deploy Task Manager and will be added as a component to this deployment")
                self._optional_components.add("ban")
            if "es" in self._optional_components and not {"ban", "cpe"}.issubset(self._optional_components):
                print(
                    "Navigator and CPE is required to deploy External Share and will be added as a component to this deployment")
                self._optional_components.add("ban")
                self._optional_components.add("cpe")
        else:
            cpe = gather_var(key="CPE", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            graphql = gather_var(key="GRAPHQL", _logger=self._logger, _envfile=self._envfile,
                                 _error_list=self._error_list)
            ban = gather_var(key="BAN", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            cmis = gather_var(key="CMIS", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            css = gather_var(key="CSS", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            tm = gather_var(key="TM", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            es = gather_var(key="ES", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            ier = gather_var(key="IER", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            iccsap = gather_var(key="ICCSAP", _logger=self._logger, _envfile=self._envfile,
                                _error_list=self._error_list)

            if cpe is not None and cpe is True:
                self._optional_components.add("cpe")
            if graphql is not None and graphql is True:
                self._optional_components.add("graphql")
            if ban is not None and ban is True:
                self._optional_components.add("ban")
            if cmis is not None and cmis is True:
                self._optional_components.add("cmis")
            if css is not None and css is True:
                self._optional_components.add("css")
            if tm is not None and tm is True:
                self._optional_components.add("tm")
            if es is not None and es is True:
                self._optional_components.add("es")
            if ier is not None and ier is True:
                self._optional_components.add("ier")
            if iccsap is not None and iccsap is True:
                self._optional_components.add("iccsap")

            if (
                    "graphql" in self._optional_components or "cmis" in self._optional_components) and "cpe" not in self._optional_components:
                print("CPE is required to deploy graphql or CMIS and will be added as a component to this deployment")
                self._optional_components.add("cpe")
            if "tm" in self._optional_components and "ban" not in self._optional_components:
                print(
                    "Navigator is required to deploy Task Manager and will be added as a component to this deployment")
                self._optional_components.add("ban")
            if "es" in self._optional_components and not {"ban", "cpe"}.issubset(self._optional_components):
                print(
                    "Navigator and CPE is required to deploy External Share and will be added as a component to this deployment")
                self._optional_components.add("ban")
                self._optional_components.add("cpe")
            if "ier" in self._optional_components and not {"ban", "cpe"}.issubset(self._optional_components):
                print(
                    "Navigator and CPE is required to deploy Enterprise Records and will be added as a component to this deployment")
                self._optional_components.add("ban")
                self._optional_components.add("cpe")
            if "iccsap" in self._optional_components and not {"ban", "cpe"}.issubset(self._optional_components):
                print(
                    "Navigator and CPE is required to deploy Content Collector for SAP and will be added as a component to this deployment")
                self._optional_components.add("ban")
                self._optional_components.add("cpe")

    def silent_ldap(self):
        self._ldap_number = self.__find_ldap_count()
        for i in range(self._ldap_number):
            ldap_id = f"LDAP{str(i + 1) if i > 0 else ''}"
            ldap_type = gather_var(key="LDAP_TYPE", section_header=ldap_id, valid_values=[1, 2, 3, 4, 5, 6, 7],
                                   _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
            ldap_ssl = gather_var(key="LDAP_SSL_ENABLE", section_header=ldap_id, _logger=self._logger,
                                  _envfile=self._envfile, _error_list=self._error_list)
            if ldap_ssl:
                self._ssl_directory_list.append(ldap_id.lower())
            if ldap_type is not None and ldap_ssl is not None:
                self._ldap_info.append((self.Ldap(self.Ldap.ldapTypes(ldap_type), ldap_ssl, ldap_id)))

    def silent_idp(self):
        self._idp_number = self.__find_idp_count()
        for i in range(self._idp_number):
            idp_id = f"IDP{str(i + 1) if i > 0 else ''}"
            idp_discovery_enabled = gather_var(key="DISCOVERY_ENABLED", section_header=idp_id, _logger=self._logger,
                                               _envfile=self._envfile, _error_list=self._error_list)
            if idp_discovery_enabled:
                idp_discovery_url = gather_var(key="DISCOVERY_URL", section_header=idp_id, valid_values="url",
                                               _logger=self._logger, _envfile=self._envfile,
                                               _error_list=self._error_list)
            else:
                idp_discovery_url = None

            if idp_discovery_enabled is not None:
                idp = self.Idp(idp_discovery_enabled, idp_id, idp_discovery_url)
                idp.parse_discovery_url()
                self._idp_info.append(idp)

    def silent_auth_type(self):
        auth_type = gather_var(key="AUTHENTICATION", valid_values=[1, 2, 3], _logger=self._logger,
                               _envfile=self._envfile, _error_list=self._error_list)
        if auth_type is not None:
            self._auth_type = self.AuthType(auth_type).name

    def silent_db(self):
        if self._fips_support:
            db_type = gather_var(key="DATABASE_TYPE", valid_values=[1, 2, 3, 4], _logger=self._logger,
                                 _envfile=self._envfile, _error_list=self._error_list)
        else:
            db_type = gather_var(key="DATABASE_TYPE", valid_values=[1, 2, 3, 4, 5], _logger=self._logger,
                                 _envfile=self._envfile, _error_list=self._error_list)
        if db_type is not None:
            # self.db_type = self.__gather_var("DATABASE.TYPE",["db2", "db2HADR", "oracle", "sqlserver", "postgresql"])
            self.db_type = self.DatabaseType(db_type).name

        os_number = gather_var(key="DATABASE_OBJECT_STORE_COUNT", valid_values=(1, float('inf')), _logger=self._logger,
                               _envfile=self._envfile, _error_list=self._error_list)
        # self.db_ssl = self.__gather_var("DATABASE.SSL_ENABLE",["True","False"]) in ["True"]
        if os_number is not None:
            self.os_number = os_number

        db_ssl = gather_var(key="DATABASE_SSL_ENABLE", _logger=self._logger, _envfile=self._envfile,
                            _error_list=self._error_list)
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
        license_model = gather_var(key="LICENSE", valid_values=["ICF.PVUNonProd", "ICF.PVUProd", "ICF.UVU", "ICF.CU",
                                                                "FNCM.PVUNonProd", "FNCM.PVUProd", "FNCM.UVU",
                                                                "FNCM.CU", "CP4BA.NonProd", "CP4BA.Prod",
                                                                "CP4BA.User"], _logger=self._logger,
                                   _envfile=self._envfile, _error_list=self._error_list)
        if license_model is not None:
            self._license_model = license_model

    def silent_initverify(self):
        content_initialize = gather_var(key="CONTENT_INIT", _logger=self._logger, _envfile=self._envfile,
                                        _error_list=self._error_list)
        if content_initialize is not None:
            self.content_initialize = content_initialize
        content_verification = gather_var(key="CONTENT_VERIFY", _logger=self._logger, _envfile=self._envfile,
                                          _error_list=self._error_list)
        if content_verification is not None:
            self.content_verification = content_verification
        if self._fncm_version != "5.5.8" and "cpe" not in self._optional_components:
            self.content_initialize = False
            self.content_verification = False

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


