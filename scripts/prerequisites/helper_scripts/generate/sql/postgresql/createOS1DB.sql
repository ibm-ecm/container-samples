-- *************************************************************************
-- IBM FileNet Content Manager ObjectStore preparation script for PostgreSQL
-- *************************************************************************
-- Usage:
-- Use psql command-line processor to execute the template file using -f option and user with administrative privileges
-- psql -h 127.0.0.1 -U dbaUser -f ./createOS1DB.sql

-- create user ${youruser1}
CREATE ROLE ${youruser1} WITH INHERIT LOGIN ENCRYPTED PASSWORD '${yourpassword}';

-- please modify location follow your requirement
create tablespace ${datatablespace} owner ${youruser1} location '/pgsqldata/${os_name}';
grant create on tablespace ${datatablespace} to ${youruser1};

-- create database ${os_name}
create database ${os_name} owner ${youruser1} tablespace ${datatablespace} template template0 encoding UTF8 ;
revoke connect on database ${os_name} from public;
grant all privileges on database ${os_name} to ${youruser1};
grant connect, temp, create on database ${os_name} to ${youruser1};

-- create a schema for ${os_name} and set the default
-- connect to the respective database before executing the below commands
\connect ${os_name};
CREATE SCHEMA IF NOT EXISTS AUTHORIZATION ${youruser1};
SET ROLE ${youruser1};
ALTER DATABASE ${os_name} SET search_path TO ${youruser1};
