-- ************************************************************************
-- IBM FileNet Content Manager ObjectStore preparation script for SQLServer
-- ************************************************************************
-- Usage:
-- Use sqlcmd command-line tool to execute the template file using -i option and
-- user with privileges to create databases and filegroups
-- sqlcmd -S serverName\instanceName -U dbaUser -P dbaPassword -i C:\createOS1DB.sql


-- Create ${os_name} object store database, update or remove FILENAME as per your database requirements.
-- Please make sure you change the drive and path to your MSSQL database.
CREATE DATABASE ${os_name}
GO

USE master
GO

ALTER DATABASE ${os_name}
ADD FILEGROUP ${os_name}SA_DATA_FG;
GO

ALTER DATABASE ${os_name}
ADD FILEGROUP ${os_name}SA_IDX_FG;
GO

ALTER DATABASE ${os_name}
ADD FILE
(
    NAME = ${os_name}_DATA,
    FILENAME = 'C:\MSSQL_DATABASE\${os_name}_DATA.mdf',
    SIZE = 400MB,
    FILEGROWTH = 128MB
)
GO

ALTER DATABASE ${os_name}
ADD FILE
(
    NAME = ${os_name}SA_DATA,
    FILENAME = 'C:\MSSQL_DATABASE\${os_name}SA_DATA.ndf',
    SIZE = 300MB,
    FILEGROWTH = 128MB
)
TO FILEGROUP ${os_name}SA_DATA_FG;
GO

ALTER DATABASE ${os_name}
ADD FILE
(
    NAME = ${os_name}SA_IDX,
    FILENAME = 'C:\MSSQL_DATABASE\${os_name}SA_IDX.ndf',
    SIZE = 300MB,
    FILEGROWTH = 128MB
)
TO FILEGROUP ${os_name}SA_IDX_FG;
GO

ALTER DATABASE ${os_name} SET RECOVERY SIMPLE
GO

ALTER DATABASE ${os_name} SET AUTO_CREATE_STATISTICS ON
GO

ALTER DATABASE ${os_name} SET AUTO_UPDATE_STATISTICS ON
GO

ALTER DATABASE ${os_name} SET READ_COMMITTED_SNAPSHOT ON
GO

-- create a SQL Server login account for the database user of each of the databases and update the master database to grant permission for XA transactions for the login account
USE MASTER
GO
-- when using SQL authentication
CREATE LOGIN ${youruser1} WITH PASSWORD='${yourpassword}'
-- when using Windows authentication:
-- CREATE LOGIN [domain\user] FROM WINDOWS
GO
CREATE USER ${youruser1} FOR LOGIN ${youruser1} WITH DEFAULT_SCHEMA=${youruser1}
GO
EXEC sp_addrolemember N'SqlJDBCXAUser', N'${youruser1}';
GO

-- Creating users and schemas for object store database
USE ${os_name}
GO
CREATE USER ${youruser1} FOR LOGIN ${youruser1} WITH DEFAULT_SCHEMA=${youruser1}
GO
CREATE SCHEMA ${youruser1} AUTHORIZATION ${youruser1}
GO
EXEC sp_addrolemember 'db_ddladmin', ${youruser1};
GO
EXEC sp_addrolemember 'db_datareader', ${youruser1};
GO
EXEC sp_addrolemember 'db_datawriter', ${youruser1};
GO
