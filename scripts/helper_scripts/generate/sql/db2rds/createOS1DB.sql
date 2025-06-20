-- ******************************************************************
-- IBM FileNet Content Manager ObjectStore preparation script for DB2RDS
-- ******************************************************************
-- Usage:
-- Connect to the DB2RDS instance using the DB2 command-line processor with a user having administrative privileges

-- Creating DB named: ${os_name}
CALL rdsadmin.create_database('${os_name}',32768,'UTF-8','US' );

--- Comment out all SQL stored procedures below when you are creating the database.
--- Once the database is created, comment out the create_database stored procedure statement and uncomment the below statements and execute them.
--- Creation of the Database can take some time, Please wait for a few minutes before executing the statements below.

-- Create bufferpool
CALL rdsadmin.create_bufferpool('${os_name}','${os_name}_1_32K',1024,'Y','Y',32768,0,32);
CALL rdsadmin.create_bufferpool('${os_name}', '${os_name}_2_32K',1024,'Y','Y',32768,0,32);
CALL rdsadmin.create_bufferpool('${os_name}', '${os_name}_3_32K',1024,'Y','Y',32768,0,32);
-- For lob storage location which is not required by default
-- CALL rdsadmin.create_bufferpool('${os_name}', '${os_name}_4_32K',1024,'Y','Y',32768,0,32);

-- Create table spaces
CALL rdsadmin.create_tablespace( '${os_name}', '${datatablespace}', '${os_name}_1_32K', 32768, NULL, NULL, 'U', 'AUTOMATIC');
CALL rdsadmin.create_tablespace( '${os_name}', '${indextablespace}', '${os_name}_2_32K', 32768, NULL, NULL, 'U', 'AUTOMATIC');
CALL rdsadmin.create_tablespace( '${os_name}', '${tmp_tablespace}', '${os_name}_3_32K', 32768, NULL, NULL, 'T', 'AUTOMATIC');
-- For lob storage location which is not required by default
-- CALL rdsadmin.create_tablespace( '${os_name}', '${lobtablespace}', '${os_name}_4_32K', 32768, NULL, NULL, 'T', 'AUTOMATIC');

-- Create role for the database with the role name of FNCM
CALL rdsadmin.create_role('${os_name}','FNCM');

-- Create a user
CALL rdsadmin.add_user('${youruser1}','${yourpassword}',null);
CALL rdsadmin.grant_role(?,'${os_name}','FNCM','USER ${youruser1}','N');
CALL rdsadmin.update_db_param('${os_name}','LOCKTIMEOUT','30');

-- Execute the below statement after the admin user is connected to the newly created Database
-- Grant permissions to DB user
GRANT CREATETAB,CONNECT ON DATABASE TO USER ${youruser1};
GRANT USE OF TABLESPACE ${datatablespace} TO USER ${youruser1};
GRANT USE OF TABLESPACE ${indextablespace} TO USER ${youruser1};
-- For lob storage location which is not required by default
-- GRANT USE OF TABLESPACE ${lobtablespace} TO USER ${youruser1};
GRANT USE OF TABLESPACE ${tmp_tablespace} TO USER ${youruser1};
GRANT SELECT ON SYSIBM.SYSVERSIONS TO USER ${youruser1};
GRANT SELECT ON SYSCAT.DATATYPES TO USER ${youruser1};
GRANT SELECT ON SYSCAT.INDEXES TO USER ${youruser1};
GRANT SELECT ON SYSIBM.SYSDUMMY1 TO USER ${youruser1};
GRANT USAGE ON WORKLOAD SYSDEFAULTUSERWORKLOAD TO USER ${youruser1};

GRANT IMPLICIT_SCHEMA ON DATABASE TO USER ${youruser1};
CREATE SCHEMA ${youruser1} AUTHORIZATION ${youruser1};

GRANT EXECUTE ON PACKAGE NULLID.SYSSH200 TO USER ${youruser1};
GRANT EXECUTE ON PACKAGE NULLID.SYSSN200 TO USER ${youruser1};
GRANT SQLADM ON DATABASE TO USER ${youruser1};

-- Done creating and tuning DB named: ${os_name}