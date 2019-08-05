# Deploying with YAML files

## Requirements and Prerequisites

Ensure that you have completed the following tasks:

- [Preparing your FileNet environment](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare.htm) 
- [Preparing your Kubernetes server](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare_env_k8s.htm)
- [Downloading the product archives and loading the component images](../README.md)


## Deploying the component images

Use the command line to deploy the image using the parameters in the appropriate YAML file. You also use the command line to determine access information for your deployed images.

To deploy Content Platform Engine: 
 1. Use the deployment file to deploy Content Platform Engine:
    
    ```kubectl apply -f cpe-deploy.yml```

   Note:  To leverage monitoring using Prometheus, update the cpe-deploy.yml and set a new environment variable MON_METRICS_WRITER_OPTION to 4 to enable the Prometheus plugin (i.e., name: MON_METRICS_WRITER_OPTION and value: "4").  The default port for Prometheus Plugin is 9103, which can be overriden by using MON_METRICS_SERVICE_ENDPOINT.


 2. Run following command to get the Public IP and port to access Content Platform Engine:
    
    ```kubectl get svc | grep ecm-cpe```

To deploy IBM Content Navigator:
 1. Use the deployment file to deploy IBM Content Navigator:
    
    ```kubectl apply -f navigator-deploy.yml```

   Note:  To leverage monitoring using Prometheus, update the navigator-deploy.yml and set a new environment variable MON_METRICS_WRITER_OPTION to 4 to enable the Prometheus plugin (i.e., name: MON_METRICS_WRITER_OPTION and value: "4").  The default port for Prometheus Plugin is 9103, which can be overriden by using MON_METRICS_SERVICE_ENDPOINT.

 2. Run the following command to get the Public IP and port to access Content Management Interoperability Services:
    
    ```kubectl get svc | ecm-navigator```


To deploy Content Search Services:
 1. Use the deployment file to deploy Content Search Services:
    
    ```kubectl apply -f css-deploy.yml```

   Note:  To leverage monitoring using Prometheus, update the css-deploy.yml and set a new environment variable MON_METRICS_WRITER_OPTION to 4 to enable the Prometheus plugin (i.e., name: MON_METRICS_WRITER_OPTION and value: "4").  The default port for Prometheus Plugin is 9103, which can be overriden by using MON_METRICS_SERVICE_ENDPOINT.

 2. Run the following command to get the Public IP and port to access Content Search Services:
    
    ```kubectl get svc | grep ecm-css```

To deploy Content Management Interoperability Services:
 1. Use the deployment file to deploy Content Management Interoperability Services:
    
    ```kubectl apply -f cmis-deploy.yml```

   Note:  To leverage monitoring using Prometheus, update the cmis-deploy.yml and set a new environment variable MON_METRICS_WRITER_OPTION to 4 to enable the Prometheus plugin (i.e., name: MON_METRICS_WRITER_OPTION and value: "4").  The default port for Prometheus Plugin is 9103, which can be overriden by using MON_METRICS_SERVICE_ENDPOINT.

 2. Run the following command to get the Public IP and port to access Content Management Interoperability Services:
    
    ```kubectl get svc | ecm-cmis```


> **Reminder**: After you deploy, return to the instructions in the Knowledge Center, [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_postdeploy.htm), to get your FileNet Content Manager environment up and running

## Deploying the External Share container

If you want to optionally include the external share capability in your environment, you also configure and deploy the External Share container. 

Ensure that you have completed the all of the preparation steps for deploying the External Share container: [Configuring external share for containers](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalshare.htm)

 1. Use the deployment file to deploy the External Share container:
    
    ```kubectl apply -f es-deploy.yml```

   Note:  To leverage monitoring using Prometheus, update the es-deploy.yml and set a new environment variable MON_METRICS_WRITER_OPTION to 4 to enable the Prometheus plugin (i.e., name: MON_METRICS_WRITER_OPTION and value: "4").  The default port for Prometheus Plugin is 9103, which can be overriden by using MON_METRICS_SERVICE_ENDPOINT.

 2. Run the following command to get the Public IP and port to access External Share:
    
    ```kubectl get svc | ecm-es```

## Deploying the Technology Preview: Content Services GraphQL API container
If you want to use the Content Services GraphQL API container, follow the instructions in the Getting Started technical notice: [Technology Preview: Getting started with Content Services GraphQL API](http://www.ibm.com/support/docview.wss?uid=ibm10883630)

 1. Use the deployment file to deploy the Content Services GraphQL API container:
    
    ```kubectl apply -f crs-deploy.yml```

   Note:  To leverage monitoring using Prometheus, update the crs-deploy.yml and set a new environment variable MON_METRICS_WRITER_OPTION to 4 to enable the Prometheus plugin (i.e., name: MON_METRICS_WRITER_OPTION and value: "4").  The default port for Prometheus Plugin is 9103, which can be overriden by using MON_METRICS_SERVICE_ENDPOINT.

 2. Run the following command to get the Public IP and port to access the Content Services GraphQL API:
    
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

