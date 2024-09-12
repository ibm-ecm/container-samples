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
import time

import requests
from rich.panel import Panel

requests.packages.urllib3.disable_warnings()
from ..utilities import kubernetes_utilites as k
from rich import print


# CLass that contains functions to delete the CR as well delete the Operator
class CleanDeployment:

    def __init__(self, console, deployment_prerequisites=None, logger=None, silent=False):
        self._deployment_prerequisites = deployment_prerequisites
        self._namespace = deployment_prerequisites.namespace
        self._logger = logger
        self._console = console
        self._clean_deployment = False
        self._silent = silent
        self._kube = k.KubernetesUtilities(logger)
        self._apps_v1_api = self._kube.apps_v1
        self._core_v1_api = self._kube.core_v1
        self._custom_api = self._kube.custom_api
        self._operator_details = {}
        self._cr_details = {}
        self._cr_name = "fncmdeploy"

    def collect_cr_details(self):
        self._kube.get_deployment_cr(namespace=self._namespace, logger=self._logger)
        cr_details = self._kube.cr_details
        self._cr_details = cr_details

        if not cr_details:
            return {}, {}

        self._cr_name = cr_details["name"]
        version = cr_details["version"]

        self.resource_type_dict = self._kube.list_namespace_resources(console=self._console,
                                                                      namespace=self._namespace,
                                                                      platform=self._deployment_prerequisites.platform,
                                                                      filter=self._cr_name)
        deployment_details_dict = {
            "Namespace": self._namespace,
            "Name": self._cr_name,
            "Platform": self._deployment_prerequisites.platform,
            "Version": version
        }

        return deployment_details_dict, self.resource_type_dict

    def delete_CR(self, task1, progress):
        SLEEP_TIMER = 5
        # Attempt to list the CR in the specific namespace
        progress.log("Starting FNCM Standalone Deployment Cleanup")
        progress.log()
        progress.log("Cleaning up namespace: " + self._namespace)

        self._custom_api.delete_namespaced_custom_object(group="fncm.ibm.com", version="v1",
                                                         namespace=self._namespace,
                                                         plural="fncmclusters", name=self._cr_name)

        progress.log()
        progress.log("Deleting CR...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Deleting configmaps...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Deleting generated secrets...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Deleting services...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Deleting deployments...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Deleting network policies...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Deleting routes or generated ingress...")
        time.sleep(SLEEP_TIMER)
        progress.advance(task1)

        progress.log()
        progress.log("Waiting for pods to gracefully shutdown...")

        # TODO: Check if the pods exists using labels query
        # TODO: Check logic if pods are sticking around
        # TODO: Update with CR name as owner

        try:
            deployments = self._kube.get_deployments_by_owner_reference(namespace=self._namespace,
                                                                        owner_reference_name=self._cr_name)
            if deployments:
                pods_to_delete = []
                for deployment in deployments:
                    pods = self._kube.get_pods_for_deployment(namespace=self._namespace,
                                                              deployment_name=deployment.metadata.name)
                    if pods:
                        # print("Pods for deployment:")
                        for pod in pods:
                            print(pod.metadata.name)
                            pods_to_delete.append(pod.metadata.name)
                    else:
                        print("No pods found for deployment")
            else:
                pods_to_delete = []
                print("No deployments found with matching owner reference name")

            retries = 0
            while retries < 20:
                pods_present = []
                pods = self._core_v1_api.list_namespaced_pod(self._namespace)
                for pod in pods.items:
                    pods_present.append(pod.metadata.name)
                all_pods_deleted = any(item in pods_present for item in pods_to_delete)
                if all_pods_deleted:
                    retries = retries + 1
                else:
                    break
            if retries == 20:
                print("Timeout Waiting for Clean up of  IBM FileNet Content Manager Deployment pods ")
                print("Please check the status of the Pods by issuing the below command:\n")
                print(
                    f"kubectl describe pod $(kubectl get pods -n {self._namespace} ")
                exit(1)
        except Exception as e:
            print("Error in logic for checking when resources are deleted -", e)

        progress.log()
        progress.log("All resources have been deleted successfully...")
        progress.advance(task1)

    def collect_operator_details(self):
        operator_deployment = "ibm-fncm-operator"
        operator_details = self._kube.get_operator_details(self._namespace, operator_deployment)
        if not operator_details:
            return {}
        self._operator_details = operator_details
        return operator_details

    # This function takes care of the deletion of operator after the CR and resources are deleted
    def delete_operator(self, task1, progress):
        SLEEP_TIMER = 5
        if self._deployment_prerequisites.platform.lower() in ["ocp", "roks"]:

            if "subscription" not in self._operator_details:
                subscription_name = None
            else:
                subscription_name = self._operator_details["subscription"]

            if "installedCSV" not in self._operator_details:
                installed_csv = None
            else:
                installed_csv = self._operator_details["installedCSV"]

            if "operatorGroup" not in self._operator_details:
                operator_group = None
            else:
                operator_group = self._operator_details["operatorGroup"]

            progress.log("Starting FNCM Standalone Operator OLM Uninstallation")
            progress.log()
            time.sleep(SLEEP_TIMER)

            progress.log()
            progress.log(f"Deleting Subscription...")
            if subscription_name:
                self._kube.delete_subscription(namespace=self._namespace, name=subscription_name)
            else:
                progress.log()
                progress.log(Panel.fit("Subscription not found", style="bold red"))
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log(f"Deleting CSV...")
            if installed_csv:
                self._kube.delete_clusterserviceversion(csv_name=installed_csv,
                                                    namespace=self._namespace)
            else:
                progress.log()
                progress.log(Panel.fit("CSV not found", style="bold red"))
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log("Deleting Operator Group...")
            if operator_group:
                self._kube.delete_operator_group(namespace=self._namespace, name=operator_group)
            else:
                progress.log()
                progress.log(Panel.fit("Operator Group not found", style="bold red"))
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log(Panel.fit("Uninstalling FNCM Standalone Operator completed!", style="bold green"))
            progress.log()
            progress.advance(task1)


        else:

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

            progress.log("Starting FNCM Standalone Operator Yaml Uninstallation")
            progress.log()
            time.sleep(SLEEP_TIMER)

            progress.log()
            progress.log("Deleting Operator Deployment...")
            self._kube.delete_operator_deployment(namespace=self._namespace)
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log("Deleting Operator RoleBinding...")
            if rolebinding:
                self._kube.delete_role_binding(namespace=self._namespace, name=rolebinding)
            else:
                progress.log()
                progress.log(Panel.fit("Rolebinding not found", style="bold red"))
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log("Deleting Operator Role...")
            if role:
                self._kube.delete_role(namespace=self._namespace, name=role)
            else:
                progress.log()
                progress.log(Panel.fit("Role not found", style="bold red"))
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log("Deleting Operator Service Account...")
            if service_account:
                self._kube.delete_service_account(namespace=self._namespace, name=service_account)
            else:
                progress.log()
                progress.log(Panel.fit("Service Account not found", style="bold red"))
            time.sleep(SLEEP_TIMER)
            progress.advance(task1)

            progress.log()
            progress.log(Panel.fit("Uninstalling FNCM Standalone Operator completed!", style="bold green"))
            progress.advance(task1)
