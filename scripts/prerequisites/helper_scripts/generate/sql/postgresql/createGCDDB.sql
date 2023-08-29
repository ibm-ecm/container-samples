-- create user ${youruser1}
CREATE ROLE ${youruser1} WITH INHERIT LOGIN ENCRYPTED PASSWORD '${yourpassword}';

-- create database ${gcd_name}
create database ${gcd_name} owner ${youruser1} template template0 encoding UTF8 ;
revoke connect on database ${gcd_name} from public;
grant all privileges on database ${gcd_name} to ${youruser1};
grant connect, temp, create on database ${gcd_name} to ${youruser1};

-- please modify location follow your requirement
create tablespace ${gcd_name}_tbs owner ${youruser1} location '/pgsqldata/${gcd_name}';
grant create on tablespace ${gcd_name}_tbs to ${youruser1};

-- create a schema for ${gcd_name} and set the default
-- connect to the respective database before executing the below commands
\connect ${gcd_name};
CREATE SCHEMA IF NOT EXISTS AUTHORIZATION ${youruser1};
SET ROLE ${youruser1};
ALTER DATABASE ${gcd_name} SET search_path TO ${youruser1};

