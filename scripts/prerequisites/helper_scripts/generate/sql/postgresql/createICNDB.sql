-- *******************************************************
-- IBM Content Navigator preparation script for PostgreSQL
-- *******************************************************
-- Usage:
-- Use psql command-line processor to execute the template file using -f option and user with administrative privileges
-- psql -h 127.0.0.1 -U dbaUser -f ./createICNDB.sql

-- create user ${youruser1}
CREATE ROLE ${youruser1} WITH INHERIT LOGIN ENCRYPTED PASSWORD '${yourpassword}';

-- please modify location follow your requirement
create tablespace ${yourtablespace} owner ${youruser1} location '/pgsqldata/${icn_name}';
grant create on tablespace ${yourtablespace} to ${youruser1};

-- create database ${icn_name}
create database ${icn_name} owner ${youruser1} tablespace ${yourtablespace} template template0 encoding UTF8 ;
revoke connect on database ${icn_name} from public;
grant all privileges on database ${icn_name} to ${youruser1};
grant connect, temp, create on database ${icn_name} to ${youruser1};

-- create a schema for ${icn_name} and set the default
-- connect to the respective database before executing the below commands
\connect ${icn_name};
CREATE SCHEMA IF NOT EXISTS ${yourschema} AUTHORIZATION ${youruser1};
SET ROLE ${youruser1};
ALTER DATABASE ${icn_name} SET search_path TO ${yourschema};
