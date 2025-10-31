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

import inspect
import os
import string



def parse_yaml_sql(parameter):
    if parameter:
        parameter = parameter.replace("'", "''")
    return parameter


# Class to create GCD, ICN, and OS db scripts
class GenerateSql:
    # Stores the template for the db scripts for reuse
    _gcd_template = ""
    _icn_template = ""
    _os_template = ""

    _template_path = os.path.join(os.getcwd(), "helper_scripts", "generate", "sql")



    def __init__(self, propertydict, logger, namespace=""):
        try:
            # Gets content of proerty file and sorts them using DbProperty class
            # self._dbprop = DbProperty(propertyfile,logger)

            self._logger = logger

            self._dbprop = propertydict

            # Where to store generated sql files
            self._dest_path = os.path.join(os.getcwd(), "generatedFiles",namespace, "database")

            # Creates destination folder
            self.make_folder(os.path.join(os.getcwd(), "generatedFiles"))
            self.make_folder(self._dest_path)

            self.load_templates()

        except Exception as e:
            self._logger.exception(
                f"Exception from generate_sql.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Make a folder by given path, skip if folder exists.
    def make_folder(self, folder):
        if not os.path.exists(folder):
            os.mkdir(folder)

    # Load the SQL templates
    def load_templates(self):
        try:
            # Both DB2RDS and DB2RDS HADR can use the same sql templates
            if self._dbprop["DATABASE_TYPE"].lower() == "db2rdshadr":
                dbtype_path = os.path.join(self._template_path, "db2rds")
            # Both DB2 and DB2HADR can use the same sql templates
            elif self._dbprop["DATABASE_TYPE"].lower() == "db2hadr":
                dbtype_path = os.path.join(self._template_path, "db2")
            else:
                dbtype_path = os.path.join(self._template_path, self._dbprop["DATABASE_TYPE"])
            with open(os.path.join(dbtype_path, "createGCDDB.sql"), encoding='UTF-8') as t:
                self._gcd_template = string.Template(t.read())
            with open(os.path.join(dbtype_path, "createICNDB.sql"), encoding='UTF-8') as t:
                self._icn_template = string.Template(t.read())
            with open(os.path.join(dbtype_path, "createOS1DB.sql"), encoding='UTF-8') as t:
                self._os_template = string.Template(t.read())

        except Exception as e:
            self._logger.exception(
                f"Exception from generate_sql.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Write GCD sql script using loaded template.
    def create_gcd(self):
        try:
            path = os.path.join(self._dest_path, "createGCD.sql")
            finished_output = self._gcd_template.safe_substitute(gcd_name=self._dbprop['GCD']['DATABASE_NAME'],
                                                                 youruser1=parse_yaml_sql(
                                                                     self._dbprop['GCD']['DATABASE_USERNAME']),
                                                                 yourpassword=parse_yaml_sql(
                                                                     self._dbprop['GCD']['DATABASE_PASSWORD']))
            with open(path, "w", encoding='UTF-8') as output:
                output.write(finished_output)

        except Exception as e:
            self._logger.exception(
                f"Exception from generate_sql.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Write ICN sql script using loaded template.
    def create_icn(self):
        try:
            path = os.path.join(self._dest_path, "createICN.sql")
            # we have tablespace and schema name that can be user filled for postgresql, sql,oracle
            if self._dbprop["DATABASE_TYPE"].lower() not in ["db2", "db2hadr", "db2rds", "db2rdshadr"]:
                finished_output = self._icn_template.safe_substitute(icn_name=self._dbprop['ICN']['DATABASE_NAME'],
                                                                     youruser1=parse_yaml_sql(
                                                                         self._dbprop['ICN']['DATABASE_USERNAME']),
                                                                     yourpassword=parse_yaml_sql(
                                                                         self._dbprop['ICN']['DATABASE_PASSWORD']),
                                                                     yourtablespace=parse_yaml_sql(
                                                                         self._dbprop['ICN']['TABLESPACE_NAME']),
                                                                     yourschema=parse_yaml_sql(
                                                                         self._dbprop['ICN']['SCHEMA_NAME'])
                                                                     )
            else:
                finished_output = self._icn_template.safe_substitute(icn_name=self._dbprop['ICN']['DATABASE_NAME'],
                                                                     youruser1=parse_yaml_sql(
                                                                         self._dbprop['ICN']['DATABASE_USERNAME']),
                                                                     yourpassword=parse_yaml_sql(
                                                                         self._dbprop['ICN']['DATABASE_PASSWORD']))

            with open(path, "w", encoding='UTF-8') as output:
                output.write(finished_output)

        except Exception as e:
            self._logger.exception(
                f"Exception from generate_sql.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # Write OS sql scripts using loaded template
    def create_os(self):
        try:
            for index, os_id in enumerate(self._dbprop["_os_ids"]):
                path = os.path.join(self._dest_path, f"create{self._dbprop[os_id]['OS_LABEL']}.sql")
                if self._dbprop["DATABASE_TYPE"].lower() in ["db2", "db2hadr", "db2rds", "db2rdshadr"]:
                    finished_output = self._os_template.safe_substitute(
                        os_name=self._dbprop[os_id.upper()]['DATABASE_NAME'],
                        youruser1=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_USERNAME']),
                        yourpassword=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_PASSWORD']),
                        datatablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['DATA_TABLESPACE']),
                        indextablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['INDEX_TABLESPACE']),
                        lobtablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['LOB_TABLESPACE']),
                        tmp_tablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['TMP_TABLESPACE'])
                    )
                elif self._dbprop["DATABASE_TYPE"] == "oracle":
                    finished_output = self._os_template.safe_substitute(
                        os_name=self._dbprop[os_id.upper()]['DATABASE_NAME'],
                        youruser1=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_USERNAME']),
                        yourpassword=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_PASSWORD']),
                        datatablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['DATA_TABLESPACE']),
                        tmp_tablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['TMP_TABLESPACE']),
                        indextablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['INDEX_TABLESPACE']),
                        lobdatatablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['LOB_TABLESPACE'])
                    )
                #no lob for postgresql only for others
                elif self._dbprop["DATABASE_TYPE"] == "postgresql":
                    finished_output = self._os_template.safe_substitute(
                        os_name=self._dbprop[os_id.upper()]['DATABASE_NAME'],
                        youruser1=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_USERNAME']),
                        yourpassword=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_PASSWORD']),
                        datatablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['DATA_TABLESPACE'].lower()),
                        indextablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['INDEX_TABLESPACE'].lower())
                    )
                elif self._dbprop["DATABASE_TYPE"] == "sqlserver":
                    finished_output = self._os_template.safe_substitute(
                        os_name=self._dbprop[os_id.upper()]['DATABASE_NAME'],
                        youruser1=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_USERNAME']),
                        yourpassword=parse_yaml_sql(self._dbprop[os_id.upper()]['DATABASE_PASSWORD']),
                        datatablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['DATA_TABLESPACE'].upper()),
                        indextablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['INDEX_TABLESPACE'].upper()),
                        lobtablespace=parse_yaml_sql(self._dbprop[os_id.upper()]['LOB_TABLESPACE'].upper())
                    )
                with open(path, "w", encoding='UTF-8') as output:
                    output.write(finished_output)

        except Exception as e:
            self._logger.exception(
                f"Exception from generate_sql.py script in {inspect.currentframe().f_code.co_name} function -  {str(e)}")

    # With a criteria (skip hidden files)
    def is_not_hidden(self, path):
        return not path.name.startswith(".")

    @property
    def template_path(self):
        return self._template_path

    @template_path.setter
    def template_path(self, value):
        self._template_path = value

    @property
    def dest_path(self):
        return self._dest_path

    @dest_path.setter
    def dest_path(self, value):
        self._dest_path = value


