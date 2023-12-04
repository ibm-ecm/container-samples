-- *************************************************************
-- IBM FileNet Content Manager GCD preparation script for Oracle
-- *************************************************************
-- Usage:
-- Use Oracle sql command-line to execute the template file using @{file} option and user as SYSDBA
-- sqlplus / as sysdba
-- @createGCDDB.sql

-- Please ensure you already have existing oracle instance.
-- If your oracle instance does not support multi-tenant architecture, comment out follow lines:
CREATE PLUGGABLE DATABASE ${gcd_name} ADMIN USER ${gcd_name}_admin IDENTIFIED BY ${yourpassword} ROLES=(DBA);
ALTER PLUGGABLE DATABASE ${gcd_name} OPEN READ WRITE;
ALTER PLUGGABLE DATABASE ${gcd_name} save state;
ALTER SESSION SET CONTAINER=${gcd_name};

-- Create tablespace
-- Please make sure you change the DATAFILE and TEMPFILE to your Oracle database.
CREATE TABLESPACE ${gcd_name}DATATS DATAFILE '/home/oracle/orcl/${gcd_name}DATATS.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL SEGMENT SPACE MANAGEMENT AUTO ONLINE PERMANENT;
CREATE TEMPORARY TABLESPACE ${gcd_name}DATATSTEMP TEMPFILE '/home/oracle/orcl/${gcd_name}DATATSTEMP.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL;

-- Create a new user for ${gcd_name}
CREATE USER ${youruser1} PROFILE DEFAULT IDENTIFIED BY ${yourpassword} DEFAULT TABLESPACE ${gcd_name}DATATS TEMPORARY TABLESPACE ${gcd_name}DATATSTEMP ACCOUNT UNLOCK;
-- Provide quota on all tablespaces with GCD tables
ALTER USER ${youruser1} QUOTA UNLIMITED ON ${gcd_name}DATATS;
ALTER USER ${youruser1} DEFAULT TABLESPACE ${gcd_name}DATATS;
ALTER USER ${youruser1} TEMPORARY TABLESPACE ${gcd_name}DATATSTEMP;

-- Allow the user to connect to the database
GRANT CONNECT TO ${youruser1};
GRANT ALTER session TO ${youruser1};

-- Grant privileges to create database objects
GRANT CREATE SESSION TO ${youruser1};
GRANT CREATE TABLE TO ${youruser1};
GRANT CREATE VIEW TO ${youruser1};
GRANT CREATE SEQUENCE TO ${youruser1};

-- Grant access rights to resolve XA related issues
GRANT SELECT on pending_trans$ TO ${youruser1};
GRANT SELECT on dba_2pc_pending TO ${youruser1};
GRANT SELECT on dba_pending_transactions TO ${youruser1};
GRANT SELECT on DUAL TO ${youruser1};
GRANT SELECT on product_component_version TO ${youruser1};
GRANT SELECT on USER_INDEXES TO ${youruser1};
GRANT EXECUTE ON DBMS_XA TO ${youruser1};
EXIT;
