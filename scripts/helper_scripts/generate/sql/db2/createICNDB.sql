-- ************************************************
-- IBM Content Navigator preparation script for DB2
-- ************************************************
-- Usage:
-- Connect to the DB2 instance using the DB2 command-line processor with a user having administrative privileges
-- db2 -vtf createICNDB.sql

-- Creating DB named: ${icn_name}DB

CREATE DATABASE ${icn_name} AUTOMATIC STORAGE YES USING CODESET UTF-8 TERRITORY US PAGESIZE 32 K;
CONNECT TO ${icn_name};
GRANT DBADM ON DATABASE TO USER ${youruser1};
CONNECT RESET;
