-- Please ensure you already have existing oracle instance or pluggable database (PDB). If not, please create one first

-- create tablespace
-- Change DATAFILE/TEMPFILE as required by your configuration
CREATE TABLESPACE ${os_name}DATATS DATAFILE '/home/oracle/orcl/${os_name}DATATS.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL SEGMENT SPACE MANAGEMENT AUTO ONLINE PERMANENT;
CREATE TEMPORARY TABLESPACE ${os_name}DATATSTEMP TEMPFILE '/home/oracle/orcl/${os_name}DATATSTEMP.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL;

-- create a new user for ${youruser1}
CREATE USER ${youruser1} PROFILE DEFAULT IDENTIFIED BY ${yourpassword} DEFAULT TABLESPACE ${os_name}DATATS TEMPORARY TABLESPACE ${os_name}DATATSTEMP ACCOUNT UNLOCK;

-- provide quota on all tablespaces with BPM tables
ALTER USER ${youruser1} QUOTA UNLIMITED ON ${os_name}DATATS;
ALTER USER ${youruser1} DEFAULT TABLESPACE ${os_name}DATATS;
ALTER USER ${youruser1} TEMPORARY TABLESPACE ${os_name}DATATSTEMP;

-- allow the user to connect to the database
GRANT CONNECT TO ${youruser1};
GRANT ALTER session TO ${youruser1};

-- grant privileges to create database objects
GRANT CREATE SESSION TO ${youruser1};
GRANT CREATE TABLE TO ${youruser1};
GRANT CREATE VIEW TO ${youruser1};
GRANT CREATE SEQUENCE TO ${youruser1};
GRANT CREATE PROCEDURE TO ${youruser1};

-- grant access rights to resolve XA related issues
GRANT SELECT on pending_trans$ TO ${youruser1};
GRANT SELECT on dba_2pc_pending TO ${youruser1};
GRANT SELECT on dba_pending_transactions TO ${youruser1};
GRANT SELECT on DUAL TO ${youruser1};
GRANT SELECT on product_component_version TO ${youruser1};
GRANT SELECT on USER_INDEXES TO ${youruser1};
GRANT EXECUTE ON DBMS_XA TO ${youruser1};
EXIT;
