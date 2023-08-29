-- create Content Platform Engine GCD database, you could update FILENAME as your requirement.
-- Please make sure you change the drive and path to your MSSQL database.
CREATE DATABASE ${gcd_name}
ON PRIMARY
(  NAME = ${gcd_name}_DATA,
   FILENAME = 'C:\MSSQL_DATABASE\${gcd_name}_DATA.mdf',
   SIZE = 400MB,
   FILEGROWTH = 128MB ),

FILEGROUP ${gcd_name}SA_DATA_FG
(  NAME = ${gcd_name}SA_DATA,
   FILENAME = 'C:\MSSQL_DATABASE\${gcd_name}SA_DATA.ndf',
   SIZE = 300MB,
   FILEGROWTH = 128MB),

FILEGROUP ${gcd_name}SA_IDX_FG
(  NAME = ${gcd_name}SA_IDX,
   FILENAME = 'C:\MSSQL_DATABASE\${gcd_name}SA_IDX.ndf',
   SIZE = 300MB,
   FILEGROWTH = 128MB)

LOG ON
(  NAME = '${gcd_name}_LOG',
   FILENAME = 'C:\MSSQL_DATABASE\${gcd_name}_LOG.ldf',
   SIZE = 160MB,
   FILEGROWTH = 50MB )
GO

ALTER DATABASE ${gcd_name} SET RECOVERY SIMPLE
GO

ALTER DATABASE ${gcd_name} SET AUTO_CREATE_STATISTICS ON
GO

ALTER DATABASE ${gcd_name} SET AUTO_UPDATE_STATISTICS ON
GO

ALTER DATABASE ${gcd_name} SET READ_COMMITTED_SNAPSHOT ON
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

-- Creating users and schemas for Content Platform Engine GCD database
USE ${gcd_name}
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
