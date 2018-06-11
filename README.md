# Container-samples
Instructions and scripts for preparing the Content Navigator database and sample files for deploying with Kubernetes.

1. Sample CPE configuration files.

•	Use the below sample configuration files depending on your Directory Server & Database provider.

    o	XML configuration file for LDAP (ldap_AD.xml & ldap_LDAP.xml)
    o	XML configuration file for Db2 & Oracle JDBC Driver (DB2JCCDriver.xml  & OraJDBCDriver.xml )
    o	XML configuration file for GCD data source (GCD.xml & GCD_HADR.xml & GCD_Oracle.xml)
    o	XML configuration file for Object Store data source (OBJSTORE.xml & OBJSTORE_HADR.xml & OBJSTORE_Oracle.xml)
    o	CPE Product deployment file (cpe-deploy.yml)


2. Sample ICN configuration files.

•	Use the below sample configuration files depending on your Directory Server & Database provider.

    o	XML configuration file for LDAP (ldap_AD.xml & ldap_LDAP.xml)
    o	XML configuration file for Db2 & Oracle JDBC Driver (DB2JCCDriver.xml  & OraJDBCDriver.xml )
    o	XML configuration file for ICN data source (ICNDS.xml & ICNDS_HADR.xml & ICNDS_Oracle.xml)
    o	ICN Product deployment file (icn-deploy.yml)

3. CSS SSL keystore.

    •	A SSL keystore file cssSelfsignedServerStore is provided for the Content Search Services container. The certification inside the sample SSL keystore of the Content Search Services container are same as the certificaton inside the default sample keystores inside the Content Platform Engine container, to ensure SSL communication work well between these containers.
    •	CSS Product deployment file. (css-deploy.yml)
    
4. Sample CMIS configuration files.

•	Use the below sample configuration files depending on your Directory Server 

    o	XML configuration file for LDAP (ldap_AD.xml & ldap_LDAP.xml)
    o	CMIS Product deployment file. (cmis-deploy.yml)






