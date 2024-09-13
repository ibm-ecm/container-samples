###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2024. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################
import inspect
import os

import toml

from ..gather.gather import GatherOptions
from ..utilities.prerequisites_utilites import gather_var


# Class for silent option for all deployment scripts i.e deployoperator, cleanupdeployment, upgradeOperator , loadimages
class SilentGatherOptions(GatherOptions):
    # Default path for env file
    _envfile_path = os.path.join(os.getcwd(), "silent_config",
                                 "silent_install_cleandeployment.toml")
    _error_list = []

    def __init__(self, logger, envfile_path=_envfile_path, script_type="cleanup", dev=False):

        super().__init__(logger=logger, console=None, script_type=script_type, dev=dev)

        self._envfile_path = envfile_path
        # Setting it to true so the gather class can accordingly skip the menu based questions
        self._silent_mode = True
        try:
            self._envfile = toml.loads(open(self._envfile_path, encoding="utf-8").read())
        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script - error loading {self._envfile_path} file -  {str(e)}")

    # method to output all variables to dict
    def to_dict(self):
        return {
            "namespace": self._namespace,
            "platform": self._platform,
            "private_catalog": self._private_catalog,
            "private_registry": self._private_registry,
            "private_registry_host": self._private_registry_host,
            "private_registry_port": self._private_registry_port,
            "private_registry_server": self._private_registry_server,
            "private_registry_username": self._private_registry_username,
            "private_registry_password": self._private_registry_password,
            "private_registry_ssl_enabled": self._private_registry_ssl_enabled,
            "private_registry_ssl_cert": self._private_registry_ssl_cert,
            "entitlement_key": self._entitlement_key,
            "components": self._components,
            "accept_license": self._accept_license,
            "sensitive_collect": self._sensitive_collect,
            "error_list": self._error_list
        }


    def silent_parse_mustgather_operator_file(self):
        self.silent_namespace()
        self.silent_collect_sensitive_info()
        self.silent_mustgather_components()


    # method to parse the file
    def parse_envfile(self):
        try:
            self.silent_platform()
            self.silent_namespace()

            # self.error_check()

        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Function to read platform information from toml file
    def silent_platform(self):
        try:
            platform = gather_var(key="PLATFORM", valid_values=[1, 2, 3], _logger=self._logger, _envfile=self._envfile,
                                  _error_list=self._error_list)
            if platform is not None:
                if platform:
                    self._platform = self.Platform(platform).name
            else:
                self.error_check()
        except Exception as e:
            self._logger.exception(
                f"Exception from silent.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Function to read namespace information from toml file
    def silent_namespace(self):
        namespace = self._envfile.get("NAMESPACE")
        super().collect_namespace(namespace)
        self._namespace = super().namespace

    def silent_license_model(self):
        license = self._envfile.get("LICENSE_ACCEPT")
        super().collect_license_model(license)
        self._accept_license = super().accept_license

    def silent_collect_sensitive_info(self):
        collected_sensitive = gather_var(key="COLLECT_SENSITIVE_DATA", _logger=self._logger, _envfile=self._envfile, _error_list=self._error_list)
        super().collect_sensitive_data(collected_sensitive)
        self._sensitive_collect = super().sensitive_collect

    def silent_mustgather_components(self):
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
            super().components.add("cpe")
        if graphql is not None and graphql is True:
            super().components.add("graphql")
        if ban is not None and ban is True:
            super().components.add("ban")
        if cmis is not None and cmis is True:
            super().components.add("cmis")
        if css is not None and css is True:
            super().components.add("css")
        if tm is not None and tm is True:
            super().components.add("tm")
        if es is not None and es is True:
            super().components.add("es")
        if ier is not None and ier is True:
            super().components.add("ier")
        if iccsap is not None and iccsap is True:
            super().components.add("iccsap")

    def silent_parse_upgrade_variables(self):
        self.silent_license_model()
        self.silent_platform()
        self.silent_namespace()

        private_catalog = not (self._envfile.get("GLOBAL_CATALOG", False))
        private_registry = self._envfile.get("PRIVATE_REGISTRY", False)
        apply_cr = self._envfile.get("APPLY_CR", False)

        self._private_catalog = private_catalog
        self._apply_cr = apply_cr
        self._private_registry = private_registry

        if self._platform == "other":
            if private_registry:
                self._private_registry_host = self._envfile.get("PRIVATE_REGISTRY_HOST")
                self._private_registry_port = self._envfile.get("PRIVATE_REGISTRY_PORT")
                self._private_registry_server = f"{self._private_registry_host}:{self._private_registry_port}"
                self._private_registry_username = self._envfile.get("PRIVATE_REGISTRY_USERNAME")
                self._private_registry_password = self._envfile.get("PRIVATE_REGISTRY_PASSWORD")
                if self._private_registry_server == "" or self._private_registry_server is None:
                    self._error_list.append(
                        f"ERROR with PRIVATE REGISTRY SERVER in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")

                if self._private_registry_username == "" or self._private_registry_server is None:
                    self._error_list.append(
                        f"ERROR with PRIVATE REGISTRY USER in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")

                if self._private_registry_password == "" or self._private_registry_server is None:
                    self._error_list.append(
                        f"ERROR with PRIVATE REGISTRY PASSWORD in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty")
                self._private_registry_ssl_enabled = self._envfile.get("PRIVATE_REGISTRY_SSL_ENABLED")
                if self._private_registry_ssl_enabled:
                    self._private_registry_ssl_cert = self._envfile.get("PRIVATE_REGISTRY_SSL_CRT_PATH")
                    if self._private_registry_ssl_cert == "" or self._private_registry_server is None:
                        self._error_list.append(
                            f"ERROR with PRIVATE REGISTRY SSL CRT PATH in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty if SSL is Enabled")
                if self._error_list:
                    self.error_check()
                else:
                    self.collect_verify_private_registry()
            else:
                self.error_check()

    # method to parse load images silent install file
    def silent_parse_load_images_file(self):
        self._entitlement_key = self._envfile.get("ENTITLEMENT_KEY")
        if self._entitlement_key == "" or self._entitlement_key is None:
            self._error_list.append(
                f"ERROR with ENTITLEMENT KEY in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")
        self._private_registry_host = self._envfile.get("PRIVATE_REGISTRY_HOST")
        self._private_registry_port = self._envfile.get("PRIVATE_REGISTRY_PORT")
        self._private_registry_server = f"{self._private_registry_host}:{self._private_registry_port}"
        self._private_registry_username = self._envfile.get("PRIVATE_REGISTRY_USERNAME")
        self._private_registry_password = self._envfile.get("PRIVATE_REGISTRY_PASSWORD")
        if self._private_registry_server == "" or self._private_registry_server is None:
            self._error_list.append(
                f"ERROR with PRIVATE REGISTRY SERVER in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")

        if self._private_registry_username == "" or self._private_registry_server is None:
            self._error_list.append(
                f"ERROR with PRIVATE REGISTRY USER in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")

        if self._private_registry_password == "" or self._private_registry_server is None:
            self._error_list.append(
                f"ERROR with PRIVATE REGISTRY PASSWORD in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty")
        self._private_registry_ssl_enabled = self._envfile.get("PRIVATE_REGISTRY_SSL_ENABLED")
        if self._private_registry_ssl_enabled:
            self._private_registry_ssl_cert = self._envfile.get("PRIVATE_REGISTRY_SSL_CRT_PATH")
            if self._private_registry_ssl_cert == "" or self._private_registry_server is None:
                self._error_list.append(
                    f"ERROR with PRIVATE REGISTRY SSL CRT PATH in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty if SSL is Enabled")

        self.error_check()

    def silent_parse_deploy_operator_file(self):
        self.silent_license_model()
        self.silent_platform()
        self._entitlement_key = self._envfile.get("ENTITLEMENT_KEY")
        private_registry = self._envfile.get("PRIVATE_REGISTRY", False)
        self._private_registry = private_registry

        if self._platform == "other":
            if private_registry:
                self._private_registry_host = self._envfile.get("PRIVATE_REGISTRY_HOST")
                self._private_registry_port = self._envfile.get("PRIVATE_REGISTRY_PORT")
                self._private_registry_server = f"{self._private_registry_host}:{self._private_registry_port}"
                self._private_registry_username = self._envfile.get("PRIVATE_REGISTRY_USERNAME")
                self._private_registry_password = self._envfile.get("PRIVATE_REGISTRY_PASSWORD")
                if self._private_registry_server == "" or self._private_registry_server is None:
                    self._error_list.append(
                        f"ERROR with PRIVATE REGISTRY SERVER in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")

                if self._private_registry_username == "" or self._private_registry_server is None:
                    self._error_list.append(
                        f"ERROR with PRIVATE REGISTRY USER in silent mode configuration {self._envfile_path} file - Field Cannot be Empty")

                if self._private_registry_password == "" or self._private_registry_server is None:
                    self._error_list.append(
                        f"ERROR with PRIVATE REGISTRY PASSWORD in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty")
                self._private_registry_ssl_enabled = self._envfile.get("PRIVATE_REGISTRY_SSL_ENABLED")
                if self._private_registry_ssl_enabled:
                    self._private_registry_ssl_cert = self._envfile.get("PRIVATE_REGISTRY_SSL_CRT_PATH")
                    if self._private_registry_ssl_cert == "" or self._private_registry_server is None:
                        self._error_list.append(
                            f"ERROR with PRIVATE REGISTRY SSL CRT PATH in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty if SSL is Enabled")
                if self._error_list:
                    self.error_check()
                else:
                    self.collect_verify_private_registry()
            else:
                if self._entitlement_key == "" or self._entitlement_key is None:
                    self._error_list.append(
                        f"ERROR with ENTITLEMENT KEY in silent mode configuration {self._envfile_path} file -  Field Cannot be Empty if a private registry is not used")
                    self.error_check()
                else:
                    self.collect_verify_entitlement_key()
        else:
            self.collect_verify_entitlement_key()
        self.silent_namespace()
        self._private_catalog = not (self._envfile.get("GLOBAL_CATALOG", False))

    def silent_print_deployment_options(self):

        self._logger.info("namespace-", self._namespace)
        self._logger.info("platform-", self._platform)
        self._logger.info("podman present-", super()._podman_available)
        self._logger.info("docker present -", super()._docker_available)
        self._logger.info("kubectl present-", super()._kubectl_available)
        self._logger.info("oc logged in", super()._ocp_logged_in)
        return_dict = {
            "namespace": self._namespace,
            "platform": self._platform,
            "podman present": super()._podman_available,
            "docker present": super()._docker_available,
            "kubectl present": super()._kubectl_available,
            "Cluster connection": super()._ocp_logged_in
        }

    def error_check(self):
        if len(self._error_list) > 0:
            for error in self._error_list:
                self._logger.error(error)
            exit()
