-- **********************************************************
-- IBM FileNet Content Manager GCD preparation script for DB2
-- **********************************************************
-- Usage:
-- Connect to the DB2 instance using the DB2 command-line processor with a user having administrative privileges
-- db2 -vtf createGCDDB.sql

-- Creating DB named: ${gcd_name}
CREATE DATABASE ${gcd_name} AUTOMATIC STORAGE YES USING CODESET UTF-8 TERRITORY US PAGESIZE 32 K;

CONNECT TO ${gcd_name};

-- Create bufferpool 
CREATE BUFFERPOOL ${gcd_name}_1_32K IMMEDIATE SIZE 1024 PAGESIZE 32K;
CREATE BUFFERPOOL ${gcd_name}_2_32K IMMEDIATE SIZE 1024 PAGESIZE 32K;

-- Create table spaces
CREATE REGULAR TABLESPACE ${gcd_name}DATA_TS PAGESIZE 32 K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL ${gcd_name}_1_32K;

CREATE USER TEMPORARY TABLESPACE ${gcd_name}_TMP_TBS PAGESIZE 32 K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL ${gcd_name}_2_32K;

-- Grant permissions to DB user
GRANT CREATETAB,CONNECT ON DATABASE TO user ${youruser1};
GRANT USE OF TABLESPACE ${gcd_name}DATA_TS TO user ${youruser1};
GRANT USE OF TABLESPACE ${gcd_name}_TMP_TBS TO user ${youruser1};
GRANT SELECT ON SYSIBM.SYSVERSIONS to user ${youruser1};
GRANT SELECT ON SYSCAT.DATATYPES to user ${youruser1};
GRANT SELECT ON SYSCAT.INDEXES to user ${youruser1};
GRANT SELECT ON SYSIBM.SYSDUMMY1 to user ${youruser1};
GRANT USAGE ON WORKLOAD SYSDEFAULTUSERWORKLOAD to user ${youruser1};
GRANT IMPLICIT_SCHEMA ON DATABASE to user ${youruser1};

-- Apply DB tunings
UPDATE DB CFG FOR ${gcd_name} USING LOCKTIMEOUT 30;
UPDATE DB CFG FOR ${gcd_name} USING APPLHEAPSZ 2560;

CONNECT RESET;

-- Notes: After DB be created, please set below setting.
-- db2set DB2_WORKLOAD=FILENET_CM
-- db2set DB2_MINIMIZE_LISTPREFETCH=YES

-- Done creating and tuning DB named: ${gcd_name}
