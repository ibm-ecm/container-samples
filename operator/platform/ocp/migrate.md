# Migrating IBM FileNet Content Manager 5.5.x persisted data to V5.5.4 on Red Hat OpenShift

Because of the change in the container deployment method, there is no upgrade path for previous versions of FileNet Content Manager to V5.5.4.

To move a V5.5.x installation to V5.5.4, you prepare your environment and deploy the operator the same way you would for a new installation. The difference is that you use the configuration values for your previously configured environment, including datasource, LDAP, storage volumes, etc. when you customize your deployment YAML file.

Optionally, to protect your production deployment, you can create a replica of your data and use that datasource information for the operator deployment to test your migration. In this option, you follow the instructions for a new deployment.


## Step 1: Collect parameter values from your existing deployment

You can use the reference topics in the [FileNet Content Manager Knowldege Center](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_configrefop.htm) to see the parameters that apply for your components and shared configuration.

## Step 2: Prepare your environment and deploy the operator

Follow the instructions in [Installing IBM FileNet Content Manager 5.5.4 on Red Hat OpenShift](install.md), until you reach Step 7: Apply the custom resources.


## Step 3: Update your custom YAML file

Use the values for your existing deployment to update the custom YAML file for the new operator deployment. For more information, see [Configure IBM FileNet Content Manager](../../FNCM/README_config.md). 

## Step 4: Stop your existing 5.5.x containers

When you are ready to deploy the V5.5.4 version of your FileNet Content Manager containers, stop your previous containers.

## Step 5: Complete the deployment with the FileNet Content Manager operator

Continue with the instructions in [Installing IBM FileNet Content Manager 5.5.4 on Red Hat OpenShift](install.md) to complete the deployment of V5.5.4. 
