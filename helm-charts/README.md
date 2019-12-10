# Deploying with Helm charts

> **NOTE**: This procedure covers a Helm chart deployment on certified Kubernetes. To deploy the Enterprise Content Management products on IBM Cloud Private 3.1.2, you must use the Business Automation Configuration Container. 

## Requirements and Prerequisites

Ensure that you have completed the following tasks:

- [Preparing your FileNet environment](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare.htm) 
- [Preparing your Kubernetes server](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare_env_k8s.htm)
- [Downloading the product archives and loading the component images](../README.md)


The Helm commands for deploying the FileNet Content Manager images include a number of required command parameters for specific environment and configuration settings. Review the reference topics for these parameters and determine the values for your environment as part of your preparation:

- [Content Platform Engine Helm command parameters](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_configcperef.htm)

- [IBM Content Navigator command parameters](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_configicnref.htm)

- [Content Search Services Helm command parameters](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_configcssref.htm)

- [Content Management Interoperability Services Helm command parameters](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_configcmisref.htm)

## Tips: 

- On Openshift, an expired Docker secret can cause errors during deployment. If an admin.registry key already exists and has expired, delete the key with the following command:
   ```console
   kubectl delete secret admin.registrykey -n <new_project>
   ```
    Then generate a new Docker secret with the following command:
    ```console
   kubectl create secret docker-registry admin.registrykey --docker-server=<registry_url> --docker-username=<new_user> --docker-password=$(oc whoami -t) --docker-email=ecmtest@ibm.com -n <new_project>
   ```
- If you are installing IBM Content Foundation / IBM FileNet Content Manager 5.5.3 GA on OpenShift, ensure that sa.scc.uid-range includes 50001 and sa.scc.supplemental-groups includes 50000.


## Initializing the command line interface
Use the following commands to initialize the command line interface:
1. Run the init command:
    ```$ helm init --client-only ```
2. Check whether the command line can connect to the remote Tiller server:
   ```console
   $ helm version
    Client: &version.Version{SemVer:"v2.9.1", GitCommit:"f6025bb9ee7daf9fee0026541c90a6f557a3e0bc", GitTreeState:"clean"}
    Server: &version.Version{SemVer:"v2.9.1", GitCommit:"f6025bb9ee7daf9fee0026541c90a6f557a3e0bc", GitTreeState:"clean"}
    ```

## Deploying images
Provide the parameter values for your environment and run the command to deploy the image.
  > **Tip**: Copy the sample command to a file, edit the parameter values, and use the updated command for deployment.
  > **Tip**: The values that are provided for 'resources' inside helm commands are examples only. Each deployment must take into account the demands that their particular workload will place on the system and adjust values accordingly. 
  
If you are installing or upgrading to IBM Content Foundation / IBM FileNet Content Manager 5.5.3 interim fixes (e.g., CPE 5.5.3 IF1+, ICN 3.0.6 IF2+, CMIS 3.0.4 IF8+, CSS 5.5.5 IF1+, CRS 5.5.3 IF1+, and ExtShare 3.0.6 LA001+), update the ownership and permissions for all of your persistent volumes and persistent volume claims folders, for Content Platform Engine, Content Search Services, IBM Content Navigator, Content Management Interoperability Services, and External Share.

For all folders created for your deployment, the group ownership and file permissions must be set to allow the container to access.
   - For example, if your CPE configuration data is stored under /cpecfgstore
   - Change the settings to -R 0, for example:
         ```chgrp -R 0 /cpecfgstore```
   - Change the current permission settings to g=u, for example:
         ```chmod -Rf g=u /cpecfgstore```
    
    
For deployments on Red Hat OpenShift, note the following considerations for whether you want to use the Arbitrary UID capability in your environment:

- If you don't want to use Arbitrary UID capability in your Red Hat OpenShift environment, deploy the images as described in the following sections.

- If you do want to use Arbitrary UID, prepare for deployment by checking and if needed editing your Security Context Constraint:
  - Set the desired user id range of minimum and maximum values for the project namespace:
  
    ```$ oc edit namespace <project> ```

    For the uid-range annotation, verify that a value similar to the following is specified:
    
    ```$ openshift.io/sa.scc.uid-range=1000490000/10000 ```
    
    This range is similar to the default range for Red Hat OpenShift.
  
  - Remove authenticated users from anyuid (if set):
  
     ```$ oc adm policy remove-scc-from-group anyuid system:authenticated ```

  - Update the runAsUser value. 
    Find the entry:
    
    ```
    $ oc get scc <SCC name> -o yaml
        runAsUser:
        type: RunAsAny
    ```

     Update the value:
    
    ```
    $ oc get scc <SCC name> -o yaml
      runAsUser:
      type:  MustRunAsRange
    ```
    
    
To deploy **Content Platform Engine:**

- Installing 5.5.3 GA:

   ```console
   $ helm install ibm-dba-contentservices-3.0.0.tgz --name dbamc-cpe --namespace dbamc --set cpeProductionSetting.license=accept,cpeProductionSetting.jvmHeapXms=512,cpeProductionSetting.jvmHeapXmx=1024,cpeProductionSetting.licenseModel=FNCM.CU,dataVolume.existingPVCforCPECfgstore=cpe-cfgstore,dataVolume.existingPVCforCPELogstore=cpe-logstore,dataVolume.existingPVCforFilestore=cpe-filestore,dataVolume.existingPVCforICMrulestore=cpe-icmrulesstore,dataVolume.existingPVCforTextextstore=cpe-textextstore,dataVolume.existingPVCforBootstrapstore=cpe-bootstrapstore,dataVolume.existingPVCforFNLogstore=cpe-fnlogstore,autoscaling.enabled=False,resources.requests.cpu=1,replicaCount=1,image.repository=<cluster.registry.repo>:<port>/dbamc/cpe,image.tag=ga-553-p8cpe,cpeProductionSetting.gcdJNDIName=FNGCDDS,cpeProductionSetting.gcdJNDIXAName=FNGCDDSXA 
   ```
 - Installing 5.5.3 IF1 (and above):
 
   ```console
   $ helm install ibm-dba-contentservices-3.1.0.tgz --name dbamc-cpe --namespace dbamc --set cpeProductionSetting.license=accept,cpeProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=18,cpeProductionSetting.JVM_MAX_HEAP_PERCENTAGE=33,service.externalmetricsPort=9103,cpeProductionSetting.licenseModel=FNCM.CU,dataVolume.existingPVCforCPECfgstore=cpe-cfgstore,dataVolume.existingPVCforCPELogstore=cpe-logstore,dataVolume.existingPVCforFilestore=cpe-filestore,dataVolume.existingPVCforICMrulestore=cpe-icmrulesstore,dataVolume.existingPVCforTextextstore=cpe-textextstore,dataVolume.existingPVCforBootstrapstore=cpe-bootstrapstore,dataVolume.existingPVCforFNLogstore=cpe-fnlogstore,autoscaling.enabled=False,resources.requests.cpu=1,replicaCount=1,image.repository=<image_repository_url>:<port>/dbamc/cpe,image.tag=ga-553-p8cpe-if001,cpeProductionSetting.gcdJNDIName=FNGDDS,cpeProductionSetting.gcdJNDIXAName=FNGDDSXA 
   ```
   
   Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
   
To deploy **IBM Content Navigator:**

- Installing 3.0.6 GA:

   ```console
   $ helm install ibm-dba-navigator-3.0.0.tgz --name dbamc-navigator --namespace dbamc --set icnProductionSetting.license=accept,icnProductionSetting.jvmHeapXms=512,icnProductionSetting.jvmHeapXmx=1024,icnProductionSetting.icnDBType=db2,icnProductionSetting.icnJNDIDSName=ECMClientDS,icnProductionSetting.icnSChema=ICNDB,icnProductionSetting.icnTableSpace=ICNDBTS,icnProductionSetting.icnAdmin=ceadmin,icnProductionSetting.navigatorMode=3,dataVolume.existingPVCforICNCfgstore=icn-cfgstore,dataVolume.existingPVCforICNLogstore=icn-logstore,dataVolume.existingPVCforICNPluginstore=icn-pluginstore,dataVolume.existingPVCforICNVWCachestore=icn-vw-cachestore,dataVolume.existingPVCforICNVWLogstore=icn-vw-logstore,dataVolume.existingPVCforICNAsperastore=icn-asperastore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/navigator,image.tag=ga-306-icn
   ```
- Installing 3.0.6 IF2 (and above):
  ```console
    $ helm install ibm-dba-navigator-3.2.0.tgz --name dbamc-navigator --namespace dbamc --set icnProductionSetting.license=accept,icnProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,icnProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,icnProductionSetting.icnDBType=db2,icnProductionSetting.icnJNDIDSName=ECMClientDS,icnProductionSetting.icnSChema=ICNDB,icnProductionSetting.icnTableSpace=ICNDBTS,icnProductionSetting.icnAdmin=ceadmin,icnProductionSetting.navigatorMode=0,dataVolume.existingPVCforICNCfgstore=icn-cfgstore,dataVolume.existingPVCforICNLogstore=icn-logstore,dataVolume.existingPVCforICNPluginstore=icn-pluginstore,dataVolume.existingPVCforICNVWCachestore=icn-vw-cachestore,dataVolume.existingPVCforICNVWLogstore=icn-vw-logstore,dataVolume.existingPVCforICNAsperastore=icn-asperastore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/navigator,image.tag=ga-306-icn-if002
    ```
    
    Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
    
To deploy **Content Search Services:**

- Installing 5.5.3 GA:
   ```console     
     $ helm install ibm-dba-contentsearch-3.0.0.tgz --name dbamc-css --namespace dbamc --set cssProductionSetting.license=accept,service.name=csssvc,service.externalSSLPort=8199,cssProductionSetting.jvmHeapXmx=3072,dataVolume.existingPVCforCSSCfgstore=css-cfgstore,dataVolume.existingPVCforCSSLogstore=css-logstore,dataVolume.existingPVCforCSSTmpstore=css-tempstore,dataVolume.existingPVCforIndex=css-indexstore,dataVolume.existingPVCforCSSCustomstore=css-customstore,resources.limits.memory=7Gi,cssProductionSetting.jvmHeapXmx=4096,image.repository=<image_repository_url>:<port>/dbamc/css,image.tag=ga-553-p8css,imagePullSecrets.name=admin.registrykey
   ```
   
- Installing 5.5.3 IF1 (and above):
   ```console     
     $ helm install ibm-dba-contentsearch-3.1.0.tgz --name dbamc-css --namespace dbamc --set cssProductionSetting.license=accept,service.name=csssvc,service.externalSSLPort=8199,cssProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=38,cssProductionSetting.JVM_MAX_HEAP_PERCENTAGE=50,service.externalmetricsPort=9103,dataVolume.existingPVCforCSSCfgstore=css-cfgstore,dataVolume.existingPVCforCSSLogstore=css-logstore,dataVolume.existingPVCforCSSTmpstore=css-tempstore,dataVolume.existingPVCforIndex=css-indexstore,dataVolume.existingPVCforCSSCustomstore=css-customstore,resources.limits.memory=7Gi,image.repository=<image_repository_url>:<port>/dbamc/css,image.tag=ga-553-p8css-if001,imagePullSecrets.name=admin.registrykey
   ```     
 Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
 
Some environments require multiple Content Search Services deployments. To deploy multiple Content Search Services instances, specify a unique release name and service name, and a new set of persistent volumes and persistent volume claims (PVs and PVCs).  The example below shows a deployment using a new release name `dbamc-css2`, a new service name `csssvc2`, and a new set of persistent volumes `css2-cfgstore`, `css2-logstore`, `css2-tempstore`, `css-indexstore`, and `css2-customstore`.  You can reuse the same persistent volume for the indexstore if you want to have multiple Content Search Services deployments that access the same set of index collections.  However, it is recommended that the other persistent volumes be unique.
 
- Installing 5.5.3 GA:
   ```console     
     $ helm install ibm-dba-contentsearch-3.0.0.tgz --name dbamc-css2 --namespace dbamc --set cssProductionSetting.license=accept,service.externalSSLPort=8199,service.name=csssvc2,cssProductionSetting.jvmHeapXmx=3072,dataVolume.existingPVCforCSSCfgstore=css2-cfgstore,dataVolume.existingPVCforCSSLogstore=css2-logstore,dataVolume.existingPVCforCSSTmpstore=css2-tempstore,dataVolume.existingPVCforIndex=css-indexstore,dataVolume.existingPVCforCSSCustomstore=css2-customstore,resources.limits.memory=7Gi,cssProductionSetting.jvmHeapXmx=4096,image.repository=<image_repository_url>:<port>/dbamc/css,image.tag=ga-553-p8css,imagePullSecrets.name=admin.registrykey
   ```
 
- Installing 5.5.3 IF1 (and above):
   ```console     
     $ helm install ibm-dba-contentsearch-3.1.0.tgz --name dbamc-css2 --namespace dbamc --set cssProductionSetting.license=accept,service.name=csssvc2,service.externalSSLPort=8199,cssProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=38,cssProductionSetting.JVM_MAX_HEAP_PERCENTAGE=50,service.externalmetricsPort=9103,dataVolume.existingPVCforCSSCfgstore=css2-cfgstore,dataVolume.existingPVCforCSSLogstore=css2-logstore,dataVolume.existingPVCforCSSTmpstore=css2-tempstore,dataVolume.existingPVCforIndex=css-indexstore,dataVolume.existingPVCforCSSCustomstore=css2-customstore,resources.limits.memory=7Gi,image.repository=<image_repository_url>:<port>/dbamc/css,image.tag=ga-553-p8css-if001,imagePullSecrets.name=admin.registrykey
   ```     
 Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
 
 
 To deploy **Content Management Interoperability Services:**

- Installing 3.0.4 GA:
   ```console
     $ helm install ibm-dba-cscmis-1.7.0.tgz --name dbamc-cmis --namespace dbamc --set cmisProductionSetting.license=accept,cmisProductionSetting.jvmHeapXms=512,cmisProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforCMISCfgstore=cmis-cfgstore,dataVolume.existingPVCforCMISLogstore=cmis-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:5000/dbamc/cmis,image.tag=ga-304-cmis-if007,cmisProductionSetting.cpeUrl=http://<cpe_server>:<port>/wsi/FNCEWS40MTOM 
   ```
   
- Installing 3.0.4 IF8 (and above):
   ```console
     $ helm install ibm-dba-cscmis-1.8.0.tgz --name dbamc-cmis --namespace dbamc --set cmisProductionSetting.license=accept,cmisProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,cmisProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,dataVolume.existingPVCforCMISCfgstore=cmis-cfgstore,dataVolume.existingPVCforCMISLogstore=cmis-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/cmis,image.tag=ga-304-cmis-if008,cmisProductionSetting.cpeUrl=http://<CPE_Hostname>:<port>:<port>/wsi/FNCEWS40MTOM 
   ```
Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
Replace `<CPE_Hostname>:<port>` with the FileNet Content Engine application host and Port.

> **Reminder**: After you deploy, return to the instructions in the Knowledge Center, [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter//SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_postdeploy.htm), to get your FileNet Content Manager environment up and running

## Deploying the External Share container

If you want to optionally include the external share capability in your environment, you also configure and deploy the External Share container. 

Ensure that you have completed the all of the preparation steps for deploying the External Share container: [Configuring external share for containers](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalshare.htm)

To deploy the **External Share container:**

- Installing 3.0.6 GA:
   ```
     $ helm install ibm-dba-extshare-prod-3.0.0.tgz --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.jvmHeapXms=512,esProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforESCfgstore=es-cfgstore,dataVolume.existingPVCforESLogstore=es-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/extshare,image.tag=ga-306-es,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=ICNDBTS,esProductionSetting.esAdmin=ceadmin
   ```
   
- Installing 3.0.6 LA1 (and above):
     ```
     $ helm install ibm-dba-extshare-prod-3.0.1.tgz --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,esProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,dataVolume.existingPVCforESCfgstore=es-cfgstore,dataVolume.existingPVCforESLogstore=es-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/extshare,image.tag=ga-306-es,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=ICNDBTS,esProductionSetting.esAdmin=ceadmin
   ```
Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
 
## Deploying the Technology Preview: Content Services GraphQL API container
If you want to use the Content Services GraphQL API container, follow the instructions in the Getting Started technical notice: [Technology Preview: Getting started with Content Services GraphQL API](http://www.ibm.com/support/docview.wss?uid=ibm10883630)

To deploy the ContentGraphQL Container:

- Installing 5.5.3 GA:
   ```
     $ helm install ibm-dba-contentrestservice-dev-3.0.0.tgz --name dbamc-crs --namespace dbamc --set crsProductionSetting.license=accept,crsProductionSetting.jvmHeapXms=512,crsProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforCfgstore=crs-icp-cfgstore,dataVolume.existingPVCforCfglogs=crs-icp-logs,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/crs,image.tag=5.5.3,crsProductionSetting.cpeUri=https://<CPE_Hostname>:<port>/wsi/FNCEWS40MTOM
   ```
   
 - Installing 5.5.3 IF1 (and above):
   ```
     $ helm install ibm-dba-contentrestservice-dev-3.1.0.tgz --name dbamc-crs --namespace dbamc --set crsProductionSetting.license=accept,crsProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,crsProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,dataVolume.existingPVCforCfgstore=crs-icp-cfgstore,dataVolume.existingPVCforCfglogs=crs-icp-logs,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/crs,image.tag=5.5.3,crsProductionSetting.cpeUri=https://<CPE_Hostname>:<port>/wsi/FNCEWS40MTOM
     ```
   Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000
   Replace `<CPE_Hostname>:<port>` with the FileNet Content Engine application host and Port.
   


## Upgrading deployments
   > **Tip**: You can discover the necessary resource values for the deployment from corresponding product deployments in IBM Cloud Private Console and Openshift Container Platform.

### Before you begin
Before you run the upgrade commands, you must prepare the environment for upgrades to Content Search Services and Content Management Interoperability Services. If you plan to upgrade those containers, complete the preparation steps in the following topic before you start the upgrade: [Upgrading Content Manager releases](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepareexisting.htm)

### Upgrading from an older release to IBM Content Foundation / IBM FileNet Content Manager 5.5.3 GA

To upgrade **Content Platform Engine:**
```
   helm upgrade dbamc-cpe ibm-dba-contentservices-3.0.0.tgz --reuse-values --set image.repository=<image_repository_url>:<port>/dbamc/cpe,image.tag=ga-553-p8cpe,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=1,resources.limits.memory=2048Mi,log.format=json
```   
Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

To upgrade **IBM Content Navigator:**

```
  $ helm upgrade dbamc-icn ibm-dba-navigator-3.0.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/dbamc/navigator,image.tag=stable-ubi,resources.requests.cpu=500m,resources.requests.memory=512Mi,imagePullSecrets.name=admin.registrykey,resources.limits.cpu=1,resources.limits.memory=1024Mi,log.format=json
```   

Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

To upgrade **Content Search Services:**

```
   $ helm upgrade dbamc-css ibm-dba-contentsearch-3.0.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/dbamc/css,image.tag=ga-553-p8css-if001,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=8,resources.limits.memory=8192Mi,log.format=json,dataVolume.existingPVCforCSSCustomstore=css-icp-customstore
```

Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000


To upgrade **Content Management Interoperability Services:**

```
   $ helm upgrade dbamc-cmis ibm-dba-cscmis-1.7.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/dbamc/cmis,image.tag=ga-304-cmis-if007,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=1,resources.limits.memory=1024Mi,log.format=json
```   

Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

### Upgrading from an older release to IBM Content Foundation / IBM FileNet Content Manager 5.5.3 interim fixes (e.g., CPE 5.5.3 IF1+, ICN 3.0.6 IF2+, CMIS 3.0.4 IF8+, CSS 5.5.5 IF1+, CRS 5.5.3 IF1+, and ExtShare 3.0.6 LA001+)

Update the ownership and permissions for all of your persistent volumes and persistent volume claims folders, for Content Platform Engine, Content Search Services, Content Management Interoperability Services, and External Share:

- Go to each folder for your deployment, for example: /cpecfgstore
- For each of the folders, change the settings to -R 0, for example:
   ```chgrp -R 0 /cpecfgstore```
- For each of the folders, change the current permission settings to g=u, for example:
    ```chmod -Rf g=u /cpecfgstore```
    

### Upgrading on Red Hat OpenShift

For deployments on Red Hat OpenShift, note the following considerations for whether you want to use the Arbitrary UID capability in your environment:
- If you don't want to use Arbitrary UID capability in your Red Hat OpenShift environment, use the instructions in Upgrading on certified Kubernetes.

- If you do want to use Arbitrary UID, use the following steps to prepare for the upgrade:

1. Check and if necessary edit your Security Context Constraint to set desired user id range of minimum and maximum values for the project namespace:
    - Set the desired user id range of minimum and maximum values for the project namespace:
  
    ```$ oc edit namespace <project> ```

    For the uid-range annotation, verify that a value similar to the following is specified:
    
    ```$ openshift.io/sa.scc.uid-range=1000490000/10000 ```
    
    This range is similar to the default range for Red Hat OpenShift.
  
   - Remove authenticated users from anyuid (if set):
  
     ```$ oc adm policy remove-scc-from-group anyuid system:authenticated ```

   - Update the runAsUser value. 
     Find the entry:
    
    ```
    $ oc get scc <SCC name> -o yaml
        runAsUser:
        type: RunAsAny
    ```

     Update the value:
    
    ```
    $ oc get scc <SCC name> -o yaml
      runAsUser:
      type:  MustRunAsRange
    ```

2. Stop all existing containers.

3. Run the new install (instead of upgrade) commands for the containers. Update the commands provided to include the values for your existing environment. 

> **NOTE**: In this context, the install commands update the application. Updates for your existing data happen automatically when the updated applications start. 

To deploy **Content Platform Engine:**

   ```console
   $ helm install ibm-dba-contentservices-3.1.0.tgz --name dbamc-cpe --namespace dbamc --set cpeProductionSetting.license=accept,cpeProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=18,cpeProductionSetting.JVM_MAX_HEAP_PERCENTAGE=33,service.externalmetricsPort=9103,cpeProductionSetting.licenseModel=FNCM.CU,dataVolume.existingPVCforCPECfgstore=cpe-cfgstore,dataVolume.existingPVCforCPELogstore=cpe-logstore,dataVolume.existingPVCforFilestore=cpe-filestore,dataVolume.existingPVCforICMrulestore=cpe-icmrulesstore,dataVolume.existingPVCforTextextstore=cpe-textextstore,dataVolume.existingPVCforBootstrapstore=cpe-bootstrapstore,dataVolume.existingPVCforFNLogstore=cpe-fnlogstore,autoscaling.enabled=False,resources.requests.cpu=1,replicaCount=1,image.repository=<image_repository_url>:<port>/dbamc/cpe,image.tag=ga-553-p8cpe,cpeProductionSetting.gcdJNDIName=FNGDDS,cpeProductionSetting.gcdJNDIXAName=FNGDDSXA 
   ```
Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

To deploy **Content Search Services:**

   ```console     
     $ helm install ibm-dba-contentsearch-3.1.0.tgz --name dbamc-css --namespace dbamc --set cssProductionSetting.license=accept,service.name=csssvc,service.externalSSLPort=8199,cssProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=38,cssProductionSetting.JVM_MAX_HEAP_PERCENTAGE=50,service.externalmetricsPort=9103,dataVolume.existingPVCforCSSCfgstore=css-cfgstore,dataVolume.existingPVCforCSSLogstore=css-logstore,dataVolume.existingPVCforCSSTmpstore=css-tempstore,dataVolume.existingPVCforIndex=css-indexstore,dataVolume.existingPVCforCSSCustomstore=css-customstore,resources.limits.memory=7Gi,image.repository=<image_repository_url>:<port>/dbamc/css,image.tag=ga-553-p8css,imagePullSecrets.name=admin.registrykey
   ```     
 Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

To deploy **IBM Content Navigator:**
   ```console
    $ helm install ibm-dba-navigator-3.2.0.tgz --name dbamc-navigator --namespace dbamc --set icnProductionSetting.license=accept,icnProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,icnProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,icnProductionSetting.icnDBType=db2,icnProductionSetting.icnJNDIDSName=ECMClientDS,icnProductionSetting.icnSChema=ICNDB,icnProductionSetting.icnTableSpace=ICNDBTS,icnProductionSetting.icnAdmin=ceadmin,icnProductionSetting.navigatorMode=0,dataVolume.existingPVCforICNCfgstore=icn-cfgstore,dataVolume.existingPVCforICNLogstore=icn-logstore,dataVolume.existingPVCforICNPluginstore=icn-pluginstore,dataVolume.existingPVCforICNVWCachestore=icn-vw-cachestore,dataVolume.existingPVCforICNVWLogstore=icn-vw-logstore,dataVolume.existingPVCforICNAsperastore=icn-asperastore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/navigator,image.tag=ga-306-icn-if002
```
 Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

 To deploy **Content Management Interoperability Services:**

   ```console
     $ helm install ibm-dba-cscmis-1.8.0.tgz --name dbamc-cmis --namespace dbamc --set cmisProductionSetting.license=accept,cmisProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,cmisProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,dataVolume.existingPVCforCMISCfgstore=cmis-cfgstore,dataVolume.existingPVCforCMISLogstore=cmis-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/cmis,image.tag=ga-304-cmis-if007,cmisProductionSetting.cpeUrl=http://10.0.0.110:9080/wsi/FNCEWS40MTOM 
   ```
Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

To deploy **External Share services:**

   ```
     $ helm install ibm-dba-extshare-prod-3.0.1.tgz --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,esProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,dataVolume.existingPVCforESCfgstore=es-cfgstore,dataVolume.existingPVCforESLogstore=es-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/dbamc/extshare,image.tag=ga-306-es,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=ICNDBTS,esProductionSetting.esAdmin=ceadmin
   ```
    
  Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

### Upgrading on certified Kubernetes platforms (for non Arbitrary UID deployments)

To upgrade **Content Platform Engine:**

On Red Hat OpenShift:

```
   helm upgrade ecm-helm-cpe ibm-dba-contentservices-3.1.0.tgz --reuse-values --set image.repository=<image_repository_url>:<port>/{namespace}/cpe,image.tag=ga-553-p8cpe-if001,imagePullSecrets.name=admin.registrykey,log.format=json,cpeProductionSetting.jvmInitialHeapPercentage=18,cpeProductionSetting.jvmMaxHeapPercentage=33,service.externalmetricsPort=9103
```   
On non-Red Hat OpenShift platforms:

```
   helm upgrade ecm-helm-cpe ibm-dba-contentservices-3.1.0.tgz --reuse-values --set image.repository=<image_repository_url>:<port>/{namespace}/cpe,image.tag=ga-553-p8cpe-if001,imagePullSecrets.name=admin.registrykey,log.format=json,cpeProductionSetting.jvmInitialHeapPercentage=18,cpeProductionSetting.jvmMaxHeapPercentage=33,runAsUser=50001,service.externalmetricsPort=9103
``` 


Replace `<image_repository_url>:<port>/{namespace}` with correct registry URL, for example, docker-registry.default.svc:5000/dbamc

To upgrade **Content Search Services:**

On Red Hat OpenShift:

```
   $ helm upgrade dbamc-css ibm-dba-contentsearch-3.1.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/{namespace}/css,image.tag=ga-553-p8css-if001,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=8,resources.limits.memory=8192Mi,log.format=json,dataVolume.existingPVCforCSSCustomstore=css-icp-customstore,service.,cssProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=38,cssProductionSetting.JVM_MAX_HEAP_PERCENTAGE=50,service.externalmetricsPort=9103
```

On non-Red Hat OpenShift platforms:

```
   $ helm upgrade dbamc-css ibm-dba-contentsearch-3.1.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/{namespace}/css,image.tag=ga-553-p8css-if001,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=8,resources.limits.memory=8192Mi,log.format=json,dataVolume.existingPVCforCSSCustomstore=css-icp-customstore,runAsUser=50001,cssProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=38,cssProductionSetting.JVM_MAX_HEAP_PERCENTAGE=50,service.externalmetricsPort=9103
```

Replace `<image_repository_url>:<port>/{namespace}` with correct registry URL, for example, docker-registry.default.svc:5000/dbamc

To upgrade **IBM Content Navigator:**

On Red Hat OpenShift:
   
```
   $ helm upgrade dbamc-helm-navigator ibm-dba-navigator-3.2.0.tgz --reuse-values --set image.repository=<image_repository_url>:<port>/dbamc/dbamc/navigator,image.tag=ga-306-icn-if002,resources.requests.cpu=500m,resources.requests.memory=512Mi,icnProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,icnProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,imagePullSecrets.name=admin.registrykey,resources.limits.cpu=1,resources.limits.memory=1024Mi,log.format=json,service.externalmetricsPort=9103
```
On non-Red Hat OpenShift:

```
   $ helm upgrade dbamc-helm-navigator ibm-dba-navigator-3.2.0.tgz --reuse-values --set image.repository=<image_repository_url>:<port>/dbamc/navigator,image.tag=ga-306-icn-if002,icnProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,icnProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103,runAsUser=50001

```
 Replace `<image_repository_url>:<port>` with the correct registry URL, for example, docker-registry.default.svc:5000

To upgrade **Content Management Interoperability Services:**

On Red Hat OpenShift:

```
   $ helm upgrade dbamc-cmis ibm-dba-cscmis-1.8.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/{namespace}/cmis,image.tag=ga-304-cmis-if007,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=1,resources.limits.memory=1024Mi,cmisProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,cmisProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,log.format=json,service.externalmetricsPort=9103
```   
On non-Red Hat OpenShift platforms:

```
   $ helm upgrade dbamc-cmis ibm-dba-cscmis-1.8.0.tgz  --reuse-values --set image.repository=<image_repository_url>:<port>/{namespace}/cmis,image.tag=ga-304-cmis-if007,imagePullSecrets.name=admin.registrykey,resources.requests.cpu=500m,resources.requests.memory=512Mi,resources.limits.cpu=1,resources.limits.memory=1024Mi,log.format=json,runAsUser=50001,cmisProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,cmisProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,service.externalmetricsPort=9103
```

Replace `<image_repository_url>:<port>/{namespace}` with correct registry URL, for example, docker-registry.default.svc:5000/dbamc

To upgrade **External Share services:**

On Red Hat OpenShift:

   ```
     $ helm upgrade ibm-dba-extshare-prod-3.0.1.tgz --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,esProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,dataVolume.existingPVCforESCfgstore=es-cfgstore,dataVolume.existingPVCforESLogstore=es-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/{namespace}/extshare,image.tag=ga-306-es,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=ICNDBTS,esProductionSetting.esAdmin=ceadmin,service.externalmetricsPort=9103
   ```

On non-Red Hat OpenShift platforms:

   ```
     $ helm upgrade ibm-dba-extshare-prod-3.0.1.tgz --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.JVM_INITIAL_HEAP_PERCENTAGE=40,esProductionSetting.JVM_MAX_HEAP_PERCENTAGE=66,dataVolume.existingPVCforESCfgstore=es-cfgstore,dataVolume.existingPVCforESLogstore=es-logstore,autoscaling.enabled=False,replicaCount=1,imagePullSecrets.name=admin.registrykey,image.repository=<image_repository_url>:<port>/{namespace}/extshare,image.tag=ga-306-es,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=ICNDBTS,esProductionSetting.esAdmin=ceadmin,runAsUser=50001,service.externalmetricsPort=9103
   ```

  Replace `<image_repository_url>:<port>/{namespace}` with correct registry URL, for example, docker-registry.default.svc:5000/dbamc




## Uninstalling a Kubernetes release of FileNet Content Manager

To uninstall and delete a release named `my-cpe-prod-release`, use the following command:

```console
$ helm delete my-cpe-prod-release --purge
```

The command removes all the Kubernetes components associated with the release, except any Persistent Volume Claims (PVCs).  This is the default behavior of Kubernetes, and ensures that valuable data is not deleted. To delete the persisted data of the release, you can delete the PVC using the following command:

```console
$ kubectl delete pvc my-cpe-prod-release-cpe-pvclaim
