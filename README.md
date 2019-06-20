# Deploying FileNet Content Manager

IBM® FileNet® Content Manager V5.5 digitizes content and manages the content lifecycle by enabling users to focus on their work and collaborate within the enterprise and with external business partners.

IBM FileNet Content Manager offers enterprise-level scalability and flexibility to handle the most demanding content challenges, the most complex business processes, and integration to all your existing systems. FileNet P8 is a reliable, scalable, and highly available enterprise platform that enables you to capture, store, manage, secure, and process information to increase operational efficiency and lower total cost of ownership. FileNet P8 enables you to streamline and automate business processes, access and manage all forms of content, and automate records management to help meet compliance needs.

## Requirements and Prerequisites

Perform the following tasks to prepare to deploy your FileNet Content Manager images on Kubernetes:

- Prepare your Kubernetes environment. See [Preparing to install automation containers on Kubernetes](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare_env_k8s.htm)

- Prepare your FileNet Content Manager environment. These procedures include setting up databases, LDAP, storage, and configuration files that are required for use and operation. If you plan to use the YAML file method, you also create YAML files that include the applicable parameter values for your deployment. You must complete all of the [preparation steps for FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare_env_k8s.htm) before you are ready to deploy the container images. 

- If you want to deploy additional optional containers, prepare the requirements that are specific to those containers. For details see the following information:
  - [Configuring external share for containers](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalshare.htm)
  - [Technology Preview: Getting started with the Content Services GraphQL API](http://www.ibm.com/support/docview.wss?uid=ibm10883630)

## Downloading packages and loading the images into the registry

1. Use the information in the [download document for FileNet Content Manager](https://www-01.ibm.com/support/docview.wss?uid=swg24044874) to download the product images from Passport Advantage: 

    CPE-container-part-number.tar
    ICN-container-part-number.tar
    CSS-container-part-number.tar
    CMIS-container-part-number.tar
    ES-container-part-number.tar


2. Use the following commands to extract the product image from the part number archive and upload the image to the Kubernetes private registry:

Content Platform Engine

   ```
  tar xvf <CPE-container-part-number.tar>
  docker load -i <image.tgz>
  docker tag <docker store>/cpe:latest <private registry>/cpe:latest
  docker push <private registry>/cpe:latest
   ```   

Navigator:

tar xvf <ICN-container-part-number.tar>
This will give 2 tgz files. 1) Navigator SSO 2) Navigator non-SSO
docker load <image.tgz>
docker tag <docker store>/navigator:latest <private registry>/navigator:latest
docker push <private registry>/navigator:latest

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



## Deploying

You can deploy your container images with the following methods:

- [Using Helm charts](helm-charts/README.md)
- [Using Kubernetes YAML](k8s-yaml/README.md)

## Completing post deployment configuration

After you deploy your container images, you perform some required and some optional steps to get your FileNet Content Manager environment up and running. For detailed instructions, see [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/en/SSYHZ8_19.0.x/com.ibm.dba.install/k8s_topics/tsk_deploy_postecmdeployk8s.html)
