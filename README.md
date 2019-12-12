# Deploying FileNet Content Manager

IBM FileNet Content Manager offers enterprise-level scalability and flexibility to handle the most demanding content challenges, the most complex business processes, and integration to all your existing systems. FileNet P8 is a reliable, scalable, and highly available enterprise platform that enables you to capture, store, manage, secure, and process information to increase operational efficiency and lower total cost of ownership. FileNet P8 enables you to streamline and automate business processes, access and manage all forms of content, and automate records management to help meet compliance needs.

## Requirements and prerequisites

Perform the following tasks to prepare to deploy your FileNet Content Manager images on Kubernetes:

- Prepare your FileNet Content Manager environment. These procedures include setting up databases, LDAP, storage, and configuration files that are required for use and operation. You must complete all of the [preparation steps for FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare.htm) before you are ready to deploy the container images. 

- Prepare your Kubernetes environment. See [Preparing for deployment with an operator](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_operators.htm)

- If you want to deploy additional optional containers, prepare the requirements that are specific to those containers. For details see the following information:
  - [Configuring external share for containers](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalshare.htm)
  - [Configuring the Content Services GraphQL API](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_graphql.htm)

- If you plan to use external key management in your environment, review the following preparation information before you deploy: [Preparing for external key management](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_externalkey.htm)

## Deploying with an operator

The FileNet Content Manager operator is built from the Red Hat and Kubernetes Operator Framework, which is an open source toolkit that is designed to automate features such as updates, backups, and scaling. The operator handles upgrades and reacts to failures automatically.

To prepare your operator and deploy your FileNet Content Manager components, follow the instructions for your operator platform:

- [Certified Kubernetes](operator/platform/k8s/README.md)
- [Red Hat OpenShift](operator/platform/ocp/README.md)
- [Managed Red Hat OpenShift on IBM Cloud Public](operator/platform/roks/README.md)

## Completing post deployment configuration

After you deploy your container images, you perform some required and some optional steps to get your FileNet Content Manager environment up and running. For detailed instructions, see [Completing post deployment tasks for IBM FileNet Content Manager](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_postdeploy.htm)
