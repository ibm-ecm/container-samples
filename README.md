# Container-samples
Instructions and sample files for deploying with Kubernetes.

1. Sample CPE configuration files.

• Use the below sample configuration files depending on your Directory Server & Database provider.

    o XML configuration file for LDAP (ldap_AD.xml & ldap_TDS.xml)
    o XML configuration file for Db2 & Oracle JDBC Driver (DB2JCCDriver.xml  & OraJDBCDriver.xml )
    o XML configuration file for GCD data source (GCD.xml & GCD_HADR.xml & GCD_Oracle.xml)
    o XML configuration file for Object Store data source (OBJSTORE.xml & OBJSTORE_HADR.xml & OBJSTORE_Oracle.xml)
    o CPE Product deployment file (cpe-deploy.yml)
    o Make sure the datasource name matches in GCD.xml with the GCDJNDINAME & GCDJNDIXANAME in deployment file (cpe-deploy.yml)


2. Sample ICN configuration files.

• Use the below sample configuration files depending on your Directory Server & Database provider.

    o XML configuration file for LDAP (ldap_AD.xml & ldap_TDS.xml)
    o XML configuration file for Db2 & Oracle JDBC Driver (DB2JCCDriver.xml  & OraJDBCDriver.xml )
    o XML configuration file for ICN data source (ICNDS.xml & ICNDS_HADR.xml & ICNDS_Oracle.xml)
    o ICN Product deployment file (icn-deploy.yml)

3. CSS SSL keystore.

    • A SSL keystore file cssSelfsignedServerStore is provided for the Content Search Services container. The certification inside the sample SSL keystore of the Content Search Services container are same as the certificaton inside the default sample keystores inside the Content Platform Engine container, to ensure SSL communication work well between these containers.
    • CSS Product deployment file. (css-deploy.yml)
    
4. Sample CMIS configuration files.

• Use the below sample configuration files depending on your Directory Server 

    o XML configuration file for LDAP (ldap_AD.xml & ldap_TDS.xml)
    o CMIS Product deployment file. (cmis-deploy.yml)

5. Sample ES configuration files.

• Use the below sample configuration files depending on your Directory Server & Database provider.

    o XML configuration file for LDAP (ldap_AD.xml & ldap_TDS.xml)
    o XML configuration file for Db2 & Oracle JDBC Driver (DB2JCCDriver.xml  & OraJDBCDriver.xml )
    o XML configuration file for ICN data source (ICNDS.xml & ICNDS_HADR.xml & ICNDS_Oracle.xml)
    o XML configuration file for Cross-Origin Resource Sharing (cors.xml)
    o Share Product deployment file (es-deploy.yml)

# Deployment of ECM product containers in K8s

Requirements

Before you deploy and run the ECM product containers in k8s, confirm the following.
•   Kubernetes Cluster
•   Kubernetes CLI
•   Setup necessary Persistent Volumes & Persistent Volume Claims.
•   Mount those created volumes.
•   Supported LDAP provider. 
•   Supported Database Server.
•   Download ECM product images and push those to K8s private repository.


Please review kubernetes documentation for more details on creating cluster 

https://kubernetes.io/docs/getting-started-guides/scratch/

Install Kube CLI

https://kubernetes.io/docs/tasks/tools/install-kubectl/

Download the ECM Product images from Passport Advantage. Here is the link which have the required product numbers.

    https://www-01.ibm.com/support/docview.wss?uid=swg24044874

From Passport Advantage, download the Docker images for the content services component containers:

    CPE-container-part-number.tar
    ICN-container-part-number.tar
    CSS-container-part-number.tar
    CMIS-container-part-number.tar
    ES-container-part-number.tar


1.   Extract the product image from part number and upload the image to kubernetes private registry.

CPE:
    
    o Extract image from part number --> tar xvf <CPE-container-part-number.tar>
    o docker load -i <image.tgz>
    o docker tag <docker store>/cpe:latest <private registry>/cpe:latest
    o docker push <private registry>/cpe:latest
    

Navigator:

    o Extract image from part number --> tar xvf <ICN-container-part-number.tar> . This will give 2 tgz files. 1) Navigator SSO 2) Navigator non-SSO
    o docker load <image.tgz>
    o docker tag <docker store>/navigator:latest <private registry>/navigator:latest
    o docker push <private registry>/navigator:latest

CSS:

    o Extract image from part number --> tar xvf <CSS-container-part-number.tar>
    o docker load <image.tgz>
    o docker tag <docker store>/css:latest <private registry>/css:latest
    o docker push <private registry>/css:latest
 	

CMIS:

    o Extract image from part number --> tar xvf <CMIS-container-part-number.tar>
    o docker load  <image.tgz>
    o docker tag <docker store>/cmis:latest <private registry>/cmis:latest
    o docker push <private registry>/cmis:latest
    
ES:

    o Extract image from part number --> tar xvf <ES-container-part-number.tar>
    o docker load  <image.tgz>
    o docker tag <docker store>/extshare:latest <private registry>/extshare:latest
    o docker push <private registry>/extshare:latest


 Content Engine Platform 

1.  Prepare persistence volume & Volume Claim for shared configuration.


    o CPE Configuration Volume --> for example cpe-cfgstore
    o CPE Logs Volume          --> for example cpe-logstore 
    o CPE Filestore Volume     --> for example cpe-filestore
    o CPE ICMRULES Volume      --> for example cpe-icmrulesstore
    o CPE FileNet Logs Volume  --> for example cpe-fnlogstore
    o CPE TEXTEXT Volume       --> for example cpe-textextstore
    o CPE BOOTSTRAP Volume     --> for example cpe-bootstrapstore
    
Refer to kubernetes document to setup persistence volumes
https://kubernetes.io/docs/concepts/storage/persistent-volumes/

Create necessary folders inside those volumes.
Example  

    o /cpecfgstore/cpe/configDropins/overrides
    o /cpelogstore/cpe/logs 
    o /cpefilestore/asa
    o /cpetextextstore/textext
    o /cpebootstrapstore/bootstrap
    o /cpefnlogstore/FileNet
    o /cpeicmrulesstore/icmrules


Make sure you set the ownership on all these folders to 501:500 
 
For example  --> chown –Rf 501:500 /cpecfgstore

1.1 Create the GCD database
Use the following information to create the GCD database

https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.planprepare.doc/p8ppi258.htm

1.2 Create the Object Store database

https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.planprepare.doc/p8ppi168.htm


Deployment of CPE in to K8s.
--

1.  Download the provided ldap xml file and modify the parameters to match with your existing LDAP server.


 For Microsoft Active Directory
 --
  https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/ldap_AD.xml

Modify ldap_AD.xml file with your LDAP host , baseDN , port , bindDN ,bindPassword. 

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have the different userFilter & groupFilter , modify those as well

For IBM Tivoli Directory Server
--

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/ldap_TDS.xml

Modify ldap_TDS.xml with your LDAP host , baseDN , port , bindDN,bindPassword.

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have different userFillter and groupFilter , please update those as well

2.  Download the provided datasource XML files and modify to match with your existing created GCD database and objectstore database information.



•   For DB2 database server.

GCD.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/GCD.xml

Modify GCD.xml file with your database serverName , GCD databaseName , portNumber , user & password.


OBJSTORE.xml
---

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/OBJSTORE.xml

Modify OBJSTORE.xml with your database serverName , Objectstore databaseName , portNumber , user & password.

If you have more than 1 objectstore , you can copy above and modify jndiName , jndiXAName , database serverName , Objectstore databaseName , portNumber , user & password

•   For DB2 HADR database

GCD_HADR.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/GCD_HADR.xml


Modify GCD_HADR.xml file with your database serverName , GCD databaseName , portNumber , user , password, clientRerouteAlternateServerName, clientRerouteAlternatePortNumber

OBJSTORE_HADR.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/OBJSTORE_HADR.xml

Modify OBJSTORE_HADR.xml file with your database serverName , Objectstore databaseName , portNumber , user , password, clientRerouteAlternateServerName, clientRerouteAlternatePortNumber.

If you have more than 1 objectstore , you can copy above and modify jndiName , jndiXAName , database serverName , Objectstore databaseName , portNumber , user & password, clientRerouteAlternateServerName, clientRerouteAlternatePortNumber.

•   For Oracle Database

GCD_Oracle.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/GCD_Oracle.xml

Modify GCD_Oracle.xml file with your database URL , user , password.

OBJSTORE_Oracle.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/OBJSTORE_Oracle.xml

 Modify the OBJSTORE_Oracle.xml file with your Objectstore database JDBC URL , user & password.
 If you have more than 1 objectstore , you can copy above and modify jndiName , jndiXAName , database URL, user & password.

3.  Copy the modified configuration xml files (ldap_TDS (or) ldap_AD.xml, GCD.xml , OBJSTORE.xml) to created configuratore store for CPE. 
    (Example  cpe-cfgstore). /cpecfgstore/cpe/configDropins/overrides
4.  Copy corresponding database JCCDriver xmll file to created configuratore store for CPE
    (Example  cpe-cfgstore). /cpecfgstore/cpe/configDropins/overrides

    For DB2 & DB2_HADR -->  DB2JCCDriver.xml

    https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/DB2JCCDriver.xml

    For Oracle         -->  OraJDBCDriver.xml

    https://github.com/ibm-ecm/container-samples/blob/master/CPE/configDropins/overrides/OraJDBCDriver.xml


5.  CPE product deployment has default SSL keystore files as part of deployment. If the user need to have your own SSL keystore and certificate files , they will need put the files (keystore.jks & trustore.jks) in the overrides folder.

(Example  cpe-cfgstore). /cpecfgstore/cpe/configDropins/overrides


6.  Copy the corresponding database JDBC driver files to created configuration store for CPE. 


For DB2  & DB2HADR  --> db2jcc4.jar , db2jcc_license_cu.jar
For Oracle          --> ojdbc8.jar

(Example  cpe-cfgstore). /cpecfgstore/cpe/configDropins/overrides

7.  Download CPE product deployment yml. (cpe-deploy.yml)

https://github.com/ibm-ecm/container-samples/blob/master/cpe-deploy.yml


8.  Modify the “image” name depending on your private repository.

(Example:  - image: mycluster.icp:8500/default/cpe:latest)


9.  Modify the yml to match with the environment with Persistent Volume Claim  names and subPath.
----
       volumeMounts:
          - name: cpecfgstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides"
            subPath: cpe/configDropins/overrides
          - name: cpelogstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/logs"
            subPath: cpe/logs
          - name: cpefilestore-pvc
            mountPath: "/opt/ibm/asa"
            subPath: asa
          - name: cpeicmrulesstore-pvc
            mountPath: "/opt/ibm/icmrules"
            subPath: icmrules
          - name: cpetextextstore-pvc
            mountPath: /opt/ibm/textext
            subPath: textext
          - name: cpebootstrapstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/lib/bootstrap"
            subPath: bootstrap
          - name: cpefnlogstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/FileNet"
            subPath: FileNet

      volumes:
        - name: cpecfgstore-pvc
          persistentVolumeClaim:
            claimName: "cpe-cfgstore"
        - name: cpelogstore-pvc
          persistentVolumeClaim:
            claimName: "cpe-logstore"
        - name: cpefilestore-pvc
          persistentVolumeClaim:
            claimName: "cpe-filestore"
        - name: cpeicmrulesstore-pvc
          persistentVolumeClaim:
            claimName: "cpe-icmrulesstore"
        - name: cpetextextstore-pvc
          persistentVolumeClaim:
            claimName: "cpe-textextstore"
        - name: cpebootstrapstore-pvc
          persistentVolumeClaim:
            claimName: "cpe-bootstrapstore"
        - name: cpefnlogstore-pvc
          persistentVolumeClaim:
            claimName: "cpe-fnlogstore"
---
10. The sample deployment yml is configured with minimum required JVM Heap.

                JVM_HEAP_XMS: 512m

                JVM_HEAP_XMS: 1024m


11. The sample deployment yml is configured with minimum k8s resources like below. 

                 CPU_REQUEST: “500m”

                 CPU_LIMIT: “1”

                 MEMORY_REQUEST: “512Mi”

                 MEMORY_LIMIT: “1024Mi” 

                 REPLICAS: 1 
                 
Please see below link for more details ..

https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/

If you want CPE product to be monitored from grafana dashboard and forward the logs to kibana dashboard add the following parameters to the deployment yml under env section. (cpe-deploy.yml)


          - name: MON_METRICS_WRITER_OPTION
            value: "0”
          - name: MON_METRICS_SERVICE_ENDPOINT
            value: troop1.ibm.com:2003
          - name: MON_BMX_GROUP
            value: 
          - name: MON_BMX_METRICS_SCOPE_ID
            value: 
          - name: MON_BMX_API_KEY
            value: 
          - name: MON_ECM_METRICS_COLLECT_INTERVAL
            value: 
          - name: MON_ECM_METRICS_FLUSH_INTERVAL
            value: 
          - name: MON_LOG_SHIPPER_OPTION
            value: “0”
          - name: MON_LOG_SERVICE_ENDPOINT
            value: troop1.ibm.com:5000
          - name: MON_BMX_LOGS_LOGGING_TOKEN
            value: 
          - name: MON_BMX_SPACE_ID
            value: 


12.  Execute the deployment file to deploy CPE.

       kubectl apply –f cpe-deploy.yml

13.  This deployment will create a service along with CPE deployment. 
14. Execute following command to get the Public IP and port to access CPE

       kubectl get svc | grep ecm-cpe



Deployment of ICN in to K8s.
--

1.  IBM FileNet P8 Content Platform Engine (CPE) container, deployed and configured
2.  Supported LDAP provider (Microsoft Active Directory or IBM Security Directory Server)
3.  Prepare the ICN database using provided script. (createICNDB.sh)

4.  Prepare persistence volume & Volume Claim for shared configuration.

  
    o ICN Configuration Volume --> for example icn-cfgstore
    o ICN Logs Volume          --> for example icn-logstore 
    o ICN Plugins   Volume     --> for example icn-pluginstore
    o ICN Viewer Cache Volume  --> for example icn-vwcachestore
    o ICN Viewer Logs Volume   --> for example icn-vwlogstore



Refer to kubernetes document to setup persistence volumes
https://kubernetes.io/docs/concepts/storage/persistent-volumes/

Create necessary folders inside those volumes.
Example  

   
    o /icncfgstore/icn/configDropins/overrides
    o /icnlogstore/icn/logs
    o /icnpluginstore/plugins
    o /icnvwcachestore/viewercache
    o /icnvwlogstore/viewerlogs


Make sure you set the ownership on these folders to 501:500 
 
For example  chown –Rf 501:500 /icncfgstore


1.  Download the provided ldap xml file and modify the parameters to match with your existing LDAP server.

For Microsoft Active Directory
--
https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/ldap_AD.xml

Modify ldap_AD.xml file with your LDAP host , baseDN , port , bindDN ,bindPassword. 

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have the different userFilter & groupFilter , modify those as well

For IBM Tivoli Directory Server
--

https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/ldap_TDS.xml

Modify ldap_TDS.xml with your LDAP host , baseDN , port , bindDN,bindPassword.

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have different userFillter and groupFilter , please update those as well

2.  Download the corresponding datasource XML files to the configuration store which created for ICN.


For Database DB2  ICNDS.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/ICNDS.xml

Modify the ICNDS.xml file with your database serverName , portNumber , user & password.

For Database DB2 HADR  ICNDS_HADR.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/ICNDS_HADR.xml


Modify the ICNDS_HADR.xml file with your database serverName ,portNumber , user , password , database clientRerouteAlternateServerName , clientRerouteAlternatePortNumber. 

For Database Oracle  ICNDS_Oracle.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/ICNDS_Oracle.xml

Modify the  ICNDS_Oracle file for the URL , database user and password.


3.  Copy these configuration files (ldap_AD.xml , ldap_TDS.xml) to created PVC for Navigator Configuration Store. (icn-cfgstore)

    (Example  icn-cfgstore). /icncfgstore/icn/configDropins/overrides


4.  Copy corresponding database JCCDriver xmll file to created configuratore store for ICN

(Example  icn-cfgstore). /icncfgstore/icn/configDropins/overrides

For DB2 & DB2_HADR -->  DB2JCCDriver.xml

https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/DB2JCCDriver.xml


For Oracle         -->  OraJDBCDriver.xml

https://github.com/ibm-ecm/container-samples/blob/master/ICN/configDropins/overrides/OraJDBCDriver.xml

5. Copy the corresponding database JDBC driver files to created configuration store for ICN. 

For DB2  & DB2HADR  --> db2jcc4.jar , db2jcc_license_cu.jar

For Oracle          --> ojdbc8.jar

(Example  cpe-cfgstore). /cpecfgstore/cpe/configDropins/overrides
                
6.  Download the sample Navigator product deployment yml. (icn-deploy.yml)

https://github.com/ibm-ecm/container-samples/blob/master/icn-deploy.yml


7.  Modify the “image” name depending on your private repository.

(Example:  - image: mycluster:8500/default/navigator:latest)


8.  Modify the yml to match with the environment with PVC names and subPath.

        volumeMounts:
          - name: icncfgstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides"
            subPath: icn/configDropins/overrides
          - name: icnlogstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/logs"
            subPath: icn/logs
          - name: icnpluginstore-pvc
            mountPath: "/opt/ibm/plugins"
            subPath: plugins
          - name: icnvwcachestore-pvc
            mountPath: "/opt/ibm/viewerconfig/cache"
            subPath: viewercache
          - name: icnvwlogstore-pvc
            mountPath: "/opt/ibm/viewerconfig/logs"
            subPath: viewerlogs

      volumes:
        - name: icncfgstore-pvc
          persistentVolumeClaim:
            claimName: "icn-cfgstore"
        - name: icnlogstore-pvc
          persistentVolumeClaim:
            claimName: "icn-logstore"
        - name: icnpluginstore-pvc
          persistentVolumeClaim:
            claimName: "icn-pluginstore"
        - name: icnvwcachestore-pvc
          persistentVolumeClaim:
            claimName: "icn-vwcachestore"
        - name: icnvwlogstore-pvc
          persistentVolumeClaim:
            claimName: "icn-vwlogstore"

9.  The sample deployment yml is configured with minimum required JVM Heap.

                JVM_HEAP_XMS: 512m

                JVM_HEAP_XMS: 1024m


10. The sample deployment yml is configured with minimum k8s resources like below. 

                 CPU_REQUEST: “500m”

                 CPU_LIMIT: “1”

                 MEMORY_REQUEST: “512Mi”

                 MEMORY_LIMIT: “1024Mi” 

                 REPLICAS: 1 

Please see below link for more details ..

https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/

11. If you want ICN product to be monitored from grafana dashboard and forward the logs to kibana dashboard specify the following as a environment variables inside icn-deploy.yml

          - name: MON_METRICS_WRITER_OPTION
            value: "0”
          - name: MON_METRICS_SERVICE_ENDPOINT
            value: troop1.ibm.com:2003
          - name: MON_BMX_GROUP
            value: 
          - name: MON_BMX_METRICS_SCOPE_ID
            value: 
          - name: MON_BMX_API_KEY
            value: 
          - name: MON_ECM_METRICS_COLLECT_INTERVAL
            value: 
          - name: MON_ECM_METRICS_FLUSH_INTERVAL
            value: 
          - name: MON_LOG_SHIPPER_OPTION
            value: “0”
          - name: MON_LOG_SERVICE_ENDPOINT
            value: troop1.ibm.com:5000
          - name: MON_BMX_LOGS_LOGGING_TOKEN
            value: 
          - name: MON_BMX_SPACE_ID
            value: 


12. Execute the deployment file to deploy ICN.
         Kubectl apply –f icn-deploy.yml
         
11. This deployment will create a service along with CPE deployment. 

12. Execute following command to get the Public IP and port to access ICN
         kubectl get svc | grep ecm-icn


Deployment of CSS in to K8s
--

1. Prepare persistence volume & Volume Claim for shared configuration.

   
    o CSS Configuration Volume --> for example css-cfgstore

    o CSS Logs Volume --> for example css-logstore

    o CSS Temp Volume --> for example css-tempstore
    
    o CSS Index Volume --> for example css-indexstore
    

Refer to kubernetes document to setup persistence volumes
https://kubernetes.io/docs/concepts/storage/persistent-volumes/

2. Create necessary folders inside those volumes.
    
Example:

   
    o /csscfgstore/css/CSS_Server_data/sslkeystone
    o /csstempstore/CSS_Server_temp
    o /cssindexstore/CSS_Indexes
    o /csslogstore/CSS_Server_log
    

Make sure you set the ownership on these folders to 501:500 
 
For example  chown –Rf 501:500 /csscfgstore


3.  Download the cssSelfsignedServerStore file and copy to CSS Configuration Store.
(Example: css-cfgstore  /csscfgstore/css/CSS_Server_data/ sslkeystone

https://github.com/ibm-ecm/container-samples/tree/master/CSS/CSS_Server_data/sslkeystone

4.  Download the sample CSS Search deployment file. (css-search-deploy.yml)

https://github.com/ibm-ecm/container-samples/blob/master/css-deploy.yml

          
5.  Modify the “image” name depending on your private repository.

(Example:  - image: mycluster.icp:8500/default/css:latest)

6.  Modify the yml to match with the environment with PVC names and subPath.
        volumeMounts:
          - name: csscfgstore-pvc
            mountPath: "/opt/IBM/ContentSearchServices/CSS_Server/data"
            subPath: css/CSS_Server_data/sslkeystone
          - name: csslogstore-pvc
            mountPath: "/opt/IBM/ContentSearchServices/CSS_Server/log"
            subPath: CSS_Server_log/csssearch_logs
          - name: csstempstore-pvc
            mountPath: "/opt/IBM/ContentSearchServices/CSS_Server/temp"
            subPath: CSS_Server_temp
          - name: cssindexstore-pvc
            mountPath: "/CSSIndex1_OS1"
            subPath: CSS_Indexes/CSSIndexArea1_OS1

      volumes:
        - name: csscfgstore-pvc
          persistentVolumeClaim:
            claimName: "css-cfgstore"
        - name: csslogstore-pvc
          persistentVolumeClaim:
            claimName: "css-logstore"
        - name: csstempstore-pvc
          persistentVolumeClaim:
            claimName: "css-tempstore"
        - name: cssindexstore-pvc
          persistentVolumeClaim:
            claimName: "css-indexstore"

7.  The sample deployment yml is configured with minimum required JVM Heap.

        JVM_HEAP_XMX: 3072

8.  The sample deployment yml is configured with minimum k8s resources like 

                 CPU_REQUEST: “500m”


                 MEMORY_REQUEST: “512Mi”

                 MEMORY_LIMIT: “1024Mi” 


Please see below link for more details ..

https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/

9. If you want CSS product to be monitored from grafana dashboard and forward the logs to kibana dashboard specify the following as a environment variables inside css-search-deploy.yml

          - name: MON_METRICS_WRITER_OPTION
            value: "0”
          - name: MON_METRICS_SERVICE_ENDPOINT
            value: troop1.ibm.com:2003
          - name: MON_BMX_GROUP
            value: 
          - name: MON_BMX_METRICS_SCOPE_ID
            value: 
          - name: MON_BMX_API_KEY
            value: 
          - name: MON_ECM_METRICS_COLLECT_INTERVAL
            value: 
          - name: MON_ECM_METRICS_FLUSH_INTERVAL
            value: 
          - name: MON_LOG_SHIPPER_OPTION
            value: “0”
          - name: MON_LOG_SERVICE_ENDPOINT
            value: troop1.ibm.com:5000
          - name: MON_BMX_LOGS_LOGGING_TOKEN
            value: 
          - name: MON_BMX_SPACE_ID
            value: 


10.  Execute CSS Search deployment in to Kubernetes

      kubectl apply –f css-deploy.yml


Configuring Content Platform Engine for CSS

1. Get Content Search Service authentication token The authentication token is used to communicate with the CPE server. Record this authentication token string value; it is used in text search configuration in Content Platform Engine.

Connect to the running Content Search Service Docker container:

kubectl exec –it [ CSS Search / Index Pod Name ] bash

2. Execute Content Search Service configTool to get token information:

cd /opt/IBM/ContentSearchServices/CSS_Server/bin

./configTool.sh printToken –configPath ../config

3. Check the output and store the authentication token:

The authentication token is printed below. This token is used to communicate with the server. Store the token if applicable.
  RNUNEWc=
  The encryption key is printed below. This key is used to encrypt the password during text index backup and restore operations. Store the key if applicable.
  RNUNEWd4rc35R80IsYNLTg==


4. Create the Content Search Service server in the Administration Console for Content Platform Engine:

•   Log in to the Administration Console and navigate to Domain > Global Configuration > Administration > Text Search Servers > New.

•   Define the Text Search Server property values as follows:

•   Mode: Dual: Index and Search

•   Status: Enabled

•   Host name: { csssearch-cluster }

•   Port: {8199 }

•   Authentication token: {The CSS authentication token, "RNUNEWc=" for the example}

•   Set the Is SSL Enabled field value to True.

•   Set the Validate Server Certificate and the Validate Certificate Host field  

•   values to False.



Deployment of CMIS in to K8s
--

1. Prepare persistence volume & Volume Claim for shared configuration.


    o CMIS Configuration Volume --> for example cmis-cfgstore

    o CMIS Logs Volume          --> for example cmis-logstore


Refer to kubernetes document to setup persistence volumes
https://kubernetes.io/docs/concepts/storage/persistent-volumes/

2. Create necessary folders inside those volumes.

   Example  

    o /cmiscfgstore/cmis/configDropins/overrides

    o /cmislogstore/cmis/logs


3. Make sure you set the ownership on these folders to 501:500 
 
For example  chown –Rf 501:500 /cmiscfgstore


1.  Download the provided ldap xml file and modify the parameters to match with your existing LDAP server.

For Microsoft Active Directory
--

https://github.com/ibm-ecm/container-samples/blob/master/CMIS/configDropins/overrides/ldap_AD.xml

Modify ldap_AD.xml file with your LDAP host , baseDN , port , bindDN ,bindPassword. 

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have the different userFilter & groupFilter , modify those as well

For IBM Tivoli Directory Server
--

https://github.com/ibm-ecm/container-samples/blob/master/CMIS/configDropins/overrides/ldap_TDS.xml

Modify ldap_TDS.xml with your LDAP host , baseDN , port , bindDN,bindPassword.

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have different userFillter and groupFilter , please update those as well


2.  Copy the modified LDAP xml (ldap_AD.xml (or) ldap_TDS.xml) to the created CMIS configuration volume.

(Example: cmis-cfgstore  /cmiscfgstore/cmis/configDropins/overrides)

3.  Download the sample CMIS product deployment yml. (cmis-deploy.yml)


https://github.com/ibm-ecm/container-samples/blob/master/cmis-deploy.yml

4.  Modify the “image” name depending on your private repository.

(Example:  - image: mycluster:8500/default/cmis:latest)


5.  Modify the yml to match with the environment with PVC names and subPath.

        volumeMounts:
          - name: cmiscfgstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides"
            subPath: configDropins/overrides
          - name: cmislogstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/logs"
            subPath: cmis/logs

      volumes:
        - name: cmiscfgstore-pvc
          persistentVolumeClaim:
            claimName: "cmis-cfgstore"
        - name: cmislogstore-pvc
          persistentVolumeClaim:
            claimName: "cmis-logstore"

6.  Modify CE_URL with corresponding CPE URL .

(Example  http://<CE_IP>:<PORT>/wsi/FNCEWS40MTOM)

7.  The deployment yml has the default required parameters for CMIS configuration. You can modify those to meet your requirements.

                 CMC_TIME_TO_LIVE: 3600000
                 CRC_TIME_TO_LIVE: 3600000
                 USER_CACHE_TIME_TO_LIVE: 28800000
                 CHECKOUT_COPYCONTENT: true
                 DEFAULTMAXITEMS: 25
                 CVL_CACHE: true
                 SECUREMETADATACACHE: false
                 FILTERHIDDENPROPERTIES: true
                 QUERYTIMELIMIT: 180
                 RESUMABLEQUERIESFORREST: true
                 ESCAPEUNSAFESTRINGCHARACTERS: false
                 MAXSOAPSIZE: 180
                 PRINTFULLSTACKTRACE: false
                 FOLDERFIRSTSEARCH: false
                 IGNOREROOTDOCUMENTS: false
                 SUPPORTINGTYPEMUTABILITY: false



8.  The sample deployment yml is configured with minimum required JVM Heap.
                JVM_HEAP_XMS: 512m

                JVM_HEAP_XMS: 1024m

9.  The sample deployment yml is configured with minimum k8s resources like below. 
                 CPU_REQUEST: “500m”

                 CPU_LIMIT: “1”

                 MEMORY_REQUEST: “512Mi”

                 MEMORY_LIMIT: “1024Mi” 

                 REPLICAS: 1 

Please see below link for more details ..

https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/

10. If you want CMIS product to be monitored from grafana dashboard and forward the logs to kibana dashboard specify the following as a environment variables inside cmis-deploy.yml

          - name: MON_METRICS_WRITER_OPTION
            value: "0”
          - name: MON_METRICS_SERVICE_ENDPOINT
            value: troop1.ibm.com:2003
          - name: MON_BMX_GROUP
            value: 
          - name: MON_BMX_METRICS_SCOPE_ID
            value: 
          - name: MON_BMX_API_KEY
            value: 
          - name: MON_ECM_METRICS_COLLECT_INTERVAL
            value: 
          - name: MON_ECM_METRICS_FLUSH_INTERVAL
            value: 
          - name: MON_LOG_SHIPPER_OPTION
            value: “0”
          - name: MON_LOG_SERVICE_ENDPOINT
            value: troop1.ibm.com:5000
          - name: MON_BMX_LOGS_LOGGING_TOKEN
            value: 
          - name: MON_BMX_SPACE_ID
            value: 


11. Execute the deployment file to deploy CMIS.

    kubectl apply –f cmis-deploy.yml

12. This deployment will create a service along with CPE deployment. 
13. Execute following command to get the Public IP and port to access CMIS

    kubectl get svc | grep ecm-cmis
    
    
Deployment of External Share in to K8s.
--

1.  IBM FileNet P8 Content Platform Engine (CPE) container, deployed and configured
2.  IBM Content Navigator (ICN) container, deployed and configured
3.  Supported LDAP provider (Microsoft Active Directory or IBM Security Directory Server)
4.  Prepare persistence volume & Volume Claim for shared configuration.

  
    o ES Configuration Volume --> for example es-cfgstore
    
    o ES Logs Volume          --> for example es-logstore 
   

Refer to kubernetes document to setup persistence volumes
https://kubernetes.io/docs/concepts/storage/persistent-volumes/

Create necessary folders inside those volumes.
Example  

   
    o /escfgstore/es/configDropins/overrides
    o /eslogstore/es/logs
   

Make sure you set the ownership on these folders to 501:500 
 
For example  chown –Rf 501:500 /escfgstore


1.  Download the provided ldap xml file and modify the parameters to match with your existing LDAP server.

For Microsoft Active Directory
--
https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/ldap_AD.xml

Modify ldap_AD.xml file with your LDAP host , baseDN , port , bindDN ,bindPassword. 

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have the different userFilter & groupFilter , modify those as well

For IBM Tivoli Directory Server
--

https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/ldap_TDS.xml

Modify ldap_TDS.xml with your LDAP host , baseDN , port , bindDN,bindPassword.

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have different userFillter and groupFilter , please update those as well

For ldapExt.xml
--
In the on-premises configuration, you add the external user LDAP server in the Administration Console for Content Platform Engine and in IBM Content Navigator. In the container environment, you add the external server as an additional ldapExt.xml file in the configuration overrides directory for each component.

. The 2 LDAP XML files must be present in the /configDropins/override directory for Content Platform Engine, IBM Content Navigator, and for the external share container
    
. The realm name in the LDAPext.xml file must be the same in each copy, and must be different from the realm name in the original ldap_AD.xml or ldap_TDS.xm file.


2.  Download the corresponding datasource XML files to the configuration store which created for ES.


For Database DB2  ICNDS.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/ICNDS.xml

Modify the ICNDS.xml file with your database serverName , portNumber , user & password.

For Database DB2 HADR  ICNDS_HADR.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/ICNDS_HADR.xml


Modify the ICNDS_HADR.xml file with your database serverName ,portNumber , user , password , database clientRerouteAlternateServerName , clientRerouteAlternatePortNumber. 

For Database Oracle  ICNDS_Oracle.xml
--

https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/ICNDS_Oracle.xml

Modify the  ICNDS_Oracle file for the URL , database user and password.


3.  Copy these configuration files (ldap_AD.xml , ldap_TDS.xml, ldapExt.xml) to created PVC for External Share Configuration Store. (es-cfgstore)

    (Example  es-cfgstore). /escfgstore/es/configDropins/overrides
    
    Copy ldapExt.xml to cpe-cfgstore and icn-cfgstore


4.  Copy corresponding database JCCDriver xmll file to created configuratore store for ES

(Example  es-cfgstore). /escfgstore/es/configDropins/overrides

For DB2 & DB2_HADR -->  DB2JCCDriver.xml

https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/DB2JCCDriver.xml


For Oracle         -->  OraJDBCDriver.xml

https://github.com/ibm-ecm/container-samples/blob/master/extShare/configDropins/overrides/OraJDBCDriver.xml

5. Copy the corresponding database JDBC driver files to created configuration store for ES. 

For DB2  & DB2HADR  --> db2jcc4.jar , db2jcc_license_cu.jar

For Oracle          --> ojdbc8.jar

(Example  es-cfgstore). /escfgstore/es/configDropins/overrides

For Cross-Origin Resource Sharing cors.xml
--

6.  Copy the Cross-Origin Resource Sharing cors.xml file to create configuration store for ES

(Example  es-cfgstore). /escfgstore/es/configDropins/overrides

7.  Download the sample External Share product deployment yml. (es-deploy.yml)

https://github.com/ibm-ecm/container-samples/blob/master/es-deploy.yml


8.  Modify the “image” name depending on your private repository.

(Example:  - image: mycluster:8500/default/extshare:latest)


9.  Modify the yml to match with the environment with PVC names and subPath.

        volumeMounts:
          - name: escfgstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides"
            subPath: es/configDropins/overrides
          - name: eslogstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/logs"
            subPath: es/logs
         
      volumes:
        - name: escfgstore-pvc
          persistentVolumeClaim:
            claimName: "es-cfgstore"
        - name: eslogstore-pvc
          persistentVolumeClaim:
            claimName: "es-logstore"
       
10.  The sample deployment yml is configured with minimum required JVM Heap.

                JVM_HEAP_XMS: 512m

                JVM_HEAP_XMS: 1024m


11. The sample deployment yml is configured with minimum k8s resources like below. 

                 CPU_REQUEST: “500m”

                 CPU_LIMIT: “1”

                 MEMORY_REQUEST: “512Mi”

                 MEMORY_LIMIT: “1024Mi” 

                 REPLICAS: 1 

Please see below link for more details ..

https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/

12. If you want ES product to be monitored from grafana dashboard and forward the logs to kibana dashboard specify the following as a environment variables inside es-deploy.yml

          - name: MON_METRICS_WRITER_OPTION
            value: "0”
          - name: MON_METRICS_SERVICE_ENDPOINT
            value: troop1.ibm.com:2003
          - name: MON_BMX_GROUP
            value: 
          - name: MON_BMX_METRICS_SCOPE_ID
            value: 
          - name: MON_BMX_API_KEY
            value: 
          - name: MON_ECM_METRICS_COLLECT_INTERVAL
            value: 
          - name: MON_ECM_METRICS_FLUSH_INTERVAL
            value: 
          - name: MON_LOG_SHIPPER_OPTION
            value: “0”
          - name: MON_LOG_SERVICE_ENDPOINT
            value: troop1.ibm.com:5000
          - name: MON_BMX_LOGS_LOGGING_TOKEN
            value: 
          - name: MON_BMX_SPACE_ID
            value: 


13. Execute the deployment file to deploy ES.

        Kubectl apply –f es-deploy.yml

14. This deployment will create a service along with CPE and ICN deployment. 

15. Execute following command to get the Public IP and port to access ES

         kubectl get svc | grep ecm-es


Deployment of ContentGraphQL in to K8s.
--

1.  IBM FileNet P8 Content Platform Engine (CPE) container, deployed and configured.
2.  Prepare persistence volume & Volume Claim for shared configuration.

  
    o CRS Configuration Volume --> for example crs-cfgstore
    
    o CRS Lib Volume --> for example crs-libstore
    
    o CRS Logs Volume          --> for example crs-logstore 
   

Refer to kubernetes document to setup persistence volumes
https://kubernetes.io/docs/concepts/storage/persistent-volumes/

Create necessary folders inside those volumes.
Example  

   
    o /crscfgstore/crs/configDropins/overrides
    o /crscfgstore/crs/lib
    o /crslogstore/crs/logs
   

Make sure you set the ownership on these folders to 50001:50000
 
For example  chown –Rf 50001:50000 /crscfgstore

1.  Download the provided ldap xml file and modify the parameters to match with your existing LDAP server.

Copy ldap_AD.xml for MS Active Directory from configuration dropins folder (CPE/configDropins/overrides) to ContentGraphQL/configDropins/overrides                                                     --
--
https://github.com/ibm-ecm/container-samples/blob/master/cpe/configDropins/overrides/ldap_AD.xml

Modify ldap_AD.xml file with your LDAP host , baseDN , port , bindDN ,bindPassword. 

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have the different userFilter & groupFilter , modify those as well

Copy ldap_tds.xml for IBM Tivoli Directory Server from configuration dropins folder (CPE/configDropins/overrides) to ContentGraphQL/configDropins/overrides                                                     --
--

https://github.com/ibm-ecm/container-samples/blob/master/cpe/configDropins/overrides/ldap_TDS.xml

Modify ldap_TDS.xml with your LDAP host , baseDN , port , bindDN,bindPassword.

If your LDAP server uses SSL port use that port and change sslEnabled=”true”

If you have different userFillter and groupFilter , please update those as well

Copy Content Process Engine datasource xml files from the configuration dropins folder (CPE/configDropins/overrides) to ContentGraphQL/configDropins/overrides
--

GCD.xml , OBJSTORE.xml for DB2 Database Server.
GCD_Oracle.xml , OBJSTORE_Oracle.xml for Oracle Database Server.
GCD_HADR.xml, OBJSTORE_HADR.xml for DB2 HADR environment.


Copy corresponding database driver file and license file to configDropis/overrides
--

DB2JCCDriver.xml
OraJDBCDriver.xml

For Cross-Origin Resource Sharing cors.xml
--

3. Copy the Cross-Origin Resource Sharing cors.xml file to create configuration store for ES

(Example  es-cfgstore). /crscfgstore/crs/configDropins/overrides

Download the sample External Share product deployment yml. (es-deploy.yml)

https://github.com/ibm-ecm/container-samples/blob/master/crs-deploy.yml


4.  Modify the “image” name depending on your private repository.

(Example:  - image: mycluster:8500/default/crs:5.5.3)

5. Modify the "CPE_URI" , "CPE_USER" , "CPE_PASSWORD" values with your existing deployed URL.

6.  Modify the yml to match with the environment with PVC names and subPath.

        volumeMounts:
          - name: crscfgstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides"
            subPath: crs/configDropins/overrides
          - name: crslogstore-pvc
            mountPath: "/opt/ibm/wlp/usr/servers/defaultServer/logs"
            subPath: crs/logs
         
      volumes:
        - name:crscfgstore-pvc
          persistentVolumeClaim:
            claimName: "crs-cfgstore"
        - name: crslogstore-pvc
          persistentVolumeClaim:
            claimName: "crs-logstore"
       
7.  The sample deployment yml is configured with minimum required JVM Heap.

                JVM_HEAP_XMS: 512m

                JVM_HEAP_XMS: 1024m


8. The sample deployment yml is configured with minimum k8s resources like below. 

                 CPU_REQUEST: “500m”

                 CPU_LIMIT: “1”

                 MEMORY_REQUEST: “512Mi”

                 MEMORY_LIMIT: “1024Mi” 

                 REPLICAS: 1 

Please see below link for more details ..

https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/


Troubleshooting & Tips
---

1   How to list pods after executing product YML ?

Kubectl get pods 

2.  How to list services after executing product YML ?

Kubectl get svc

3.  How to get Cluster information ?

Kubectl cluster-info

4.  How to get cluster configuration ?

Kubectl config view

5.  Getting error “Error Syncing Pod” after executing product YML ?

This error happens when the image name which was used in deployment yml is not found or not accessible. Please edit the deployment yml and modify with correct image name.

6.  Deployment is failed with Pod status “ImagePullBackOff”

When you describe the pod you will notice “ Failed to pull image <image name> .
    Correct the image name inside deployment yml and redeploy the application.

7.  How do I access the deployed pod ?

•   Get the corresponding pods

Kubectl get pods

•   Access the pod

Kubectl exec –it {pod name} bash

8.  How do I check the logs for a deployed application ?

Kubectl get pods 

Kubectl logs {pod name}



9.  Deployment hung with pod status “Container Creating” ?

One of the possible reason for this behavior is due to defined Persistent Volumes does not exist.

Describe the deployed pod to get the details of the deployment and errors.

Kubectl descrive pod <pod name>

You will notice the similar error like below ..

Warning FailedMount  Failed to attach volume <volume name>

Please correct the error by modifying the deployment yml with correct volume name and deploy again.

10. How do I delete the deployment and services ?

Delete the deployment

Kubectl delete –f <deployment yaml>

If the deployment yaml contains the definition for both deployment and service then the above command will delete both.

Delete the services

Kubecl delete –f <svc-deploy yml>


11. Unable to login to ACCE after deployment ?

Mostly this error happens when the specified user in ldap.xml does not have access to the domain.

You can access the product logs with the following ways and address the issue my modifying ldap.xml with correct user.

•   Access the CPE pod to get to the logs (messages.log) 

Kubectl exec –it <podname> bash

cat logs/<podname>messages.log

•   Access the specified persistent volume for logs.

cd /cplogstore/cpe/logs/<podname>

cat messages.log

           
         

