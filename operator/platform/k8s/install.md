# Installing IBM FileNet Content Manager 5.5.4 on Certified Kubernetes

- [Step 1: Get access to the container images](install.md#step-1-get-access-to-the-container-images)
- [Step 2: Prepare your environment for FileNet Content Manager software](install.md#step-2-prepare-your-environment-for-automation-software)
- [Step 3: Create a shared PV and add the JDBC drivers](install.md#step-3-create-a-shared-pv-and-add-the-jdbc-drivers)
- [Step 4: Create or reuse Docker registry secrets](install.md#step-4-create-or-reuse-a-docker-registry-secret)
- [Step 5: Deploy the operator manifest files to your cluster](install.md#step-5-deploy-the-operator-manifest-files-to-your-cluster)
- [Step 6: Configure the software that you want to install](install.md#step-6-configure-the-software-that-you-want-to-install)
- [Step 7: Apply the custom resources](install.md#step-7-apply-the-custom-resources)
- [Step 8: Verify that the FileNet Content Manager containers are running](install.md#step-8-verify-that-the-automation-containers-are-running)
- [Step 9: Complete some post-installation steps](install.md#step-9-complete-some-post-installation-steps)
- [Step 10: Troubleshooting](install.md#step-10-troubleshooting)

##  Step 1: Get access to the container images

You can access the container images in the IBM Docker registry with your IBMid (Option 1), or you can use the downloaded archives from IBM Passport Advantage (PPA) (Option 2).

### Option 1: Create a pull secret for the IBM Cloud Entitled Registry

1. Log in to [MyIBM Container Software Library](https://myibm.ibm.com/products-services/containerlibrary) with the IBMid and password that are associated with the entitled software.

2. In the **Container software library** tile, click **View library** and then click **Copy key** to copy the entitlement key to the clipboard.

3. Create a pull secret by running a `kubectl create secret` command.
   ```bash
   $ kubectl create secret docker-registry <my_pull_secret> --docker-server=cp.icr.io --docker-username=iamapikey --docker-password="<API_KEY_GENERATED>" --docker-email=user@foo.com
   ```

   > **Note**: The `cp.icr.io` value for the **docker-server** parameter is the only registry domain name that contains the images.

4. Take a note of the secret and the server values so that you can set them to the **pullSecrets** and **repository** parameters when you run the operator for your containers.

### Option 2: Download the packages from PPA and load the images

[IBM Passport Advantage (PPA)](https://www-01.ibm.com/software/passportadvantage/pao_customer.html) provides archives (.tgz) for the software. To view the list of Passport Advantage eAssembly installation images, refer to the [FileNet Content Manager V5.5.4 download document](http://www.ibm.com/support/pages/node/1096522).

1. Download one or more PPA packages to a server that is connected to your Docker registry.
2. Download the [`loadimages.sh`](../../scripts/loadimages.sh) script from GitHub.
3. Log in to your Kubernetes cluster.
4. Check that you can run a docker command.
   ```bash
   $ docker ps
   ```
5. Login to the Docker registry with your credentials.
   ```bash
   $ docker login <registry_url> -u <your_account>
   ```
   > **Note**: You can connect to a node in the cluster to resolve the `docker-registry.default.svc` parameter.

6. Run a `kubectl` command to make sure that you have access to Kubernetes.
   ```bash
   $ kubectl cluster-info
   ```
7. Run the `loadimages.sh` script to load the images into your Docker registry. Specify the two mandatory parameters in the command line.

   ```
   -p  PPA archive files location or archive filename
   -r  Target Docker registry and namespace
   -l  Optional: Target a local registry
   ```

   The following example shows the input values in the command line.

   ```
   # scripts/loadimages.sh -p <PPA-ARCHIVE>.tgz -r docker-registry.default.svc:5000/my-project
   ```

   > **Note**: The project must have pull request privileges to the registry where the images are loaded. The project must also have pull request privileges to push the images into another namespace/project.

4. Check that the images are pushed correctly to the registry.

## Step 2: Prepare your environment for automation software

Before you install any of the containerized software:

1. Go to the prerequisites page in the [IBM FileNet Content Manager 5.5.4](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_prepare.htm) Knowledge Center.
2. Follow the instructions on preparing your environment for the software components that you want to install.

  How much preparation you need to do depends on what you want to install and how familiar you are with your environment.

  ## Step 3: Create a shared PV and add the JDBC drivers

  1. Create a persistent volume (PV) for the operator. This PV is needed for the JDBC drivers. The following example YAML defines a PV, but PVs depend on your cluster configuration. 
     ```yaml
     apiVersion: v1
     kind: PersistentVolume
     metadata:
       labels:
         type: local
       name: operator-shared-pv
     spec:
       capacity:
         storage: 1Gi
       accessModes:
         - ReadWriteMany
       hostPath:
         path: "/root/operator"
       persistentVolumeReclaimPolicy: Delete
     ```

  2. Deploy the PV.
     ```bash
     $ kubectl create -f operator-shared-pv.yaml
     ```

  2. Create a claim for the PV, or check that the PV is bound dynamically, [operator-shared-pvc.yaml](../../descriptors/operator-shared-pvc.yaml?raw=true).

     > Replace the storage class if you do not want to create the relevant persistent volume.

     ```yaml
     apiVersion: v1
     kind: PersistentVolumeClaim
     metadata:
       name: operator-shared-pvc
       namespace: my-project
     spec:
       accessModes:
         - ReadWriteMany
       storageClassName: ""
       resources:
         requests:
           storage: 1Gi
       volumeName: operator-shared-pv
     ```

  3. Deploy the PVC.
     ```bash
     $ kubectl create -f descriptors/operator-shared-pvc.yaml
     ```

  4. Copy all of the JDBC drivers that are needed by the components you intend to install to the persistent volume. Depending on your storage configuration you might not need these drivers.

     > **Note**: File names for JDBC drivers cannot include additional version information.
       - DB2:
          - db2jcc4.jar
          - db2jcc_license_cu.jar
       - Oracle:
          - ojdbc8.jar
       - SQLServer:
          - mssql-jdbc.jre8.jar

      The following structure shows an example remote file system.

      ```
      pv-root-dir

         └── jdbc

            ├── db2

            │   ├── db2jcc4.jar

            │   └── db2jcc_license_cu.jar

            ├── oracle

            │   └── ojdbc8.jar

            └── sqlserver

               └── mssql-jdbc.jre8.jar
      ```

## Step 4: Create or reuse a Docker registry secret

In your target namespace, you must create a Docker registry secret if you want to use an external Docker registry or reuse a secret in the target project if you want to use an internal Docker registry. If you want to pull directly from the IBM entitled registry, reuse the secret that you created in [Step 1](install.md#step-1-create-a-namespace-and-get-access-to-the-container-images), Option 1.          

```yaml
imagePullSecrets:
   name: "<secret_name>"
```

> **Note**: The secret_name must match the imagePullSecrets.name parameter in the operator custom resource definition (.yaml) file.

For an external Docker registry.

```bash
$ kubectl create secret docker-registry <secret_name> --docker-server=<registry_url> --docker-username=<your_account> --docker-password=<your_password> --docker-email=fncmtest@ibm.com
```

## Step 5: Deploy the operator to your cluster

The operator has a number of descriptors that must be applied.
  - [descriptors/fncm_v1_fncm_crd.yaml](../../descriptors/fncm_v1_fncm_crd.yaml?raw=true) contains the description of the Custom Resource Definition.
  - [descriptors/operator.yaml](../../descriptors/operator.yaml?raw=true) defines the deployment of the operator code.
  - [descriptors/role.yaml](../../descriptors/role.yaml?raw=true) defines the access of the operator.
  - [descriptors/role_binding.yaml](../../descriptors/role_binding.yaml?raw=true) defines the access of the operator.
  - [descriptors/service_account.yaml](../../descriptors/service_account.yaml?raw=true) defines the identity for processes that run inside the pods of the operator.    

1. Modify the `image` parameter for containers (ansible and operator) and the `imagePullSecrets` name in `descriptors/operator.yaml` to a valid image registry URL. The value for `imagePullSecrets` name is the secret that you created in [Step 4](install.md#step-4-create-or-reuse-a-docker-registry-secret).

   ```yaml

   containers:
      - name: ansible
          # Replace this with the built image name
          image: "cp.icr.io/cp/cp4a/fncm-operator:ga-5.5.4"   
     -    
     -   
     - name: operator
          # Replace this with the built image name
          image: "cp.icr.io/cp/cp4a/fncm-operator:ga-5.5.4"      
    
    imagePullSecrets:
      - name: "admin.registrykey"
   ```


2. Edit the namespace spec in the `service_account.yaml` and `operator.yaml` files.

   ```yaml
   metadata:
      name: ibm-fncm-operator
      namespace: <my-project>
   ```

3. Apply the [Security Context Constraints (SCC)](../../descriptors/scc-fncm.yaml) that are needed for FileNet Content Manager:

   ```bash
   $ kubectl apply -f descriptors/scc-fncm.yaml
   ```

   > **Note**: `fsGroup` and `supplementalGroups` are `RunAsAny` and  `runAsUser` is `MustRunAsRange`.

   ```yaml
   fsGroup:
      type: RunAsAny
      ...
      ...
   runAsUser:
      type: MustRunAsRange
      ...
      ...
   supplementalGroups:
      type: RunAsAny
   ```

4. Prepare and deploy the ibm-fncm-operator on your cluster.
   
   The script [deployOperator.sh](../../scripts/deployOperator.sh) can be used to deploy the descriptors and the operator pod.
   ```bash
   $ ./scripts/deployOperator.sh -i <registry_url>/ibm-fncm-operator:latest -p '<secret_name>' -n <Namespace>
   ```

   > **Note**: If you do not specify the -i and -n options the operator is deployed in the default namespace at this URL: master_node:8500/default/ibm-fncm-operator:v1.0.0.
   
    If you want to deploy the operator YAML files without using the deployOperator.sh script, you can use the deploy command to deploy each file, for example:
   ```bash
   oc apply -f ./descriptors/fncm_v1_fncm_crd.yaml
   oc apply -f ./descriptors/service_account.yaml
   oc apply -f ./descriptors/role.yaml
   oc apply -f ./descriptors/role_bingding.yaml
   oc apply -f ./descriptors/operator.yaml
   ``` 

5. Monitor the pod until it shows a STATUS of *Running* or *Completed*:
   ```bash
   $ while kubectl get pods  | grep -v -E "(Running|Completed|STATUS)"; do sleep 5; done
   ```

## Step 6: Configure the software that you want to install

1. Make a copy of the template custom resources YAML file [fncm_v1_fncm_cr_template.yaml](../../descriptors/fncm_v1_fncm_cr_template.yaml?raw=true) and name it appropriately for your deployment (for example my_fncm_v1_fncm_cr.yaml).

   > **Important:** Because the maximum length of labels in Kubernetes is 63 characters, be careful with the lengths of your CR name and instance names. Some components can configure multiple instances, each instance must have a different name. The total length of the CR name and an instance name must not exceed 24 characters, otherwise some component deployments fail.
   
   You must use a single custom resource file to include all of the components that you want to deploy with an operator instance. Each time that you need to make an update or modification you must use this same file to apply the changes to your deployments. When you apply a new custom resource to an operator you must make sure that all previously deployed resources are included if you do not want the operator to delete them.

2. Change the default name of your instance in descriptors/my_fncm_v1_fncm_cr.yaml:

   ```yaml
   metadata:
     name: <MY-INSTANCE>
   ```

3. If you use an internal registry, enter values for the `image_pull_secrets` and `images` parameters with the information that you noted from [Step 4](install.md#step-4-create-or-reuse-a-docker-registry-secret) in the `shared_configuration` section.

   ```yaml
   shared_configuration:
     image_pull_secrets:
     - pull-secret
    ```

4. Use the information in [Configure IBM FileNet Content Manager](../../FNCM/README_config.md) to configure the software that you want to install. When you have completed all entries into your deployment copy of the `fncm_v1_fncm_cr_template.yaml` file, return to these instructions to continue the deployment.

## Step 7: Apply the custom resources

1. Check that all the components you want to install are configured.

   ```bash
   $ cat descriptors/my_fncm_v1_fncm_cr.yaml
   ```

2. Deploy the configured components by applying the custom resource.

   ```bash
   $ kubectl apply -f descriptors/my_fncm_v1_fncm_cr.yaml
   ```


## Step 8: Verify that the automation containers are running

Deployment can take a few minutes, and can take longer if more applications are configured and included in your custom YAML.

When all of the pods are *Running*, you can access the status of your containers with the following commands.
```bash
$ kubectl get deployment
$ kubectl logs <operatorPodName> -f -c operator
```

When all of the pods are Running and Ready, retrieve the cluster-info-ip name and port numbers with the following commands:
```bash
$ kubectl cluster-info
Kubernetes master is running at https://cluster-info-ip:8443
CoreDNS is running at https://cluster-info-ip:8443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

$ kubectl get services
```


## Step 9: Complete post-installation steps

You must complete additional post deployment tasks to make sure your environment is up and running. See [Completing post-deployment startup tasks for a new domain](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_postdeploy.htm) to follow the post-installation steps. Your tasks will vary depending on whether you used the Initialization and Verify containers to set up your environment.

If you deployed the Content Services GraphQL container, you must complete the steps to configure authentication, logging, and so on. For more information, see [Configuring the Content Services GraphQL API](https://www.ibm.com/support/knowledgecenter/SSNW2F_5.5.0/com.ibm.p8.containers.doc/containers_graphql.htm).

## Step 10: Troubleshooting

The `ibm-fncm-operator` deployment on a cluster creates an `operator` and `ansible` container. The `ansible` container shows the standard Ansible stdout logs. To see the logs of a container, run the following command:

```bash
$ kubectl logs deployment/ibm-fncm-operator -c ansible
```

The `operator` logs contain much more information about the operator than Kubernetes does.
```bash
$ kubectl logs deployment/ibm-fncm-operator -c operator
```

For runtime Ansible logs, go inside the pod that runs the `ansible` container, and look at the `/tmp/ansible-operator/runner/<group>/<version>/<kind>/<namespace>/<name>/artifacts/<jod-id>/stdout` directory.


