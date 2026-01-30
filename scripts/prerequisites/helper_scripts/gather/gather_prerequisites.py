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
import os
from enum import Enum
from urllib.parse import urlparse

import requests
import xmltodict
from kubernetes import config
from rich import print
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.text import Text

from ..utilities.interface import clear
from ..utilities.kubernetes_utilites import KubernetesUtilities

requests.packages.urllib3.disable_warnings()


# create a class to gather all deployment options from the user for the prerequisite scripts
class GatherPrereqOptions:
    # Inner Class to take care of FNCM version.
    class Version:
        FNCMVersion = Enum(
            value='FNCMVersion',
            names=[("5.5.8", 1), ("5.5.11", 2), ("5.5.12", 3), ("5.6.0", 4), ("5.7.0", 5)]
        )

        def __init__(self, fncm_version: FNCMVersion):
            self._fncm_version = fncm_version

    # Create an inner class to gather ldap info from the user
    class Ldap:
        ldapTypes = Enum(
            value='LdapType',
            names=[
                ('Microsoft Active Directory', 1),
                ('IBM Security Verify Directory', 2),
                ('NetIQ eDirectory', 3),
                ('Oracle Internet Directory', 4),
                ('Oracle Directory Server Enterprise Edition', 5),
                ('Oracle Unified Directory', 6),
                ('CA eTrust', 7)
            ]
        )

        def __init__(self, ldap_type: ldapTypes, ldap_ssl: bool, ldap_id: str = None):
            self._type = ldap_type
            self._ssl = ldap_ssl
            self._ldap_id = ldap_id

        # Create a function to display the ldap info
        def display(self):
            print("Type:", self._type.name)
            print("SSL Enabled:", self._ssl)
            print("LDAP ID:", self._ldap_id)

        # Create a function to return the ldap info as a dictionary
        def to_dict(self):
            return {
                "type": self._type.name,
                "ssl": self._ssl,
                "id": self._ldap_id
            }

    # Create an inner class to gather ldap info from the user
    class Idp:
        def __init__(self, discovery_enabled: bool, idp_id: str = None, discovery_url: str = None):
            self._discovery_url = discovery_url
            self._discovery_enabled = discovery_enabled
            self._idp_id = idp_id
            self._validation_method = "introspect"
            self._introspect_url = "<Required>"
            self._userinfo_url = "<Required>"
            self._token_url = "<Required>"
            self._revoke_url = "<Required>"
            self._issuer = "<Required>"
            self._client_id = "<Required>"
            self._client_secret = "<Required>"
            self._jwks_url = "<Required>"
            self._user_identifier = "sub"
            self._unique_user_identifier = "sub"
            self._user_identifier_to_sub = "sub"
            self._ssl_enabled = True

        # Create a function to parse the json return from discovery url
        def parse_discovery_url(self):
            try:
                # Create a variable to hold the url
                url = self._discovery_url

                # Check if the url is valid
                if url is None:
                    return False
                else:
                    if url.endswith(".well-known/openid-configuration"):
                        # Create a variable to hold the json
                        json = requests.get(url, timeout=5, verify=False).json()

                        # Check if the json is valid
                        if json is None:
                            return False
                        else:
                            # Check if the json contains the required fields
                            if "introspection_endpoint" in json:
                                self._introspect_url = json["introspection_endpoint"]
                                self._validation_method = "introspect"

                                if "preferred_username" in json["claims_supported"]:
                                    self._user_identifier = "preferred_username"

                            elif "userinfo_endpoint" in json:
                                self._userinfo_url = json["userinfo_endpoint"]
                                self._validation_method = "userinfo"

                                if "email" in json["claims_supported"]:
                                    self._user_identifier = "email"

                            else:
                                return False

                            if "token_endpoint" in json:
                                self._token_url = json["token_endpoint"]

                            if "revocation_endpoint" in json:
                                self._revoke_url = json["revocation_endpoint"]

                            if "issuer" in json:
                                self._issuer = json["issuer"]

                            if "jwks_uri" in json:
                                self._jwks_url = json["jwks_uri"]

                            # Check if the discovery url is https scheme
                            if urlparse(url).scheme == "https":
                                self._ssl_enabled = True
                            else:
                                self._ssl_enabled = False

                            return True

                    else:
                        return False
            except Exception as e:
                print(f"Exception from parse_discovery_url function - {str(e)}")
                return False

        # Create a function to display the ldap info
        def display(self):
            print("Discovery URL:", self._discovery_url)
            print("Discovery Enabled:", self._discovery_enabled)
            print("IDP ID:", self._idp_id)

        # Create a function to return the ldap info as a dictionary
        def to_dict(self):
            return {
                "discovery_url": self._discovery_url,
                "discovery_enabled": self._discovery_enabled,
                "id": self._idp_id,
                "validation_method": self._validation_method,
                "introspect_url": self._introspect_url,
                "userinfo_url": self._userinfo_url,
                "jwks_url": self._jwks_url,
                "token_url": self._token_url,
                "revoke_url": self._revoke_url,
                "issuer": self._issuer,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "user_identifier": self._user_identifier,
                "unique_user_identifier": self._unique_user_identifier,
                "user_identifier_to_sub": self._user_identifier_to_sub,
                "ssl_enabled": self._ssl_enabled
            }

    # Create an enum for all the database types
    class DatabaseType(Enum):
        db2 = 1
        db2HADR = 2
        oracle = 5
        sqlserver = 3
        postgresql = 4
        # Adding DB2 RDS and DB2 RDS HADR to the list of database types the user can select from ( only from 5.7.0)
        db2rds = 6
        db2rdsHADR = 7

    class AuthType(Enum):
        LDAP = 1
        LDAP_IDP = 2
        SCIM_IDP = 3

    # Create an enum for all the database types
    class LicenseModel(Enum):
        ICF = 1
        FNCM = 2
        CP4BA = 3

    # Create an enum for all the database types
    class LicenseMetricCP4BA(Enum):
        NonProd = 1
        Prod = 2
        User = 3

    class LicenseMetricFNCM(Enum):
        PVUProd = 1
        PVUNonProd = 2
        UVU = 3
        CU = 4

    # Create an enum for all optional components
    class OptionalComponents(Enum):
        cpe = 1
        graphql = 2
        ban = 3
        css = 4
        cmis = 5
        tm = 6
        es = 7
        ier = 8
        iccsap = 9

    # Create an enum for all platform types
    class Platform(Enum):
        OCP = 1
        other = 2

    def __init__(self, logger, console):
        self._optional_components = set()
        self._ldap_info = []
        self._ldap_number = 0
        self._db_type = None
        self._db_ssl = False
        self._idp_info = []
        self._idp_number = 0
        self._os_number = 1
        self._content_initialize = False
        self._content_verification = False
        self._platform = self.Platform(1).name
        self._license_model = None
        self._ingress = False
        self._logger = logger
        self._console = console
        self._ssl_directory_list = []
        self._fncm_version = "5.7.0"
        self._sendmail_support = False
        self._icc_support = False
        self._tm_custom_groups = False
        self._egress_support = False
        self._np_support = False
        self._fips_support = False
        self._auth_type = self.AuthType(1).name
        self._namespace = None
        self._current_namespace = None
        self._script_type = 'gather'
        self._k = KubernetesUtilities(self._logger)

    # Create a function to gather all deployment options from the user
    @property
    def license_model(self):
        return self._license_model

    @property
    def namespace(self):
        return self._namespace

    @property
    def fncm_version(self):
        return self._fncm_version

    @property
    def egress_support(self):
        return self._egress_support

    @property
    def np_support(self):
        return self._np_support

    @property
    def fips_support(self):
        return self._fips_support

    @property
    def db_ssl(self):
        return self._db_ssl

    @property
    def sendmail_support(self):
        return self._sendmail_support

    @property
    def icc_support(self):
        return self._icc_support

    @property
    def tm_custom_groups(self):
        return self._tm_custom_groups

    @property
    def optional_components(self):
        return self._optional_components

    @optional_components.setter
    def optional_components(self, value):
        self._optional_components = value

    @property
    def auth_type(self):
        return self._auth_type

    @auth_type.setter
    def auth_type(self, value):
        self._auth_type = value

    @property
    def ldap_info(self):
        return self._ldap_info

    @ldap_info.setter
    def ldap_info(self, value):
        self._ldap_info = value

    @property
    def idp_info(self):
        return self._idp_info

    @idp_info.setter
    def idp_info(self, value):
        self._idp_info = value

    @property
    def idp_number(self):
        return self._idp_number

    @property
    def db_type(self):
        return self._db_type

    @db_type.setter
    def db_type(self, value):
        self._db_type = value

    @property
    def os_number(self):
        return self._os_number

    @os_number.setter
    def os_number(self, value):
        self._os_number = value

    @property
    def content_initialize(self):
        return self._content_initialize

    @content_initialize.setter
    def content_initialize(self, value):
        self._content_initialize = value

    @property
    def content_verification(self):
        return self._content_verification

    @content_verification.setter
    def content_verification(self, value):
        self._content_verification = value

    @property
    def platform(self):
        return self._platform

    @platform.setter
    def platform(self, value):
        self._platform = value

    @property
    def ingress(self):
        return self._ingress

    @ingress.setter
    def ingress(self, value):
        self._ingress = value

    # Create a method to return the ssl directory list
    @property
    def ssl_directory_list(self):
        return self._ssl_directory_list

    # Create a property to return the ldap number
    @property
    def ldap_number(self):
        return self._ldap_number

    @ldap_number.setter
    def ldap_number(self, value):
        self._ldap_number = value

    def collect_namespace(self, namespace=None):
        # namespace parameter is none when silent mode is NOT selected, hence the conditions to skip conditions if silent mode is selected
        try:
            self._logger.info("Gathering namespace information")
            if namespace is None:
                print()
                print(Panel.fit("Namespace"))
                print()
                try:
                    self._current_namespace = self._k.current_namespace
                    self._logger.info(f"Current namespace from kubeconfig: {self._current_namespace}")
                except Exception as e:
                    self._current_namespace = None
                    self._logger.info("Gathering namespace information failed")


            if self._platform in ["OCP"]:
                invalid_namespaces = ["services", "default", "calico-system", "ibm-cert-store", "ibm-observe",
                                      "ibm-system", "ibm-odf-validation-webhook"]
                invalid_namespace_to_start_with = ["openshift-", "kube-"]
            else:
                invalid_namespaces = ["services", "default", "calico-system"]
                invalid_namespace_to_start_with = ["kube-"]

            while True:
                if namespace is None:
                    answer = Prompt.ask("Enter your namespace", default=self._current_namespace)
                    if self._script_type != "deploy":
                        namespace_exists = self._k.check_namespace_exists(namespace=answer)
                        if not namespace_exists:
                            print()
                            print(Panel.fit(f"Namespace '{answer}' does not exist.\n"
                                            f"Enter a valid namespace for script to proceed.", style="bold red"))
                            print()
                            continue
                else:
                    # silent install check for namespace will not loop more than once if invalid namespace is provided
                    if self._script_type != "deploy":
                        self._logger.info(f"Checking if namespace: {namespace} exists.")
                        namespace_exists = self._k.check_namespace_exists(namespace=namespace)
                        if not namespace_exists:
                            self._logger.debug(f"Namespace '{namespace}' does not exist.")
                            print()
                            print(Panel.fit(f"Namespace '{namespace}' does not exist.\n"
                                            f"Enter a valid namespace for script to proceed.", style="bold red"))
                            print()
                            exit(1)
                    answer = namespace

                answer = answer.strip()
                # Start of namespace validation
                # Check if the answer is not empty after stripping whitespace
                if answer == '':
                    self._logger.debug(f"Namespace cannot be empty. Please try again")
                    print()
                    print("[prompt.invalid]Namespace cannot be empty. Please try again")
                    print()
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if the answer is not in the list of invalid namespaces
                if any(answer in value for value in invalid_namespaces):
                    invalid_msg = ""
                    for value in invalid_namespaces:
                        invalid_msg += f"- {value}\n"
                    invalid_msg.strip()

                    print()
                    print(f"[prompt.invalid]Namespace cannot be any of the following. Please try again.\n{invalid_msg}")
                    print()
                    self._logger.debug(f"Namespace cannot be any of the following: {invalid_msg}")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                if any(answer.startswith(value) for value in invalid_namespace_to_start_with):
                    invalid_msg = ""
                    for value in invalid_namespace_to_start_with:
                        invalid_msg += f"- {value}\n"
                    invalid_msg = invalid_msg.strip()
                    print()
                    print(
                        f"[prompt.invalid]Namespace cannot start with any of the following. Please try again.\n{invalid_msg}")
                    print()
                    self._logger.debug(f"Namespace cannot start with any of the following: {invalid_msg}")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if namespace is only numbers
                if answer.isnumeric():
                    print()
                    print("[prompt.invalid]Namespace cannot be a number. Please try again.")
                    print()
                    self._logger.debug(f"Namespace cannot be a number. Please try again.")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if namespace is more than 1 word
                if " " in answer:
                    print()
                    print("[prompt.invalid]Namespace cannot contain spaces. Use '-'. Please try again.")
                    print()
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # Check if namespace has an underscore
                if "_" in answer:
                    print()
                    print("[prompt.invalid]Namespace cannot contain '_'. Use '-'. Please try again.")
                    print()
                    self._logger.debug(f"Namespace cannot be a number. Please try again.")
                    if namespace is None:
                        continue
                    else:
                        exit(0)

                # for all scripts using this function other than deploy operator we need to check if namespace exists
                self._namespace = answer
                self._logger.info(f"Namespace entered: {self._namespace}")
                break

        except Exception as e:
            self._logger.exception(
                f"Exception from gathering deployment details in collect namespace function -  {str(e)}")


    def parse_db_files(self, path, db_files):
        try:
            db_type = set()
            for idx, db_file in enumerate(db_files):
                # open the ldap file
                with open(os.path.join(path, db_file)) as fd:
                    # parse the ldap file
                    db_dict = xmltodict.parse(fd.read())

                    db_type.add(db_dict['configuration']['@implementorid'])
            result = 0
            if len(db_type) > 1:
                print(
                    "Multiple database types found in the database files.  Please check the database files and try again.")
                exit(1)
            else:
                xml_type = list(db_type)[0]
                if xml_type == "mssql":
                    result = 3
                elif xml_type in ["oracle", "oracle_ssl", "oracle_rac"]:
                    result = 5
                elif xml_type == "db2":
                    result = 1
                elif xml_type == "db2hadr":
                    result = 2
                else:
                    print("Unknown DB type")
                self._db_type = self.DatabaseType(result).name



        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in parse_db_files function -  {str(e)}")

    def parse_ldap_files(self, path, ldap_files):
        try:
            result = 0
            for idx, ldap_file in enumerate(ldap_files):
                # open the ldap file
                with open(os.path.join(path, ldap_file)) as fd:

                    # Determine the LDAP ID
                    if idx == 0:
                        ldap_id = "ldap"
                    else:
                        ldap_id = f"ldap{idx + 1}"

                    # parse the ldap file
                    ldap_dict = xmltodict.parse(fd.read())
                    # Determine LDAP type
                    xml_type = ldap_dict['configuration']['@implementorid']
                    if "tivoli" in xml_type:
                        result = 2
                    # Need to search the string for .ad to support federated.ad and standalone.ad
                    elif any(x in xml_type for x in ["adam", "activedirectory", ".ad"]):
                        result = 1
                    elif "ca" in xml_type:
                        result = 7
                    elif "edirectory" in xml_type:
                        result = 3
                    elif "oid" in xml_type:
                        result = 4
                    elif any(x in xml_type for x in ["oracledirectoryse","sunjavads"]):
                        result = 5
                    else:
                        print(Text(f"Unable to parse XML file: {ldap_file}\n"
                                   f"Unknown LDAP type", style='bold red'))

                    # Determine if SSL is enabled
                    for prop in ldap_dict['configuration']['property']:
                        if prop['@name'] == "SSLEnabled":
                            if prop['value'] == "true":
                                ssl = True
                                self._ssl_directory_list.append(ldap_id)
                            else:
                                ssl = False
                            break
                        else:
                            ssl = False

                    # Add the ldap info to the ldap_info list
                    self.ldap_info.append(
                        self.Ldap(
                            self.Ldap.ldapTypes(result),
                            ssl,
                            ldap_id
                        )
                    )
        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in parse_ldap_files function -  {str(e)}")

    # Create a function to parse optional components
    def __parse_optional_components__(self, choices=None):
        try:
            if choices is None:
                print("No optional components chosen")
            else:
                # loop through choices and add to optional components list based on Enum value
                for choice in choices:
                    self.optional_components.add(self.OptionalComponents(choice).name)

            return self.optional_components

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in set_optional_components function -  {str(e)}")

    # Function to collect Egress related info
    def collect_egress_info(self):
        try:
            if self.fncm_version in ["5.5.12", "5.6.0"]:
                print(Panel.fit("Restricted Internet Access"))
                print()
                print("Restricted Internet Access is a security feature that restricts outbound network access.")
                print()
                result = Confirm.ask("Do you want to enable Restricted Internet Access")
                if result:
                    self._egress_support = True

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in FNCM S collect version function -  {str(e)}")
    
    def collect_networkpolicy_info(self):
        try:
            if self.fncm_version in ["5.7.0"]:
                print(Panel.fit("Generate Network Policies Templates"))
                print()
                print("Network Policies are used to control the network traffic to and from the pods in your cluster.")
                print("Network Policies are not installed automatically by the operator, but can be generated.")
                print("The operator can generate network policy templates for both egress and ingress that can be applied manually.")
                print()
                print()
                result = Confirm.ask("Do you want to generate Network Policies templates for your deployment?")
                if result:
                    self._np_support = True

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in FNCM S collect version function -  {str(e)}")

    # Create a function to check if the dsicovery url is valid
    def check_discovery_url(self, url: str):
        try:

            # Check if the url is valid
            if url is None:
                return False
            else:
                if url.endswith(".well-known/openid-configuration"):
                    return True
                else:
                    return False
        except Exception as e:
            print(f"Exception from check_discovery_url function - {str(e)}")
            return False

    # Create a function to gather optional components from the user
    def collect_auth_type(self):
        try:
            if self._fncm_version != "5.5.8":
                print(Panel.fit("Authentication Type"))
                while True:
                    print()
                    print("Your Authentication Type determines how users login and where they are stored.")
                    print()
                    print("Select an Authentication Type")
                    print(f'1. LDAP')
                    print(f'2. LDAP + IDP')
                    print(f'3. SCIM + IDP')

                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]3[/b]]')

                    if 1 <= result <= 3:
                        self._auth_type = self.AuthType(result).name
                        break

                    print("[prompt.invalid] Number must be between [[b]1[/b] and [b]3[/b]]")


            else:
                # SCIM is not supported in 5.5.9 and below
                print(Panel.fit("Authentication Type"))
                while True:
                    print()
                    print("Your Authentication Type determines how users login and where they are stored.")
                    print()
                    print("Select an Authentication Type")
                    print(f'1. LDAP')
                    print(f'2. LDAP + IDP')

                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]2[/b]]')

                    if 1 <= result <= 2:
                        self._auth_type = self.AuthType(result).name
                        break

                    print("[prompt.invalid] Number must be between [[b]1[/b] and [b]2[/b]]")

        except Exception as e:
            # Create log for exception
            self._logger.exception(
                f"Exception from gather script in auth_type function -  {str(e)}")

    # Create a function to gather optional components from the user
    def collect_optional_components(self):
        try:
            choices = {1, 2, 3}
            if self._fncm_version == "5.5.8":
                print(Panel.fit("Optional Components"))

                num_components = 4

                while True:
                    print()
                    print("CPE, BAN and GraphQL are required in FNCM 5.5.8")
                    print("Select zero or more Optional Components")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CSS {":heavy_check_mark:" if 4 in choices else ""}')
                    print(f'2. CMIS {":heavy_check_mark:" if 5 in choices else ""}')
                    print(f'3. Task Manager {":heavy_check_mark:" if 6 in choices else ""}')
                    print(f'4. External Share {":heavy_check_mark:" if 7 in choices else ""}')

                    result = IntPrompt.ask(f"Enter a valid option [[b]1[/b] and [b]{num_components}[/b]]")

                    if result == 0:
                        break

                    if 1 <= result <= num_components:
                        # remove from set if already present
                        # since we added cpe, ban and graphql to the list we are checking the result +3 which maps to css cmis and tm
                        # for this use case only since we have content pattern components as a must in 5.5.8
                        if (result + 3) in choices:
                            choices.remove(result + 3)
                        else:
                            choices.add(result + 3)
                        clear(self._console)
                        print(Panel.fit("Optional Components"))
                    else:
                        print(f"[prompt.invalid] Number must be between [[b]1[/b] and [b]{num_components}[/b]]")
            elif self._fncm_version in ["5.5.11", "5.5.12"]:
                # in this case we have the option to select only cpe /ban/graphql instead having all three as a must
                # default is having all three selected
                print(Panel.fit("Components"))

                num_components = 7

                while True:
                    print()
                    print("Select zero or more FileNet Content Management Components")
                    print("Enter a number to toggle selection")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CPE {":heavy_check_mark:" if 1 in choices else ""}')
                    print(f'2. GraphQL {":heavy_check_mark:" if 2 in choices else ""}')
                    print(f'3. Navigator {":heavy_check_mark:" if 3 in choices else ""}')
                    print(f'4. CSS {":heavy_check_mark:" if 4 in choices else ""}')
                    print(f'5. CMIS {":heavy_check_mark:" if 5 in choices else ""}')
                    print(f'6. Task Manager {":heavy_check_mark:" if 6 in choices else ""}')
                    print(f'7. External Share {":heavy_check_mark:" if 7 in choices else ""}')

                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]{}[/b]]'.format(num_components))

                    if result == 0:
                        if any(item in [2, 4, 5] for item in choices) and (1 not in choices):
                            print(
                                "\n[prompt.invalid]IBM Content Platform Engine is required to deploy IBM Content Service GraphQL, IBM Content Management Interoperability Services or IBM Content Search Services.")
                            continue

                        if 6 in choices and 3 not in choices:
                            print(
                                "\n[prompt.invalid]IBM Content Navigator is required to deploy IBM Task Manager.")
                            continue

                        if 7 in choices and not {3, 1}.issubset(choices):
                            print(
                                "\n[prompt.invalid]IBM Content Navigator is required to deploy IBM External Share.")
                            continue

                        break

                    if 1 <= result <= num_components:
                        # remove from set if already present
                        if result in choices:
                            choices.remove(result)
                        else:
                            choices.add(result)
                        clear(self._console)
                        print(Panel.fit("Components"))
                    else:
                        print(f'[prompt.invalid] Number must be between [[b]1[/b] and [b]{num_components}[/b]]')
            else:
                print(Panel.fit("Components"))

                num_components = 9

                while True:
                    print()
                    print("Select zero or more FileNet Content Management Components")
                    print("Enter a number to toggle selection")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CPE {":heavy_check_mark:" if 1 in choices else ""}')
                    print(f'2. GraphQL {":heavy_check_mark:" if 2 in choices else ""}')
                    print(f'3. Navigator {":heavy_check_mark:" if 3 in choices else ""}')
                    print(f'4. CSS {":heavy_check_mark:" if 4 in choices else ""}')
                    print(f'5. CMIS {":heavy_check_mark:" if 5 in choices else ""}')
                    print(f'6. Task Manager {":heavy_check_mark:" if 6 in choices else ""}')
                    print(f'7. External Share {":heavy_check_mark:" if 7 in choices else ""}')
                    print(f'8. IER {":heavy_check_mark:" if 8 in choices else ""}')
                    print(f'9. ICCSAP {":heavy_check_mark:" if 9 in choices else ""}')

                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]{}[/b]]'.format(num_components))

                    if result == 0:
                        if any(item in [2, 4, 5] for item in choices) and (1 not in choices):
                            print(
                                "\n[prompt.invalid]IBM Content Platform Engine is required to deploy IBM Content Service GraphQL, IBM Content Management Interoperability Services or IBM Content Search Services.")
                            continue

                        if 6 in choices and 3 not in choices:
                            print(
                                "\n[prompt.invalid]IBM Content Navigator is required to deploy IBM Task Manager.")
                            continue

                        if 7 in choices and not {3, 1}.issubset(choices):
                            print(
                                "\n[prompt.invalid]IBM Content Navigator is required to deploy IBM External Share.")
                            continue

                        if 8 in choices and not {3, 1}.issubset(choices):
                            print(
                                "\n[prompt.invalid]IBM Content Navigator and IBM Content Platform Engine is required to deploy IBM Enterprise Records.")
                            continue

                        if 9 in choices and not {3, 1}.issubset(choices):
                            print(
                                "\n[prompt.invalid]IBM Content Navigator and IBM Content Platform Engine is required to deploy IBM Content Collector for SAP.")
                            continue

                        break

                    if 1 <= result <= num_components:
                        # remove from set if already present
                        if result in choices:
                            choices.remove(result)
                        else:
                            choices.add(result)
                        clear(self._console)
                        print(Panel.fit("Components"))
                    else:
                        print(f'[prompt.invalid] Number must be between [[b]1[/b] and [b]{num_components}[/b]]')

            if any(item in [3, 4, 6] for item in choices):
                print()
                print(Panel.fit("Component Options"))

            if 3 in choices:
                print()
                sendmailresult = Confirm.ask("Add Java SendMail support for IBM Content Navigator?")
                if sendmailresult:
                    self._sendmail_support = True
            if 4 in choices:
                print()
                iccresult = Confirm.ask("Add IBM Content Collector support for IBM Content Search Services?")
                if iccresult:
                    self._icc_support = True
            if 6 in choices:
                print()
                tmresult = Confirm.ask("Add custom groups and users for IBM Task Manager?")
                if tmresult:
                    self._tm_custom_groups = True

            self.__parse_optional_components__(choices)
        except Exception as e:
            # Create log for exception
            self._logger.exception(
                f"Exception from gather script in optional_components_menu function -  {str(e)}")

    # Create a function to gather init and verify content from the user
    def collect_init_verify_content(self):
        try:
            if self._fncm_version == "5.5.8" or "cpe" in self._optional_components:
                print(Panel.fit("Initialize and Verify Content"))
                print()
                print("Content Initialization is recommended and includes the following steps:")
                print()
                print(" - Creation of the P8 domain")
                print(" - Creation of the directory services")
                print(" - Assignments of users/groups to the P8 domain and object store(s)")
                print(" - Creation of the object store(s)")
                print(" - Creation/addition of add-ons for each object store")
                print(" - Optional Enablement of Process Engine Workflow for each object store")
                print(
                    " - Creation of Content Search Services servers, index areas, and enabling of Content-based Retrieval (CBR) for each object store")
                print(" - Creation of Navigator desktop")
                print()

                self._content_initialize = (Confirm.ask("Do you want to initialize content?"))

                print()
                print(
                    "Content Verification process ensures that the FNCM and BAN components are functioning correctly and includes:")
                print()
                print(" - Creation of a CPE folder & CPE document")
                print(" - CBR search")
                print(" - Verifying the Process Engine Workflow configuration")
                print(" - Validation of the BAN desktop")
                print()

                if self._content_initialize:
                    self._content_verification = (Confirm.ask("Do you want to verify content?"))
            else:
                self._content_initialize = False
                self._content_verification = False

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in check_init_verify function -  {str(e)}")

    # Create a function to gather os number from the user
    def collect_os_number(self):
        try:
            # only ask in 5.5.8 or in releases above that if cpe graphql is selected
            if self._fncm_version == "5.5.8" or ("cpe" in self._optional_components):
                print()
                if "ier" in self._optional_components:
                    print("Deployments including Content Platform Engine, require at least one object store.\n\n"
                          "Deployments including Enterprise Records, require at least two object stores.\n"
                          " - Record Object Store (ROS)\n"
                          " - File Plan Object Store (FPOS)")
                    default = 2
                else:
                    print("Deployments including Content Platform Engine, require at least one object store.")
                    default = 1
                while True:
                    print()
                    result = IntPrompt.ask(
                        "How many Object Stores do you want to deploy?", default=default
                    )
                    if result >= default:
                        self._os_number = result
                        break
                    print(f"[prompt.invalid]Number of Object Stores must be equal or greater than [[b]{default}[/b]]")

        except Exception as e:
            self._logger.exception(
                f'Exception from gather script in object_store_menu function -  {str(e)}')

    # Create a function to gather db info from the user
    def collect_db_info(self):
        self.collect_db_type()
        self.collect_os_number()
        self.collect_db_ssl_info()

    # Create a private function to collect db ssl info from the user
    def collect_db_ssl_info(self):
        print()
        self._db_ssl = Confirm.ask("Do you want to enable SSL for your database selection?")

        if self._db_ssl:
            # if we are using 5.5.8 no custom component deployments so existing logic for this case
            if self._fncm_version == "5.5.8":
                self._ssl_directory_list.append("gcd")
                self._ssl_directory_list.append("icn")
            else:
                if "cpe" in self._optional_components:
                    self._ssl_directory_list.append("gcd")
                if "ban" in self._optional_components:
                    self._ssl_directory_list.append("icn")
            for i in range(self._os_number):
                if i == 0:
                    self._ssl_directory_list.append("os")
                else:
                    self._ssl_directory_list.append(f"os{i + 1}")

    # Function to collect the fncm version
    def collect_fncm_version(self):
        try:
            print(Panel.fit("Version"))
            while True:
                print()
                print("Which version of FileNet Content Manager do you want to deploy?")
                print("1. 5.5.8")
                print("2. 5.5.11")
                print("3. 5.5.12")
                print("4. 5.6.0")
                print("5. 5.7.0")
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]5[/b]]')

                if 1 <= result <= 5:
                    self._fncm_version = self.Version.FNCMVersion(result).name
                    break

                print("[prompt.invalid] Number must be between [[b]1[/b] and [b]5[/b]]")


        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in FileNet Content Manager collect version function -  {str(e)}")

    # Function to collect FIPS related info
    def collect_fips_info(self):
        try:
            if self.fncm_version in ["5.5.12", "5.6.0", "5.7.0"]:
                print(Panel.fit("FIPS (Federal Information Processing Standard)"))
                print()
                print("FIPS is a U.S. government computer security standard.")
                print("Make sure your K8s Cluster has FIPS enabled nodes, before you enable FIPS on your deployment.")
                print()
                result = Confirm.ask("Do you want to configure a FIPS enabled deployment")
                if result:
                    self._fips_support = True

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in FNCM S collect version function -  {str(e)}")

    # Create a function to gather db_type from the user
    def collect_license_model(self, version_data):
        try:

            print(Panel.fit("License and Version"))
            print()

            self._fncm_version = version_data.get("VERSION", '5.7.0')
            display = version_data.get("DISPLAY", '5.7.0')

            print(Panel.fit(Text(f"Detected IBM FileNet Content Manager Version: {display}"), style="bold cyan"))
            print()

            if self._fncm_version == "5.5.8":
                fncm_license_url = Text(
                    "https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KPMK",
                    style="link https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KPMK")
                icf_license_url = Text(
                    "https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KQ34",
                    style="link https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KQ34")

                print(Panel.fit(
                    f"IMPORTANT: Review the license  information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}"))

            elif self._fncm_version == "5.5.11":
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_5_11",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_5_11")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_5_11",
                                       style="link https://ibm.biz/CPE_ICF_License_5_5_11")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_11",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_11")

                print(Panel.fit(
                    f"IMPORTANT: Review the license information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}"))

            elif self._fncm_version == "5.5.12":
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_5_12",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_5_12")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_5_12",
                                       style="link https://ibm.biz/CPE_ICF_License_5_5_12")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_12",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_12")
                cp4ba_license_url = Text("https://ibm.biz/cp4ba_license_2302",
                                         style="link https://ibm.biz/cp4ba_license_2302")

                print(Panel.fit(
                    f"IMPORTANT: Review the license  information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}\n"
                    f"IBM Cloud Pak for Business Automation license information here: {cp4ba_license_url}"))
            elif self._fncm_version == "5.6.0":
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_6_0",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_6_0")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_6_0",
                                       style="link https://ibm.biz/CPE_ICF_License_5_6_0")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_6_0",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_6_0")
                ier_license_url = Text("https://ibm.biz/ier_license_521",
                                       style="link https://ibm.biz/ier_license_521")
                iccsap_license_url = Text("https://ibm.biz/iccsap_license_4002",
                                          style="link https://ibm.biz/iccsap_license_4002")
                cp4ba_license_url = Text("https://ibm.biz/cp4ba_license_2400",
                                         style="link https://ibm.biz/cp4ba_license_2400")

                print(Panel.fit(
                    f"IMPORTANT: Review the license information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}\n"
                    f"IBM Enterprise Records information here: {ier_license_url}\n"
                    f"IBM Content Collector for SAP license information here: {iccsap_license_url}\n"
                    f"IBM Cloud Pak for Business Automation license information here: {cp4ba_license_url}"))
            else:
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_7_0",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_7_0")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_7_0",
                                       style="link https://ibm.biz/CPE_ICF_License_5_7_0")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_7_0",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_7_0")
                ier_license_url = Text("https://ibm.biz/ier_license_521",
                                       style="link https://ibm.biz/ier_license_521")
                iccsap_license_url = Text("https://ibm.biz/iccsap_license_4002",
                                          style="link https://ibm.biz/iccsap_license_4002")
                cp4ba_license_url = Text("https://ibm.biz/cp4ba_license_2500",
                                         style="link https://ibm.biz/cp4ba_license_2500")

                print(Panel.fit(
                    f"IMPORTANT: Review the license information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}\n"
                    f"IBM Enterprise Records information here: {ier_license_url}\n"
                    f"IBM Content Collector for SAP license information here: {iccsap_license_url}\n"
                    f"IBM Cloud Pak for Business Automation license information here: {cp4ba_license_url}"))

            print()

            self._accept_license = Confirm.ask("Do you accept the International Program License?")

            if not self._accept_license:
                print("\n[prompt.invalid]You must accept the International Program License to continue.")
                exit(1)

            while True:
                print()
                print("Select a License Type")
                print("1. ICF")
                print("2. FNCM")
                print("3. CP4BA")
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]3[/b]]')

                if 1 <= result <= 3:
                    model = self.LicenseModel(result).name
                    break

                print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]3[/b]]")

            while True:
                print()
                print("Select a License Metric")
                if result == 3:
                    print("1. NonProd")
                    print("2. Prod")
                    print("3. User")
                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]3[/b]]')
                    if 1 <= result <= 3:
                        metric = self.LicenseMetricCP4BA(result).name
                        break

                    print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]3[/b]]")

                else:
                    print("1. PVUProd")
                    print("2. PVUNonProd")
                    print("3. UVU")
                    print("4. CU")
                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]4[/b]]')

                    if 1 <= result <= 4:
                        metric = self.LicenseMetricFNCM(result).name
                        break

                    print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]4[/b]]")

            self._license_model = f"{model}.{metric}"

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in license model function -  {str(e)}")

    # Create a function to gather db_type from the user
    def collect_db_type(self):
        try:
            print(Panel.fit("Database"))
            while True:
                if self._fips_support:
                    print()
                    print("Select a Database Type")
                    print("1. IBM Db2")
                    print("2. IBM Db2 HADR")
                    print("3. Microsoft SQL Server")
                    print("4. PostgreSQL")
                    # Adding DB2 RDS and DB2 RDS HADR to the list of database types the user can select from ( only from 5.7.0)
                    if self.fncm_version in ["5.7.0"]:
                        # Adding Oracle SSL for FIPS in 5.7.0
                        print("5. Oracle")
                        print("6. IBM Db2 RDS")
                        print("7. IBM Db2 RDS HADR")
                        result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]7[/b]]')
                    else:
                        result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]4[/b]]')

                    if self.fncm_version in ["5.7.0"]:
                        if 1 <= result <= 7:
                            self._db_type = self.DatabaseType(result).name
                            break
                    else:
                        if 1 <= result <= 4:
                            self._db_type = self.DatabaseType(result).name
                            break

                    if self.fncm_version in ["5.7.0"]:
                        print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]6[/b]]")
                    else:
                        print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]4[/b]]")
                else:
                    print()
                    print("Select a Database Type")
                    print("1. IBM Db2")
                    print("2. IBM Db2 HADR")
                    print("3. Microsoft SQL Server")
                    print("4. PostgreSQL")
                    print("5. Oracle")
                    if self.fncm_version in ["5.7.0"]:
                        print("6. IBM Db2 RDS")
                        print("7. IBM Db2 RDS HADR")
                        result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]7[/b]]')
                    else:
                        result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]5[/b]]')

                    if self.fncm_version in ["5.7.0"]:
                        if 1 <= result <= 7:
                            self._db_type = self.DatabaseType(result).name
                            break
                    else:
                        if 1 <= result <= 5:
                            self._db_type = self.DatabaseType(result).name
                            break
                    if self.fncm_version in ["5.7.0"]:
                        print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]7[/b]]")
                    else:
                        print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]5[/b]]")


        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in collect DB function -  {str(e)}")

    # Create a function to gather platform and ingress enabled from user
    def collect_platform_ingress(self):
        try:
            print(Panel.fit("Platform"))
            while True:
                print()
                print("Select a Platform Type")
                print("1. OCP")
                print("2. CNCF")
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]2[/b]]')

                if 1 <= result <= 2:
                    self._platform = self.Platform(result).name
                    break

                print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]2[/b]]")

            if self._platform == "other" and self.fncm_version != "5.5.8":
                print()
                self._ingress = Confirm.ask("Do you want to enable ingress creation?")


        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in collect_platform_ingress function -  {str(e)}")

    # Create a function to gather idp_number from user
    def collect_idp_number(self):
        try:
            if self._auth_type == "SCIM_IDP":
                self._idp_number = 1
                self._scim_number = 1
                self._ssl_directory_list.append("scim")
            else:
                print(Panel.fit("Identity Provider (IDP)"))
                while True:
                    print()
                    result = IntPrompt.ask(
                        "How many IDP's do you want to configure?", default=1
                    )
                    if result >= 1:
                        self._idp_number = result
                        break
                    print("[prompt.invalid]Number of IDP's must be greater than 0")
        except Exception as e:
            self._logger.exception(
                f'Exception from gather script in collect_idp_number function -  {str(e)}')

    # Create a function to gather idp_number from user
    def collect_idp_discovery(self):
        try:
            for i in range(self._idp_number):
                if i == 0:
                    idp_id = "idp"
                else:
                    idp_id = f"idp{i + 1}"

                self._ssl_directory_list.append(idp_id)

                print()
                print(Panel.fit(f"IDP ID: {idp_id}"))

                while True:
                    print()
                    print("Discovery Endpoints can used to retrieve the IDP configuration.\n"
                          "If you do not have a discovery endpoint, you can still configure the IDP manually.\n"
                          "Discovery endpoints URLs typically end with '/.well-known/openid-configuration'")
                    print()
                    discovery_enabled = Confirm.ask("Does this IDP support discovery?")

                    if discovery_enabled:
                        print()
                        url = Prompt.ask("Enter a valid URL for the IDP discovery endpoint")

                        if self.check_discovery_url(url):
                            idp = self.Idp(discovery_enabled, idp_id, url)
                            idp.parse_discovery_url()
                            self._idp_info.append(idp)
                            break
                        else:
                            print("\n[prompt.invalid]Discovery URL is invalid")
                            print(
                                '\n[prompt.invalid]Make sure your discovery URL ends with ".well-known/openid-configuration"')
                    else:
                        idp = self.Idp(discovery_enabled, idp_id)
                        self._idp_info.append(idp)
                        break



        except Exception as e:
            self._logger.exception(
                f'Exception from gather script in collect_idp function -  {str(e)}')

    # Create a function to gather ldap_number from user
    def collect_ldap_number(self):

        try:
            print(Panel.fit("LDAP"))
            while True:
                print()
                result = IntPrompt.ask(
                    "How many LDAP's do you want to configure?", default=1
                )
                if result >= 1:
                    self._ldap_number = result
                    break
                print("[prompt.invalid]Number of LDAP's must be greater than 0")
        except Exception as e:
            self._logger.exception(
                f'Exception from gather script in object_store_menu function -  {str(e)}')

    # Create a function to gather ldap_type from the user
    def collect_ldap_type(self):
        # loop through the number of ldaps and collect the type
        try:
            for i in range(self._ldap_number):
                if i == 0:
                    ldap_id = "ldap"
                else:
                    ldap_id = f"ldap{i + 1}"

                print()
                print(Panel.fit(f"LDAP ID: {ldap_id}"))
                while True:
                    print()
                    print("Select a LDAP Type")
                    print("1. Microsoft Active Directory")
                    print("2. IBM Security Verify Directory")
                    print("3. NetIQ eDirectory")
                    print("4. Oracle Internet Directory")
                    print("5. Oracle Directory Server Enterprise Edition")
                    print("6. Oracle Unified Directory")
                    if self._fncm_version == "5.5.8":
                        result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]6[/b]]')

                        if 1 <= result <= 6:
                            ldap_type = self.Ldap.ldapTypes(result)
                            print()
                            ldap_ssl = Confirm.ask("Do you want to enable SSL for this LDAP?")

                            if ldap_ssl:
                                self._ssl_directory_list.append(ldap_id)

                            # add the ldap type and ssl to the list
                            self._ldap_info.append((self.Ldap(ldap_type, ldap_ssl, ldap_id)))
                            break

                        print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]6[/b]]")
                    else:
                        print("7. CA eTrust")
                        result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]7[/b]]')

                        if 1 <= result <= 7:
                            ldap_type = self.Ldap.ldapTypes(result)
                            print()
                            ldap_ssl = Confirm.ask("Do you want to enable SSL for this LDAP?")

                            if ldap_ssl:
                                self._ssl_directory_list.append(ldap_id)

                            # add the ldap type and ssl to the list
                            self._ldap_info.append((self.Ldap(ldap_type, ldap_ssl, ldap_id)))
                            break

                        print("\n[prompt.invalid]Number must be between [[b]1[/b] and [b]7[/b]]")

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in ldap_menu function -  {str(e)}")

    # Create a function to print all the deployment options
    def print_deployment_options(self):
        print(f"Optional Components: {self.optional_components}")

        # Print all ldap info
        for i in range(self._ldap_number):
            print(f"LDAP {i + 1}:")
            self._ldap_info[i].display()
        print(f"Database Type: {self.db_type}")
        print(f"OS Number: {self.os_number}")
        print(f"License Model: {self.license_model}")
        print(f"Content Initialize: {self.content_initialize}")
        print(f"Content Verification: {self.content_verification}")
        print(f"Platform: {self.platform}")
        print(f"Ingress: {self.ingress}")
        print("")

    # Create a function to return all the deployment options as a dictionary
    def to_dict(self):

        ldap_list = []
        for i in range(self._ldap_number):
            ldap_list.append(self._ldap_info[i].to_dict())

        idp_list = []
        for i in range(self._idp_number):
            idp_list.append(self._idp_info[i].to_dict())

        return {
            "optional_components": self.optional_components,
            "ldap_info": ldap_list,
            "idp_info": idp_list,
            "db_type": self.db_type,
            "os_number": self.os_number,
            "db_ssl": self.db_ssl,
            "np_support": self.np_support,
            "fips_support": self.fips_support,
            "egress_support": self.egress_support,
            "license_model": self.license_model,
            "fncm_version": self.fncm_version,
            "sendmail_support": self.sendmail_support,
            "content_initialize": self.content_initialize,
            "content_verification": self.content_verification,
            "platform": self.platform,
            "ingress": self.ingress,
        }


