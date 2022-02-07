# Updating FileNet Content Manager 5.5.7

If you installed any of the FileNet Content Manager 5.5.7 components on a Kubernetes cluster, update the components to a higher interim fix level using the updated operator and the relevant container interim fixes. Required details, like the image:tag, of the interim fix Docker image can be found in the individual interim fix readmes.

Unlike installations and upgrades, which both deal with major versions of a release, an update is a change to your containers that are applied within a major release. This readme is used to apply container updates for minor version changes within a major release.

> If you are using this interim fix as a part of a new deployment of the Content Platform Engine container, you must deploy the container as described in the Knowledge Center topic [Deploying a new P8 domain by using containers](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_deploy.htm). In the parts of the process described in [Deploying a custom resource](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_deploying_cr.htm), use the information provided in the section "Edits to the custom resource YAML file after 5.5.7/3.0.10" at the end of this readme.

> If you are using this interim fix as a part of a upgrading an existing deployment, you must deploy the container as described in the Knowledge Center topic [Upgrading container deployments](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_upgradeversion.htm). In the parts of the process described in [Checking the deployment type and license](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_upgrading_license.htm) and [Upgrading your components](https://www.ibm.com/support/knowledgecenter/en/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_upgrading_fncm.htm), use the information provided in the section "Edits to the custom resource YAML file after 5.5.7/3.0.10" at the end of this readme.

## Updating a deployment with interim fixes

The high-level process to updating an environment with interim fixes is
- [Step 1: Get access to the interim fix container images](#step-1-get-access-to-the-interim-fix-container-images)
- [Step 2: Get access to the current version of the operator](#step-2-get-access-to-the-current-version-of-the-operator)
- [Step 3: Update the installed operator](#step-3-update-the-installed-operator)
- [Step 4: [Optional] Update the custom resource YAML file for your FileNet Content Manager deployment](#step-4-optional-update-the-custom-resource-yaml-file-for-your-filenet-content-manager-deployment)
- [Step 5: [Optional] Apply the updated custom resource YAML file](#step-5-optional-apply-the-updated-custom-resource-yaml-file)
- [Step 6: Verify the updated containers](#step-6-verify-the-updated-containers)

The following sections describe these steps in detail.

##  Step 1: Get access to the interim fix container images

You can access the container images in the IBM Docker registry with your IBMid.

1. Log in to [MyIBM Container Software Library](https://myibm.ibm.com/products-services/containerlibrary) with the IBMid and password that are associated with the entitled software.

2. In the **Container software library** tile, click **View library** and then click **Copy key** to copy the entitlement key to the clipboard.

3. Log in to your Kubernetes cluster and set the context to the project for your existing deployment.

4. Create a pull secret by running a `kubectl create secret` command.
   ```bash
   $ kubectl create secret docker-registry admin.registrykey --docker-server=cp.icr.io --docker-username=iamapikey --docker-password="<API_KEY_GENERATED>" --docker-email=user@foo.com
   ```

   > **Note**: The `cp.icr.io` value for the **docker-server** parameter is the only registry domain name that contains the images.

5. Take a note of the secret and the server values so that you can set them to the **pullSecrets** and **repository** parameters when you run the operator for your containers.


## Step 2: Get access to the current version of the operator

If the operator in the project (namespace) of your deployment is already at the correct operator level, skip to step 4.

1. Log in to your Kubernetes cluster and set the context to the project for your existing deployment.

2. Download or clone the repository on your local machine and change to the `operator` directory.
   ```bash
   $ git clone -b <version_branch> git@github.com:ibm-ecm/container-samples.git
    Where <version_branch> is 5.5.7 for the current release.
   ```
   The repository contains the scripts and Kubernetes descriptors that are necessary to upgrade the FileNet Content Manager operator.


## Step 3: Update the installed operator

1. Log in to your Kubernetes cluster and set the context to the project for your existing deployment.

2. Go to the downloaded container-samples.git for FileNet Content Manager V5.5.7

   For example:
   ```bash
   $ cd container-samples/ 
   ```
3. Remove the .OPERATOR_TYPE file in case it exists from a previous deployment

   ```bash
   rm -f /<hostPath>/.OPERATOR_TYPE
   ```

   Where <hostPath> is the location of your PV (root/operator).

4. Upgrade the fncm-operator on your project.

   Use the [scripts/upgradeOperator.sh](../../scripts/upgradeOperator.sh) script to deploy the operator manifest descriptors. Use the operator image tag as provided in the readme file for the operator interim fix you are deploying.
   ```bash
   $ ./scripts/upgradeOperator.sh -i <registry_url>/icp4a-operator:21.0.2 -n <namespace> -p 'admin.registrykey' -a accept
   ```

   Where *registry_url* is the value for your internal docker registry or `cp.icr.io/cp/cp4a` for the IBM Cloud Entitled Registry,  admin.registrykey is the secret created to access the registry, and *accept* means that you accept the [license](../../LICENSE).

   > **Note**: If you plan to use a non-admin user to install the operator, you must add the user to the `ibm-fncm-operator` role. For example:
   ```bash
   $ oc adm policy add-role-to-user ibm-fncm-operator <user_name>
   ```
5. Monitor the pod until it shows a STATUS of Running:
   ```bash
   $ oc get pods -w
   ```
     > **Note**: When started, you can monitor the operator logs with the following command:
   ```bash
   $ oc logs -f deployment/ibm-fncm-operator -c operator
   ```
   (You can also use kubectl in place of oc in the previous commands.)

## Step 4: [Optional] Update the custom resource YAML file for your FileNet Content Manager deployment

If you upgraded the operator to an interim fix level and decided to use image digests as described in the documentation topic [Choosing image tags or digests](https://www.ibm.com/docs/en/filenet-p8-platform/5.5.x?topic=deployment-choosing-image-tags-digests), skip to step 6.

Get the custom resource YAML file that you previously deployed and edit it as follows:

1. Verify that the metadata.labels.release version is 5.5.7.

2. Verify the appVersion in the global spec section reflects the major release you are applying a fix to. The appVersion depends on the version of the operator and choice of eGA. The corresponding version of the deployed operator automatically defaults the image:tag or digest values for deployed containers to reflect a particular set of containers that correspond to the release of the operator.

    Use the following link to get the FNCM Operator tags and appVersions: [FileNet P8 Fix Pack Compatibility Matrices](https://www.ibm.com/support/pages/filenet-p8-fix-pack-compatibility-matrices)

    **Tips**:
    > The default values of the tags or digests known to the operator reflect the versions of component interim fixes that a particular operator was released with. To utilize different component version or to update to a component where a corresponding new operator version is not available, specify the image tags in the CR for each component where a non-default version is desired.

    > Use the "Operator Information" tab in the FileNet P8 Fix Pack Compatibility Matrix to see operator interim fixes and choose the version of operator that corresponds to the most recent interim fix you wish to deploy. This might entail utilizing the operator interim fix and then providing the *tag* parameter in the CR to indicate images that should remain at their current level (eGA or an earlier interim fix level) or update to a higher interim fix level.

3. If you want to override the default tags, then in the sections for each of those components you wish to override, modify the configuration parameter `ecm_configuration.<component>.image.tag` to reflect the value for the image loaded, for example to choose an interim fix image:
    ```bash
       repository: cp.icr.io/cp/cp4a/ban/navigator
       tag: ga-3010-icn-if001
   ```
   or to specify an eGA image
   ```bash
       repository: cp.icr.io/cp/cp4a/ban/navigator
       tag: ga-3010-icn
   ```

   **Tips**:
    > The values of the tags for a given interim fix can be found in the readme provided with that interim fix. The values for eGA tags can be found in the Knowledge Center for the product you are deploying.

    > Verify the secret named in the CR YAML file as the imagePullSecrets is valid. Note the secret might be expired, in which case you must re-create the secret.

   Repeat this step for each component that you want to update to a new version.

4. Verify the following parameters in the shared_configuration section are set to false:

   ```
    shared_configuration.sc_content_initialization: false 
    shared_configuration.sc_content_verification: false

   ```

## Step 5: [Optional] Apply the updated custom resource YAML file
If you upgraded the operator to the latest interim fix level and decided to use image digests values known to the corresponding operator, this step is skipped.

1. Check that all the components being updated are configured with the correct image tag values.

   ```bash
   $ cat descriptors/my_fncm_v1_fncm_cr.yaml
   ```

2. Update the configured components by applying the custom resource.

   ```bash
   $ kubectl apply -f descriptors/my_fncm_v1_fncm_cr.yaml
   ```

## Step 6: Verify the updated containers

The operator reconciliation loop might take several minutes. When all pods are Running, access the status of the containers by using the following commands:
```bash
$ oc status
$ oc get pods -w
$ oc logs <operatorPodName> -f -c operator
```
(You can also use `kubectl` in place of `oc` in these commands.)

Return to the interim fix readme for additional verification instructions of the particular component being updated.

## Rolling a deployment back to a previous version

Leave the operator and custom resource file at interim fix level.

Edit the custom resource file:

1. Revert the appVersion in the global spec section to the previous level:
   appVersion:21.0.1.1

2. To override the default tags for the appVersion, in the sections for each of the components you want to override, modify the configuration parameter `ecm_configuration.<component>.image.tag` to reflect the value for the desired image, for example:

   ```bash
       repository: cp.icr.io/cp/cp4a/fncm/cmis
       tag: ga-306-cmis-if001
   ```
      > **Tip**: If you are rolling your deployment back to an earlier interim fix, the values of the tags for a given interim fix can be found in the readme provided with that interim fix.

      > **Tip**: Verify the secret named in the CR YAML file as the imagePullSecrets is valid. Note the secret might be expired, in which case you must re-create the secret.

3. Follow Step 5 and Step 6 in the previous procedure to apply the edited custom resource file and monitor the completion of the operator reconciliation loop.

## Edits to the custom resource YAML file after 5.5.7/3.0.10

As a part of the process to create a new deployment or upgrade an existing one, the custom resource YAML file is created or updated as described in the IBM FileNet Content Manager Knowledge Center. The differences that are introduced by the operator interim fix are described in the interim fix readme for the particular operator version. Consider these differences when creating or updating your custom resource YAML file.
