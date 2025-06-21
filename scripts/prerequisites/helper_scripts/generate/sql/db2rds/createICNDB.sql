-- ************************************************
-- IBM Content Navigator preparation script for DB2RDS
-- ************************************************
-- Usage:
-- Connect to the DB2 instance using the DB2 command-line processor with a user having administrative privileges

-- Creating DB named: ${icn_name}DB
CALL rdsadmin.create_database('${icn_name}',32768,'UTF-8','US' );

--- Comment out all SQL stored procedures below when you are creating the database.
--- Once the database is created, comment out the create_database stored procedure statement and uncomment the below statements and execute them.
--- Creation of the Database can take some time, Please wait for a few minutes before executing the statements below.

-- Create bufferpool
CALL rdsadmin.create_bufferpool('${icn_name}','${icn_name}_BP',1024,'Y','Y',32768,0,32);
CALL rdsadmin.create_bufferpool('${icn_name}', '${icn_name}_TEMPBP',1024,'Y','Y',32768,0,32);

-- Create table spaces
CALL rdsadmin.create_tablespace( '${icn_name}', 'ICNDB', '${icn_name}_BP', 32768, NULL, NULL, 'U', 'AUTOMATIC');
CALL rdsadmin.create_tablespace( '${icn_name}', '${icn_name}_TEMP', '${icn_name}_TEMPBP', 32768, NULL, NULL, 'T', 'AUTOMATIC');

-- Create role for the database ICNDB with the role name of BAN
CALL rdsadmin.create_role('${icn_name}','BAN');

-- Create a user
CALL rdsadmin.add_user('${icn_name}','${yourpassword}',null);
CALL rdsadmin.grant_role(?,'${icn_name}','BAN','USER ${youruser1}','N');
CALL rdsadmin.dbadm_grant(?,'${icn_name}','DBADM','USER ${youruser1}');
CALL rdsadmin.update_db_param('${icn_name}','LOCKTIMEOUT','30');

-- Execute the below statement after the admin user is connected to the newly created Database
-- Grant permissions to DB user
GRANT CONNECT ON DATABASE TO USER ${youruser1};
GRANT SELECT ON SYSIBM.SYSVERSIONS TO USER ${youruser1};
GRANT SELECT ON SYSCAT.DATATYPES TO USER ${youruser1};
GRANT SELECT ON SYSCAT.INDEXES TO USER ${youruser1};
GRANT SELECT ON SYSIBM.SYSDUMMY1 TO USER ${youruser1};
GRANT USAGE ON WORKLOAD SYSDEFAULTUSERWORKLOAD TO USER ${youruser1};

GRANT IMPLICIT_SCHEMA ON DATABASE TO USER ${youruser1};
CREATE SCHEMA ICNDB AUTHORIZATION ${youruser1};

GRANT EXECUTE ON PACKAGE NULLID.SYSSH200 TO USER ${youruser1};
GRANT EXECUTE ON PACKAGE NULLID.SYSSN200 TO USER ${youruser1};
GRANT SQLADM ON DATABASE TO USER ${youruser1};

-- Done creating and tuning DB named: ${icn_name}