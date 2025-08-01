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
import os.path
import re
import shutil
from datetime import datetime
from time import sleep

import yaml
from rich import print
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from pathlib import Path

from ..utilities import kubernetes_utilites as k
from ..utilities.prerequisites_utilites import zip_folder, write_yaml_to_file
from ..utilities.utilities import replace_namespace_in_file, create_tmp_folder, is_key_present, update_value_by_path, \
    find_keys_and_structures


# Class to handle upgrade operator and deployment related functionalities
class Upgrade:
    def __init__(self, console, setup=None, logger=None, silent=False, required_files=None):
        self._logger = logger
        self._console = console
        self._silent = silent
        self._kube = k.KubernetesUtilities(logger)
        self._setup = setup
        self._namespace = self._setup.namespace
        self._cr_present = True
        self._operator_present = True

        # checking if custom resource file exists
        cr_details = self._kube.get_deployment_cr(namespace=self._namespace, logger=self._logger)

        if not cr_details:
            self._cr_present = False
            self._logger.info(f"No Custom Resource file found in '{self._namespace}'.")

        # checking if operator exists
        if self._setup.platform.lower() == "ocp" or self._setup.platform.lower() == "roks":
            self._subscription_details = self._kube.get_subscription(namespace=self._namespace)

        # Collect Operator details
        operator_deployment = "ibm-fncm-operator"
        self._operator_details = self._kube.get_operator_details(self._namespace, operator_deployment)
        if not self._operator_details:
            self._operator_present = False

        # Deployment Details
        self._deployment_details = {}

        # Version Details
        self._version_details = {}

        # Custom Resource Details
        self._cr_details = {}

        self._apps_v1_api = self._kube.apps_v1
        self._core_v1_api = self._kube.core_v1
        self._custom_api = self._kube.custom_api

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

        self._download_location = os.path.join(os.getcwd(), "FNCMUpgrade")
        self._cr_template_save_location = os.path.join(os.getcwd(), "FNCMUpgrade", "CustomResources")
        self._current_cr_template_save_location = ""
        self._updated_cr_template_save_location = ""
        self._networkwork_policy_save_location = os.path.join(os.getcwd(), "FNCMUpgrade", "NetworkPolicies")
        self._networkwork_policy_ingress_save_location= os.path.join(self._networkwork_policy_save_location, "Ingress")
        self._networkwork_policy_egress_save_location = os.path.join(self._networkwork_policy_save_location, "Egress")

        if "catalogType" in self._operator_details:
            self._catalog_type = self._operator_details["catalogType"]

            if self._operator_details["catalogType"] != "Private":
                self._catalog_namespace = "openshift-marketplace"
            else:
                self._catalog_namespace = self._namespace
        else:
            self._catalog_type = "Private"
            self._catalog_namespace = self._namespace

        if self._setup.platform.lower() == "ocp" or self._setup.platform.lower() == "roks":
            self._deployment_type = "olm"
            self._task_numbers = {
                "UpgradeSetup": 3,
                "Upgrade": 4,
            }
            if "type" in self._operator_details:
                if self._operator_details["type"] == "YAML":
                    self._remove_yaml = True
                    self._task_numbers["CleanYaml"] = 3
                else:
                    self._remove_yaml = False
            else:
                self._remove_yaml = False

        else:
            self._deployment_type = "other"
            self._remove_yaml = False
            self._task_numbers = {
                "UpgradeSetup": 4,
                "Upgrade": 3,
            }

        self._updates_list = []

    @property
    def download_location(self):
        return self._download_location

    @property
    def cr_template_save_location(self):
        return self._cr_template_save_location

    @property
    def current_cr_template_save_location(self):
        return self._current_cr_template_save_location

    @property
    def updated_cr_template_save_location(self):
        return self._updated_cr_template_save_location

    @property
    def updates_list(self):
        return self._updates_list

    @property
    def deployment_details(self):
        return self._deployment_details

    @deployment_details.setter
    def deployment_details(self, value):
        self._deployment_details = value

    @property
    def version_details(self):
        return self._version_details

    @version_details.setter
    def version_details(self, value):
        self._version_details = value

    @property
    def remove_yaml(self):
        return self._remove_yaml

    @property
    def task_numbers(self):
        return self._task_numbers

    @property
    def deployment_type(self):
        return self._deployment_type

    @property
    def operator_details(self):
        return self._operator_details

    @property
    def catalog_namespace(self):
        return self._catalog_namespace

    @catalog_namespace.setter
    def catalog_namespace(self, value):
        self._catalog_namespace = value

    @property
    def catalog_type(self):
        return self._catalog_type

    @catalog_type.setter
    def catalog_type(self, value):
        self._catalog_type = value

    # Function to remove yaml style deployment
    def remove_yaml_deployment(self, progress, task):
        # Number of tasks = 4
        SLEEP_TIMER = 5
        if "role" not in self._operator_details:
            role = None
        else:
            if self._operator_details["role"]:
                role = self._operator_details["role"]
            else:
                role = None

        if "rolebinding" not in self._operator_details:
            rolebinding = None
        else:
            if self._operator_details["rolebinding"]:
                rolebinding = self._operator_details["rolebinding"]
            else:
                rolebinding = None

        if "service_account" not in self._operator_details:
            service_account = None
        else:
            if self._operator_details["service_account"]:
                service_account = self._operator_details["service_account"]
            else:
                service_account = None

        progress.log(Panel.fit("Starting FileNet Operator YAML Deployment Cleanup", style="cyan"))
        progress.log()
        try:
            progress.log()
            progress.log("Deleting Operator Deployment...")
            self._kube.delete_operator_deployment(namespace=self._namespace)
            sleep(SLEEP_TIMER)
            progress.advance(task)

            progress.log()
            progress.log("Deleting Operator RoleBinding...")
            if rolebinding:
                self._kube.delete_role_binding(namespace=self._namespace, name=rolebinding)
            else:
                progress.log()
                progress.log(Panel.fit("Rolebinding not found", style="bold red"))
            sleep(SLEEP_TIMER)
            progress.advance(task)

            progress.log()
            progress.log("Deleting Operator Role...")
            if role:
                self._kube.delete_role(namespace=self._namespace, name=role)
            else:
                progress.log()
                progress.log(Panel.fit("Role not found", style="bold red"))
            sleep(SLEEP_TIMER)
            progress.advance(task)

            progress.log()
            progress.log("Deleting Operator Service Account...")
            if service_account:
                self._kube.delete_service_account(namespace=self._namespace, name=service_account)
            else:
                progress.log()
                progress.log(Panel.fit("Service Account not found", style="bold red"))
            sleep(SLEEP_TIMER)
            progress.advance(task)

            progress.log(Panel.fit("FileNet Operator YAML Deployment Cleanup Completed", style="bold green"))
            progress.log()

        except Exception as e:
            progress.log(Text(f"Error occurred while removing the resources: {e}", style="bold red"))

    def apply_cncf(self, progress, task):
        try:
            # Number of Tasks = 4
            progress.log(Panel.fit("Starting CRD and Permission Upgrade", style="cyan"))
            progress.log()

            # Apply the CRD
            progress.log(f"Applying/Patching Custom Resource Definition")
            progress.log()
            self._kube.apply_cluster_resource_files(
                resource_file=self.required_file_paths["fncm_v1_fncm_crd.yaml"],
                resource_type="Custom Resource Definition")
            progress.update(task, advance=1)

            # Apply the Cluster Role
            progress.log(f"Applying/Patching Cluster Role")
            progress.log()
            self._kube.apply_cluster_resource_files(
                resource_file=self.required_file_paths["service_account.yaml"],
                resource_type="Service Account", namespace=self._setup.namespace)
            progress.update(task, advance=1)

            # Apply the Role
            progress.log(f"Applying/Patching Role")
            progress.log()
            self._kube.apply_cluster_resource_files(
                resource_file=self.required_file_paths["role.yaml"], resource_type="Role",
                namespace=self._setup.namespace)
            progress.update(task, advance=1)

            # Apply the Role Binding
            progress.log(f"Applying/Patching Role Binding")
            progress.log()
            self._kube.apply_role_binding(
                namespace=self._setup.namespace, resource_file=self.required_file_paths["role_binding.yaml"])
            progress.update(task, advance=1)

            progress.log(Panel.fit("CRD and Permission Upgrade Completed", style="bold green"))
            progress.log()
        except Exception as e:
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))

    def apply_olm(self, progress, task):
        # Number of tasks = 3
        try:
            progress.log(Panel.fit("Starting OLM Upgrade", style="cyan"))
            progress.log()
            if self._catalog_type == "Private":
                self._catalog_namespace = self._namespace
                progress.log(f"Using private catalog namespace: {self._catalog_namespace}")
                progress.log()

            else:
                progress.log(f"Using global catalog namespace (GCN): {self._catalog_namespace}")
                progress.log()
            replace_namespace_in_file(project_name=self._catalog_namespace,
                                      input_file=self.required_file_paths["catalogsource.yaml"],
                                      output_file=self.tmp_file_paths["catalogsource.yaml"],
                                      resource_type="catalog source")

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
                                "ibm-fncm-operator-catalog" in pod.metadata.name and pod.status.phase == "Running"]
                if running_pods:
                    progress.log(
                        Text(f"IBM FileNet Content Manager Operator Catalog Pod is running.", style="bold green"))
                    progress.log()
                    progress.update(task, advance=1)
                    break
                else:
                    retries = retries + 1
                    progress.log(f"FileNet Content Management Catalog deployment in progress ({retries + 1}/40) ")
                    progress.log()
                    sleep(5)

            if retries == 40:
                progress.log(Text("Timeout Waiting for IBM FileNet Content Manager Operator Catalog pod to start",
                                  style="bold red"))
                progress.log()

                progress.log("Please check the status of Pod by issuing the below command:")
                progress.log()
                progress.log(Syntax(
                    f"kubectl describe pod $(kubectl get pod -n {self._catalog_namespace} | grep ibm-fncm-operator-catalog | awk '{{print $1}}') -n ${self._catalog_namespace}",
                    "bash"))

            # Collect Operator Group
            operator_group = self._kube.get_operator_group(self._namespace)
            if operator_group:
                progress.log(f"Operator Group already exists")
                progress.log()
            else:
                progress.log("Applying/Patching Operator Group")
                progress.log()
                replace_namespace_in_file(project_name=self._namespace,
                                          input_file=self.required_file_paths["operator_group.yaml"],
                                          output_file=self.tmp_file_paths["operator_group.yaml"],
                                          resource_type="operator group")

                self._kube.apply_cluster_resource_files(
                    resource_file=self.tmp_file_paths["operator_group.yaml"],
                    namespace=self._namespace,
                    resource_type="Operator Group")
            progress.update(task, advance=1)

            progress.log(Panel.fit("OLM Installation Completed", style="bold green"))
            progress.log()
        except Exception as e:
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))

    def wait_for_operator(self, progress, task):
        try:
            # Initialize attempts counter
            # Number of tasks = 1
            attempts = 0
            retries = 0
            progress.log(f"Checking rollout status of FileNet Content Management Operator deployment")
            progress.log()
            while retries < 40:
                pods = self._core_v1_api.list_namespaced_pod(self._namespace)
                running_pods = [pod.metadata.name for pod in pods.items if
                                "ibm-fncm-operator" in pod.metadata.name and "catalog" not in pod.metadata.name and pod.status.phase == "Running" and
                                pod.status.container_statuses[0].ready]
                if running_pods:
                    progress.log(
                        Text(f"IBM FileNet Content Manager Operator Pod is running.", style="bold green"))
                    progress.log()
                    progress.update(task, advance=1)
                    break
                else:
                    retries = retries + 1
                    progress.log(f"FileNet Content Management Operator upgrade in progress ({retries + 1}/40) ")
                    progress.log()
                    sleep(15)

            if retries == 40:
                progress.log(Text("Timeout Waiting for IBM FileNet Content Manager Operator pod to start",
                                  style="bold red"))
                progress.log()

                progress.log("Please check the status of Pod by issuing the below command:")
                progress.log()
                progress.log(Syntax(
                    f"kubectl describe pod $(kubectl get pods -n {self._namespace} -l 'name=ibm-fncm-operator' | awk '{{print $1}}') -n ${self._namespace}",
                    "bash"))
                exit()

            progress.log(Panel.fit("IBM FileNet Content Manager Operator Upgrade Completed", style="bold green"))
            progress.update(task, advance=1)
        except Exception as e:
            progress.log(Text(f"Error occurred while applying the resources: {e}", style="bold red"))
            progress.log()

    def upgrade_operator_olm(self, progress, task):
        # Number of tasks = 2

        progress.log(Panel.fit("Starting IBM FileNet Content Manager Operator Upgrade", style="cyan"))
        progress.log()

        progress.log(f"Scaling down older operator pod before upgrading")
        progress.log()

        # Scale down older operator pod before upgrading
        # If moving from Yaml deployment, the deployment will not exist
        if not self.remove_yaml:
            operator_deployment = self._operator_details["deployment"]
            self._kube.scale_operator_deployment(namespace=self._namespace, deployment_name=operator_deployment,
                                                 scale="down")

        progress.log(f"Applying/Patching Subscription")
        progress.log()

        if self._catalog_type == "Private":
            replace_namespace_in_file(project_name=self._namespace,
                                      input_file=self.required_file_paths["subscription.yaml"],
                                      output_file=self.tmp_file_paths["subscription.yaml"],
                                      resource_type="subscription",
                                      private=True)
            progress.log(f"Using private catalog namespace: {self._namespace}")
            progress.log()
            progress.update(task, advance=1)
        else:
            replace_namespace_in_file(project_name=self._namespace,
                                      input_file=self.required_file_paths["subscription.yaml"],
                                      output_file=self.tmp_file_paths["subscription.yaml"],
                                      resource_type="subscription")
            progress.log(f"Using global catalog namespace (GCN): {self._catalog_namespace}")
            progress.update(task, advance=1)

        self._kube.apply_cluster_resource_files(
            resource_file=self.tmp_file_paths["subscription.yaml"],
            namespace=self._namespace,
            resource_type="Subscription")

        progress.update(task, advance=1)

        self.wait_for_operator(progress, task)

    # Function to install operator on CNCF
    def upgrade_operator_cncf(self, progress, task):
        # Number of tasks = 2
        progress.log(Panel.fit("Starting IBM FileNet Content Manager Operator Upgrade", style="cyan"))
        progress.log()

        shutil.copy(self.required_file_paths["operator.yaml"], self.tmp_file_paths["operator.yaml"])
        with open(self.tmp_file_paths["operator.yaml"], 'r') as file:
            content = file.read()

        progress.log("Setting license acceptance to 'accept' in the operator file")
        progress.log()

        # Update the 'fncm_license' value to 'accept'
        content = re.sub(r'fncm_license:\n  value:.*', 'fncm_license:\n  value: accept', content)

        # Write the modified content back to the temporary operator file
        with open(self.tmp_file_paths["operator.yaml"], 'w') as file:
            file.write(content)

        with open(self.tmp_file_paths["operator.yaml"], 'r') as file:
            content = file.read()
        registry_in_file = "icr.io"

        if self._setup.private_registry_valid:
            progress.log("FileNet Content Management Operator is being upgraded using a private registry")
            progress.log()
            pattern = re.compile(re.escape(registry_in_file) + r'\b')
            replacement = self._setup.private_registry_server
            content = pattern.sub(replacement, content)

            # Write the modified content back to the temporary operator file
            with open(self.tmp_file_paths["operator.yaml"], 'w') as file:
                file.write(content)
        else:
            progress.log("FileNet Content Management Operator is being upgraded using the IBM Entitlement Registry")
            progress.log()
            if self._setup.runtime_mode == "dev":
                progress.log("Using dev registry for FileNet Content Management Operator upgrade")
                progress.log()
                pattern = re.compile(re.escape(registry_in_file + '/cpopen') + r'\b')
                replacement = "cp.stg.icr.io" + '/cp'
                content = pattern.sub(replacement, content)

                # Write the modified content back to the temporary operator file
                with open(self.tmp_file_paths["operator.yaml"], 'w') as file:
                    file.write(content)

        progress.log(f"Applying/Patching FileNet Operator Deployment")
        progress.log()

        self._kube.apply_cluster_resource_files(
            resource_file=self.tmp_file_paths["operator.yaml"], resource_type="Deployment",
            namespace=self._namespace)

        progress.update(task, advance=1)

        self.wait_for_operator(progress, task)

    def convert_keys_to_camel_case(self, obj):
        KEYS_TO_REMOVE = {
            "status",
            "managedFields",
            "creationTimestamp",
            "ownerReferences",
        }

        def snake_to_camel(snake_str):
            components = snake_str.lstrip('_').split('_') 
            return components[0] + ''.join(x.title() for x in components[1:])

        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                key_no_underscore = k.lstrip('_')
                camel_key = snake_to_camel(key_no_underscore)

                if camel_key in KEYS_TO_REMOVE or v is None:
                    continue

                new_dict[camel_key] = self.convert_keys_to_camel_case(v)
            return new_dict
        elif isinstance(obj, list):
            return [self.convert_keys_to_camel_case(i) for i in obj if i is not None]
        else:
            return obj

    def clean_networkpolicies(self, network_policy_path):
        np_files = list(Path(network_policy_path).glob("*.yaml")) + list(Path(network_policy_path).glob("*.yml"))
        for file in np_files:
            with open(file, 'r') as f:
                data = yaml.safe_load(f)
            np_case_converted = self.convert_keys_to_camel_case(data)
                            # Remove unused sections from the CR
            remove_fields = ["creationTimestamp",
                                "generation",
                                "resourceVersion",
                                "uid",
                                "managedFields"]
            for field in remove_fields:
                if field in np_case_converted["metadata"].keys():
                    del np_case_converted["metadata"][field]
            if "annotations" in np_case_converted["metadata"].keys():
                if 'kubectl.kubernetes.io/last-applied-configuration' in np_case_converted["metadata"]["annotations"]:
                    del np_case_converted["metadata"]["annotations"]['kubectl.kubernetes.io/last-applied-configuration']
                if not np_case_converted["metadata"]["annotations"]:
                    del np_case_converted["metadata"]["annotations"]
            with open(file, 'w') as f:
                yaml.safe_dump(np_case_converted, f, default_flow_style=False, sort_keys=False)

    def collect_network_policy_info(self):
        resource_type_dict = self._kube.list_namespace_resources(console=self._console,
                                                               namespace=self._namespace,
                                                               platform=self._setup.platform,
                                                               filter=self._cr_details["name"])
        
        if len(resource_type_dict["network_policy"]) == 0:
            self._logger.info("There exists no network policy managed by the operator")
            return False
        
        # Create folder for network policies if it does not exist
        self._networkwork_policy_save_location = os.path.join(os.getcwd(), "FNCMUpgrade", "NetworkPolicies")
        if not os.path.exists(self._networkwork_policy_save_location):
            os.makedirs(self._networkwork_policy_save_location)

        if not os.path.exists(self._networkwork_policy_ingress_save_location):
            os.makedirs(self._networkwork_policy_ingress_save_location)

        if not os.path.exists(self._networkwork_policy_egress_save_location):
            os.makedirs(self._networkwork_policy_egress_save_location)

        try:
            self._logger.info("Starting Network Policy Information Collection")
            for network_policy in resource_type_dict["network_policy"]:
                self._logger.info(f"Collecting network policy {network_policy}")
                if "ingress" in network_policy:
                    path = os.path.join(
                    f"{self._networkwork_policy_ingress_save_location}",
                    f"{network_policy}.yaml")
                else:
                    path = os.path.join(
                        f"{self._networkwork_policy_egress_save_location}",
                        f"{network_policy}.yaml")
                if os.path.isfile(path):
                    self._logger.info("Network Policy file already exists.")
                else:
                    network_policy_response = self._kube.describe_network_policy(network_policy, self._namespace)
                    write_yaml_to_file(network_policy_response, path)
            self.clean_networkpolicies(self._networkwork_policy_ingress_save_location)
            self.clean_networkpolicies(self._networkwork_policy_egress_save_location)

            self._logger.info("Network Policies have been downloaded")
            self._updates_list.append("Network Policies downloaded")
            return True
                
        except Exception as e:
            self._logger.info("Unable to retrieve network policies, caught %s Skipping...", e)

    def update_network_policy(self, progress):
        resource_type_dict = self._kube.resource_type_dict
        try:
            progress.log()
            progress.log(Panel.fit("Starting Network Policy Patch", style="cyan"))
            progress.log()
            for network_policy in resource_type_dict["network_policy"]:
                self._kube.remove_network_policy_owner_reference(progress= progress,network_policy_name= network_policy,namespace= self._namespace)
            if resource_type_dict["network_policy"] :
                progress.log(Panel.fit("Network Policy Information Collection Completed", style="bold green"))
                progress.log(Panel.fit("Owner references for existing Network policy has been removed", style="bold green"))
                progress.log()
            else:
                progress.log(Panel.fit("There exists no network policy managed by the FNCM Standalone Operator", style="bold green"))
                progress.log()
        except Exception as e:
            self._logger.info("Unable to retrieve network policies, caught %s Skipping...", e)

    def remove_custom_ssl_secrets(self, progress):
        resource_type_dict = self._kube.resource_type_dict
        try:

            cr_name = self._cr_details["name"]

            secrets = [
                f"{cr_name}-fncm-custom-ssl-secret",
                f"{cr_name}-ban-custom-ssl-secret"
            ]

            if 'secret' in resource_type_dict:
                progress.log()
                progress.log(Panel.fit("Starting Custom SSL Certificates Patch", style="cyan"))
                progress.log()
                for secret in secrets:
                    if secret in resource_type_dict["secret"]:
                        self._kube.delete_secret(namespace=self._namespace, name=secret )
                        progress.log(f"Secret '{secret}' patched successfully.")
                        progress.log()
                
                progress.log(Panel.fit("Custom SSL Certificates Patch Completed", style="bold green"))
                progress.log()
        
        except Exception as e:
            self._logger.info(f"Unable to retrieve secrets: {e}")
        



    # Function to update certain CR parameters , used in the upgrade script
    def update_cr_values(self):
        """
        Updates the current Custom Resource (CR) values based on the Full Custom Resource Template.

        This function reads the Full Custom Resource Template and updates the current CR with the latest values.
        It handles various aspects such as release, appVersion, image tags, resource requests and limits,
        and initialization/verification fields.

        Parameters:
        self (object): An instance of the class containing necessary attributes and methods.

        Returns:
        tuple: A tuple containing the updated CR details and a list of updates made.
        """
        try:
            cr_details = self._current_cr.copy()
            fc_template_cr = self.required_file_paths["ibm_fncm_cr_production_FC_content.yaml"]
            update_list = []

            try:
                # Get the Full Custom Resource Template for updated release
                with open(fc_template_cr, 'r') as yaml_file:
                    fc_template_cr_details = yaml.safe_load(yaml_file)
            except Exception as e:
                self._logger.exception('Unable to load Full Custom Resource Template', e)

            # TODO: Check for "int" type resource values and update to string
            # Update release
            if is_key_present(dictionary=cr_details, key="release"):
                release = fc_template_cr_details["metadata"]["labels"][
                    "release"]
                cr_details["metadata"]["labels"]["release"] = release
                update_list.append(f"Updated release label to {release}")

            # Update AppVersion
            if is_key_present(dictionary=cr_details, key="appVersion"):
                if cr_details["spec"]["appVersion"] == "21.0.3":
                    cr_details["spec"]["license"] = {}
                    cr_details["spec"]["license"]["accept"] = True
                    update_list.append("Updated license field to new format")
                app_version = fc_template_cr_details["spec"]["appVersion"]
                cr_details["spec"]["appVersion"] = app_version
                update_list.append(f"Updated appVersion to {app_version}")

            # Update image tags if present
            if is_key_present(cr_details, "tag") and is_key_present(cr_details, "repository"):
                update_list.append("Updated component image tags")
                for key in ["repository", "tag"]:
                    # getting all nested paths in the yaml where tag and repository is present
                    key_results = find_keys_and_structures(dictionary=cr_details, key=key)
                    if key_results:
                        for nested_structure, path, key in key_results:
                            try:
                                update_value_by_path(dictionary1=cr_details, path=path,
                                                     dictionary2=fc_template_cr_details, logger=self._logger)
                            except KeyError as e:
                                self._logger.info(e)
            
            # Check if component boolean list exists 
            if not is_key_present(cr_details, key="content_optional_components"):
                self._logger.info("No content_optional_components found in custom resource file")
                # Copy entire component boolean structure 
                component_boolean = fc_template_cr_details['spec']["content_optional_components"].copy()
                self._logger.info("Add new structure and updating all components to false")
                # Update boolean list to false
                component_list = ['cpe', 'graphql', "cmis", "css", "es", "tm", "ban", "iccsap", "ier"]
                for component in component_list:
                    component_boolean[component] = False

                cr_details["spec"]["content_optional_components"] = component_boolean

            # Convert pattern into boolean list
            if is_key_present(cr_details, key="sc_deployment_patterns"):
                self._logger.info("Converting deployment pattern")
                if cr_details["spec"]["shared_configuration"]["sc_deployment_patterns"].lower() == "content":
                    component_list = ['cpe', 'graphql', "ban"]
                    for component in component_list:
                        cr_details["spec"]["content_optional_components"][component] = True
                    cr_details["spec"]["shared_configuration"].pop("sc_deployment_patterns")
                update_list.append("Updated content pattern to new format")
            
            # Convert optional component list to boolean list 
            if is_key_present(cr_details, key="sc_optional_components"):
                self._logger.info("Converting optional component list")
                component_string = cr_details["spec"]["shared_configuration"]["sc_optional_components"]
                # Split string into list 
                component_list = component_string.split(",")
                for component in component_list:
                    if component in cr_details["spec"]["content_optional_components"]:
                        cr_details["spec"]["content_optional_components"][component] = True
                cr_details["spec"]["shared_configuration"].pop("sc_optional_components")
                update_list.append("Updated optional components to new format")
                

            # Update resource requests and limits
            # TODO: Make sure limits are higher than currently listed
            if is_key_present(cr_details, key="requests") and is_key_present(cr_details, key="limits"):
                update_list.append("Updated component resource requests and limits")
                resources_results = find_keys_and_structures(dictionary=cr_details, key="requests")
                for nested_structure, path, key in resources_results:
                    try:
                        update_value_by_path(dictionary1=cr_details, path=path,
                                             dictionary2=fc_template_cr_details,
                                             requests=True, logger=self._logger)
                    except KeyError as e:
                        self._logger.info(e)
                    except Exception as e:
                        self._logger.info(e)

                limits_results = find_keys_and_structures(dictionary=cr_details, key="limits")
                for nested_structure, path, key in limits_results:
                    try:
                        update_value_by_path(dictionary1=cr_details, path=path,
                                             dictionary2=fc_template_cr_details,
                                             limits=True, logger=self._logger)
                    except KeyError as e:
                        self._logger.info(e)
            try:
                if self._version_details["version"] == "5.7.0" and is_key_present(cr_details, key="sc_restricted_internet_access"):
                    if cr_details["spec"]["shared_configuration"]["sc_egress_configuration"]["sc_restricted_internet_access"]:
                        update_list.append("Enabled sc_generate_sample_network_policies")
                        cr_details["spec"]["shared_configuration"]["sc_generate_sample_network_policies"] = True
            except Exception as e:
                self._logger.exception(
                    f"Exception while enabling sc_generate_sample_network_policies", e)

            # Disable init and verify
            # Takes into account the OLM and script format
            try:
                if is_key_present(cr_details, key="olm_sc_content_initialization"):
                    update_list.append("Disabled Content Initialization")
                    cr_details["spec"]["shared_configuration"]["olm_sc_content_initialization"] = False
                elif is_key_present(cr_details, key="sc_content_initialization"):
                    cr_details["spec"]["shared_configuration"]["sc_content_initialization"] = False
                    update_list.append("Disabled Content Initialization")

                if is_key_present(cr_details, key="olm_sc_content_verification"):
                    cr_details["spec"]["shared_configuration"]["olm_sc_content_verification"] = False
                    update_list.append("Disabled Content Verification")
                elif is_key_present(cr_details, key="sc_content_verification"):
                    cr_details["spec"]["shared_configuration"]["sc_content_verification"] = False
                    update_list.append("Disabled Content Verification")

                if not is_key_present(cr_details, key="scim_configuration"):
                    if is_key_present(cr_details, key="initialize_configuration"):
                        cr_details["spec"].pop("initialize_configuration")
                        update_list.append("Removed initialize_configuration section")
                if is_key_present(cr_details, key="verify_configuration"):
                    cr_details["spec"].pop("verify_configuration")
                    update_list.append("Removed verify_configuration section")

            except Exception as e:
                self._logger.exception(
                    "Exception while updating the initialization and verification fields and sections", e)

            # Removing the existing resource version and uid
            if is_key_present(cr_details, key="status"):
                update_list.append("Removed status field")
                cr_details.pop("status")

            return cr_details, update_list

        except Exception as e:
            self._logger.exception("Exception while updating Custom Resource fields and sections", e)
            return {}

    # Function to prepare the upgrade CR and save it in the .tmp folder
    def prepare_upgrade_cr(self):
        """
        This function prepares for an upgrade of the Custom Resource (CR) by retrieving the current CR,
        backing up the existing CR folder, and generating an updated CR file.

        Parameters:
        self (object): An instance of the class containing this method.

        Returns:
        None
        """

        self._current_cr = self._kube.get_deployment_cr(
            namespace=self._namespace, logger=self._logger)
        if not self._current_cr:
            self._logger.info(
                "Error will retrieving Custom Resource File. This Means either the namespace entered was incorrect or a custom resource file does not exist\n"
                "Run the script without the deployment flag if no Custom Resource file exists\n")
            print(Panel.fit("Unable to retrieve FNCM Custom Resource file.\n"
                            "Please check your namespace or CR type \"FNCMCluster\"", style="bold red"))
            print()
            exit(1)

        cr_details = self._kube.cr_details
        self._cr_details = cr_details

        # Backup existing Custom Resource folder
        if os.path.exists(self._download_location):
            self._logger.info("Backup existing Upgrade folder")
            if not os.path.exists(os.path.join(os.getcwd(), "backups")):
                os.mkdir(os.path.join(os.getcwd(), "backups"))
            now = datetime.now()
            dt_string = now.strftime("%Y-%m-%d_%H-%M")
            zip_folder(os.path.join(os.getcwd(), "backups", "FNCMUpgrade" + dt_string),
                       os.path.join(os.getcwd(), "FNCMUpgrade"))
            shutil.rmtree(self._download_location)
            os.makedirs(self._download_location)
            os.makedirs(self._cr_template_save_location)
        else:
            self._logger.info("Creating FNCMUpgrade folder")
            os.makedirs(self._download_location)
            os.makedirs(self._cr_template_save_location)

        # Get Version info
        current_version = cr_details["version"]
        current_version = current_version.replace(".", "")
        upgrade_version = self._version_details["version"]
        upgrade_version = upgrade_version.replace(".", "")

        # Create the file paths for the current and updated CR
        self._current_cr_template_save_location = os.path.join(self._cr_template_save_location,
                                                               f"fncm_deployed_cr.yaml")
        self._updated_cr_template_save_location = os.path.join(self._cr_template_save_location,
                                                               f"fncm_{upgrade_version}_cr.yaml")

        # Writing the current cr to a file
        write_yaml_to_file(self._current_cr, self._current_cr_template_save_location)

        # Generate the updated CR
        updated_cr, update_list = self.update_cr_values()

        self._updates_list = update_list

        # writing the data to a file
        write_yaml_to_file(updated_cr, self._updated_cr_template_save_location)

    # logic to scale down and wait for pods replica count to be zero
    # additional logic is there to scale up the pods if required which can be done using scale="up"
    def scale_pods(self, scale="down", progress=None):
        try:

            upgrade_version = self._version_details["version"]

            progress.log()
            progress.log(Panel.fit("Scaling down IBM FileNet Content Manager Deployments", style="green"))

            cr_name = self._cr_details["name"]
            deployments = self._kube.get_deployments_by_owner_reference(
                namespace=self._namespace,
                owner_reference_name=cr_name)

            progress.log()
            progress.log(f"Scaling down current FNCM Standalone Operator pod before upgrading")

            # Scale down older operator pod before upgrading
            operator_deployment = self._operator_details["deployment"]
            self._kube.scale_operator_deployment(namespace=self._namespace,
                                                 deployment_name=operator_deployment,
                                                 scale="down")

            # Removing scale down for 5.6.0 as it is not required, with new rolling update strategy
            # if upgrade_version in ["5.6.0"]:
            #
            #     progress.log()
            #     progress.log("Collecting IBM FileNet Content Manager Deployment pods to scale down")
            #     if deployments:
            #         pods_to_scale = []
            #         for deployment in deployments:
            #             deploymemt_name = deployment.metadata.name
            #             progress.log()
            #             progress.log(Panel.fit(f"Scaling down pods for deployment: {deploymemt_name}"), style="cyan")
            #             pods = self._kube.get_pods_for_deployment(
            #                 namespace=self._namespace,
            #                 deployment_name=deploymemt_name)
            #             if pods:
            #                 for pod in pods:
            #                     pod_name = pod.metadata.name
            #                     progress.log()
            #                     progress.log(f"Scaling down pod: {pod_name}")
            #                     pods_to_scale.append(pod_name)
            #             else:
            #                 continue
            #
            #     else:
            #         pods_to_scale = []
            #         progress.log()
            #         progress.log(
            #             Text("No deployment related pods are running which means no pods need to be scaled down",
            #                 style="bold green"))
            #     if pods_to_scale:
            #         self._kube.scale_pods_in_namespace(
            #             namespace=self._namespace, deployments=deployments, scale=scale)
            #         retries = 0
            #         progress.log()
            #         progress.log(f"Waiting for pods to gracefully shutdown - {retries + 1}/40")
            #         while retries < 40:
            #             pods_present = []
            #             pods = self._core_v1_api.list_namespaced_pod(self._namespace)
            #             for pod in pods.items:
            #                 pods_present.append(pod.metadata.name)
            #             all_pods_deleted = any(item in pods_present for item in pods_to_scale)
            #             if all_pods_deleted:
            #                 sleep(30)
            #                 retries = retries + 1
            #                 progress.log()
            #                 progress.log(f"Waiting for pods to gracefully shutdown - {retries + 1}/40")
            #             else:
            #                 progress.log()
            #                 progress.log(Text("All FNCM pods have been scaled down", style="bold green"))
            #                 break
            #         if retries == 40:
            #             progress.log()
            #             progress.log(Text("Timeout waiting for all FNCM pods to scale down", style="bold red"))
            #             progress.log("Please check the status of the Pods by issuing the below command")
            #             progress.log(Syntax(f"kubectl get pods -n {self._namespace} ", "bash"))
            #             exit(1)
            #     else:
            #         progress.log()
            #         progress.log(
            #             Text("No deployment related pods are running which means no pods need to be scaled down",
            #                 style="bold green"))
        except Exception as e:
            progress.log()
            progress.log(
                Text(f"Error in scaling down pods function - {e}", style="bold red"))

    # Ask if the CR should be updated, if user does not want to update CR we will just update the Operators
    # IF CR is to be updated then we will scale pods down , apply the latest CR and then upgrade the operator
    def apply_upgraded_cr(self, progress=None):
        progress.log()
        progress.log(Panel.fit("Applying Upgraded FNCM Custom Resource", style="cyan"))
        cr_applied = self._kube.apply_cluster_resource_files(
            resource_file=self._updated_cr_template_save_location, resource_type="Custom Resource",
            namespace=self._namespace)
        if not cr_applied:
            progress.log()
            progress.log(Text("Error occurred while applying the upgraded Custom Resource", style="bold red"))
            exit(1)
        else:
            progress.log()
            progress.log(Text("Upgraded Custom Resource applied successfully", style="bold green"))

    # Function to display the post upgrade steps
    # Jason to fill this up as part of the upgrade steps
    def post_upgrade_steps(self):
        print("Here are the post upgrade steps to follow\n")
        print("TBA")
