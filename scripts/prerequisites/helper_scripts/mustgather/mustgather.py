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

import os
from pathlib import Path

from rich import print
from rich.panel import Panel
from rich.text import Text

from ..utilities.prerequisites_utilites import write_yaml_to_file, write_log_to_file


# Create a MustGather Class

class MustGather:

    def __init__(self, console, namespace, logger=None, mustgather_folder="", deployment_details=dict, operator_details={}, kube=None):
        self._logger = logger
        self._console = console
        self._deployment_details = deployment_details
        self._operator_details = operator_details
        self._kube = kube
        self._mustgather_folder = mustgather_folder
        self._namespace = namespace
        self._version = "5.7.0"
        self._cr_name = ""
        if "name" in self._deployment_details.keys():
            self._cr_name = deployment_details["name"]
        if "version" in deployment_details.keys():
            self._version = deployment_details["version"]
        elif "release" in operator_details.keys():
            self._version = operator_details["release"]

    def to_dict(self):
        return {
            "deployment_details": self._deployment_details,
            "operator_details": self._operator_details,
            "mustgather_folder": self._mustgather_folder,
            "namespace": self._namespace,
            "cr_name": self._cr_name
        }

    def collect_cluster_info(self, progress):
        # Number of tasks = 4

        # Create folder for secrets if it does not exist
        cluster_folder_path = os.path.join(self._mustgather_folder, "cluster")
        if not os.path.exists(cluster_folder_path):
            os.makedirs(cluster_folder_path)
        try:

            progress.log(Panel.fit("Starting Cluster Information Collection", style="cyan"))
            progress.log()
            progress.log(f"Collecting cluster version information")
            progress.log()
            path = os.path.join(
                f"{cluster_folder_path}",
                "cluster_version.yaml",
            )
            if os.path.isfile(path):
                self._logger.info("Log already collected in the previous step. Skipping...")
            else:
                version_response = self._kube.get_version()
                write_yaml_to_file(version_response, path)
        except Exception as e:
            self._logger.info("Unable to retrieve version information, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve version information", style="bold red"))
            progress.log()

        try:
            progress.log("Collecting cluster events")
            progress.log()
            path = os.path.join(
                f"{cluster_folder_path}",
                "events.yaml",
            )
            if os.path.isfile(path):
                self._logger.info("Log already collected in the previous step. Skipping...")
            else:
                version_response = self._kube.get_events(self._namespace)
                write_yaml_to_file(version_response, path)


        except Exception as e:
            self._logger.info("Unable to retrieve events, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve events", style="bold red"))
            progress.log()

        try:
            progress.log("Collecting cluster node information")
            progress.log()
            path = os.path.join(
                f"{cluster_folder_path}",
                "nodes.yaml",
            )
            if os.path.isfile(path):
                self._logger.info("Log already collected in the previous step. Skipping...")
            else:
                nodes = self._kube.get_nodes()
                write_yaml_to_file(nodes, path)

        except Exception as e:
            self._logger.info("Unable to retrieve nodes, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve nodes", style="bold red"))
            progress.log()

        try:
            progress.log("Collecting node resource allocations and usage")
            progress.log()
            path = os.path.join(
                f"{cluster_folder_path}",
                "nodeusage.yaml",
            )
            if os.path.isfile(path):
                self._logger.info("Log already collected in the previous step. Skipping...")
            else:
                node = self._kube.get_node_top()
                write_yaml_to_file(node, path)

        except Exception as e:
            self._logger.info("Unable to retrieve node usage information, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve node usage information, {e}", style="bold red"))

        progress.log(Panel.fit("Cluster Information Collection Completed", style="bold green"))

    # Function to collect secrets information
    def collect_secret_info(self, progress, secrets=[]):

        # Create folder for secrets if it does not exist
        secrets_folder_path = os.path.join(self._mustgather_folder, "secrets")
        if not os.path.exists(secrets_folder_path):
            os.makedirs(secrets_folder_path)

        try:
            progress.log(Panel.fit("Starting Secrets Information Collection", style="cyan"))
            progress.log()

            for secret in secrets:
                progress.log(f"Collecting secret {secret}")
                progress.log()
                path = os.path.join(
                    f"{secrets_folder_path}",
                    f"{secret}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    secret_response = self._kube.describe_secret(secret, self._namespace, progress)
                    write_yaml_to_file(secret_response, path)

            progress.log()
            progress.log(Panel.fit("Secrets Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve secrets, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve secrets", style="bold red"))
            progress.log()

    # Function to collect configmap information
    def collect_configmap_info(self, progress, configmaps=[]):

        # Create folder for configmaps if it does not exist
        configmap_folder_path = os.path.join(self._mustgather_folder, "configmaps")
        if not os.path.exists(configmap_folder_path):
            os.makedirs(configmap_folder_path)

        try:
            progress.log(Panel.fit("Starting ConfigMap Information Collection", style="cyan"))
            progress.log()

            for configmap in configmaps:
                progress.log(f"Collecting configmap {configmap}")
                progress.log()
                path = os.path.join(
                    f"{configmap_folder_path}",
                    f"{configmap}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    configmap_response = self._kube.describe_configmap(configmap, self._namespace)
                    write_yaml_to_file(configmap_response, path)

            progress.log()
            progress.log(Panel.fit("ConfigMap Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve configmaps, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve configmaps", style="bold red"))
            progress.log()

    # Function to collection deployment information
    def collect_deployment_info(self, progress, deployments=list):

        # Create folder for deployments if it does not exist
        deployment_folder_path = os.path.join(self._mustgather_folder, "deployments")
        if not os.path.exists(deployment_folder_path):
            os.makedirs(deployment_folder_path)

        try:
            progress.log(Panel.fit("Starting Deployment Information Collection", style="cyan"))
            progress.log()

            for deployment in deployments:
                progress.log(f"Collecting deployment {deployment}")
                progress.log()
                path = os.path.join(
                    f"{deployment_folder_path}",
                    f"{deployment}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    deployment_response = self._kube.describe_deployment(deployment, self._namespace)
                    write_yaml_to_file(deployment_response, path)

            progress.log()
            progress.log(Panel.fit("Deployment Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve deployments, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve deployments: {e}", style="bold red"))
            progress.log()

    # Function to collect ingress information
    def collect_ingress_info(self, progress, ingresses=[]):

        # Create folder for ingresses if it does not exist
        ingress_folder_path = os.path.join(self._mustgather_folder, "ingresses")
        if not os.path.exists(ingress_folder_path):
            os.makedirs(ingress_folder_path)

        try:
            progress.log(Panel.fit("Starting Ingress Information Collection", style="cyan"))
            progress.log()

            for ingress in ingresses:
                progress.log(f"Collecting ingress {ingress}")
                progress.log()
                path = os.path.join(
                    f"{ingress_folder_path}",
                    f"{ingress}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    ingress_response = self._kube.describe_ingress(ingress, self._namespace)
                    write_yaml_to_file(ingress_response, path)

            progress.log()
            progress.log(Panel.fit("Ingress Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve ingresses, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve ingresses", style="bold red"))
            progress.log()

    # Function to collect route or ingress information
    def collect_route_info(self, progress, routes=[]):

        # Create folder for routes if it does not exist
        route_folder_path = os.path.join(self._mustgather_folder, "routes")
        if not os.path.exists(route_folder_path):
            os.makedirs(route_folder_path)

        try:
            progress.log(Panel.fit("Starting Route Information Collection", style="cyan"))
            progress.log()

            for route in routes:
                progress.log(f"Collecting route {route}")
                progress.log()
                path = os.path.join(
                    f"{route_folder_path}",
                    f"{route}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    route_response = self._kube.describe_route(route, self._namespace)
                    write_yaml_to_file(route_response, path)

            progress.log()
            progress.log(Panel.fit("Route Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve routes, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve routes", style="bold red"))
            progress.log()


    # Function to collect all HorizonalPodAutoscaler information
    def collect_hpa_info(self, progress, hpas=[]):
        # Create folder for hpas if it does not exist
        hpa_folder_path = os.path.join(self._mustgather_folder, "hpas")
        if not os.path.exists(hpa_folder_path):
            os.makedirs(hpa_folder_path)

        try:
            progress.log(Panel.fit("Starting HPA Information Collection", style="cyan"))
            progress.log()

            for hpa in hpas:
                progress.log(f"Collecting HPA {hpa}")
                progress.log()
                path = os.path.join(
                    f"{hpa_folder_path}",
                    f"{hpa}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    hpa_response = self._kube.describe_hpa(hpa, self._namespace)
                    write_yaml_to_file(hpa_response, path)

            progress.log()
            progress.log(Panel.fit("HPA Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve HPAs, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve HPAs", style="bold red"))
            progress.log()

    # Function to collect Network Policy information
    def collect_network_policy_info(self, progress, network_policies=[]):

        # Create folder for network policies if it does not exist
        network_policy_folder_path = os.path.join(self._mustgather_folder, "network_policies")
        if not os.path.exists(network_policy_folder_path):
            os.makedirs(network_policy_folder_path)

        try:
            progress.log(Panel.fit("Starting Network Policy Information Collection", style="cyan"))
            progress.log()

            for network_policy in network_policies:
                progress.log(f"Collecting network policy {network_policy}")
                progress.log()
                path = os.path.join(
                    f"{network_policy_folder_path}",
                    f"{network_policy}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    network_policy_response = self._kube.describe_network_policy(network_policy, self._namespace)
                    write_yaml_to_file(network_policy_response, path)

            progress.log()
            progress.log(Panel.fit("Network Policy Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve network policies, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve network policies", style="bold red"))
            progress.log()

    # Function to collect service information
    def collect_service_info(self, progress, services=[]):

        # Create folder for services if it does not exist
        service_folder_path = os.path.join(self._mustgather_folder, "services")
        if not os.path.exists(service_folder_path):
            os.makedirs(service_folder_path)

        try:
            progress.log(Panel.fit("Starting Service Information Collection", style="cyan"))
            progress.log()

            for service in services:
                progress.log(f"Collecting service {service}")
                progress.log()
                path = os.path.join(
                    f"{service_folder_path}",
                    f"{service}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    service_response = self._kube.describe_service(service, self._namespace)
                    write_yaml_to_file(service_response, path)

            progress.log()
            progress.log(Panel.fit("Service Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve services, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve services", style="bold red"))
            progress.log()

    # Function to collect pvcs
    def collect_pvc_info(self, progress, pvcs=list):

        # Create folder for pvcs if it does not exist
        pvc_folder_path = os.path.join(self._mustgather_folder, "pvcs")
        if not os.path.exists(pvc_folder_path):
            os.makedirs(pvc_folder_path)

        try:
            progress.log(Panel.fit("Starting PVC Information Collection", style="cyan"))
            progress.log()

            for pvc in pvcs:
                progress.log(f"Collecting PVC {pvc}")
                progress.log()
                path = os.path.join(
                    f"{pvc_folder_path}",
                    f"{pvc}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    pvc_response = self._kube.describe_pvc(pvc, self._namespace)
                    write_yaml_to_file(pvc_response, path)

            progress.log()
            progress.log(Panel.fit("PVC Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve pvcs, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve pvcs", style="bold red"))
            progress.log()

    # Function to write CR file
    def write_cr_file(self, progress, name):
        try:
            progress.log(Panel.fit("Collecting FNCM Custom Resource File", style="cyan"))
            progress.log()
            path = os.path.join(
                f"{self._mustgather_folder}",
                f"{self._cr_name}-cr.yaml",
            )
            if os.path.isfile(path):
                self._logger.info("Log already collected in the previous step. Skipping...")
            else:
                cr_response = self._kube.custom_resource

                progress.log(f"Collecting custom resource {name}")
                write_yaml_to_file(cr_response, path)
            progress.log()
            progress.log(Panel.fit("FNCM Custom Resource Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve CR, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve CR", style="bold red"))
            progress.log()

    # Function to collect storage class information
    def collect_storage_class_info(self, progress, storage_classes=[]):

        # Create folder for storage if it does not exist
        storageclass_folder_path = os.path.join(self._mustgather_folder, "storageclasses")
        if not os.path.exists(storageclass_folder_path):
            os.makedirs(storageclass_folder_path)

        try:
            progress.log(Panel.fit("Starting Storage Class Information Collection", style="cyan"))
            progress.log()

            for storage_class in storage_classes:
                progress.log(f"Collecting storage class {storage_class}")
                progress.log()
                path = os.path.join(
                    f"{storageclass_folder_path}",
                    f"{storage_class}.yaml",
                )
                if os.path.isfile(path):
                    self._logger.info("Log already collected in the previous step. Skipping...")
                else:
                    storage_class_response = self._kube.describe_storage_class(storage_class)
                    write_yaml_to_file(storage_class_response, path)

            progress.log()
            progress.log(Panel.fit("Storage Class Information Collection Completed", style="bold green"))

        except Exception as e:
            self._logger.info("Unable to retrieve storage classes, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve storage classes", style="bold red"))
            progress.log()

    def collect_network_policy_templates(self,progress, operator_details):
        operator_pods = operator_details["pods"]

        try:
            policies_folder_path = os.path.join(self._mustgather_folder, "templates")
            if not os.path.exists(policies_folder_path):
                os.makedirs(policies_folder_path)
                progress.log()
                progress.log("Creating Network Policy Templates folder")
            else:
                progress.log()
                progress.log("Using existing Network Policy Templates folder")

            progress.log()
            progress.log("Collecting Egress Network Policy Templates")
            progress.log()
            progress.log("Collecting Ingress Network Policy Templates")

            copied = self._kube.copy_files_from_pod(pod_name=operator_pods[0], namespace=self._namespace, src_path=f"/tmp/{self._namespace}/network-policies", dest_path=policies_folder_path)

            if not copied:
                progress.log(Text(f"Network Policy Templates not found in Operator", style="bold red"))
                progress.log()
                progress.log(Text(f"Make sure shared_configuration.sc_generate_sample_network_policies: true is present in CR\n"
                                  f"If the parameter is enabled in CR, wait for a reconcile for the operator to generate the templates", style="bold red"))
                return

            progress.log()
            progress.log(Panel.fit("Network Policy Templates Collection Completed", style="bold green"))
        except Exception as e:
            self._logger.info("Unable to retrieve Network Policy Templates, caught %s Skipping...", e)
            progress.log()
            progress.log(Text(f"Network Policy from Templates not found in Operator\n\n"
                              f"Make sure shared_configuration.sc_generate_sample_network_policies: true is present in CR\n"
                              f"If the parameter is enabled in CR, wait for a reconcile for the operator to generate the templates", style="bold red"))
            progress.log()
    
    def auto_apply_networkpolicy(self):
        content_egress_folder_path=os.path.join(self._mustgather_folder, "templates","Content","egress")
        content_ingress_folder_path=os.path.join(self._mustgather_folder, "templates","Content","ingress")
        ier_egress_folder_path=os.path.join(self._mustgather_folder, "templates","IER","egress")
        ier_ingress_folder_path=os.path.join(self._mustgather_folder, "templates","IER","ingress")
        iccsap_egress_folder_path=os.path.join(self._mustgather_folder, "templates","ICCSAP","egress")
        iccsap_ingress_folder_path=os.path.join(self._mustgather_folder, "templates","ICCSAP","ingress")
        # Get all yaml and yml files from the egress and ingress folders
        egress_files = list(Path(content_egress_folder_path).glob("*.yaml")) + list(Path(content_egress_folder_path).glob("*.yml")) + list(Path(ier_egress_folder_path).glob("*.yaml")) + list(Path(ier_egress_folder_path).glob("*.yml")) + list(Path(iccsap_egress_folder_path).glob("*.yaml")) + list(Path(iccsap_egress_folder_path).glob("*.yml"))
        ingress_files = list(Path(content_ingress_folder_path).glob("*.yaml")) + list(Path(content_ingress_folder_path).glob("*.yml")) + list(Path(ier_ingress_folder_path).glob("*.yaml")) + list(Path(ier_ingress_folder_path).glob("*.yml")) + list(Path(iccsap_ingress_folder_path).glob("*.yaml")) + list(Path(iccsap_ingress_folder_path).glob("*.yml"))
        if len(egress_files) == 0:
            self._logger.info(f"No egress network policy files found in FNCMNetworkPolicies/{self._namespace}")
            print()
            print(Panel.fit(Text(f"No egress network policy files found in FNCMNetworkPolicies/{self._namespace}/templates/*/egress/"), style="bold red"))
        if len(ingress_files) == 0:
            self._logger.info(f"No ingress network policy files found in CASNetworkPolicies/")
            print()
            print(Panel.fit(Text(f"No ingress network policy files found in FNCMNetworkPolicies/{self._namespace}/templates/*/ingress/"), style="bold red"))
        if len(egress_files) == 0 and len(ingress_files) == 0:
            return

         # Apply each network policy file

        print()
        print(Panel.fit(Text(f"Applying Egress and Ingress Network Policies"), style="cyan"))

        for file in egress_files:
            # Get Filename from path
            file_name = os.path.basename(file)
            self._logger.info(f"Applying network policy file: {str(file)}")
            try:
                applied = self._kube.apply_cluster_resource_files(resource_type='network_policy', resource_file=str(file), namespace=self._namespace)
                if not applied:
                    self._logger.info(f"Failed to apply network policy file: {str(file_name)}")
                    print()
                    print(Text(f"Failed to apply network policy file: {str(file_name)}", style="bold red"))
                else:
                    self._logger.info(f"Successfully applied network policy file: {str(file_name)}")
                    print()
                    print(Text(f"Successfully applied network policy file: {str(file_name)}", style="bold green"))
            except Exception as e:
                self._logger.info(f"Failed to apply network policy file {str(file_name)}: {e}")
                continue


        for file in ingress_files :
            # Get Filename from path
            file_name = os.path.basename(file)
            self._logger.info(f"Applying network policy file: {str(file)}")
            try:
                applied = self._kube.apply_cluster_resource_files(resource_type='network_policy', resource_file=str(file), namespace=self._namespace)
                if not applied:
                    self._logger.info(f"Failed to apply network policy file: {str(file_name)}")
                    print()
                    print(Text(f"Failed to apply network policy file: {str(file_name)}", style="bold red"))
                else:
                    self._logger.info(f"Successfully applied network policy file: {str(file_name)}")
                    print()
                    print(Text(f"Successfully applied network policy file: {str(file_name)}", style="bold green"))
            except Exception as e:
                self._logger.info(f"Failed to apply network policy file {str(file_name)}: {e}")
                continue

        print()
        print(Panel.fit(Text(f"Successfully applied Egress and Ingress Network Policies", style="bold green")))

    # Function to collect CPE information
    def collect_cpe_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for CPE if it does not exist
        cpe_folder_path = os.path.join(self._mustgather_folder, "cpe")
        if not os.path.exists(cpe_folder_path):
            os.makedirs(cpe_folder_path)

        cpe_pods = pods

        progress.log(Panel.fit("Starting CPE Information Collection", style="cyan"))
        progress.log()

        try:
            if len(cpe_pods) == 0:
                progress.log(Text(f"No CPE pods found", style="bold red"))
                progress.log()
                return

            # Collect FileNet Logs
            # Collection from the first pods as this shared in a PVC
            progress.log(f"Collecting FileNet logs")
            progress.log()
            path = os.path.join(
                f"{cpe_folder_path}",
                f"FileNet",
            )
            if not os.path.exists(path):
                os.makedirs(path)

            self._kube.copy_files_from_pod(pod_name=cpe_pods[0], namespace=self._namespace,
                                                    src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/FileNet/",
                                                    dest_path=path,
                                                    file_filter=f'{self._cr_name}-cpe*/*.log')


            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting CPE configuration files")
                progress.log()
                path = os.path.join(
                    f"{cpe_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=cpe_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path)


            for pod in cpe_pods:
                progress.log(Panel.fit(f"Collecting for CPE pod: {pod}", style="yellow"))
                progress.log()
                self.collect_pod_info(progress, cpe_folder_path, pod, init_containers, "cpe")

            progress.log(Panel.fit("CPE Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve CPE, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve CPE Logs", style="bold red"))
            progress.log()

    # Function to collect general pod information
    def collect_pod_info(self, progress, folder, pod, init_containers=list, component=""):
        # Create folder for pod info
        pod_path = os.path.join(f"{folder}", "pods", pod)
        if not os.path.exists(pod_path):
            os.makedirs(pod_path)


        # Collect product version
        if component not in ["iccsap"]:
            self.get_component_version(pod, pod_path, progress)

        if component not in ["css", "operator", "iccsap"]:
            # Collect Liberty Version
            self.get_liberty_version(pod, pod_path, progress)

        # Collect Java Version
        self.get_java_version(pod, pod_path, progress)

        # Collect env variables
        self.get_environment_variables(pod, pod_path, progress)

        if component not in ["css", "operator", "iccsap"]:
            self.get_jvm_options(pod, pod_path, progress)

        # Collect Liberty Logs
        if component not in ["css", "operator", "iccsap"]:
            progress.log(f"Collecting Liberty logs")
            progress.log()

            self._kube.copy_files_from_pod(pod_name=pod, namespace=self._namespace,
                                                    src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/logs/{pod}",
                                                    dest_path=pod_path,
                                                    file_filter=f'*')

        # Collect init-container logs
        for container in init_containers:
            progress.log(f"Collecting init-container logs: {container}")
            progress.log()
            path = os.path.join(
                f"{pod_path}",
                f"{container}.log",
            )

            init_container_response = self._kube.get_init_container_logs(pod, self._namespace, container)
            write_log_to_file(init_container_response, path)

        # Collect pod yaml
        path = os.path.join(
            f"{pod_path}",
            f"{pod}.yaml",
        )

        cpe_response = self._kube.describe_pod(pod, self._namespace)
        write_yaml_to_file(cpe_response, path)

    def collect_ier_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for IER if it does not exist
        ier_folder_path = os.path.join(self._mustgather_folder, "ier")
        if not os.path.exists(ier_folder_path):
            os.makedirs(ier_folder_path)

        ier_pods = pods

        progress.log(Panel.fit("Starting IER Information Collection", style="cyan"))
        progress.log()

        try:
            if len(ier_pods) == 0:
                progress.log(Text(f"No IER pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting IER configuration files")
                progress.log()
                path = os.path.join(
                    f"{ier_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=ier_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path,
                                                        file_filter=f'*')

            for pod in ier_pods:
                progress.log(Panel.fit(f"Collecting for IER pod: {pod}", style="yellow"))
                progress.log()

                self.collect_pod_info(progress, ier_folder_path, pod, init_containers, "ier")

                progress.log(f"Collecting IER Plugin Configuration")
                progress.log()

                # Collect plugin-cfg.xml
                command = ["cat", "/opt/ibm/wlp/usr/servers/defaultServer/logs/state/plugin-cfg.xml"]
                response = self._kube.pod_exec(pod, self._namespace, command)
                plugin_path = os.path.join(
                    f"{ier_folder_path}", "pods", f"{pod}", "plugin-cfg.xml"
                )
                with open(plugin_path, "w", encoding="utf8") as f:
                    f.write(response)

            progress.log(Panel.fit("IER Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve IER, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve IER Logs", style="bold red"))
            progress.log()

    # Function to collect ICCSAP information
    def collect_iccsap_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for ICCSAP if it does not exist
        iccsap_folder_path = os.path.join(self._mustgather_folder, "iccsap")
        if not os.path.exists(iccsap_folder_path):
            os.makedirs(iccsap_folder_path)

        iccsap_pods = pods

        progress.log(Panel.fit("Starting ICCSAP Information Collection", style="cyan"))
        progress.log()

        try:

            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting ICCSAP configuration files")
                progress.log()
                path = os.path.join(
                    f"{iccsap_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=iccsap_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/IBM/iccsap/instance",
                                                        dest_path=path,
                                                        file_filter=f'*')


            for pod in iccsap_pods:
                progress.log(Panel.fit(f"Collecting for ICCSAP pod: {pod}", style="yellow"))
                progress.log()

                pod_path = os.path.join(f"{iccsap_folder_path}", "pods", pod)
                if not os.path.exists(pod_path):
                    os.makedirs(pod_path)

                self._kube.copy_files_from_pod(pod_name=pod, namespace=self._namespace,
                                                        src_path=f"/opt/IBM/iccsap/logs/{pod}",
                                                        dest_path=pod_path,
                                                        file_filter=f'*')


                self.collect_pod_info(progress, iccsap_folder_path, pod, init_containers, "iccsap")

            progress.log(Panel.fit("ICCSAP Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve ICCSAP, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve ICCSAP Logs", style="bold red"))
            progress.log()

    # Function to collect CSS information
    def collect_css_info(self, progress, collect_sensitive, pods=list, init_containers=list, deployment_num=""):

        # Create folder for CSS if it does not exist
        css_folder_path = os.path.join(self._mustgather_folder, "css", f"css-deploy-{deployment_num}")
        if not os.path.exists(css_folder_path):
            os.makedirs(css_folder_path)

        css_pods = pods

        progress.log(Panel.fit(f"Starting CSS Information Collection: css-deploy-{deployment_num}", style="cyan"))
        progress.log()

        try:
            if len(css_pods) == 0:
                progress.log(Text(f"No CSS pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting CSS configuration files")
                progress.log()
                path = os.path.join(
                    f"{css_folder_path}",
                    f"Configuration",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=css_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/IBM/ContentSearchServices/CSS_Server/config",
                                                        dest_path=path,
                                                        file_filter=f'*')


            for pod in css_pods:
                progress.log(Panel.fit(f"Collecting for CSS pod: {pod}", style="yellow"))
                progress.log()

                pod_path = os.path.join(f"{css_folder_path}", "pods", pod)
                if not os.path.exists(pod_path):
                    os.makedirs(pod_path)

                self._kube.copy_files_from_pod(pod_name=pod, namespace=self._namespace,
                                                src_path=f"/opt/IBM/ContentSearchServices/CSS_Server/log/{pod}",
                                                dest_path=pod_path,
                                                file_filter=f'*.log')


                self.collect_pod_info(progress, css_folder_path, pod, init_containers, "css")

            progress.log(Panel.fit("CSS Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve CSS, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve CSS Logs", style="bold red"))
            progress.log()

    # Function to collect GraphQL Information
    def collect_graphql_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for GraphQL if it does not exist
        graphql_folder_path = os.path.join(self._mustgather_folder, "graphql")
        if not os.path.exists(graphql_folder_path):
            os.makedirs(graphql_folder_path)

        graphql_pods = pods

        progress.log(Panel.fit("Starting GraphQL Information Collection", style="cyan"))
        progress.log()

        try:
            if len(graphql_pods) == 0:
                progress.log(Text(f"No GraphQL pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting GraphQL configuration files")
                progress.log()
                path = os.path.join(
                    f"{graphql_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=graphql_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path,
                                                        file_filter=f'*')

            for pod in graphql_pods:
                progress.log(Panel.fit(f"Collecting for GraphQL pod: {pod}", style="yellow"))
                progress.log()

                self.collect_pod_info(progress, graphql_folder_path, pod, init_containers, "graphql")

            progress.log(Panel.fit("GraphQL Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve GraphQL, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve GraphQL Logs", style="bold red"))
            progress.log()

    # Function to ExternalShare Information
    def collect_es_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for ExternalShare if it does not exist
        externalshare_folder_path = os.path.join(self._mustgather_folder, "es")
        if not os.path.exists(externalshare_folder_path):
            os.makedirs(externalshare_folder_path)

        externalshare_pods = pods

        progress.log(Panel.fit("Starting ExternalShare Information Collection", style="cyan"))
        progress.log()

        try:
            if len(externalshare_pods) == 0:
                progress.log(Text(f"No ExternalShare pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting ExternalShare configuration files")
                progress.log()
                path = os.path.join(
                    f"{externalshare_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=externalshare_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path,
                                                        file_filter=f'*')


            for pod in externalshare_pods:
                progress.log(Panel.fit(f"Collecting for ExternalShare pod: {pod}", style="yellow"))
                progress.log()

                self.collect_pod_info(progress, externalshare_folder_path, pod, init_containers, "es")

            progress.log(Panel.fit("ExternalShare Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve ExternalShare, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve ExternalShare Logs", style="bold red"))
            progress.log()

    # Function to collect CMIS Information
    def collect_cmis_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for CMIS if it does not exist
        cmis_folder_path = os.path.join(self._mustgather_folder, "cmis")
        if not os.path.exists(cmis_folder_path):
            os.makedirs(cmis_folder_path)

        cmis_pods = pods

        progress.log(Panel.fit("Starting CMIS Information Collection", style="cyan"))
        progress.log()

        try:
            if len(cmis_pods) == 0:
                progress.log(Text(f"No CMIS pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting CMIS configuration files")
                progress.log()
                path = os.path.join(
                    f"{cmis_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=cmis_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path,
                                                        file_filter=f'*')


            for pod in cmis_pods:
                progress.log(Panel.fit(f"Collecting for CMIS pod: {pod}", style="yellow"))
                progress.log()

                self.collect_pod_info(progress, cmis_folder_path, pod, init_containers, "cmis")

            progress.log(Panel.fit("CMIS Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve CMIS, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve CMIS Logs", style="bold red"))
            progress.log()

    # Function to collect TaskManager Information
    def collect_tm_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for TaskManager if it does not exist
        taskmanager_folder_path = os.path.join(self._mustgather_folder, "tm")
        if not os.path.exists(taskmanager_folder_path):
            os.makedirs(taskmanager_folder_path)

        taskmanager_pods = pods

        progress.log(Panel.fit("Starting TaskManager Information Collection", style="cyan"))
        progress.log()

        try:
            if len(taskmanager_pods) == 0:
                progress.log(Text(f"No TaskManager pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting TaskManager configuration files")
                progress.log()
                path = os.path.join(
                    f"{taskmanager_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=taskmanager_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path,
                                                        file_filter=f'*')


            for pod in taskmanager_pods:
                progress.log(Panel.fit(f"Collecting for TaskManager pod: {pod}", style="yellow"))
                progress.log()

                self.collect_pod_info(progress, taskmanager_folder_path, pod, init_containers, "tm")

            progress.log(Panel.fit("TaskManager Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve TaskManager, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve TaskManager Logs", style="bold red"))
            progress.log()

    # Function to collect Navigator information
    def collect_ban_info(self, progress, collect_sensitive, pods=list, init_containers=list):

        # Create folder for Navigator if it does not exist
        navigator_folder_path = os.path.join(self._mustgather_folder, "ban")
        if not os.path.exists(navigator_folder_path):
            os.makedirs(navigator_folder_path)

        navigator_pods = pods

        progress.log(Panel.fit("Starting Navigator Information Collection", style="cyan"))
        progress.log()

        try:
            if len(navigator_pods) == 0:
                progress.log(Text(f"No Navigator pods found", style="bold red"))
                progress.log()
                return
            # Collect Configuration Files
            if collect_sensitive:
                progress.log(f"Collecting Navigator configuration files")
                progress.log()
                path = os.path.join(
                    f"{navigator_folder_path}",
                    f"ConfigDropins",
                )
                if not os.path.exists(path):
                    os.makedirs(path)

                self._kube.copy_files_from_pod(pod_name=navigator_pods[0], namespace=self._namespace,
                                                        src_path=f"/opt/ibm/wlp/usr/servers/defaultServer/configDropins/overrides",
                                                        dest_path=path,
                                                        file_filter=f'*')


            for pod in navigator_pods:
                progress.log(Panel.fit(f"Collecting for Navigator pod: {pod}", style="yellow"))
                progress.log()

                self.collect_pod_info(progress, navigator_folder_path, pod, init_containers, "ban")

            progress.log(Panel.fit("Navigator Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve Navigator, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve Navigator Logs", style="bold red"))
            progress.log()

    # Function to collect Content Operator information
    def collect_operator_info(self, progress, collect_sensitive, operator_details=dict):

        # Create folder for Content Operator if it does not exist
        operator_folder_path = os.path.join(self._mustgather_folder, "operator")
        if not os.path.exists(operator_folder_path):
            os.makedirs(operator_folder_path)

        operator_pods = operator_details["pods"]

        progress.log(Panel.fit("Starting FNCM Operator Information Collection", style="cyan"))
        progress.log()

        try:
            # Collect Deployment Information
            deployment = operator_details["deployment"]
            progress.log(f"Collecting deployment {deployment}")
            progress.log()
            path = os.path.join(
                f"{operator_folder_path}",
                f"{deployment}.yaml",
            )

            deployment_response = self._kube.describe_deployment(deployment, self._namespace)
            write_yaml_to_file(deployment_response, path)

            deployment_type = operator_details["type"]

            if deployment_type == "OLM":

                # Collect CSV Information
                csv = operator_details["installedCSV"]
                progress.log(f"Collecting CSV {csv}")
                progress.log()
                path = os.path.join(
                    f"{operator_folder_path}",
                    f"cluster-service-version.yaml",
                )

                csv_response = self._kube.describe_csv(csv, self._namespace)
                write_yaml_to_file(csv_response, path)


                # Collect Subscription Information
                subscription = operator_details["subscription"]
                progress.log(f"Collecting subscription {subscription}")
                progress.log()
                path = os.path.join(
                    f"{operator_folder_path}",
                    f"subscription.yaml",
                )

                subscription_response = self._kube.describe_subscription(subscription, self._namespace)
                write_yaml_to_file(subscription_response, path)

                # Collect CatalogSource Information

                catalogsource = operator_details["catalogSource"]
                catalogsource_namespace = operator_details["sourceNamespace"]
                progress.log(f"Collecting catalogsource {catalogsource}")
                progress.log()
                path = os.path.join(
                    f"{operator_folder_path}",
                    f"catalogsource.yaml",
                )

                catalogsource_response = self._kube.describe_catalogsource(catalogsource, catalogsource_namespace)
                write_yaml_to_file(catalogsource_response, path)

                # Collect OperatorGroup Information
                operator_group = operator_details["operatorGroup"]
                progress.log(f"Collecting operator group {operator_group}")
                progress.log()
                path = os.path.join(
                    f"{operator_folder_path}",
                    f"operatorgroup.yaml",
                )

                operator_group_response = self._kube.describe_operator_group(operator_group, self._namespace)
                write_yaml_to_file(operator_group_response, path)

            # Collect Configuration Files
            if len(operator_pods) == 0:
                progress.log(Text(f"No Content Operator pods found", style="bold red"))
                progress.log()
                return

            for pod in operator_pods:

                pod_path = os.path.join(f"{operator_folder_path}", "pods", pod)
                if not os.path.exists(pod_path):
                    os.makedirs(pod_path)

                progress.log(Panel.fit(f"Collecting for Content Operator pod: {pod}", style="yellow"))
                progress.log()

                init_containers = operator_details["init_containers"]

                self.collect_pod_info(progress, operator_folder_path, pod, init_containers, "operator")

            progress.log(f"Collecting FNCM Operator Ansible logs")
            progress.log()
            path = os.path.join(
                f"{operator_folder_path}",
                f"logs"
            )
            if not os.path.exists(path):
                os.makedirs(path)

            log_path = f'/logs/{operator_pods[0]}/ansible-operator/runner/fncm.ibm.com/v1/FNCMCluster/{self._namespace}/{self._cr_name}/artifacts'


            self._kube.copy_files_from_pod(pod_name=operator_pods[0], namespace=self._namespace,
                                           src_path=log_path,
                                           file_filter='*',
                                           dest_path=path)

            # Check if the logs folder is empty
            # if logs folder is empty, download the logs from the tmp folder
            if not os.listdir(path):
                inprogressPath = os.path.join(
                    f"{path}",
                    f"inProgress"
                )

                if not os.path.exists(inprogressPath):
                    os.makedirs(inprogressPath)

                progress.log(f"No completed Ansible logs found in /logs folder. Downloading the in progress logs from /tmp folder")
                progress.log()

                self._kube.copy_files_from_pod(pod_name=operator_pods[0], namespace=self._namespace,
                                               src_path=f'/tmp/ansible-operator/runner/fncm.ibm.com/v1/FNCMCluster/{self._namespace}/{self._cr_name}/artifacts',
                                               dest_path=inprogressPath,
                                               file_filter=f'*')


            progress.log(Panel.fit("Content Operator Information Collection Completed", style="bold green"))
            progress.log()

        except Exception as e:
            self._logger.info("Unable to retrieve Content Operator, caught %s Skipping...", e)
            progress.log(Text(f"Unable to retrieve Content Operator Logs", style="bold red"))
            progress.log()

    # Function to collect environment variables
    def get_environment_variables(self, pod, folder_path, progress):
        try:
            progress.log(f"Collecting environment variables")
            progress.log()
            command = ["printenv"]
            env_vars = self._kube.pod_exec(pod, self._namespace, command)
            local_path = os.path.join(
                f"{folder_path}", "environment_variables.txt"
            )
            with open(local_path, "w", encoding="utf8") as f:
                f.write(env_vars)

        except Exception as e:
            self._logger.info(
                "Unable to copy from pod, caught %s Skipping...", e
            )
            progress.log(
                Text(f"Unable to copy from pod", style="bold red")
            )
            progress.log()

    # Function to collect Product Version
    def get_component_version(self, pod, folder_path, progress):
        try:
            progress.log(f"Collecting component version")
            progress.log()
            command = ["cat", "/opt/ibm/version.txt"]
            version = self._kube.pod_exec(pod, self._namespace, command)
            local_path = os.path.join(
                f"{folder_path}", "version.txt"
            )
            with open(local_path, "w", encoding="utf8") as f:
                f.write(version)

        except Exception as e:
            self._logger.info(
                "Unable to copy from pod, caught %s Skipping...", e
            )
            progress.log(
                Text(f"Unable to copy from pod", style="bold red")
            )
            progress.log()

    # Function to collect Liberty Version
    def get_liberty_version(self, pod, folder_path, progress):
        try:
            progress.log(f"Collecting liberty version")
            progress.log()
            command = ["/opt/ibm/wlp/bin/server", "version"]
            version = self._kube.pod_exec(pod, self._namespace, command)
            local_path = os.path.join(
                f"{folder_path}", "liberty_version.txt"
            )
            with open(local_path, "w", encoding="utf8") as f:
                f.write(version)

        except Exception as e:
            self._logger.info(
                "Unable to copy from pod, caught %s Skipping...", e
            )
            progress.log(
                Text(f"Unable to copy from pod", style="bold red")
            )
            progress.log()

    # Function to collect jvm.options
    def get_jvm_options(self, pod, folder_path, progress):
        try:
            progress.log(f"Collecting jvm.options")
            progress.log()
            command = ["cat", "/opt/ibm/wlp/usr/servers/defaultServer/jvm.options"]
            options = self._kube.pod_exec(pod, self._namespace, command)
            local_path = os.path.join(
                f"{folder_path}", "jvm_options.txt"
            )
            with open(local_path, "w", encoding="utf8") as f:
                f.write(options)

        except Exception as e:
            self._logger.info(
                "Unable to copy from pod, caught %s Skipping...", e
            )
            progress.log(
                Text(f"Unable to copy from pod", style="bold red")
            )
            progress.log()

    # Function to collect Java Version
    def get_java_version(self, pod, folder_path, progress):
        try:
            progress.log(f"Collecting IBM Java version")
            progress.log()
            command = ["java", "-version"]
            version = self._kube.pod_exec(pod, self._namespace, command)
            local_path = os.path.join(
                f"{folder_path}", "java_version.txt"
            )
            with open(local_path, "w", encoding="utf8") as f:
                f.write(version)

        except Exception as e:
            self._logger.info(
                "Unable to copy from pod, caught %s Skipping...", e
            )
            progress.log(
                Text(f"Unable to copy from pod", style="bold red")
            )
            progress.log()
