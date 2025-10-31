###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2024. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################
import base64
import os.path
import re
import shutil

from kubernetes import client
from kubernetes.client import ApiException
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from time import sleep

from ..utilities import kubernetes_utilites as k
from ..utilities.utilities import replace_namespace_in_file, create_tmp_folder


# CLass that contains functions to delete the CR as well delete the Operator
class Deploy:

    def __init__(self, console, setup=None, logger=None, required_files=None):
        self._logger = logger
        self._kube = k.KubernetesUtilities(logger)
        self._setup = setup
        self._console = console

        self.required_file_paths = {}
        for file in required_files:
            file_name = file.split("/")[-1]
            self.required_file_paths[file_name] = file

        # Tmp File paths for the resources
        create_tmp_folder()
        modified_files = [
            "cluster_role_binding.yaml",
            "catalogsource.yaml",
            "operator_group.yaml",
            "subscription.yaml",
            "operator.yaml"
        ]
        self.tmp_file_paths = {}
        for file in modified_files:
            self.tmp_file_paths[file] = os.path.join(os.getcwd(), ".tmp", file)

        self._apps_v1_api = self._kube.apps_v1
        self._core_v1_api = self._kube.core_v1
        self._custom_api = self._kube.custom_api

        if self._setup.private_catalog:
            self._catalog_namespace = self._setup.namespace
        else:
            self._catalog_namespace = "openshift-marketplace"

        if self._setup.platform.lower() == "ocp":
            self._deployment_type = "olm"
            self._task_numbers = {
                "ClusterSetup": 4,
                "DeploymentSetup": 3,
                "Install": 3,
            }
        else:
            self._deployment_type = "yaml"
            self._task_numbers = {
                "ClusterSetup": 2,
                "DeploymentSetup": 4,
                "Install": 2,
            }

    @property
    def task_numbers(self):
        return self._task_numbers

    @property
    def deployment_type(self):
        return self._deployment_type

    # Function to create the entitlement key secret for either entitlement key or the private registry

    def create_entitlement_key_secret(self, progress, task):
        try:
            if self._setup.private_registry_valid:
                self._logger.info(f"Creating image pull secret for private registry: {self._setup.private_registry_server}")
                progress.log(
                    f"Creating image pull secret for private registry: {self._setup.private_registry_server}")
                progress.log()
                data = {
                    '.dockerconfigjson': base64.b64encode(
                        bytes(
                            '{{"auths": {{"{}": {{"username": "{}", "password": "{}", "email": "example@example.com"}}}}}}'.format(
                                self._setup.private_registry_server,
                                self._setup.private_registry_username,
                                self._setup.private_registry_password),
                            'utf-8'
                        )
                    ).decode('utf-8')
                }

            else:
                self._logger.info('Creating image pull secret for IBM Entitlement Registry')
                progress.log(f"Creating image pull secret for IBM Entitlement Registry")
                progress.log()

                data = {
                    '.dockerconfigjson': base64.b64encode(
                        bytes(
                            '{{"auths": {{"{}": {{"username": "{}", "password": "{}", "email": "example@example.com"}}}}}}'.format(
                                self._setup.registry, "cp",
                                self._setup.entitlement_key),
                            'utf-8'
                        )
                    ).decode('utf-8')
                }

            # Create Docker registry secret object
            secret = client.V1Secret(
                api_version="v1",
                data=data,
                kind="Secret",
                metadata=client.V1ObjectMeta(name="ibm-entitlement-key"),
                type="kubernetes.io/dockerconfigjson"
            )
            self._core_v1_api.read_namespaced_secret(name="ibm-entitlement-key", namespace=self._setup.namespace)
        except client.ApiException as e:
            if e.status == 404:
                self._core_v1_api.create_namespaced_secret(namespace=self._setup.namespace, body=secret)
                self._logger.info("Secret 'ibm-entitlement-key' created successfully")
                progress.log(Text(f"Secret 'ibm-entitlement-key' created successfully", style="bold green"))
                progress.log()
                progress.advance(task, advance=1)
                return

        progress.log(Text(f"Secret 'ibm-entitlement-key' already exists", style="bold yellow"))
        self._logger.info("Secret 'ibm-entitlement-key' already exists")
        progress.log()
        progress.advance(task, advance=1)

    def cluster_setup(self, progress, task):
        # Number of tasks = 1
        try:
            self._logger.info("Starting Cluster Setup")
            progress.log(Panel.fit("Starting Cluster Setup", style="cyan"))
            progress.log()

            self._logger.info("Creating namespace for the FileNet Content Manager Deployment")
            progress.log("Creating namespace for the FileNet Content Manager Deployment")
            progress.log()

            # Check if the namespace is already present in the cluster
            try:
                api_response = self._core_v1_api.read_namespace_status(self._setup.namespace)

                if api_response.status.phase == "Active":
                    self._logger.info(f"Namespace '{self._setup.namespace}' already exists")
                    progress.log(Text(f"Namespace '{self._setup.namespace}' already exists", style="bold yellow"))
                    progress.log()
            except ApiException as e:
                if e.status == 404:
                    self._kube.create_namespace(self._setup.namespace)
                    self._logger.info(f"Namespace '{self._setup.namespace}' created successfully")
                    progress.log(Text(f"Namespace '{self._setup.namespace}' created successfully", style="bold green"))
                    progress.log()

            progress.update(task, advance=1)

            self.create_entitlement_key_secret(progress, task)

            if self._deployment_type == "olm":

                progress.log(
                    "Label the default namespace to allow network policies to open traffic to the ingress controller using a namespaceSelector")
                progress.log()

                patch_body = [
                    {"op": "replace", "path": "/metadata/labels/network.openshift.io~1policy-group", "value": "ingress"}
                ]
                try:
                    self._core_v1_api.patch_namespace(name="default", body=patch_body)
                    progress.update(task, advance=1)
                except Exception as e:
                    progress.log("Error while labelling the default namespace ", e)
                    progress.log()

            progress.log(Panel.fit("Cluster Setup Completed", style="bold green"))
            progress.log()
            progress.update(task, advance=1)
        except Exception as e:
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))
            progress.log()

    # Function to prepare the installation of the operator, includes applying CRD ,Cluster role, Service account etc
    def apply_cncf(self, progress, task):
        try:
            # Number of Tasks = 4
            self._logger.info("Starting CRD and Permission Setup")
            progress.log(Panel.fit("Starting CRD and Permission Setup", style="cyan"))
            progress.log()

            # Apply the CRD
            self._logger.info("Applying/Patching Custom Resource Definition")
            progress.log(f"Applying/Patching Custom Resource Definition")
            progress.log()
            self._kube.apply_cluster_resource_files(
                resource_file=self.required_file_paths["fncm_v1_fncm_crd.yaml"],
                resource_type="Custom Resource Definition")
            progress.update(task, advance=1)

            # Apply the Cluster Role
            self._logger.info("Applying/Patching Cluster Role")
            progress.log(f"Applying/Patching Cluster Role")
            progress.log()
            self._kube.apply_cluster_resource_files(
                resource_file=self.required_file_paths["service_account.yaml"],
                resource_type="Service Account", namespace=self._setup.namespace)
            progress.update(task, advance=1)

            # Apply the Role
            self._logger.info("Applying/Patching Role")
            progress.log(f"Applying/Patching Role")
            progress.log()
            self._kube.apply_cluster_resource_files(
                resource_file=self.required_file_paths["role.yaml"], resource_type="Role",
                namespace=self._setup.namespace)
            progress.update(task, advance=1)

            # Apply the Role Binding
            self._logger.info("Applying/Patching Role Binding")
            progress.log(f"Applying/Patching Role Binding")
            progress.log()
            self._kube.apply_role_binding(
                namespace=self._setup.namespace, resource_file=self.required_file_paths["role_binding.yaml"])
            progress.update(task, advance=1)

            self._logger.info("CRD and Permission Setup Completed")
            progress.log(Panel.fit("CRD and Permission Setup Completed", style="bold green"))
            progress.log()
        except Exception as e:
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))

    # Function to apply OLM , for OCP only
    def apply_olm(self, progress, task):
        # Number of tasks = 3
        try:
            self._logger.info("Starting OLM Installation")
            progress.log(Panel.fit("Starting OLM Installation", style="cyan"))
            progress.log()
            if self._setup.private_catalog:
                self._catalog_namespace = self._setup.namespace
                self._logger.info(f"Using private catalog namespace: {self._catalog_namespace}")
                progress.log(f"Using private catalog namespace: {self._catalog_namespace}")
                progress.log()

            else:
                self._logger.info(f"Using global catalog namespace (GCN): {self._catalog_namespace}")
                progress.log(f"Using global catalog namespace (GCN): {self._catalog_namespace}")
                progress.log()
            replace_namespace_in_file(project_name=self._catalog_namespace,
                                      input_file=self.required_file_paths["catalogsource.yaml"],
                                      output_file=self.tmp_file_paths["catalogsource.yaml"],
                                      resource_type="catalog source")

            self._logger.info("Applying/Patching Catalog Source")
            progress.log(f"Applying/Patching Catalog Source")
            progress.log()

            self._kube.apply_cluster_resource_files(
                resource_file=self.tmp_file_paths["catalogsource.yaml"],
                namespace=self._catalog_namespace, resource_type="Catalog Source")
            progress.update(task, advance=1)

            retries = 0
            progress.log(f"Waiting for IBM FileNet Content Manager Operator Catalog Pod to start")
            progress.log()
            while retries < 40:
                pods = self._core_v1_api.list_namespaced_pod(self._catalog_namespace)
                running_pods = [pod.metadata.name for pod in pods.items if
                                "ibm-fncm-operator-catalog" in pod.metadata.name and pod.status.phase == "Running" and pod.status.container_statuses[0].ready]
                if running_pods:
                    progress.log(
                        Text(f"IBM FileNet Content Manager Operator Catalog Pod is running.", style="bold green"))
                    progress.log()
                    progress.update(task, advance=1)
                    break
                else:
                    retries = retries + 1
                    progress.log(f"FileNet Content Management Catalog deployment in progress ({retries}/40) ")
                    progress.log()
                    sleep(5)

            if retries == 40:
                self._logger.debug("Timeout Waiting for IBM FileNet Content Manager Operator Catalog pod to start")
                progress.log(Text("Timeout Waiting for IBM FileNet Content Manager Operator Catalog pod to start",
                                  style="bold red"))
                progress.log()

                progress.log("Please check the status of Pod by issuing the below command:")
                progress.log()
                progress.log(Syntax(
                    f"kubectl describe pod $(kubectl get pod -n {self._catalog_namespace} | grep ibm-fncm-operator-catalog | awk '{{print $1}}') -n ${self._catalog_namespace}",
                    "bash"))

            self._logger.info("Applying/Patching Operator Group")
            progress.log("Applying/Patching Operator Group")
            progress.log()

            # Check if existing operator group file is present, if not create a new one
            operator_groups = self._kube.list_operator_groups(namespace=self._setup.namespace)
            if operator_groups:
                self._logger.info("Operator Group already exists, skipping creation")
                progress.log(Text("Operator Group already exists, skipping creation", style="bold yellow"))
                progress.log()
            else:
                replace_namespace_in_file(project_name=self._setup.namespace,
                                          input_file=self.required_file_paths["operator_group.yaml"],
                                          output_file=self.tmp_file_paths["operator_group.yaml"],
                                          resource_type="operator group")

                self._kube.apply_cluster_resource_files(
                    resource_file=self.tmp_file_paths["operator_group.yaml"],
                    namespace=self._setup.namespace,
                    resource_type="Operator Group")

            progress.update(task, advance=1)

            self._logger.info("OLM Installation Completed")
            progress.log(Panel.fit("OLM Installation Completed", style="bold green"))
            progress.log()
        except Exception as e:
            self._logger.debug(f"Error occurred while applying the resources: {e}")
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))

    def wait_for_operator(self, progress, task):
        try:
            # Initialize attempts counter
            # Number of tasks = 1
            attempts = 0
            retries = 0
            self._logger.info("Checking rollout status of FileNet Content Management Operator deployment")
            progress.log(f"Checking rollout status of FileNet Content Management Operator deployment")
            progress.log()
            while retries < 40:
                pods = self._core_v1_api.list_namespaced_pod(self._setup.namespace)
                running_pods = [pod.metadata.name for pod in pods.items if
                                "ibm-fncm-operator" in pod.metadata.name and "catalog" not in pod.metadata.name and pod.status.phase == "Running" and pod.status.container_statuses[0].ready]
                if running_pods:
                    progress.log(
                        Text(f"IBM FileNet Content Manager Operator Pod is running.", style="bold green"))
                    progress.log()
                    progress.update(task, advance=1)
                    break
                else:
                    retries = retries + 1
                    progress.log(f"FileNet Content Management Operator deployment in progress ({retries}/40) ")
                    progress.log()
                    sleep(15)

            if retries == 40:
                self._logger.info("Timeout Waiting for IBM FileNet Content Manager Operator pod to start")
                progress.log(Text("Timeout Waiting for IBM FileNet Content Manager Operator pod to start",
                                  style="bold red"))
                progress.log()

                progress.log("Please check the status of Pod by issuing the below command:")
                progress.log()
                progress.log(Syntax(
                    f"kubectl describe pod $(kubectl get pod -n {self._setup.namespace} | grep ibm-fncm-operator | awk '{{ print $1 }}') -n {self._setup.namespace}",
                    "bash"))
                exit()

            self._logger.info("IBM FileNet Content Manager Operator Deployment Completed")
            progress.log(Panel.fit("IBM FileNet Content Manager Operator Deployment Completed", style="bold green"))
            progress.update(task, advance=1)
        except Exception as e:
            self._logger.debug(f"Error occurred while applying the resources: {e}")
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))
            progress.log()

    def apply_operator_olm(self, progress, task):
        # Number of tasks = 2

        self._logger.info("Starting IBM FileNet Content Manager Operator Installation")
        progress.log(Panel.fit("Starting IBM FileNet Content Manager Operator Installation", style="cyan"))
        progress.log()

        self._logger.info("Applying/Patching Subscription")
        progress.log(f"Applying/Patching Subscription")
        progress.log()

        if self._setup.private_catalog:
            replace_namespace_in_file(project_name=self._setup.namespace,
                                      input_file=self.required_file_paths["subscription.yaml"],
                                      output_file=self.tmp_file_paths["subscription.yaml"],
                                      resource_type="subscription",
                                      private=True)
            self._logger.info(f"Using private catalog namespace: {self._setup.namespace}")
            progress.log(f"Using private catalog namespace: {self._setup.namespace}")
            progress.log()
        else:
            replace_namespace_in_file(project_name=self._setup.namespace,
                                      input_file=self.required_file_paths["subscription.yaml"],
                                      output_file=self.tmp_file_paths["subscription.yaml"],
                                      resource_type="subscription")
            self._logger.info(f"Using global catalog namespace (GCN): {self._catalog_namespace}")
            progress.log(f"Using global catalog namespace (GCN): {self._catalog_namespace}")

        self._kube.apply_cluster_resource_files(
            resource_file=self.tmp_file_paths["subscription.yaml"],
            namespace=self._setup.namespace,
            resource_type="Subscription")

        progress.update(task, advance=1)

        self.wait_for_operator(progress, task)

    # Function to install operator on CNCF
    def apply_operator_cncf(self, progress, task):
        # Number of tasks = 2
        self._logger.info("Starting IBM FileNet Content Manager Operator Installation")
        progress.log(Panel.fit("Starting IBM FileNet Content Manager Operator Installation", style="cyan"))
        progress.log()

        shutil.copy(self.required_file_paths["operator.yaml"], self.tmp_file_paths["operator.yaml"])

        with open(self.tmp_file_paths["operator.yaml"], 'r') as file:
            content = file.read()

        self._logger.info("Setting license acceptance to 'accept' in the operator file")
        progress.log("Setting license acceptance to 'accept' in the operator file")
        progress.log()

        # Update the 'fncm_license' value to 'accept'
        content = re.sub(r'fncm_license:\n  value:.*', 'fncm_license:\n  value: accept', content)

        # Write the modified content back to the temporary operator file
        with open(self.tmp_file_paths["operator.yaml"], 'w') as file:
            file.write(content)

        with open(self.tmp_file_paths["operator.yaml"], 'r') as file:
            content = file.read()
        registry_in_file = "icr.io/cpopen"

        if self._setup.entitlement_key_valid:
            self._logger.info("FileNet Content Management Operator is being installed using the IBM Entitlement Registry")
            progress.log("FileNet Content Management Operator is being installed using the IBM Entitlement Registry")
            progress.log()
            if self._setup.runtime_mode == "dev":
                pattern = re.compile(re.escape(registry_in_file) + r'\b')
                replacement = "cp.stg.icr.io" + '/cp'
                content = pattern.sub(replacement, content)

                # Write the modified content back to the temporary operator file
                with open(self.tmp_file_paths["operator.yaml"], 'w') as file:
                    file.write(content)
        else:
            self._logger.info("FileNet Content Management Operator is being installed using a private registry")
            progress.log("FileNet Content Management Operator is being installed using a private registry")
            progress.log()
            pattern = re.compile(re.escape(registry_in_file) + r'\b')
            replacement = self._setup.private_registry_server
            content = pattern.sub(replacement, content)

            # Write the modified content back to the temporary operator file
            with open(self.tmp_file_paths["operator.yaml"], 'w') as file:
                file.write(content)

        self._logger.info("Applying/Patching FileNet Operator Deployment")
        progress.log(f"Applying/Patching FileNet Operator Deployment")
        progress.log()

        self._kube.apply_cluster_resource_files(
            resource_file=self.tmp_file_paths["operator.yaml"], resource_type="Deployment",
            namespace=self._setup.namespace)

        progress.update(task, advance=1)

        self.wait_for_operator(progress, task)
