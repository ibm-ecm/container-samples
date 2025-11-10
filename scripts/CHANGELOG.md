## 6.0.2 (2025-11-10)

### Fix

- upgrade will remove older image tags from generated custom resource
- mssql jdbc driver version updated to 12.2.1

## 6.0.0 (2025-10-29)

### Fix

- docker python library and support has been removed, only podman is supported for image loading and credential checks
- prerequisite scripts request a namespace parameter to ensure all k8s interactions are done in the correct namespace context
- running mustgather and prerequisite scripts can now be run from inside the operator pod, using service account permissions
- namespace create will not allow uppercase characters to avoid k8s namespace creation errors
- `ROKS` platform option have been removed, as OCP will apply to both ROKS and OCP clusters
- a single set of jdbc drivers are now used for all FNCM and Java versions, reducing the download size and complexity
- oracle jdbc driver version updated to 19.28.0

### Feat

- all property and generated files are namespaced scoped to avoid conflicts and improve multi-namespace management
- kubectl binary requirement has been removed, all kubernetes interactions are done via python kubernetes client
- specific java version is no longer required, script will continue with any installed java version 8 or higher
- automatic version detection for deployment, upgrade, and prerequisite scripts
- simplified OIDC CR generation for IDP configurations
- `fncm.ibm.com/backup-type: mandatory` label added to all secrets that would need to be backed up for migrations or restores
- loadimages scripts now supports digests for image loading
- mustgather will now collect HPA (Horizontal Pod Autoscaler) information if configured
- mustgather will now collect environmental variables from pods 
- prerequisite validation will check SAN of supplied certificates against hostnames
- non-ssl verification fallback for database and ldap connections if ssl connection fails or using self-signed certificates

## 5.1.3 (2025-09-19)

### Fix

- refactored program validation check to use shutil.which

## 5.1.2 (2025-08-11)

### Fix

- added support for IDP authentication when moving LDAP settings from OnPrem install

## 5.1.1 (2025-07-31)

### feat

- added support for rolling update for FNCM 5.6.x and 5.7.x deployments

## 5.1.0 (2025-06-30)

### Fix

- fixed invalid operator image for silent deployment
- fixed missing variable when operator install is in pending state

## 5.0.0 (2025-06-20)

### Feat

- added support for FNCM 5.7.0 deployment
- added validation checks for IDP (Identity Provider) configuration
- added validation checks for SCIM (System for Cross-domain Identity Management) configuration
- added support for DB2RDS and DB2RDSHA databases
- added flags to customize pvc size for validation 
- added support for ipv6 addresses in prerequisite scripts
- added support for multi-certificates and multi-certificates files 
- switched all java connections to use pkcs12 truststore
- added support for network policy gathering in MustGather
- added oracle database fips support 

### Refactor

- refactored generation scripts to use jinja2 templates

### Fix

- fixed unknown ldap type when moving xml files
- fixed k8s namespace check in deployment script
- commented all tablespaces in generated CR 

## 4.4.4 (2025-04-30)

### Fix

- fixed appVersion check for new license format during cr upgrade
- generated verification cr section will have the correct objectstore names
- keeps the objectstore name as the same case provided in the property files

## 4.4.2 (2025-03-21)

### Feat

- added global catalog server check for ms active directory

### Fix

- fixed logging error for registry reachability check
- fixed datasource names for objectstore init section in cr
- fixed external file logging feature

## 4.3.0 (2025-02-28)

### Fix

- changed ldap connection to same test as operator deployment
- fixed number of tasks for OCP cluster setup
- increased timeout for operator deployment

### Feat

- flags introduced to skip validation tests
- ip are now tested if hostnames are supplied

## 4.1.1 (2025-01-31)

### Fix

- fixed oracle password special character handling in db template

### Feat

- added support for openshift airgap in loadImages script

## 4.0.0 (2025-01-23)

### Fix

- fixed oracle url parsing error during database validation
- fixed version query when using move / migration feature
- fixed missing external share optional component
- added lc_bind_secret for multildap configuration
- replaced kubectl connection check with 'kubectl version'
- fixed case for oracle tablespaces

## 3.1.1 (2024-10-10)

### Fix

- fixed process engine duplicate region name for generated custom resource
- fixed mustgather to allow select component to have zero pods available
- added unique name and timestamp to mustgather tar file
- fixed mustgather for unparseable custom resource
- fixed cleanup script to delete catalog source for private catalog deployments

## 3.1.0 (2024-09-11)

### Feat

- added support for running MustGather with only the operator deployed
- added support for inProgress Operator Ansible log in MustGather
- adding support for table lob and index storage locations for os database

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
