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

from time import sleep

import urllib3
import yaml
from kubernetes import config, client
from kubernetes.client import ApiException
from kubernetes.stream import stream
from rich.text import Text


class KubernetesUtilities:
    def __init__(self, logger=None):
        config.load_kube_config()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._core_v1 = client.CoreV1Api()
        self._apps_v1 = client.AppsV1Api()
        self._rbac_v1 = client.RbacAuthorizationV1Api()
        self._networking_v1 = client.NetworkingV1Api()
        self._custom_api = client.CustomObjectsApi()
        self._storage_v1 = client.StorageV1Api()
        self._extensions_v1 = client.ApiextensionsV1Api()
        self._version_v1 = client.VersionApi()
        self._custom_resource = {}
        self._cr_details = {}
        self._operator_details = {}
        self._logger = logger

    @property
    def custom_resource(self):
        return self._custom_resource

    @property
    def cr_details(self):
        return self._cr_details

    @property
    def core_v1(self):
        return self._core_v1

    @property
    def apps_v1(self):
        return self._apps_v1

    @property
    def networking_v1(self):
        return self._networking_v1

    @property
    def custom_api(self):
        return self._custom_api

    @property
    def extensions_v1(self):
        return self._extensions_v1

    @property
    def version_v1(self):
        return self._version_v1

    # Function to collect all user-created configmaps
    def calculate_user_configmaps(self, components=list):
        configmaps = set()
        cr = self._custom_resource

        # Collect configmaps from ecm_configuration
        ecm_components = ["cpe", "css", "cmis", "graphql", "es", "tm"]

        if any(e in ecm_components for e in components):
            if "ecm_configuration" in cr["spec"].keys():

                for component in ecm_components:
                    if component in cr["spec"]["ecm_configuration"].keys():
                        section_name = f"{component}_production_setting"
                        if section_name in cr["spec"]["ecm_configuration"][component].keys():
                            if "custom_configmap" in cr["spec"]["ecm_configuration"][component][section_name].keys():
                                for item in cr["spec"]["ecm_configuration"][component][section_name][
                                    "custom_configmap"]:
                                    if "name" in item.keys():
                                        configmaps.add(item["name"])

        # Collect configmaps from ban
        if "ban" in components:
            if "navigator_configuration" in cr["spec"].keys():
                if "icn_production_setting" in cr["spec"]["navigator_configuration"].keys():
                    if "custom_configmap" in cr["spec"]["navigator_configuration"]["icn_production_setting"].keys():
                        for item in cr["spec"]["navigator_configuration"]["icn_production_setting"]["custom_configmap"]:
                            if "name" in item.keys():
                                configmaps.add(item["name"])

        # Collect configmaps from ier
        if "ier" in components:
            if "ier_configuration" in cr["spec"].keys():
                if "ier_production_setting" in cr["spec"]["ier_configuration"].keys():
                    if "custom_configmap" in cr["spec"]["ier_configuration"]["ier_production_setting"].keys():
                        for item in cr["spec"]["ier_configuration"]["ier_production_setting"]["custom_configmap"]:
                            if "name" in item.keys():
                                configmaps.add(item["name"])

        # Collect configmaps from iccsap
        if "iccsap" in components:
            if "iccsap_configuration" in cr["spec"].keys():
                if "iccsap_production_setting" in cr["spec"]["iccsap_configuration"].keys():
                    if "custom_configmap" in cr["spec"]["iccsap_configuration"]["iccsap_production_setting"].keys():
                        for item in cr["spec"]["iccsap_configuration"]["iccsap_production_setting"]["custom_configmap"]:
                            if "name" in item.keys():
                                configmaps.add(item["name"])

        return list(configmaps)

    # Function to collect all user-created secrets
    def calculate_user_secrets(self, components=list):
        secrets = set()
        cr = self._custom_resource

        # Collect different sections from the CR
        # LDAP Secrets
        # Get all LDAP Sections
        result = filter(lambda x: str(x).startswith("ldap_configuration"), cr["spec"].keys())
        ldap_sections = list(result)
        for section in ldap_sections:
            if "lc_bind_secret" in cr["spec"][section].keys():
                secrets.add(cr["spec"][section]["lc_bind_secret"])

            if "lc_ldap_ssl_enabled" in cr["spec"][section].keys():
                if cr["spec"][section]["lc_ldap_ssl_enabled"]:
                    secrets.add(cr["spec"][section]["lc_ldap_ssl_secret_name"])

        # DB Secrets
        db_ssl = False
        if "datasource_configuration" in cr["spec"].keys():
            if "dc_ssl_enabled" in cr["spec"]["datasource_configuration"].keys():
                if cr["spec"]["datasource_configuration"]["dc_ssl_enabled"]:
                    db_ssl = True

        if db_ssl:
            for section in cr["spec"]["datasource_configuration"].keys():
                if isinstance(cr["spec"]["datasource_configuration"][section], list):
                    for item in cr["spec"]["datasource_configuration"][section]:
                        if "database_ssl_secret_name" in item.keys():
                            secrets.add(item["database_ssl_secret_name"])
                elif isinstance(cr["spec"]["datasource_configuration"][section], dict):
                    if "database_ssl_secret_name" in cr["spec"]["datasource_configuration"][section].keys():
                        secrets.add(cr["spec"]["datasource_configuration"][section]["database_ssl_secret_name"])

        # ECM Secrets
        ecm_components = ["cpe", "css", "cmis", "graphql", "es", "tm"]
        if any(e in ecm_components for e in components):
            if "ecm_configuration" in cr["spec"].keys():
                if "fncm_secret_name" in cr["spec"]["ecm_configuration"].keys():
                    secrets.add(cr["spec"]["ecm_configuration"]["fncm_secret_name"])
                else:
                    secrets.add("ibm-fncm-secret")
            else:
                secrets.add("ibm-fncm-secret")

        # CSS Secrets
        if "css" in components:
            if "ecm_configuration" in cr["spec"].keys():
                if "css" in cr["spec"]["ecm_configuration"].keys():
                    if "css_production_setting" in cr["spec"]["ecm_configuration"]["css"].keys():
                        if "icc" in cr["spec"]["ecm_configuration"]["css"]["css_production_setting"].keys():
                            if "icc_enabled" in cr["spec"]["ecm_configuration"]["css"]["css_production_setting"][
                                "icc"].keys():
                                if cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                                    "icc_enabled"]:
                                    secrets.add(cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                                                    "icc_secret_name"])
                                    secrets.add(cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                                                    "secret_masterkey_name"])

        # BAN Secrets
        if "ban" in components:
            if "navigator_configuration" in cr["spec"].keys():
                if "ban_secret_name" in cr["spec"]["navigator_configuration"].keys():
                    secrets.add(cr["spec"]["navigator_configuration"]["ban_secret_name"])
                else:
                    secrets.add("ibm-ban-secret")
            else:
                secrets.add("ibm-ban-secret")

        # IER Secrets
        if "ier" in components:
            if "ier_configuration" in cr["spec"].keys():
                if "ier_secret_name" in cr["spec"]["ier_configuration"].keys():
                    secrets.add(cr["spec"]["ier_configuration"]["ier_secret_name"])
                else:
                    secrets.add("ibm-ier-secret")
            else:
                secrets.add("ibm-ier-secret")

        # ICCSAP Secrets
        if "iccsap" in components:
            if "iccsap_configuration" in cr["spec"].keys():
                if "iccsap_secret_name" in cr["spec"]["iccsap_configuration"].keys():
                    secrets.add(cr["spec"]["iccsap_configuration"]["iccsap_secret_name"])
                else:
                    secrets.add("ibm-iccsap-secret")
            else:
                secrets.add("ibm-iccsap-secret")

        # Trusted Certificates
        if "shared_configuration" in cr["spec"].keys():
            if "trusted_certificate_list" in cr["spec"]["shared_configuration"].keys():
                for cert_secret in cr["spec"]["shared_configuration"]["trusted_certificate_list"]:
                    secrets.add(cert_secret)

        # OIDC Secrets
        if "shared_configuration" in cr["spec"].keys():
            if "open_id_connect_providers" in cr["spec"]["shared_configuration"].keys():
                for item in cr["spec"]["shared_configuration"]["open_id_connect_providers"]:
                    if "client_oidc_secret" in item.keys():
                        for secret in item["client_oidc_secret"].values():
                            secrets.add(secret)

        # SCIM Secrets
        if "initialize_configuration" in cr["spec"].keys():
            if "scim_configuration" in cr["spec"]["initialize_configuration"].keys():
                for item in cr["spec"]["initialize_configuration"]["scim_configuration"]:
                    if "scim_secret_name" in item.keys():
                        secrets.add(item["scim_secret_name"])

        return list(secrets)

    # Function to calculate the deployed components
    def calculate_deployed_components(self):
        try:
            components = set()
            cr = self._custom_resource

            # TODO: Validate component names

            # Collect different sections from the CR

            if "content_optional_components" in cr["spec"].keys():
                for item, value in cr["spec"]["content_optional_components"].items():
                    if bool(value):
                        components.add(item)

            if "sc_deployment_patterns" in cr["spec"]["shared_configuration"].keys():
                if cr["spec"]["shared_configuration"]["sc_deployment_patterns"].lower() == "content":
                    components.add("cpe")
                    components.add("graphql")
                    components.add("ban")

            if "sc_optional_components" in cr["spec"]["shared_configuration"].keys():
                optional_list = cr["spec"]["shared_configuration"]["sc_optional_components"]
                optional = optional_list.split(",")
                for item in optional:
                    components.add(item)

            # Collect individual components from the CR
            if "ecm_configuration" in cr["spec"].keys():
                if "cpe" in cr["spec"]["ecm_configuration"].keys():
                    components.add("cpe")

                if "css" in cr["spec"]["ecm_configuration"].keys():
                    components.add("css")

                if "cmis" in cr["spec"]["ecm_configuration"].keys():
                    components.add("cmis")

                if "graphql" in cr["spec"]["ecm_configuration"].keys():
                    components.add("graphql")

                if "es" in cr["spec"]["ecm_configuration"].keys():
                    components.add("es")

                if "tm" in cr["spec"]["ecm_configuration"].keys():
                    components.add("tm")

            if "navigator_configuration" in cr["spec"].keys():
                components.add("ban")

            if "ier_configuration" in cr["spec"].keys():
                components.add("ier")

            if "iccsap_configuration" in cr["spec"].keys():
                components.add("iccsap")

            return list(components)

        except Exception as e:
            self._logger.info(f"Error calculating deployed components: {e}")
            return {}

    # Function to extract storage classes from the CR
    def extract_storage_classes(self):
        try:
            cr = self._custom_resource
            storage_classes = set()

            if "storage_configuration" in cr["spec"]["shared_configuration"].keys():
                storage_classes.add(
                    cr["spec"]["shared_configuration"]["storage_configuration"]["sc_fast_file_storage_classname"])
                storage_classes.add(
                    cr["spec"]["shared_configuration"]["storage_configuration"]["sc_medium_file_storage_classname"])
                storage_classes.add(
                    cr["spec"]["shared_configuration"]["storage_configuration"]["sc_slow_file_storage_classname"])

            return list(storage_classes)
        except Exception as e:
            self._logger.info(f"Error extracting storage classes: {e}")
            return {}

    # Function to read storage classes
    def describe_storage_class(self, storage_class_name):
        try:
            storage_classes = self._storage_v1.read_storage_class(storage_class_name)
            return storage_classes
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_storage_class: {e}")
            return {}

    # Function to parse and extract important info from the CR
    def parse_cr(self):
        try:
            cr = self._custom_resource
            # Extract the important information from the CR

            # TODO: Calculate profile size
            cr_details = {
                "name": cr["metadata"]["name"],
                "namespace": cr["metadata"]["namespace"],
                "platform": cr["spec"]["shared_configuration"]["sc_deployment_platform"],
                "context": cr["spec"]["shared_configuration"]["sc_deployment_context"],
                "appVersion": cr["spec"]["appVersion"]
            }

            # Extract the components from the CR
            components = self.calculate_deployed_components()
            cr_details["components"] = components

            # Equate AppVersion to FNCM Version
            versions = {
                "21.0.3": "5.5.8",
                "22.0.1": "5.5.9",
                "22.0.2": "5.5.10",
                "23.0.1": "5.5.11",
                "23.0.2": "5.5.12",
                "24.0.0": "5.6.0",
            }

            cr_details["version"] = versions[cr_details["appVersion"]]

            cr_details["storage_classes"] = self.extract_storage_classes()

            # Extract User Secrets
            cr_details["user_secrets"] = self.calculate_user_secrets(components)

            # Extract User Configmaps
            cr_details["user_configmaps"] = self.calculate_user_configmaps(components)

            self._cr_details = cr_details
            return cr_details
        except Exception as e:
            self._logger.info(f"Error parsing CR: {e}")
            return {}

    # Function to list the resources deployed by FNCM deployment in a specific namespace
    # Can see to add more resource types
    def list_namespace_resources(
            self, console, namespace, platform, filter="fncmdeploy"
    ):
        try:

            app_v1_resource_types = ["deployment"]
            core_v1_resource_types = [
                "service",
                "config_map",
                "secret",
                "persistent_volume_claim",
            ]
            networking_v1_resource_types = ["ingress", "network_policy"]
            resource_type_dict = {}
            for resource_type in app_v1_resource_types:
                resource_type_dict[resource_type] = []
                try:
                    response = getattr(self._apps_v1, f"list_namespaced_{resource_type}")(namespace=namespace)
                    for item in response.items:
                        if item.metadata.owner_references is not None:
                            if item.metadata.owner_references[0].name == filter:
                                resource_type_dict[resource_type].append(item.metadata.name)
                except client.exceptions.ApiException as e:
                    self._logger.info(f"Error listing {resource_type}: {e}")

            # Routes are only for OCP and CNCF ->
            if platform.lower() != "other":
                try:
                    resource_routes = self._custom_api.get_namespaced_custom_object(group="route.openshift.io",
                                                                                    version="v1",
                                                                                    namespace=namespace,
                                                                                    plural="routes", name="")
                    resource_type_dict["routes"] = []
                    for item in resource_routes["items"]:
                        if item["metadata"]["ownerReferences"] is not None:
                            if item["metadata"]["ownerReferences"][0]["name"] == filter:
                                resource_type_dict["routes"].append(item["metadata"]["name"])
                except Exception as e:
                    self._logger.info(f"Error listing Routes: {e}")

            for resource_type in core_v1_resource_types:
                resource_type_dict[resource_type] = []
                try:
                    response = getattr(self._core_v1, f"list_namespaced_{resource_type}")(namespace=namespace)
                    for item in response.items:
                        if item.metadata.owner_references is not None:
                            if item.metadata.owner_references[0].name == filter:
                                resource_type_dict[resource_type].append(item.metadata.name)
                        if item.metadata.labels is not None:
                            if 'app.kubernetes.io/instance' in item.metadata.labels.keys():
                                if item.metadata.labels['app.kubernetes.io/instance'] == filter:
                                    resource_type_dict[resource_type].append(item.metadata.name)
                        resource_type_dict[resource_type] = list(set(resource_type_dict[resource_type]))
                except client.exceptions.ApiException as e:
                    self._logger.info(f"Error listing {resource_type}: {e}")

            for resource_type in networking_v1_resource_types:
                resource_type_dict[resource_type] = []
                try:
                    response = getattr(self._networking_v1, f"list_namespaced_{resource_type}")(namespace=namespace)
                    for item in response.items:
                        if item.metadata.owner_references is not None:
                            if item.metadata.owner_references[0].name == filter:
                                resource_type_dict[resource_type].append(item.metadata.name)
                except client.exceptions.ApiException as e:
                    self._logger.info(f"Error listing {resource_type}: {e}")

            return resource_type_dict
        except Exception as e:
            self._logger.info(f"Error in listing resources in namespace function: {e}")
            return None

    # Function to get catalog source details
    def describe_catalogsource(self, name="ibm-fncm-catalog-source", namespace=""):
        # Define the resource group, version, and plural name for the custom resource
        group = "operators.coreos.com"
        version = "v1alpha1"
        plural = "catalogsources"

        try:
            catalog_source = self._custom_api.get_namespaced_custom_object(
                group=group, version=version, namespace=namespace, plural=plural, name=name
            )
            return catalog_source
        except Exception as e:
            self._logger.info(
                f"Error in kubernetes_utilities.py from the get_catalog_source_details function: {e}")
            return {}

    def parse_subscription(self, subscription):
        try:
            if not subscription:
                return {}
            # Extract the important information from the Subscription
            subscription_details = {
                "subscription": subscription["metadata"]["name"],
                "namespace": subscription["metadata"]["namespace"],
                "installedCSV": subscription["status"]["installedCSV"],
                "catalogSource": subscription["spec"]["source"],
                "channel": subscription["spec"]["channel"],
                "sourceNamespace": subscription["spec"]["sourceNamespace"],
            }

            gnc_namespace = "openshift-marketplace"

            if subscription_details["sourceNamespace"] == gnc_namespace:
                subscription_details["catalogType"] = "Global"
            else:
                subscription_details["catalogType"] = "Private"
            return subscription_details
        except Exception as e:
            self._logger.info(f"Error parsing Subscription: {e}")
            return {}

    def describe_subscription(self, name="", namespace=""):

        # Define the resource group, version, and plural name for the custom resource
        group = "operators.coreos.com"
        version = "v1alpha1"
        plural = "subscriptions"

        try:
            if name == "":
                name = self.get_subscription(namespace)

            subscription = self._custom_api.get_namespaced_custom_object(
                group=group, version=version, namespace=namespace, plural=plural, name=name
            )
            return subscription
        except Exception as e:
            self._logger.info(f"Error in kubernetes_utilities.py from the get_subscription: {e}")
            return {}

    # Function to get subscription name
    def get_subscription(self, namespace):
        try:
            subscriptions = self._custom_api.list_namespaced_custom_object(
                group="operators.coreos.com", version="v1alpha1", namespace=namespace, plural="subscriptions"
            )

            for subscription in subscriptions.get('items', []):
                if "ibm-fncm-operator" in subscription["metadata"]['name']:
                    name = subscription["metadata"]['name']
                    return name

            self._logger.info("Subscription could not be found")
            return None
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_subscription: {e}")
            return None

    # Function to delete the subscription of FNCM operator in OCP/ROKS
    def delete_subscription(self, namespace, name):
        # Define the resource group, version, and plural name for the custom resource
        group = "operators.coreos.com"
        version = "v1alpha1"
        plural = "subscriptions"

        try:
            # Delete the custom resource
            self._custom_api.delete_namespaced_custom_object(
                group=group, version=version, namespace=namespace, plural=plural, name=name
            )

            self._logger.info(f"Subscription '{name}' deleted successfully in namespace '{namespace}'.")
            return True
        except client.ApiException as e:
            self._logger.info(f"Error in utilities.py from the delete_subscription: {e}")
            return False

    # This function deletes the csv from the namespace in OCP/ROKS
    def delete_clusterserviceversion(self, csv_name="", namespace=""):

        # Define the resource group, version, and plural name for the custom resource
        group = "operators.coreos.com"
        version = "v1alpha1"
        plural = "clusterserviceversions"
        namespace = namespace
        name = csv_name

        # Specify the name of the ClusterServiceVersion
        name = csv_name

        try:
            # Delete the custom resource using kubectl APIS
            self._custom_api.list_namespaced_custom_object(group=group, version=version, plural=plural,
                                                           namespace=namespace)

            self._custom_api.delete_namespaced_custom_object(
                group=group, version=version, plural=plural, name=name, namespace=namespace
            )
            return True
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the delete_clusterserviceversion: {e}")
            return False

    # This function deletes the role, role binding , service account from the namespace
    def delete_operator_cncf(self, namespace=""):

        name = "ibm-fncm-operator"
        try:
            # Delete the Deployment
            self._apps_v1.delete_namespaced_deployment(name, namespace)

            # Delete the RoleBinding
            self._rbac_v1.delete_namespaced_role_binding(name, namespace)

            # Delete the Role
            self._rbac_v1.delete_namespaced_role(name, namespace)

            # Delete the ServiceAccount
            self._core_v1.delete_namespaced_service_account(name, namespace)

        except Exception as e:
            self._logger.info(f"Error in utilities.py from the delete_operator_cncf: {e}")

    def delete_operator_deployment(self, namespace="", name=""):
        if not name:
            name = "ibm-fncm-operator"
        try:
            # Delete the Deployment
            self._apps_v1.delete_namespaced_deployment(name, namespace)

        except Exception as e:
            self._logger.info(f"Error in utilities.py from the delete_operator_deployment: {e}")

    def delete_role_binding(self, namespace="", name=""):
        if not name:
            name = "ibm-fncm-operator"
        try:
            # Delete the RoleBinding
            self._rbac_v1.delete_namespaced_role_binding(name, namespace)
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the delete_role_binding: {e}")

    def delete_role(self, namespace="", name=""):
        if not name:
            name = "ibm-fncm-operator"
        try:
            # Delete the Role
            self._rbac_v1.delete_namespaced_role(name, namespace)
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the delete_role: {e}")

    def delete_service_account(self, namespace="", name=""):
        if not name:
            name = "ibm-fncm-operator"
        try:
            # Delete the ServiceAccount
            self._core_v1.delete_namespaced_service_account(name, namespace)
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the delete_service_account: {e}")

    # Function to check the storage class reclaim policy
    def check_storage_class_mode(self):
        try:
            # List all storage classes
            storage_classes = self._storage_v1.list_storage_class()

            # Print the names of the storage classes
            storage_class_return_dict = {}
            for sc in storage_classes.items:
                name = sc.metadata.name
                storage_class_return_dict[name] = sc.reclaim_policy

            return storage_class_return_dict

        except Exception as e:
            self._logger.info(f"Error in utilities.py from the check_storage_class_mode: {e}")

    # Function to check if role is created and if so create the role binding
    def apply_role_binding(self, resource_file, namespace):
        counter = 0
        while True:
            try:
                role = self._rbac_v1.read_namespaced_role(name="ibm-fncm-operator", namespace=namespace)
                if role.metadata.name == 'ibm-fncm-operator':
                    role_binding_applied = self.apply_cluster_resource_files(resource_type="role binding",
                                                                             namespace=namespace,
                                                                             resource_file=resource_file)
                    break
            except client.ApiException as e:
                if e.status == 404:
                    if counter < 3:
                        sleep(5)
                        counter = counter + 1
                    else:
                        role_binding_applied = False
                        break
        return role_binding_applied

    # Function to apply CRD , cluster role and role binding
    def apply_cluster_resource_files(self, resource_type, resource_file, namespace=None):

        try:
            # Read the resource manifest file
            with open(resource_file, "r") as file:
                resource_manifest = file.read()

            # Deserialize the YAML content into a Python dictionary
            resource_definition = yaml.safe_load(resource_manifest)
            if resource_type.lower() == "operator group":
                resource_definition["apiVersion"] = "operators.coreos.com/v1"

            # Determine the API method based on the resource type
            if resource_type.lower() == "custom resource definition":
                api_method = self._extensions_v1.create_custom_resource_definition
                api_patch_method = self._extensions_v1.patch_custom_resource_definition
            elif resource_type.lower() == "cluster role binding":
                api_method = self._rbac_v1.create_cluster_role_binding
                api_patch_method = self._rbac_v1.patch_cluster_role_binding
            elif resource_type.lower() == "role binding":
                if namespace:
                    api_method = self._rbac_v1.create_namespaced_role_binding
                    api_patch_method = self._rbac_v1.patch_namespaced_role_binding
            elif resource_type.lower() == "cluster role":
                api_method = self._rbac_v1.create_cluster_role
                api_patch_method = self._rbac_v1.patch_cluster_role
            elif resource_type.lower() == "role":
                if namespace:
                    api_method = self._rbac_v1.create_namespaced_role
                    api_patch_method = self._rbac_v1.patch_namespaced_role
            elif resource_type.lower() == "service account":
                api_method = self._core_v1.create_namespaced_service_account
                api_patch_method = self._core_v1.patch_namespaced_service_account
            elif resource_type.lower() == "catalog source":
                if namespace:
                    api_method = self._custom_api.create_namespaced_custom_object
                    group = "operators.coreos.com"
                    version = "v1alpha1"
                    plural = "catalogsources"
                    api_patch_method = self._custom_api.patch_namespaced_custom_object
            elif resource_type.lower() == "operator group":
                if namespace:
                    api_method = self._custom_api.create_namespaced_custom_object
                    group = "operators.coreos.com"
                    version = "v1"
                    plural = "operatorgroups"
                    api_patch_method = self._custom_api.patch_namespaced_custom_object
            elif resource_type.lower() == "subscription":
                if namespace:
                    api_method = self._custom_api.create_namespaced_custom_object
                    group = "operators.coreos.com"
                    version = "v1alpha1"
                    plural = "subscriptions"
                    api_patch_method = self._custom_api.patch_namespaced_custom_object

            elif resource_type.lower() == "deployment":
                if namespace:
                    api_method = self._apps_v1.create_namespaced_deployment
                    api_patch_method = self._apps_v1.patch_namespaced_deployment

            elif resource_type.lower() == "custom resource":
                if namespace:
                    api_method = self._custom_api.create_namespaced_custom_object
                    group = "fncm.ibm.com"
                    version = "v1"
                    plural = "fncmclusters"
                    api_patch_method = self._custom_api.patch_namespaced_custom_object

            else:
                self._logger.info(f"Resource type '{resource_type}' is not supported.")
                return False

            # Create the resource
            if namespace:
                if resource_type.lower() in ["catalog source", "operator group", "subscription", "custom resource"]:
                    api_response = api_method(body=resource_definition, namespace=namespace, group=group,
                                              version=version, plural=plural)
                else:
                    api_response = api_method(body=resource_definition, namespace=namespace)
            else:
                api_response = api_method(body=resource_definition)

            return True

        except client.ApiException as e:
            if e.status == 409:
                if namespace:
                    if resource_type.lower() in ["catalog source", "operator group", "subscription", "custom resource"]:
                        api_patch_method(
                            body=resource_definition,
                            name=resource_definition["metadata"]["name"], namespace=namespace, group=group,
                            plural=plural, version=version,
                        )
                    else:
                        api_patch_method(
                            body=resource_definition,
                            name=resource_definition["metadata"]["name"], namespace=namespace,
                        )
                else:
                    api_patch_method(
                        body=resource_definition,
                        name=resource_definition["metadata"]["name"],
                    )
                return True
            else:
                return False
        except Exception as e:
            return False

    def get_node_top(self):
        try:
            node = self.custom_api.list_cluster_custom_object(
                group="metrics.k8s.io", version="v1beta1", plural="nodes", pretty="true"
            )
            return node
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_node_top: {e}")
            return {}

    def get_nodes(self):
        try:
            nodes = self.core_v1.list_node()
            return nodes
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_nodes: {e}")
            return {}

    def get_events(self, namespace):
        try:
            version_response = self.core_v1.list_namespaced_event(namespace=namespace)
            return version_response
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_events: {e}")
            return {}

    def describe_pod(self, pod_name, namespace):
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            return pod
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_pod: {e}")
            return {}

    def describe_deployment(self, deployment_name, namespace):
        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name, namespace=namespace, pretty='true'
            )
            return deployment
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_deployment: {e}")
            return {}

    def describe_configmap(self, configmap_name, namespace):
        try:
            configmap = self.core_v1.read_namespaced_config_map(
                name=configmap_name, namespace=namespace,
            )
            return configmap
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_configmap: {e}")
            return {}

    def describe_pvc(self, pvc_name, namespace):
        try:
            pvc = self.core_v1.read_namespaced_persistent_volume_claim(
                name=pvc_name, namespace=namespace,
            )
            return pvc
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_pvc: {e}")
            return {}

    def describe_service(self, service_name, namespace):
        try:
            service = self.core_v1.read_namespaced_service(
                name=service_name, namespace=namespace,
            )
            return service
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_service: {e}")
            return {}

    def describe_ingress(self, ingress_name, namespace):
        try:
            ingress = self.networking_v1.read_namespaced_ingress(
                name=ingress_name, namespace=namespace,
            )
            return ingress
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_ingress: {e}")
            return {}

    def describe_network_policy(self, network_policy_name, namespace):
        try:
            network_policy = self.networking_v1.read_namespaced_network_policy(
                name=network_policy_name, namespace=namespace,
            )
            return network_policy
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_network_policy: {e}")
            return {}

    def describe_route(self, route_name, namespace):
        try:
            route = self.custom_api.get_namespaced_custom_object(
                "route.openshift.io",
                "v1",
                namespace,
                "routes",
                route_name,
            )
            return route
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_route: {e}")
            return {}

    def describe_secret(self, secret_name, namespace, progress=None):
        try:
            secret = self.core_v1.read_namespaced_secret(
                name=secret_name, namespace=namespace,
            )
            return secret
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_secret: {e}")
            if progress:
                progress.log(Text(f"Secret not found: {secret_name}", style="bold red"))
                progress.log()
            return {}

    # Function to collect init-container logs
    def get_init_container_logs(self, pod_name, namespace, ini_container):
        try:
            logs = self.core_v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, container=ini_container)
            return logs
        except Exception as e:
            return ""

    def pod_exec(self, pod_name, namespace, command):
        try:
            exec_command = command
            resp = stream(
                self.core_v1.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                command=exec_command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    stdout = resp.read_stdout()
                if resp.peek_stderr():
                    stdout = resp.read_stderr()
            return stdout
        except Exception as e:
            self._logger.info(f"Unable to execute command {e}")

    def create_namespace(self, namespace):
        try:
            # Create a namespace
            body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
            self._core_v1.create_namespace(body)
            return True
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the create_namespace: {e}")
            return False

    # Function to get Operator Group details
    def describe_operator_group(self, name, namespace):
        try:
            og = self._custom_api.read_namespaced_custom_object(
                group="operators.coreos.com",
                version="v1",
                namespace=namespace,
                plural="operatorgroups",
                name=name,
            )
            return og
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_operator_group: {e}")
            return {}

    # Function to get operator group details
    def get_operator_group(self, namespace):
        group = "operators.coreos.com"
        version = "v1"
        plural = "operatorgroups"
        # List Role objects in the specified namespace
        try:
            og = self._custom_api.list_namespaced_custom_object(group=group, version=version, plural=plural,
                                                                namespace=namespace)
            for group in og.get('items', []):
                if "FNCMCluster" in group["metadata"]['annotations']['olm.providedAPIs']:
                    return group["metadata"]['name']

            return ""
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_operator_group: {e}")
            return ""

    def get_rolename(self, namespace):
        try:
            roles = self._rbac_v1.list_namespaced_role(namespace=namespace)
            for role in roles.items:
                if "ibm-fncm-operator" in role.metadata.name:
                    name = role.metadata.name
                    return name

            return ""
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_rolename: {e}")
            return ""

    def get_rolebinding(self, namespace):
        try:
            rolebindings = self._rbac_v1.list_namespaced_role_binding(namespace=namespace)
            for rolebind in rolebindings.items:
                if "ibm-fncm-operator" in rolebind.metadata.name:
                    name = rolebind.metadata.name
                    return name

            return ""
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_rolebinding: {e}")
            return ""

    def get_service_account(self, namespace):
        try:
            service_accounts = self._core_v1.list_namespaced_service_account(namespace=namespace)
            for sa in service_accounts.items:
                if "ibm-fncm-operator" in sa.metadata.name:
                    name = sa.metadata.name
                    return name

            return ""
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_service_account: {e}")
            return ""

    def delete_operator_group(self, namespace, name):
        try:
            self._custom_api.delete_namespaced_custom_object(
                group="operators.coreos.com", version="v1", namespace=namespace, plural="operatorgroups", name=name
            )
            self._logger.info(f"Operator Group '{name}' deleted successfully in namespace '{namespace}'.")
            return True
        except client.ApiException as e:
            self._logger.info(f"Error in utilities.py from the delete_subscription: {e}")
            return False

    def get_version(self):
        try:
            version_response = self.version_v1.get_code()
            return version_response
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_version: {e}")
            return {}

    def describe_csv(self, csv_name, namespace):
        try:
            csv = self.custom_api.get_namespaced_custom_object(
                group="operators.coreos.com",
                version="v1alpha1",
                namespace=namespace,
                plural="clusterserviceversions",
                name=csv_name,
            )
            return csv
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_csv: {e}")
            return {}

    def parse_operator_deployment(self, deployment, namespace):
        try:
            # Extract the important information from the Deployment
            name = deployment.metadata.name
            operator_deployment_details = {"deployment": name, "namespace": namespace,
                                           "replicas": deployment.spec.replicas,
                                           "image": deployment.spec.template.spec.containers[0].image,
                                           "pods": self.get_pod_names_for_deployment(namespace, name),
                                           "init_containers": self.get_init_containers_for_deployment(namespace, name),
                                           "type": "YAML",
                                           "release": deployment.spec.template.metadata.labels["release"]}

            if deployment.metadata.owner_references:
                for owner in deployment.metadata.owner_references:
                    if owner.kind == "ClusterServiceVersion":
                        operator_deployment_details["type"] = "OLM"

            return operator_deployment_details
        except Exception as e:
            self._logger.info(f"Error in kubernetes_utilities.py from the parse_operator_deployment: {e}")
            return {}

    # function to check if namespace exists
    def check_namespace_exists(self, namespace):
        try:
            self._core_v1.read_namespace(name=namespace)
            return True
        except client.ApiException as e:
            if e.status == 404:
                return False
            else:
                print(f"An error occurred: {e}")
                exit(0)

    # Function to describe the role
    def describe_role(self, namespace, name=""):
        try:
            role = self._rbac_v1.read_namespaced_role(name=name, namespace=namespace)

            return role
        except client.ApiException as e:
            if e.status == 404:
                return False

    # Function to get the service account
    def describe_service_account(self, namespace, name=""):
        try:
            service_account = self._core_v1.read_namespaced_service_account(name=name, namespace=namespace)

            return service_account
        except client.ApiException as e:
            if e.status == 404:
                return False

    # Function to get the rolebinding
    def descibe_rolebinding(self, namespace, name=""):
        try:
            rolebinding = self._rbac_v1.read_namespaced_role_binding(name=name, namespace=namespace)

            return rolebinding
        except ApiException as e:
            if e.status == 404:
                return False


    # Function to collect operator details
    def get_operator_details(self, namespace, deployment_name="ibm-fncm-operator"):
        try:

            operator_details = {}

            # Get the deployment object
            deployment = self._apps_v1.read_namespaced_deployment(deployment_name, namespace)

            if not deployment:
                return {}

            operator_details.update(self.parse_operator_deployment(deployment, namespace))

            # Check if OLM install
            if operator_details["type"] == "OLM":
                # Get the Subscription object
                subscription = self.describe_subscription(namespace=namespace)
                operator_details.update(self.parse_subscription(subscription))

                # Add Operator Group name
                operator_details["operatorGroup"] = self.get_operator_group(namespace)
            else:
                # Add Permissions
                operator_details["role"] = self.get_rolename(namespace)
                operator_details["rolebinding"] = self.get_rolebinding(namespace)
                operator_details["service_account"] = self.get_service_account(namespace)

            self._operator_details = operator_details
            return operator_details

        except Exception as e:
            # self._logger.info(f"Error in kubernetes_utilities.py from the get_operator_details: {e}")
            return {}

    # Function to get CR file from a FNCM deployment
    def get_deployment_cr(self, namespace, logger=None):
        # Attempt to list the CR in the specific namespace
        try:
            cr_details = self._custom_api.list_namespaced_custom_object(group="fncm.ibm.com", version="v1",
                                                                        namespace=namespace,
                                                                        plural="fncmclusters")
            cr = cr_details["items"][0]

            if len(cr) == 0:
                return {}
            else:
                # Remove unused sections from the CR
                remove_fields = ["creationTimestamp",
                                 "generation",
                                 "resourceVersion",
                                 "uid",
                                 "managedFields"]
                for field in remove_fields:
                    if field in cr["metadata"].keys():
                        del cr["metadata"][field]
                if "annotations" in cr["metadata"].keys():
                    if 'kubectl.kubernetes.io/last-applied-configuration' in cr["metadata"]["annotations"]:
                        del cr["metadata"]["annotations"]['kubectl.kubernetes.io/last-applied-configuration']
                    if not cr["metadata"]["annotations"]:
                        del cr["metadata"]["annotations"]
                self._custom_resource = cr
                self.parse_cr()
                return cr
        except ApiException as e:
            if e.status == 404:
                self._logger.info(f"No Custom Resource file found in '{namespace}'.")
                return {}
        except Exception as e:
            self._logger.info("Error while checking for Custom Resource file : " + str(e))
            return {}

    def scale_operator_deployment(self, namespace, deployment_name, scale="down"):
        try:
            # Retrieve the deployment object
            deployment = self._apps_v1.read_namespaced_deployment(deployment_name, namespace)

            # Patch the deployment object
            self._apps_v1.patch_namespaced_deployment_scale(
                name=deployment.metadata.name,
                namespace=namespace,
                body={"spec": {"replicas": 0}}
            )
            return True
        except Exception as e:
            self._logger.info(f"Error in scaling operator deployment: {e}")
            return False

    # Function to scale down pods
    def scale_pods_in_namespace(self, namespace, deployments, scale="down"):
        if scale == "down":
            try:
                for deployment in deployments:
                    # Scale down each pod to 0 replicas
                    if deployment.metadata.name != "ibm-fncm-operator":
                        self._apps_v1.patch_namespaced_deployment_scale(
                            name=deployment.metadata.name,
                            namespace=namespace,
                            body={"spec": {"replicas": 0}}
                        )

            except Exception as e:
                self._logger.info(f"Error in scaling down pods function: {e}")
        else:
            try:
                # List all pods in the namespace
                deployments = self._apps_v1.list_namespaced_deployment(namespace=namespace).items

                for deployment in deployments:
                    # Scale down each pod to 0 replicas
                    if deployment.metadata.name == "ibm-fncm-operator":
                        self._apps_v1.patch_namespaced_deployment_scale(
                            name=deployment.metadata.name,
                            namespace=namespace,
                            body={"spec": {"replicas": 1}}
                        )

            except Exception as e:
                self._logger.info(f"Error in scaling up pods function: {e}")

    def get_deployments_by_owner_reference(self, namespace, owner_reference_name):

        try:
            # List deployments in the specified namespace
            deployments = self._apps_v1.list_namespaced_deployment(namespace)

            # Filter deployments based on owner reference name
            filtered_deployments = [deployment for deployment in deployments.items
                                    if deployment.metadata.owner_references
                                    and any(
                    owner.name == owner_reference_name for owner in deployment.metadata.owner_references)]

            return filtered_deployments

        except Exception as e:
            self._logger.info(f"Error in get_deployments_by_owner_reference function: {e}")

    # Function to collect init-containers names from a deployment
    def get_init_containers_for_deployment(self, namespace, deployment_name):
        try:
            # Retrieve the deployment object
            deployment = self._apps_v1.read_namespaced_deployment(deployment_name, namespace)
            # Get the init containers for the deployment
            init_containers = deployment.spec.template.spec.init_containers

            if not init_containers:
                return []

            return [container.name for container in init_containers]

        except Exception as e:
            self._logger.info(f"Error getting init-containers for deployment: {e}")

    def get_pods_for_deployment(self, namespace, deployment_name):
        try:
            # Retrieve the deployment object
            deployment = self._apps_v1.read_namespaced_deployment(deployment_name, namespace)
            # Get the label selector for the deployment
            label_selector = ",".join(
                [f"{key}={value}" for key, value in deployment.spec.selector.match_labels.items()])
            # Use the label selector to list pods with matching labels
            pods = self._core_v1.list_namespaced_pod(namespace, label_selector=label_selector)

            return pods.items

        except Exception as e:
            self._logger.info(f"Error getting pods for deployment: {e}")

    # Get pods names for a deployment
    def get_pod_names_for_deployment(self, namespace, deployment_name):

        try:
            # Retrieve the deployment object
            deployment = self._apps_v1.read_namespaced_deployment(deployment_name, namespace)
            # Get the label selector for the deployment
            label_selector = ",".join(
                [f"{key}={value}" for key, value in deployment.spec.selector.match_labels.items()])
            # Use the label selector to list pods with matching labels
            pods = self._core_v1.list_namespaced_pod(namespace, label_selector=label_selector)

            return [pod.metadata.name for pod in pods.items]

        except Exception as e:
            self._logger.info(f"Error getting pods for deployment: {e}")
