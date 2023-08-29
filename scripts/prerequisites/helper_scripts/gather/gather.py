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
# Create a class to gather all deployment options from the user
#  - the class should have a constructor that takes the filename as an argument
#  - the class should have a method to gather the deployment options from the user
#  - the class should have a method to return the deployment options
from enum import Enum

import xmltodict
from rich import print
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt
from rich.text import Text

from helper_scripts.utilities.utilites import clear


# create a class to gather all deployment options from the user
class GatherOptions:
    # Inner Class to take care of FNCM version.
    class Version:
        FNCMVersion = Enum(
            value='FNCMVersion',
            names=[("5.5.8", 1), ("5.5.11", 2)]
        )

        def __init__(self, fncm_version: FNCMVersion):
            self._fncm_version = fncm_version

    # Create an inner class to gather ldap info from the user
    class Ldap:
        ldapTypes = Enum(
            value='LdapType',
            names=[
                ('Microsoft Active Directory', 1),
                ('IBM Security Directory Server', 2),
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

    # Create an enum for all the database types
    class DatabaseType(Enum):
        db2 = 1
        db2HADR = 2
        oracle = 3
        sqlserver = 4
        postgresql = 5

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

    # Create an enum for all platform types
    class Platform(Enum):
        OCP = 1
        ROKS = 2
        other = 3

    def __init__(self, logger, console):
        self._optional_components = []
        self._ldap_info = []
        self._ldap_number = 1
        self._db_type = None
        self._db_ssl = False
        self._os_number = 1
        self._content_initialize = False
        self._content_verification = False
        self._platform = self.Platform(1).name
        self._license_model = None
        self._ingress = False
        self._logger = logger
        self._console = console
        self._ssl_directory_list = []
        self._fncm_version = "5.5.11"
        self._sendmail_support = False
        self._icc_support = False
        self._tm_custom_groups = False

    # Create a function to gather all deployment options from the user
    @property
    def license_model(self):
        return self._license_model

    @property
    def fncm_version(self):
        return self._fncm_version

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
    def ldap_info(self):
        return self._ldap_info

    @ldap_info.setter
    def ldap_info(self, value):
        self._ldap_info = value

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
                    result = 4
                elif xml_type in ["oracle", "oracle_ssl", "oracle_rac"]:
                    result = 3
                elif xml_type == "db2":
                    result = 1
                elif xml_type == "db2hadr":
                    result = 2
                else:
                    print("Unknown LDAP type")
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
                    elif "adam" in xml_type:
                        result = 1
                    elif "activedirectory" in xml_type:
                        result = 1
                    elif "ca" in xml_type:
                        result = 7
                    elif "edirectory" in xml_type:
                        result = 3
                    elif "oid" in xml_type:
                        result = 4
                    elif "oracledirectoryse" in xml_type:
                        result = 5
                    else:
                        print("Unknown LDAP type")

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
                    self.optional_components.append(self.OptionalComponents(choice).name)

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in set_optional_components function -  {str(e)}")

    # Create a function to gather optional components from the user
    def collect_optional_components(self):
        try:
            choices = set([1, 2, 3])
            if self._fncm_version != "5.5.8":
                # in this case we have the option to select only cpe /ban/graphql instead having all three as a must
                # default is having all three selected
                print(Panel.fit("Components"))
                while True:
                    print()
                    print("Select zero or more FileNet Content Management Components")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CPE {"*" if 1 in choices else ""}')
                    print(f'2. GraphQL {"*" if 2 in choices else ""}')
                    print(f'3. Navigator {"*" if 3 in choices else ""}')
                    print(f'4. CSS {"*" if 4 in choices else ""}')
                    print(f'5. CMIS {"*" if 5 in choices else ""}')
                    print(f'6. Task Manager {"*" if 6 in choices else ""}')
                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]6[/b]]')

                    if result == 0:
                        if any(item in [2, 4, 5] for item in choices) and (1 not in choices):
                            print(
                                "\n[prompt.invalid]IBM Content Platform Engine is required to deploy IBM Content Service GraphQL, IBM Content Management Interoperability Services or IBM Content Search Services.")
                            continue

                        if 6 in choices and 3 not in choices:
                            print(
                                "\n[prompt.invalid]IBM Content Navigator is required to deploy IBM Task Manager.")
                            continue

                        break

                    if 1 <= result <= 6:
                        # remove from set if already present
                        if result in choices:
                            choices.remove(result)
                        else:
                            choices.add(result)
                        clear(self._console)
                        print(Panel.fit("Components"))
                    else:
                        print("[prompt.invalid] Number must be between [[b]1[/b] and [b]6[/b]]")
            else:
                print(Panel.fit("Optional Components"))
                while True:
                    print()
                    print("CPE, BAN and GraphQL are required in 5.5.8")
                    print("Select zero or more Optional Components")
                    print("Enter [[b]0[/b]] to finish selection")
                    print(f'1. CSS {"*" if 4 in choices else ""}')
                    print(f'2. CMIS {"*" if 5 in choices else ""}')
                    print(f'3. Task Manager {"*" if 6 in choices else ""}')
                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]3[/b]]')

                    if result == 0:
                        break

                    if 1 <= result <= 3:
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
                        print("[prompt.invalid] Number must be between [[b]1[/b] and [b]3[/b]]")

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
                self._content_initialize = (Confirm.ask("Do you want to initialize content?"))

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
            if self._fncm_version == "5.5.8" or (
                    "cpe" in self._optional_components and "graphql" in self._optional_components):
                while True:
                    print()
                    result = IntPrompt.ask(
                        "How many Object Stores do you want to deploy?", default=1
                    )
                    if result >= 1:
                        self._os_number = result
                        break
                    print("[prompt.invalid]Number of Object Stores must be greater than [[b]1[/b]]")

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
                self._ssl_directory_list.append("os")
                self._ssl_directory_list.append("icn")
            else:
                if "cpe" in self._optional_components:
                    self._ssl_directory_list.append("gcd")
                    self._ssl_directory_list.append("os")
                if "ban" in self._optional_components:
                    self._ssl_directory_list.append("icn")
            for i in range(1, self._os_number):
                self._ssl_directory_list.append(f"os{i + 1}")

    # Function to collect the fncm version
    def collect_fncm_version(self):
        try:
            print(Panel.fit("Version"))
            while True:
                print()
                print("Which version of FNCM S do you want to deploy?")
                print("1. 5.5.8")
                print("2. 5.5.11")
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]2[/b]]')

                if 1 <= result <= 2:
                    self._fncm_version = self.Version.FNCMVersion(result).name
                    break

                print("[prompt.invalid] Number must be between [[b]1[/b] and [b]2[/b]]")


        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in FNCM S collect version function -  {str(e)}")

    # Create a function to gather db_type from the user
    def collect_license_model(self):
        try:
            print(Panel.fit("License"))
            print()
            if self._fncm_version == "5.5.8":
                fncm_license_url = Text("https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KPMK",
                                        style="link https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KPMK")
                icf_license_url = Text("https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KQ34",
                                       style="link https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-C6KQ34")

                print(Panel.fit(
                    f"IMPORTANT: Review the license  information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}"))

            else:
                fncm_license_url = Text("https://ibm.biz/CPE_FNCM_License_5_5_11",
                                        style="link https://ibm.biz/CPE_FNCM_License_5_5_11")
                icf_license_url = Text("https://ibm.biz/CPE_ICF_License_5_5_11",
                                       style="link https://ibm.biz/CPE_ICF_License_5_5_11")
                cpe_notices_url = Text("https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_11",
                                       style="link https://ibm.biz/CPE_FNCM_ICF_Notices_5_5_11")

                print(Panel.fit(
                    f"IMPORTANT: Review the license  information for the product bundle you are deploying.\n\n"
                    f"IBM FileNet Content Manager license information here: {fncm_license_url}\n"
                    f"IBM Content Foundation license information here: {icf_license_url}\n"
                    f"IBM Content Platform Engine Software Notices here: {cpe_notices_url}"))

            print()

            accept_license = Confirm.ask("Do you accept the International Program License?")

            if not accept_license:
                print("[prompt.invalid] You must accept the International Program License to continue.")
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

                print("[prompt.invalid] Number must be between [[b]1[/b] and [b]3[/b]]")

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

                    print("[prompt.invalid] Number must be between [[b]1[/b] and [b]3[/b]]")

                else:
                    print("1. PVUProd")
                    print("2. PVUNonProd")
                    print("3. UVU")
                    print("4. CU")
                    result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]4[/b]]')

                    if 1 <= result <= 4:
                        metric = self.LicenseMetricFNCM(result).name
                        break

                    print("[prompt.invalid] Number must be between [[b]1[/b] and [b]4[/b]]")

            self._license_model = f"{model}.{metric}"

        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in license model function -  {str(e)}")

    # Create a function to gather db_type from the user
    def collect_db_type(self):
        try:
            print(Panel.fit("Database"))
            while True:
                print()
                print("Select a Database Type")
                print("1. IBM Db2")
                print("2. IBM Db2 HADR")
                print("3. Oracle")
                print("4. Microsoft SQL Server")
                print("5. PostgreSQL")
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]5[/b]]')

                if 1 <= result <= 5:
                    self._db_type = self.DatabaseType(result).name
                    break

                print("[prompt.invalid] Number must be between [[b]1[/b] and [b]5[/b]]")


        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in storage_class_menu function -  {str(e)}")

    # Create a function to gather platform and ingress enabled from user
    def collect_platform_ingress(self):
        try:
            print(Panel.fit("Platform"))
            while True:
                print()
                print("Select a Platform Type")
                print("1. OCP")
                print("2. ROKS")
                print("3. CNCF")
                result = IntPrompt.ask('Enter a valid option [[b]1[/b] and [b]3[/b]]')

                if 1 <= result <= 3:
                    self._platform = self.Platform(result).name
                    break

                print("[prompt.invalid] Number must be between [[b]1[/b] and [b]3[/b]]")

            if self._platform == "other" and self.fncm_version != "5.5.8":
                print()
                self._ingress = Confirm.ask("Do you want to enable ingress creation?")


        except Exception as e:
            self._logger.exception(
                f"Exception from gather script in collect_platform_ingress function -  {str(e)}")

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
                    print("2. IBM Security Directory Server")
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

                        print("[prompt.invalid] Number must be between [[b]1[/b] and [b]6[/b]]")
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

                        print("[prompt.invalid] Number must be between [[b]1[/b] and [b]7[/b]]")

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

        return {
            "optional_components": self.optional_components,
            "ldap_info": ldap_list,
            "db_type": self.db_type,
            "os_number": self.os_number,
            "db_ssl": self.db_ssl,
            "license_model": self.license_model,
            "fncm_version": self.fncm_version,
            "sendmail_support": self.sendmail_support,
            "content_initialize": self.content_initialize,
            "content_verification": self.content_verification,
            "platform": self.platform,
            "ingress": self.ingress,
        }
