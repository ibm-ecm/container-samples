-- create user ${youruser1}
CREATE ROLE ${youruser1} WITH INHERIT LOGIN ENCRYPTED PASSWORD '${yourpassword}';

-- create database ${icn_name}
create database ${icn_name} owner ${youruser1} template template0 encoding UTF8 ;
revoke connect on database ${icn_name} from public;
grant all privileges on database ${icn_name} to ${youruser1};
grant connect, temp, create on database ${icn_name} to ${youruser1};

-- please modify location follow your requirement
create tablespace ICNDB owner ${youruser1} location '/pgsqldata/${icn_name}';
grant create on tablespace ICNDB to ${youruser1};

-- create a schema for ${icn_name} and set the default
-- connect to the respective database before executing the below commands
\connect ${icn_name};
CREATE SCHEMA IF NOT EXISTS ICNDB AUTHORIZATION ${youruser1};
SET ROLE ${youruser1};
ALTER DATABASE ${icn_name} SET search_path TO ICNDB;
