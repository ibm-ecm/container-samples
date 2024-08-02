-- *********************************************************************
-- IBM FileNet Content Manager ObjectStore preparation script for Oracle
-- *********************************************************************
-- Usage:
-- Use Oracle sql command-line to execute the template file using @{file} option and user as SYSDBA
-- sqlplus / as sysdba
-- @createOS1DB.sql

-- Please ensure you already have existing oracle instance.
-- If your oracle instance does not support multi-tenant architecture, comment out follow lines:
CREATE PLUGGABLE DATABASE ${os_name} ADMIN USER ${os_name}_admin IDENTIFIED BY ${yourpassword} ROLES=(DBA);
ALTER PLUGGABLE DATABASE ${os_name} OPEN READ WRITE;
ALTER PLUGGABLE DATABASE ${os_name} save state;
ALTER SESSION SET CONTAINER=${os_name};

-- Create tablespace
-- Change DATAFILE/TEMPFILE as required by your configuration
CREATE TABLESPACE ${datatablespace} DATAFILE '/home/oracle/orcl/${datatablespace}.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL SEGMENT SPACE MANAGEMENT AUTO ONLINE PERMANENT;
CREATE TEMPORARY TABLESPACE ${tmp_tablespace} TEMPFILE '/home/oracle/orcl/${tmp_tablespace}.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL;

-- Create a new user for ${youruser1}
CREATE USER ${youruser1} PROFILE DEFAULT IDENTIFIED BY ${yourpassword} DEFAULT TABLESPACE ${datatablespace} TEMPORARY TABLESPACE ${tmp_tablespace} ACCOUNT UNLOCK;

-- Provide quota on all tablespaces with BPM tables
ALTER USER ${youruser1} QUOTA UNLIMITED ON ${datatablespace};
ALTER USER ${youruser1} DEFAULT TABLESPACE ${datatablespace};
ALTER USER ${youruser1} TEMPORARY TABLESPACE ${tmp_tablespace};

-- Allow the user to connect to the database
GRANT CONNECT TO ${youruser1};
GRANT ALTER session TO ${youruser1};

-- Grant privileges to create database objects
GRANT CREATE SESSION TO ${youruser1};
GRANT CREATE TABLE TO ${youruser1};
GRANT CREATE VIEW TO ${youruser1};
GRANT CREATE SEQUENCE TO ${youruser1};
GRANT CREATE PROCEDURE TO ${youruser1};

-- Grant access rights to resolve XA related issues
GRANT SELECT on pending_trans$ TO ${youruser1};
GRANT SELECT on dba_2pc_pending TO ${youruser1};
GRANT SELECT on dba_pending_transactions TO ${youruser1};
GRANT SELECT on DUAL TO ${youruser1};
GRANT SELECT on product_component_version TO ${youruser1};
GRANT SELECT on USER_INDEXES TO ${youruser1};
GRANT EXECUTE ON DBMS_XA TO ${youruser1};

-- Sharing a single database connection for multiple object stores, uncomment the following grants.
-- GRANT ALTER ANY SEQUENCE TO ${youruser1};
-- GRANT ALTER ANY TABLE TO ${youruser1};
-- GRANT ALTER ANY PROCEDURE TO ${youruser1};
-- GRANT ANALYZE ANY TO ${youruser1};
-- GRANT EXECUTE ANY PROCEDURE TO ${youruser1};
-- GRANT CREATE ANY INDEX TO ${youruser1};
-- GRANT CREATE ANY SEQUENCE TO ${youruser1};
-- GRANT CREATE ANY TABLE TO ${youruser1};
-- GRANT CREATE ANY VIEW TO ${youruser1};
-- GRANT CREATE ANY PROCEDURE TO ${youruser1};
-- GRANT DELETE ANY TABLE TO ${youruser1};
-- GRANT DROP ANY INDEX TO ${youruser1};
-- GRANT DROP ANY SEQUENCE TO ${youruser1};
-- GRANT DROP ANY TABLE TO ${youruser1};
-- GRANT DROP ANY VIEW TO ${youruser1};
-- GRANT DROP ANY PROCEDURE TO ${youruser1};
-- GRANT INSERT ANY TABLE TO ${youruser1};
-- GRANT LOCK ANY TABLE TO ${youruser1};
-- GRANT SELECT ANY SEQUENCE TO ${youruser1};
-- GRANT SELECT ANY TABLE TO ${youruser1};
-- GRANT SELECT ON ALL_USERS TO ${youruser1};
-- GRANT UPDATE ANY TABLE TO ${youruser1};
-- GRANT CREATE USER TO ${youruser1};
EXIT;
