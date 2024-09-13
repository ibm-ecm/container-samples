-- ******************************************************************
-- IBM FileNet Content Manager ObjectStore preparation script for DB2
-- ******************************************************************
-- Usage:
-- Connect to the DB2 instance using the DB2 command-line processor with a user having administrative privileges
-- db2 -vtf createOS1DB.sql

-- Creating DB named: ${os_name}
CREATE DATABASE ${os_name} AUTOMATIC STORAGE YES USING CODESET UTF-8 TERRITORY US PAGESIZE 32 K;

CONNECT TO ${os_name};

-- Create bufferpool
CREATE BUFFERPOOL ${os_name}_1_32K IMMEDIATE SIZE 1024 PAGESIZE 32K;
CREATE BUFFERPOOL ${os_name}_2_32K IMMEDIATE SIZE 1024 PAGESIZE 32K;
CREATE BUFFERPOOL ${os_name}_3_32K IMMEDIATE SIZE 1024 PAGESIZE 32K;

-- Create table spaces
CREATE LARGE TABLESPACE ${datatablespace} PAGESIZE 32 K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL ${os_name}_1_32K;
CREATE LARGE TABLESPACE ${vwdatatablespace} PAGESIZE 32 K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL ${os_name}_2_32K;
CREATE USER TEMPORARY TABLESPACE ${tmp_tablespace} PAGESIZE 32 K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL ${os_name}_3_32K;

-- Grant permissions to DB user
GRANT CREATETAB,CONNECT ON DATABASE TO USER ${youruser1};
GRANT USE OF TABLESPACE ${datatablespace} TO USER ${youruser1};
GRANT USE OF TABLESPACE ${vwdatatablespace} TO USER ${youruser1};
GRANT USE OF TABLESPACE ${tmp_tablespace} TO USER ${youruser1};
GRANT SELECT ON SYSIBM.SYSVERSIONS TO USER ${youruser1};
GRANT SELECT ON SYSCAT.DATATYPES TO USER ${youruser1};
GRANT SELECT ON SYSCAT.INDEXES TO USER ${youruser1};
GRANT SELECT ON SYSIBM.SYSDUMMY1 TO USER ${youruser1};
GRANT USAGE ON WORKLOAD SYSDEFAULTUSERWORKLOAD TO USER ${youruser1};
GRANT IMPLICIT_SCHEMA ON DATABASE TO USER ${youruser1};


-- Apply DB tunings
UPDATE DB CFG FOR ${os_name} USING LOCKTIMEOUT 30;
UPDATE DB CFG FOR ${os_name} USING LOGFILSIZ 6000; 

-- Notes: Please verify below environment configuration settings were applied to the Db2 server.
-- db2set DB2_WORKLOAD=FILENET_CM
-- db2set DB2_MINIMIZE_LISTPREFETCH=YES

CONNECT RESET;

-- Done creating and tuning DB named: ${os_name}
