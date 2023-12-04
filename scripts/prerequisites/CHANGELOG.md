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
