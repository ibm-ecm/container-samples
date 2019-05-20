# Deploying with Helm charts

## Requirements and Prerequisites

Ensure that you have completed the following tasks:

- [Preparing FileNet environment](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_18.0.x/com.ibm.dba.install/k8s_topics/tsk_prepare_ecmk8s.html)

- [Preparing your Kubernetes server with Kubernetes, Helm Tiller, and the Kubernetes command line](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_18.0.x/com.ibm.dba.install/k8s_topics/tsk_prepare_env_k8s.html)

- [Downloading the PPA archive](../../README.md)

The Helm commands for deploying the FileNet Content Manager images include a number of required command parameters for specific environment and configuration settings. Review the reference topics for these parameters and determine the values for your environment as part of your preparation:

- [Content Platform Engine Helm command parameters](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_18.0.x/com.ibm.dba.ref/k8s_topics/ref_cm_cpeparamsk8s_helm.html)

- [Content Search Services Helm command parameters](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_18.0.x/com.ibm.dba.ref/k8s_topics/ref_cm_cssparamsk8s_helm.html)

- [Content Management Interoperability Services Helm command parameters](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_18.0.x/com.ibm.dba.ref/k8s_topics/ref_cm_cmisparamsk8s_helm.html)

## Tips: 

- On Openshift, an expired docker secret can cause errors during deployment. If an admin.registry key already exists and has expired, delete the key with the following command:
   ```console
   kubectl delete secret admin.registrykey -n <new_project>
   ```
    Then generate a new docker secret with the following command:
    ```console
   kubectl create secret docker-registry admin.registrykey --docker-server=<registry_url> --docker-username=<new_user> --docker-password=$(oc whoami -t) --docker-email=ecmtest@ibm.com -n <new_project>
   ```

- On Openshift, the security context constraint can cause deployment errors. To prevent this, update the namespace to include the constraints for the components that you want to deploy. For example, the following update accommodates the Content Platform Engine (50000,50001) and Content Management Interoperability Services (500,501):

   ```console
   oc edit namespace dbamc-project
   openshift.io/sa.scc.supplemental-groups: 500/50000
   openshift.io/sa.scc.uid-range: 501/50001 
   ```

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

To deploy Content Platform Engine:

   ```console
   $ helm install ibm-dba-contentservices-3.0.0.tgz --name dbamc-cpe --namespace dbamc --set cpeProductionSetting.license=accept,cpeProductionSetting.jvmHeapXms=512,cpeProductionSetting.jvmHeapXmx=1024,cpeProductionSetting.licenseModel=FNCM.CU,dataVolume.existingPVCforCPECfgstore=cpe-cfgstore,dataVolume.existingPVCforCPELogstore=cpe-logstore,dataVolume.existingPVCforFilestore=cpe-filestore,dataVolume.existingPVCforICMrulestore=cpe-icmrulesstore,dataVolume.existingPVCforTextextstore=cpe-textextstore,dataVolume.existingPVCforBootstrapstore=cpe-bootstrapstore,dataVolume.existingPVCforFNLogstore=cpe-fnlogstore,autoscaling.enabled=False,resources.requests.cpu=1,replicaCount=1,image.repository=<cluster.registry.repo>/dbamc/cpe,image.tag=5.5.3,cpeProductionSetting.gcdJNDIName=FNGCDDS,cpeProductionSetting.gcdJNDIXAName=FNGCDDSXA 
   ```

To deploy Content Search Services:

   ```console     
     $ helm install ibm-dba-contentsearch-3.0.0.tgz --name dbamc-css1 --namespace dbamc --set cssProductionSetting.license=accept,service.externalSSLPort=8199,service.name=csssvc1,cssProductionSetting.jvmHeapXmx=3072,dataVolume.existingPVCforCSSCfgstore=css-cfgstore,dataVolume.existingPVCforCSSLogstore=css-logstore,dataVolume.existingPVCforCSSTmpstore=css-tempstore,dataVolume.existingPVCforIndex=css-indexstore,image.repository=172.30.1.1:5000/dbamc/css,image.tag=5.5.3 
   ```     
 
 Note:  To deploy multiple Content Search Services deployments, please make sure you specify a unique release name, service name, and a new set of persistent volumes (PVs and PVCs).  The example below shows a deployment using a new release name `dbamc-css2`, a new service name `csssvc2`, and a new set of persistent volumes `css2-cfgstore`, `css2-logstore`, `css2-tempstore`, and `css2-indexstore`.  You may reuse the same persistent volume for indexstore if you wish to have multiple Content Search Services deployments accessing the same set of index collections.  However, it is recommended that the other persistent volumes should be unique.
 
   ```console     
     $ helm install ibm-dba-contentsearch-3.0.0.tgz --name dbamc-css2 --namespace dbamc --set cssProductionSetting.license=accept,service.externalSSLPort=8199,service.name=csssvc2,cssProductionSetting.jvmHeapXmx=3072,dataVolume.existingPVCforCSSCfgstore=css2-cfgstore,dataVolume.existingPVCforCSSLogstore=css2-logstore,dataVolume.existingPVCforCSSTmpstore=css2-tempstore,dataVolume.existingPVCforIndex=css2-indexstore,image.repository=172.30.1.1:5000/dbamc/css,image.tag=5.5.3
   ``` 
    
 
 
 To deploy Content Management Interoperability Service:

   ```console
     $ helm install ibm-dba-cscmis-1.7.0.tgz --name dbamc-cmis --namespace dbamc --set cmisProductionSetting.license=accept,cmisProductionSetting.jvmHeapXms=512,cmisProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforCMISCfgstore=cmis-cfgstore,dataVolume.existingPVCforCMISLogstore=cmis-logstore,autoscaling.enabled=False,replicaCount=1,image.repository=172.30.1.1:5000/dbamc/cmis,image.tag=3.0.4,cmisProductionSetting.cpeUrl=http://10.0.0.110:9080/wsi/FNCEWS40MTOM 
   ```

To deploy External Share Container:

    
    IBM Cloud Private 3.1.2
    
    ```
     $ export HELM_HOME=/root/.helm
    
     $ helm repo add local-charts https://mycluster.icp:8443/helm-repo/charts --ca-file $HELM_HOME/ca.pem --cert-file $HELM_HOME/cert.pem --key-file $HELM_HOME/key.pem
    
     $ helm install local-charts/ibm-dba-extshare --version 3.0.0 --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.jvmHeapXms=512,esProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforESCfgstore=ecm-es-config-pvc,dataVolume.existingPVCforESLogstore=ecm-es-logs-pvc,autoscaling.enabled=False,replicaCount=1,image.repository=mycluster.icp:8500/dbamc/extshare,image.tag=3.0.6,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=UBI_ICN,esProductionSetting.esAdmin=ceadmin --tls
    ```
   
   Certified Kubernetes platform
   
    ```
     $ helm install ibm-dba-extshare-prod-3.0.0.tgz --name dbamc-es --namespace dbamc --set esProductionSetting.license=accept,esProductionSetting.jvmHeapXms=512,esProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforESCfgstore=es-cfgstore,dataVolume.existingPVCforESLogstore=es-logstore,autoscaling.enabled=False,replicaCount=1,image.repository=172.30.1.1:5000/dbamc/extshare,image.tag=3.0.6,esProductionSetting.esDBType=db2,esProductionSetting.esJNDIDSName=ECMClientDS,esProductionSetting.esSChema=ICNDB,esProductionSetting.esTableSpace=ICNDBTS,esProductionSetting.esAdmin=ceadmin
    ```

To deploy ContentGraphQL Container:

    IBM Cloud Private 3.1.2
    
    ```
     $ export HELM_HOME=/root/.helm
    
     $ helm repo add local-charts https://mycluster.icp:8443/helm-repo/charts --ca-file $HELM_HOME/ca.pem --cert-file $HELM_HOME/cert.pem --key-file $HELM_HOME/key.pem

     $ helm install local-charts/ibm-dba-contentrestservice-dev --name dbamc-crs --namespace dbamc --set crsProductionSetting.license=accept,crsProductionSetting.jvmHeapXms=512,crsProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforCfgstore=crs-icp-cfgstore,dataVolume.existingPVCforCfglogs=crs-icp-logs,autoscaling.enabled=False,replicaCount=1,image.repository=mycluster.icp:8500/dbamc/crs,image.tag=5.5.3
    ```
   
   Certified Kubernetes platform 

   ```
     $ helm install ibm-dba-contentrestservice-dev-3.0.0.tgz --name dbamc-crs --namespace dbamc --set crsProductionSetting.license=accept,crsProductionSetting.jvmHeapXms=512,crsProductionSetting.jvmHeapXmx=1024,dataVolume.existingPVCforCfgstore=crs-icp-cfgstore,dataVolume.existingPVCforCfglogs=crs-icp-logs,autoscaling.enabled=False,replicaCount=1,image.repository=172.30.1.1:5000/dbamc/crs,image.tag=5.5.3
   ```
> **Reminder**: After you deploy, return to the instructions in the Knowledge Center, [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_18.0.x/com.ibm.dba.install/k8s_topics/tsk_deploy_postecmdeployk8s.html), to get your FileNet Content Manager environment up and running

## Uninstalling a Kubernetes release of FileNet Content Manager

To uninstall and delete a release named `my-cpe-prod-release`, use the following command:

```console
$ helm delete my-cpe-prod-release --purge --tls
```

The command removes all the Kubernetes components associated with the release, except any Persistent Volume Claims (PVCs).  This is the default behavior of Kubernetes, and ensures that valuable data is not deleted. To delete the persisted data of the release, you can delete the PVC using the following command:

```console
$ kubectl delete pvc my-cpe-prod-release-cpe-pvclaim
