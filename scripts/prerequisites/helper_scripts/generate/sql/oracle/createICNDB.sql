-- ***************************************************
-- IBM Content Navigator preparation script for Oracle
-- ***************************************************
-- Usage:
-- Use Oracle sql command-line to execute the template file using @{file} option and user as SYSDBA
-- sqlplus / as sysdba
-- @createICNDB.sql

-- Please ensure you already have existing oracle instance.
-- If your oracle instance does not support multi-tenant architecture, comment out follow lines:
CREATE PLUGGABLE DATABASE ${icn_name} ADMIN USER ${icn_name}_admin IDENTIFIED BY ${yourpassword} ROLES=(DBA);
ALTER PLUGGABLE DATABASE ${icn_name} OPEN READ WRITE;
ALTER PLUGGABLE DATABASE ${icn_name} save state;
ALTER SESSION SET CONTAINER=${icn_name};

-- Create a new user
-- Note: the Operator default for schema is ICNDB
CREATE USER ${youruser1} IDENTIFIED BY ${yourpassword};

-- Allow the user to connect to the database
GRANT CONNECT TO ${youruser1};

-- Provide quota on all tablespaces with tables
GRANT UNLIMITED TABLESPACE TO ${youruser1};

-- Grant privileges to create database objects:
GRANT RESOURCE TO ${youruser1};
GRANT CREATE VIEW TO ${youruser1};

-- Grant access rights to resolve lock issues
GRANT EXECUTE ON DBMS_LOCK TO ${youruser1};

-- Grant access rights to resolve XA related issues:
GRANT SELECT ON PENDING_TRANS$ TO ${youruser1};
GRANT SELECT ON DBA_2PC_PENDING TO ${youruser1};
GRANT SELECT ON DBA_PENDING_TRANSACTIONS TO ${youruser1};
GRANT EXECUTE ON DBMS_XA TO ${youruser1};

-- Create tablespaces
-- Please make sure you change the DATAFILE and TEMPFILE to your Oracle database.
-- Note: the Operator default for the tablesapce is ICNDB
CREATE TABLESPACE ${yourtablespace}
    DATAFILE '/home/oracle/orcl/${icn_name}TS.dbf' SIZE 200M REUSE
    AUTOEXTEND ON NEXT 20M
    EXTENT MANAGEMENT LOCAL
    SEGMENT SPACE MANAGEMENT AUTO
    ONLINE
    PERMANENT
;

CREATE TEMPORARY TABLESPACE ${icn_name}TSTEMP
    TEMPFILE '/home/oracle/orcl/${icn_name}TSTEMP.dbf' SIZE 200M REUSE
    AUTOEXTEND ON NEXT 20M
    EXTENT MANAGEMENT LOCAL
;


-- Alter existing schema
ALTER USER ${youruser1}
    DEFAULT TABLESPACE ${yourtablespace}
    TEMPORARY TABLESPACE ${icn_name}TSTEMP;

GRANT CONNECT, RESOURCE to ${youruser1};
GRANT UNLIMITED TABLESPACE TO ${youruser1};
GRANT CREATE TRIGGER TO ${youruser1};
EXIT;
