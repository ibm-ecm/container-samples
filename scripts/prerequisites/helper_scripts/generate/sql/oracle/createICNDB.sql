-- Please ensure you already have existing oracle instance or pluggable database (PDB). If not, please create one first

-- create a new user
CREATE USER ${youruser1} IDENTIFIED BY ${yourpassword};

-- allow the user to connect to the database
GRANT CONNECT TO ${youruser1};

-- provide quota on all tablespaces with tables
GRANT UNLIMITED TABLESPACE TO ${youruser1};

-- grant privileges to create database objects:
GRANT RESOURCE TO ${youruser1};
GRANT CREATE VIEW TO ${youruser1};

-- grant access rights to resolve lock issues
GRANT EXECUTE ON DBMS_LOCK TO ${youruser1};

-- grant access rights to resolve XA related issues:
GRANT SELECT ON PENDING_TRANS$ TO ${youruser1};
GRANT SELECT ON DBA_2PC_PENDING TO ${youruser1};
GRANT SELECT ON DBA_PENDING_TRANSACTIONS TO ${youruser1};
GRANT EXECUTE ON DBMS_XA TO ${youruser1};

-- Create tablespaces
-- Please make sure you change the DATAFILE and TEMPFILE to your Oracle database.
CREATE TABLESPACE ICNDB
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
    DEFAULT TABLESPACE ICNDB
    TEMPORARY TABLESPACE ${icn_name}TSTEMP;

GRANT CONNECT, RESOURCE to ${youruser1};
GRANT UNLIMITED TABLESPACE TO ${youruser1};
EXIT;
