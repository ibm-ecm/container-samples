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

import platform

import toml


class ReadProp():
    # Shared by all instances for this type of class.
    required_fields = {}

    # Recursively checks for missing/required fields
    # in tables or tables within tables
    def __recurse_check_values(self, table, key_history=[]):
        for key in table:
            # If the value is indicated as another table,
            # we recursively call this function to check for other tables
            if type(table[key]) is dict:
                # key_history is required when outputting which specific
                # field is missing to the user when using recursive calls
                self.__recurse_check_values(table[key], key_history + [key])

            elif type(table[key]) is list:
                if "<Required>" in table[key]:
                    # Create a new entry for this property file as to what fields might be
                    # split filename from path and store it in required_fields
                    if platform.system() == "Windows":
                        delimiter = "\\"
                    else:
                        delimiter = "/"
                    file_name = self._prop_filepath.split(delimiter + "propertyFile" + delimiter)[-1]

                    if file_name not in self.required_fields:
                        self.required_fields[file_name] = []
                    self.required_fields[file_name].append((key_history + [key], table[key]))

            # If the value field is not a table, we just check
            # the user has not entered or edited the fields yet
            elif table[key] == '<Required>' or table[key] == '':
                # Create a new entry for this property file as to what fields might be
                # split filename from path and store it in required_fields
                if platform.system() == "Windows":
                    delimiter = "\\"
                else:
                    delimiter = "/"
                file_name = self._prop_filepath.split(delimiter + "propertyFile" + delimiter)[-1]

                if file_name not in self.required_fields:
                    self.required_fields[file_name] = []
                self.required_fields[file_name].append((key_history + [key], table[key]))

    # Returns true if user has missed any required fields.
    def missing_required_fields(self):
        if len(self.required_fields) > 0:
            return True
        return False

    # function to read property files into dictionaries
    def __init__(self, propertyfile, logger):
        self._prop_filepath = None

        self._logger = logger
        self._prop_filepath = propertyfile
        self._toml_dict = None
        self._toml_dict = toml.loads(open(self._prop_filepath, encoding="utf-8").read())
        self.__recurse_check_values(self._toml_dict)


    def to_dict(self):
        return self._toml_dict


# ReadPropDb does additional parsing for postgres and looking for OS labels to find number of OS's
class ReadPropDb(ReadProp):
    def __find_os_ids(self):
        os_ids = []
        for key in self._toml_dict.keys():
            if "OS" in key:
                os_ids.append(key)
        self._toml_dict["_os_ids"] = os_ids

    def __generate_tablespace_names(self):
        # Generate tablespace names for each OS
        if self._toml_dict["DATABASE_TYPE"] == "sqlserver":
            for os_id in self._toml_dict["_os_ids"]:
                self._toml_dict[os_id]["DATA_TABLESPACE"] = "PRIMARY"
        elif self._toml_dict["DATABASE_TYPE"] == "oracle":
            for os_id in self._toml_dict["_os_ids"]:
                os_name = self._toml_dict[os_id]["DATABASE_NAME"]
                self._toml_dict[os_id]["DATA_TABLESPACE"] = f"{os_name}DATATS"
                self._toml_dict[os_id]["TMP_TABLESPACE"] = f"{os_name}DATATSTEMP"
        elif self._toml_dict["DATABASE_TYPE"] == "postgresql":
            for os_id in self._toml_dict["_os_ids"]:
                os_name = self._toml_dict[os_id]["DATABASE_NAME"]
                self._toml_dict[os_id]["DATA_TABLESPACE"] = f"{os_name}_tbs"
        elif self._toml_dict["DATABASE_TYPE"] == "db2":
            for os_id in self._toml_dict["_os_ids"]:
                os_name = self._toml_dict[os_id]["DATABASE_NAME"]
                self._toml_dict[os_id]["DATA_TABLESPACE"] = f"{os_name}DATA_TS"
                self._toml_dict[os_id]["VWDATA_TABLESPACE"] = f"{os_name}VWDATA_TS"
                self._toml_dict[os_id]["TMP_TABLESPACE"] = f"{os_name}_TMP_TBS"


    def __force_postgres_dbnames(self):
        # Forcing lowercase on postgres db names
        if self._toml_dict["DATABASE_TYPE"] == "postgresql":
            self._logger.info("Forcing lowercase on postgres db names...")

            toml_dict_keys = self._toml_dict.keys()

            if "GCD" in toml_dict_keys:
                self._toml_dict["GCD"]["DATABASE_NAME"] = self._toml_dict["GCD"]["DATABASE_NAME"].lower()

            if "ICN" in toml_dict_keys:
                self._toml_dict["ICN"]["DATABASE_NAME"] = self._toml_dict["ICN"]["DATABASE_NAME"].lower()

            for os_id in self._toml_dict["_os_ids"]:
                self._toml_dict[os_id]["DATABASE_NAME"] = self._toml_dict[os_id]["DATABASE_NAME"].lower()

    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)
        self.__find_os_ids()
        self.__force_postgres_dbnames()
        self.__generate_tablespace_names()

        # Calculate DB number based on sections in property file
        db_keys = self._toml_dict.keys()

        db_list = self._toml_dict["_os_ids"].copy()
        db_number = len(db_list)

        if "GCD" in db_keys:
            db_number += 1
            db_list.append("GCD")

        if "ICN" in db_keys:
            db_number += 1
            db_list.append("ICN")

        self._toml_dict["db_number"] = db_number
        self._toml_dict["db_list"] = db_list


class ReadPropLdap(ReadProp):
    def __find_ldap_ids(self):
        ldap_ids = []
        for key in self._toml_dict.keys():
            if "LDAP" in key:
                ldap_ids.append(key)
        self._toml_dict["_ldap_ids"] = ldap_ids
        self._toml_dict["ldap_number"] = len(self._toml_dict["_ldap_ids"])

    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)
        self.__find_ldap_ids()

class ReadPropIdp(ReadProp):
    def __find_idp_ids(self):
        idp_ids = []
        for key in self._toml_dict.keys():
            if "IDP" in key:
                idp_ids.append(key)
        self._toml_dict["_idp_ids"] = idp_ids
        self._toml_dict["idp_number"] = len(self._toml_dict["_idp_ids"])

    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)
        self.__find_idp_ids()

class ReadPropSCIM(ReadProp):
    def __find_scim_ids(self):
        scim_ids = []
        for key in self._toml_dict.keys():
            if "SCIM" in key:
                scim_ids.append(key)
        self._toml_dict["_scim_ids"] = scim_ids
        self._toml_dict["scim_number"] = len(self._toml_dict["_scim_ids"])

    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)
        self.__find_scim_ids()

class ReadPropUsergroup(ReadProp):
    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)


class ReadPropDeployment(ReadProp):
    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)


class ReadPropIngress(ReadProp):
    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)

class ReadPropCustomComponent(ReadProp):
    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)

class ReadPropImageTag(ReadProp):
    def __init__(self, propertyfile, logger):
        super().__init__(propertyfile, logger)

    def check_toml(self):
        keys_to_check = ["TAG", "REPOSITORY"]
        self._incorrect_keys_list = []
        for key, value in self._toml_dict.items():
            if set(value.keys()) != set(keys_to_check):
                self._incorrect_keys_list.append(key)
        if not self._incorrect_keys_list:
            for key,value in self._toml_dict.items():
                if not value["REPOSITORY"] or not value["TAG"]:
                    self._incorrect_keys_list.append(key)
        return self._incorrect_keys_list
