## 3.1.0 (2024-09-11)

### Feat

- added support for running MustGather with only the operator deployed
- added support for inProgress Operator Ansible log in MustGather

### Fix

- fixed python package error when running prerequisite scripts inside of operator pod
- fix for outdated script copy instructions
- fix for incorrect folder path for operator image push
- fix for silent deploy entitlement key issue

## 3.0.1 (2024-07-20)

### Fix

- fix for mismatched tablespace for PE initialization in custom resource file
- updated pyyaml to 6.0.2rc1, tomlkit to 0.13.0, cryptography to 43.0.0, kubernetes to 30.1.0

## 3.0.0 (2024-06-28)

### Feat

- added new scripts: 'deployOperator', 'upgradeDeployment', 'cleanDeployment', 'loadImages'
- added new script: 'mustGather'  
- added support for FNCM 5.6.0 deployment 
- added support for IBM Enterprise Records in prerequisites
- added support for IBM Content Collector for SAP in prerequisites
- added support for Process Engine workflow enablement in prerequisites
- updated MSSQL Server SQL template to support AzureSQL Managed Instance
- added support for TLS 1.3 in prerequisites

### Fix

- enhanced 'move' logic for LDAP xml files

### Refactor

- changed IBM Security Directory Server (SDS) to IBM Security Verify Directory (ISVD) in prerequisites

## 2.4.7 (2024-02-26)

### Fix

- fixed serverAuth postgresql secret generation for FNCM 5.5.8
- fixed missing OIDC secret for External Share and GraphQL
- added support for postgres and oracle SSL/TLS connection validation
- updated cryptography library to 42.0.4
- updated postgresql JDBC driver to 42.7.2
- removed hostname and port property requirement for oracle db
- fix to add content pattern only CPE, GraphQL, Navigator are selected
- make tablespace and schema customizable for oracle, postgresql, sqlserver sql files
- allow selection of external share on 5.5.8 w/ LDAP and IDP
- fixed ldap error handling on invalid base dn or password
- fixed kubectl login and DB connection issues on Windows
- validate function successful on Windows
- apply trusted certificates through validation
- allow special characters in CLIENT_ID properties
- allow connection to self-signed SSL hosts

## 2.4.2 (2023-12-03)

### Feat

- added parsing of server hosts to remove protocols
- added validation of TLS protocol and cipher suites
- added option to allow self-signed certificate validation
- added support for SCIM
- added support for External Share
- added support for IDP's (Identity Providers)
- added support for External Share deployment
- adding support for restricted internet access
- fips support
- adding additional validation including user/group ldap search, cert validation and storage class validation

### Fix

- special characters are honored through TOML and Validation shell commands
- adding fips flag for java jdbc commands
- adding a check for java version in validate mode
- fips related checks for ssl mode and db password length
- fixed issue with reapplying existing CR file
- allow users to apply k8s secrets and CR without all checks passing
- added graceful failure when reading invalid TOML files
- SSL secrets are only generated for components that are selected
- updating ldap connection logic to use pyopenssl and remove jks truststore logic
- added supported for .arm certs
- fixed extra empty SSL secrets being generated for non-SSL enabled Database and LDAP's
- fixed user and group filter properties for CR generation
- validate UI changes and storage class validation update
- changed Oracle non-SSL JDBC URL to updated format
- fixed 'Issue Found' section for custom component files

### Refactor

- switched ldap validation logic to use ldap3 library
- refactored UI for issues
- refactor CR generation to account for new auth types
- refactor custom feature support to allow for expansion

## 1.6.7 (2023-12-02)

### Fix

- special characters are honored through TOML and validation shell commands
- added "FNCM AppLogin User" to the list for OS init
- added logic to avoid hidden files for SSL certificates parsing
- added remediation steps for database conventions
- added check for DB2 database name length
- replaced openssl library with cryptography library to work with certificates

## 1.6.1 (2023-09-22)

### Fix

- fixed ICN Oracle SQL template to include CREATE TRIGGER permissions
- fix to add content pattern only cpe, graphql, ban are selected

## 1.5.0 (2023-09-17)

### Feat

- add support for Oracle Pluggable databases as default

### Fix

- fixed missing key when component not selected for postgres

## 1.4.0 (2023-08-28)

### Feat

- added support for ICC for email
- support custom task manager group names
- support for custom component deployment in 5.5.11

### Fix

- apply ssl secrets only if the ssl secret folder is created
- increased timeout for storage class validation
- add migration of datasource names
- added 5.5.8 license links

## 1.3.0 (2023-08-21)

### Feat

- added support for Java SendMail

### Fix

- increased timeout for storage class validation
- add migration of datasource names
- added 5.5.8 license links