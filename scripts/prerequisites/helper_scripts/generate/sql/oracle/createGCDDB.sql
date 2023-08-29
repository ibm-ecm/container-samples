-- Please ensure you already have existing oracle instance or pluggable database (PDB). If not, please create one first

-- create tablespace
-- Please make sure you change the DATAFILE and TEMPFILE to your Oracle database.
CREATE TABLESPACE ${gcd_name}DATATS DATAFILE '/home/oracle/orcl/${gcd_name}DATATS.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL SEGMENT SPACE MANAGEMENT AUTO ONLINE PERMANENT;
CREATE TEMPORARY TABLESPACE ${gcd_name}DATATSTEMP TEMPFILE '/home/oracle/orcl/${gcd_name}DATATSTEMP.dbf' SIZE 200M REUSE AUTOEXTEND ON NEXT 20M EXTENT MANAGEMENT LOCAL;

-- create a new user for ${gcd_name}
CREATE USER ${youruser1} PROFILE DEFAULT IDENTIFIED BY ${yourpassword} DEFAULT TABLESPACE ${gcd_name}DATATS TEMPORARY TABLESPACE ${gcd_name}DATATSTEMP ACCOUNT UNLOCK;
-- provide quota on all tablespaces with GCD tables
ALTER USER ${youruser1} QUOTA UNLIMITED ON ${gcd_name}DATATS;
ALTER USER ${youruser1} DEFAULT TABLESPACE ${gcd_name}DATATS;
ALTER USER ${youruser1} TEMPORARY TABLESPACE ${gcd_name}DATATSTEMP;

-- allow the user to connect to the database
GRANT CONNECT TO ${youruser1};
GRANT ALTER session TO ${youruser1};

-- grant privileges to create database objects
GRANT CREATE SESSION TO ${youruser1};
GRANT CREATE TABLE TO ${youruser1};
GRANT CREATE VIEW TO ${youruser1};
GRANT CREATE SEQUENCE TO ${youruser1};

-- grant access rights to resolve XA related issues
GRANT SELECT on pending_trans$ TO ${youruser1};
GRANT SELECT on dba_2pc_pending TO ${youruser1};
GRANT SELECT on dba_pending_transactions TO ${youruser1};
GRANT SELECT on DUAL TO ${youruser1};
GRANT SELECT on product_component_version TO ${youruser1};
GRANT SELECT on USER_INDEXES TO ${youruser1};
GRANT EXECUTE ON DBMS_XA TO ${youruser1};
EXIT;
