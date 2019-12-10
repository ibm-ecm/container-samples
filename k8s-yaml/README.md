# Deploying with YAML files

## Requirements and Prerequisites

Ensure that you have completed the following tasks:

- [Preparing your FileNet environment](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare.htm) 
- [Preparing your Kubernetes server](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare_env_k8s.htm)
- [Downloading the product archives and loading the component images](../README.md)

## Tips: 

- On OpenShift, an expired Docker secret can cause errors during deployment. If an admin.registry key already exists and has expired, delete the key with the following command:
   ```console
   kubectl delete secret admin.registrykey -n <new_project>
   ```
    Then generate a new Docker secret with the following command:
    ```console
   kubectl create secret docker-registry admin.registrykey --docker-server=<registry_url> --docker-username=<new_user> --docker-password=$(oc whoami -t) --docker-email=ecmtest@ibm.com -n <new_project>
   ```
- On OpenShift, if you are installing IBM Content Foundation / IBM FileNet Content Manager 5.5.3 GA, ensure that sa.scc.uid-range includes 50001 and sa.scc.supplemental-groups includes 50000.

If you are installing or upgrading to IBM Content Foundation / IBM FileNet Content Manager 5.5.3 interim fixes (e.g., CPE 5.5.3 IF1+, ICN 3.0.6 IF2+, CMIS 3.0.4 IF8+, CSS 5.5.5 IF1+, CRS 5.5.3 IF1+, and ExtShare 3.0.6 LA001+), update the ownership and permissions for all of your persistent volumes and persistent volume claims folders, for Content Platform Engine, Content Search Services, IBM Content Navigator, Content Management Interoperability Services, and External Share.

For all folders created for your deployment, the group ownership and file permissions must be set to allow the container to access. 

   - For example, if your CPE configuration data is stored under /cpecfgstore
      - change the settings to -R 0, for example:
         ```chgrp -R 0 /cpecfgstore```
      - change the current permission settings to g=u, for example:
         ```chmod -Rf g=u /cpecfgstore```
    
    
On OpenShift, note the following considerations for whether you want to use the Arbitrary UID capability in your environment:

- If you don't want to use Arbitrary UID capability in your Red Hat OpenShift environment, deploy the images as described in the following sections.

- If you do want to use Arbitrary UID, prepare for deployment by editing your Security Context Constraint:
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

**New features:**  There are a number of new features starting in IBM Content Foundation / IBM FileNet Content Manager 5.5.3 interim fixes (e.g., CPE 5.5.3 IF1+, ICN 3.0.6 IF2+, CMIS 3.0.4 IF8+, CSS 5.5.5 IF1+, CRS 5.5.3 IF1+, and ExtShare 3.0.6 LA001+).  Please see each component below for details.


## Installing 5.5.3 GA the component images

Use the command line to deploy the image using the parameters in the appropriate YAML file. You also use the command line to determine access information for your deployed images.

    
### To deploy **Content Platform Engine:**
1.  Use the deployment file to deploy Content Platform Engine:
    ```kubectl apply -f cpe-deploy.yml```

2. Run following command to get the Public IP and port to access Content Platform Engine:
    ```kubectl get svc | grep ecm-cpe```

### To deploy **IBM Content Navigator:**
 1. Use the deployment file to deploy IBM Content Navigator:
    ```kubectl apply -f navigator-deploy.yml```
    
 2. Run the following command to get the Public IP and port to access Content Management Interoperability Services:
    ```kubectl get svc | ecm-navigator```

### To deploy **Content Search Services:**
 1. Use the deployment file to deploy Content Search Services:
    
    ```kubectl apply -f css-deploy.yml```
 2. Run the following command to get the Public IP and port to access Content Search Services:
    
    ```kubectl get svc | grep ecm-css```

Some environments require multiple Content Search Services deployments. To deploy multiple Content Search Services instances, specify a unique release name and service name, and a new set of persistent volumes and persistent volume claims (PVs and PVCs). You must reuse the same persistent volume for the indexstore if you want to have multiple Content Search Services deployments that access the same set of index collections. However, it is recommended that the other persistent volumes be unique.


### To deploy **Content Management Interoperability Services:**
 1. Use the deployment file to deploy Content Management Interoperability Services:
    
    ```kubectl apply -f cmis-deploy.yml```
 2. Run the following command to get the Public IP and port to access Content Management Interoperability Services:
    
    ```kubectl get svc | ecm-cmis```


> **Reminder**: After you deploy, return to the instructions in the Knowledge Center, [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_postdeploy.htm), to get your FileNet Content Manager environment up and running

## Deploying the External Share container

If you want to optionally include the external share capability in your environment, you also configure and deploy the External Share container. 

Ensure that you have completed the all of the preparation steps for deploying the External Share container: [Configuring external share for containers](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalshare.htm)

 1. Use the deployment file to deploy the **External Share container:**
    
    ```kubectl apply -f es-deploy.yml```
 2. Run the following command to get the Public IP and port to access External Share:
    
    ```kubectl get svc | ecm-es```

## Deploying the Technology Preview: Content Services GraphQL API container
If you want to use the Content Services GraphQL API container, follow the instructions in the Getting Started technical notice: [Technology Preview: Getting started with Content Services GraphQL API](http://www.ibm.com/support/docview.wss?uid=ibm10883630)

 1. Use the deployment file to deploy the Content Services GraphQL API container:
    
    ```kubectl apply -f crs-deploy.yml```
 2. Run the following command to get the Public IP and port to access the Content Services GraphQL API:
    
    ```kubectl get svc | ecm-crs```


## Installing or upgrading to IBM Content Foundation / IBM FileNet Content Manager 5.5.3 interim fixes (e.g., CPE 5.5.3 IF1+, ICN 3.0.6 IF2+, CMIS 3.0.4 IF8+, CSS 5.5.5 IF1+, CRS 5.5.3 IF1+, and ExtShare 3.0.6 LA001+)

Use the command line to deploy the image using the parameters in the appropriate YAML file. You also use the command line to determine access information for your deployed images.

    
### To deploy **Content Platform Engine:**
 1. Download the sample cpe-deploy.yml or make changes to your own 5.5.3 cpe-deploy.yml file
 2. Update the cpe-deploy.yml with the following:
    * Remove the existing parameters: JVM_HEAP_XMS and JVM_HEAP_XMX
    * Add the new parameters: JVM_INITIAL_HEAP_PERCENTAGE and JVM_MAX_HEAP_PERCENTAGE.  The recommended default values are 18 and 33 respectively.
    * On OpenShift, remove the following line: `runAsUser: 50001`
    * Optional: Add the JVM_CUSTOMIZE_OPTIONS to set your own JVM arguments for the container.  For example,  JVM_CUSTOMIZE_OPTIONS="-Dmy.test.jvm.arg1=123,-Dmy.test.jvm.arg2=abc,-XX:+SomeJVMSettings,XshowSettings:vm"
    * Optional: To leverage monitoring using Prometheus, add MON_METRICS_WRITER_OPTION and set it to 4 (i.e., name: MON_METRICS_WRITER_OPTION and value: "4"). The default port for Prometheus Plugin is 9103, which can be overridden by using MON_METRICS_SERVICE_ENDPOINT
    * Update the `image: <value>` with the interim fix image tag
 3.  Use the deployment file to deploy Content Platform Engine:
    ```kubectl apply -f cpe-deploy.yml```

 4. Run following command to get the Public IP and port to access Content Platform Engine:
    ```kubectl get svc | grep ecm-cpe```

 5. Browse to the FileNet P8 System Health page and verify the P8 domain is accessible: 
https://\<CPE host name or cluster IP>:\<CPE service port>/P8CE/Health
 6. Use the link to the CE Ping page to verify the Product Name shows the expected version of the deployed Content Platform Engine. 
https://\<CPE host name or cluster IP>:\<CPE service port>/FileNet/Engine
   
### To deploy **IBM Content Navigator:**
1. Download the sample navigator-deploy.yml or make changes to your own 3.0.6 navigator-deploy.yml file
2. Update the navigator-deploy.yml with the following:
    * Remove the existing parameters: JVM_HEAP_XMS and JVM_HEAP_XMX
    * Add the new parameters: JVM_INITIAL_HEAP_PERCENTAGE and JVM_MAX_HEAP_PERCENTAGE.  The recommended default values are 40 and 66 respectively.
    * On OpenShift, remove the following line: `runAsUser: 50001`
    * Optional: Add the JVM_CUSTOMIZE_OPTIONS to set your own JVM arguments for the container.  For example,  JVM_CUSTOMIZE_OPTIONS="-Dmy.test.jvm.arg1=123,-Dmy.test.jvm.arg2=abc,-XX:+SomeJVMSettings,XshowSettings:vm"
    * Optional: To leverage monitoring using Prometheus, add MON_METRICS_WRITER_OPTION and set it to 4 (i.e., name: MON_METRICS_WRITER_OPTION and value: "4"). The default port for Prometheus Plugin is 9103, which can be overridden by using MON_METRICS_SERVICE_ENDPOINT
    * Update the `image: <value>` with the interim fix image tag
3. Use the deployment file to deploy IBM Content Navigator:
    ```kubectl apply -f navigator-deploy.yml```

4. Run the following command to get the Public IP and port to access Content Management Interoperability Services:
    ```kubectl get svc | ecm-navigator```


### To deploy **Content Search Services:**
1. Download the sample css-deploy.yml or make changes to your own 5.5.3 css-deploy.yml file
2. Update the css-deploy.yml with the following:
    * Remove the existing parameter: JVM_HEAP_XMX
    * Add the new parameters: JVM_INITIAL_HEAP_PERCENTAGE and JVM_MAX_HEAP_PERCENTAGE.  The recommended default values are 38 and 50 respectively.
    * On OpenShift, remove the following line: `runAsUser: 50001`
    * Optional: To leverage monitoring using Prometheus, add MON_METRICS_WRITER_OPTION and set it to 4 (i.e., name: MON_METRICS_WRITER_OPTION and value: "4"). The default port for Prometheus Plugin is 9103, which can be overridden by using MON_METRICS_SERVICE_ENDPOINT
    * Update the `image: <value>` with the interim fix image tag
3. Use the deployment file to deploy Content Search Services:
    ```kubectl apply -f css-deploy.yml```

4. Run the following command to get the Public IP and port to access Content Search Services:
    ```kubectl get svc | grep ecm-css```

Some environments require multiple Content Search Services deployments. To deploy multiple Content Search Services instances, specify a unique release name and service name, and a new set of persistent volumes and persistent volume claims (PVs and PVCs). You must reuse the same persistent volume for the indexstore if you want to have multiple Content Search Services deployments that access the same set of index collections. However, it is recommended that the other persistent volumes be unique.


### To deploy **Content Management Interoperability Services:**
1. Download the sample cmis-deploy.yml or make changes to your own 3.0.4 cmis-deploy.yml file
2. Update the cmis-deploy.yml with the following:
    * Remove the existing parameters: JVM_HEAP_XMS and JVM_HEAP_XMX
    * Add the new parameters: JVM_INITIAL_HEAP_PERCENTAGE and JVM_MAX_HEAP_PERCENTAGE.  The recommended default values are 40 and 66 respectively.
    * On OpenShift, remove the following line: `runAsUser: 50001`
    * Optional: To leverage monitoring using Prometheus, add MON_METRICS_WRITER_OPTION and set it to 4 (i.e., name: MON_METRICS_WRITER_OPTION and value: "4"). The default port for Prometheus Plugin is 9103, which can be overridden by using MON_METRICS_SERVICE_ENDPOINT
    * Update the `image: <value>` with the interim fix image tag
3.  Use the deployment file to deploy Content Management Interoperability Services:
    ```kubectl apply -f cmis-deploy.yml```
4. Run the following command to get the Public IP and port to access Content Management Interoperability Services:
    ```kubectl get svc | ecm-cmis```


> **Reminder**: After you deploy, return to the instructions in the Knowledge Center, [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_postdeploy.htm), to get your FileNet Content Manager environment up and running

### Deploying External Share Services

If you want to optionally include the external share capability in your environment, you also configure and deploy the External Share container. 

Ensure that you have completed the all of the preparation steps for deploying the External Share container: [Configuring external share for containers](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalshare.htm)
1. Download the sample es-deploy.yml or make changes to your own 3.0.6 es-deploy.yml file
2. Update the es-deploy.yml with the following:
    * Remove the existing parameters: JVM_HEAP_XMS and JVM_HEAP_XMX
    * Add the new parameters: JVM_INITIAL_HEAP_PERCENTAGE and JVM_MAX_HEAP_PERCENTAGE.  The recommended default values are 40 and 66 respectively.
    * On OpenShift, remove the following line: `runAsUser: 50001`
    * Optional: To leverage monitoring using Prometheus, add MON_METRICS_WRITER_OPTION and set it to 4 (i.e., name: MON_METRICS_WRITER_OPTION and value: "4"). The default port for Prometheus Plugin is 9103, which can be overridden by using MON_METRICS_SERVICE_ENDPOINT
    * Update the `image: <value>` with the interim fix image tag
3. Use the deployment file to deploy the External Share container:   
    ```kubectl apply -f es-deploy.yml```
    
4. Run the following command to get the Public IP and port to access External Share:
    ```kubectl get svc | ecm-es```

### Deploying the Technology Preview: Content Services GraphQL API container
If you want to use the Content Services GraphQL API container, follow the instructions in the Getting Started technical notice: [Technology Preview: Getting started with Content Services GraphQL API](http://www.ibm.com/support/docview.wss?uid=ibm10883630)

1. Download the sample crs-deploy.yml or make changes to your own 5.5.3 crs-deploy.yml file
2. Update the crs-deploy.yml with the following:
    * Remove the existing parameters: JVM_HEAP_XMS and JVM_HEAP_XMX
    * Add the new parameters: JVM_INITIAL_HEAP_PERCENTAGE and JVM_MAX_HEAP_PERCENTAGE.  The recommended default values are 40 and 66 respectively.
    * On OpenShift, remove the following line: `runAsUser: 50001`
    * Optional: To leverage monitoring using Prometheus, add MON_METRICS_WRITER_OPTION and set it to 4 (i.e., name: MON_METRICS_WRITER_OPTION and value: "4"). The default port for Prometheus Plugin is 9103, which can be overridden by using MON_METRICS_SERVICE_ENDPOINT
    * Update the `image: <value>` with the interim fix image tag
3. Use the deployment file to deploy the Content Services GraphQL API container:   
    ```kubectl apply -f crs-deploy.yml```
    
4. Run the following command to get the Public IP and port to access the Content Services GraphQL API:   
    ```kubectl get svc | ecm-crs```


## Uninstalling a Kubernetes release of FileNet Content Manager

To uninstall and delete the Content Platform Engine release, use the following command:

```console
$ kubectl delete -f <cpe-deploy.yml>
```

The command removes all the Kubernetes components associated with the release, except any Persistent Volume Claims (PVCs).  This is the default behavior of Kubernetes, and ensures that valuable data is not deleted. To delete the persisted data of the release, you can delete the PVC using the following command:

```console
$ kubectl delete pvc my-cpe-prod-release-cpe-pvclaim
```
Repeat the process for any other deployments that you want to delete.

