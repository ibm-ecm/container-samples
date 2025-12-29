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

import io
import tarfile
import warnings

import urllib3
import yaml
from kubernetes import config, client
from kubernetes.client import ApiException
from kubernetes.stream import stream
from requests.exceptions import ConnectTimeout, ConnectionError
from rich.text import Text
from time import sleep


class KubernetesUtilities:
    def __init__(self, logger=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._logger = logger
        self._current_namespace = None

        try:
            config.load_incluster_config()
            self._in_cluster = True
            self._current_namespace = self.get_current_namespace()
            self._logger.info("Running inside the cluster.")
            self._logger.info(f"Current namespace: {self._current_namespace}")
        except Exception:
            self._in_cluster = False
            config.load_kube_config()
            self._current_context = config.list_kube_config_contexts()[1]
            self._current_namespace = self.get_current_namespace()
            self._logger.info("Running outside the cluster.")
            self._logger.info(f"Current context: {self._current_namespace}")


        self._core_v1 = client.CoreV1Api()
        self._apps_v1 = client.AppsV1Api()
        self._policy_v1 = client.PolicyV1Api()
        self._rbac_v1 = client.RbacAuthorizationV1Api()
        self._networking_v1 = client.NetworkingV1Api()
        self._auto_scaling_v2 = client.AutoscalingV2Api()
        self._custom_api = client.CustomObjectsApi()
        self._storage_v1 = client.StorageV1Api()
        self._extensions_v1 = client.ApiextensionsV1Api()
        self._version_v1 = client.VersionApi()
        self._custom_resource = {}
        self._cr_details = {}
        self._operator_details = {}

        self._resource_type_dict = {}

    @property
    def in_cluster(self):
        return self._in_cluster

    @property
    def current_namespace(self):
        return self._current_namespace

    @property
    def resource_type_dict(self):
        return self._resource_type_dict

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
    def policy_v1(self):
        return self._policy_v1

    @property
    def networking_v1(self):
        return self._networking_v1

    @property
    def auto_scaling_v2(self):
        return self._auto_scaling_v2

    @property
    def custom_api(self):
        return self._custom_api

    @property
    def extensions_v1(self):
        return self._extensions_v1

    @property
    def version_v1(self):
        return self._version_v1

    # Common function to get current namespace when running in-cluster
    def get_current_namespace(self):
        try:
            # Check if inside or outside the cluster
            if self._in_cluster:
                self._logger.info("Getting namespace from in-cluster service account")
                # Read the namespace from the service account secret
                with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
                    namespace = f.read().strip()
                self._logger.info(f"In-cluster namespace: {namespace}")
            else:
                self._logger.info("Not running inside the cluster.")
                namespace = self._current_context['context']['namespace']
                self._logger.info(f"Current context namespace: {namespace}")

            return namespace
        except Exception as e:
            self._logger.info(f"Error getting namespace: {e}")
            return None

    # Function to collect all user-created configmaps
    def calculate_user_configmaps(self, components=list):
        configmaps = set()
        cr = self._custom_resource
        cr_keys = cr["spec"].keys()

        # Collect configmaps from ecm_configuration
        ecm_components = ["cpe", "css", "cmis", "graphql", "es", "tm"]

        if any(e in ecm_components for e in components):
            try:
                for component in ecm_components:
                    section_name = f"{component}_production_setting"
                    if cr["spec"]["ecm_configuration"][component][section_name].get("custom_configmap"):
                        for item in cr["spec"]["ecm_configuration"][component][section_name]["custom_configmap"]:
                            if "name" in item.keys():
                                configmaps.add(item["name"])
                    else:
                        self._logger.info(f"No {component} Configmaps found")
            except Exception as e:
                self._logger.info(f"No ECM Configmaps found")

        # Collect configmaps from ban
        try:
            if "ban" in components:
                if cr["spec"]["navigator_configuration"]["icn_production_setting"].get("custom_configmap"):
                    for item in cr["spec"]["navigator_configuration"]["icn_production_setting"]["custom_configmap"]:
                        if "name" in item.keys():
                            configmaps.add(item["name"])
            else:
                self._logger.info(f"No BAN Configmaps found")
        except Exception as e:
            self._logger.info(f"No BAN Configmaps found")

        # Collect configmaps from ier
        try:
            if "ier" in components:
                if cr["spec"]["ier_configuration"]["ier_production_setting"].get("custom_configmap"):
                    for item in cr["spec"]["ier_configuration"]["ier_production_setting"]["custom_configmap"]:
                        if "name" in item.keys():
                            configmaps.add(item["name"])
            else:
                self._logger.info(f"No IER Configmaps found")
        except Exception as e:
            self._logger.info(f"No IER Configmaps found")

        # Collect configmaps from iccsap
        try:
            if "iccsap" in components:
                if cr["spec"]["iccsap_configuration"]["iccsap_production_setting"].get("custom_configmap"):
                    for item in cr["spec"]["iccsap_configuration"]["iccsap_production_setting"]["custom_configmap"]:
                        if "name" in item.keys():
                            configmaps.add(item["name"])
            else:
                self._logger.info(f"No ICCSAP Configmaps found")
        except Exception as e:
            self._logger.info(f"No ICCSAP Configmaps found")

        return list(configmaps)

    # Function to collect all user-created secrets
    def calculate_user_secrets(self, components=list):
        secrets = set()
        cr = self._custom_resource
        cr_keys = cr["spec"].keys()

        # Collect different sections from the CR
        # LDAP Secrets
        # Get all LDAP Sections
        result = filter(lambda x: str(x).startswith("ldap_configuration"), cr_keys)
        ldap_sections = list(result)
        for section in ldap_sections:
            if cr["spec"][section].get("lc_bind_secret"):
                secrets.add(cr["spec"][section]["lc_bind_secret"])

            if cr["spec"][section].get("lc_ldap_ssl_enabled"):
                if cr["spec"][section]["lc_ldap_ssl_enabled"]:
                    secrets.add(cr["spec"][section]["lc_ldap_ssl_secret_name"])

        # DB Secrets
        db_ssl = False
        if cr["spec"]['datasource_configuration'].get("dc_ssl_enabled"):
            if cr["spec"]['datasource_configuration']["dc_ssl_enabled"]:
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
            try:
                if cr["spec"]["ecm_configuration"].get("fncm_secret_name"):
                    secrets.add(cr["spec"]["ecm_configuration"].get("fncm_secret_name"))
                else:
                    secrets.add("ibm-fncm-secret")
            except Exception as e:
                self._logger.info(f"No ECM Secret found")
                secrets.add("ibm-fncm-secret")

        # CSS Secrets
        try:
            if "css" in components:
                if cr["spec"]["ecm_configuration"]["css"]["css_production_setting"].get("icc"):
                    if cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"].get("icc_enabled"):
                        if cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"]["icc_enabled"]:
                            secrets.add(cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                                            "icc_secret_name"])
                            secrets.add(cr["spec"]["ecm_configuration"]["css"]["css_production_setting"]["icc"][
                                            "secret_masterkey_name"])
        except Exception as e:
            self._logger.info(f"No ICC Secret found")

        # BAN Secrets
        try:
            if "ban" in components:
                if cr["spec"]["navigator_configuration"].get("ban_secret_name"):
                    secrets.add(cr["spec"]["navigator_configuration"].get("ban_secret_name"))
        except Exception as e:
            self._logger.info(f"No BAN Secret found")
            secrets.add("ibm-ban-secret")

        # IER Secrets
        try:
            if "ier" in components:
                if cr["spec"]["ier_configuration"].get("ier_secret_name"):
                    secrets.add(cr["spec"]["ier_configuration"].get("ier_secret_name"))
                else:
                    secrets.add("ibm-ier-secret")
        except Exception as e:
            self._logger.info(f"No IER Secret found")
            secrets.add("ibm-ier-secret")

        # ICCSAP Secrets
        try:
            if "iccsap" in components:
                if cr["spec"]["iccsap_configuration"].get("iccsap_secret_name"):
                    secrets.add(cr["spec"]["iccsap_configuration"].get("iccsap_secret_name"))
                else:
                    secrets.add("ibm-iccsap-secret")
        except Exception as e:
            self._logger.info(f"No ICCSAP Secret found")
            secrets.add("ibm-iccsap-secret")

        # Trusted Certificates
        try:
            if cr["spec"]["shared_configuration"].get("trusted_certificate_list"):
                for cert_secret in cr["spec"]["shared_configuration"]["trusted_certificate_list"]:
                    secrets.add(cert_secret)
        except Exception as e:
            self._logger.info(f"No trusted certificates found")

        # OIDC Secrets
        try:
            if cr["spec"]["shared_configuration"].get("open_id_connect_providers"):
                for item in cr["spec"]["shared_configuration"]["open_id_connect_providers"]:
                    if "client_oidc_secret" in item.keys():
                        for secret in item["client_oidc_secret"].values():
                            secrets.add(secret)
        except Exception as e:
            self._logger.info(f"No OIDC Secrets found")

        # SCIM Secrets
        try:
            if cr["spec"]["initialize_configuration"].get("scim_configuration"):
                for item in cr["spec"]["initialize_configuration"]["scim_configuration"]:
                    secrets.add(item["scim_secret_name"])
        except Exception as e:
            self._logger.info(f"No SCIM Secrets found")

        return list(secrets)

    # Function to calculate the deployed components
    def calculate_deployed_components(self):
        try:
            components = set()
            cr = self._custom_resource
            cr_keys = cr["spec"].keys()

            # TODO: Validate component names

            # Collect different sections from the CR

            if "content_optional_components" in cr_keys:
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
            if "ecm_configuration" in cr_keys:
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

            if "navigator_configuration" in cr_keys:
                components.add("ban")

            if "ier_configuration" in cr_keys:
                components.add("ier")

            if "iccsap_configuration" in cr_keys:
                components.add("iccsap")

            return list(components)

        except Exception as e:
            self._logger.info(f"Error calculating deployed components: {e}")
            return {}

    # Function to check the status of catalog source upgrade rollout
    def check_catalogsource_rollout_status(self, name="ibm-fncm-operator-catalog", namespace=""):
        try:
            catalog_source = self._custom_api.get_namespaced_custom_object(
                group="operators.coreos.com",
                version="v1alpha1",
                namespace=namespace,
                plural="catalogsources",
                name=name
            )
            status = catalog_source.get("status", {})
            connection = status.get("connectionState", {})

            self._logger.info(f"Catalog source '{name}' status: {connection}")

            if connection.get("lastObservedState").lower() in ["ready", "healthy", "idle"]:
                return True

            return False
        except Exception as e:
            self._logger.info(f"Error checking catalog source rollout status: {e}")
            return False

    # Function to check the status of a deployment upgrade rollout
    def check_deployment_rollout_status(self, deployment_name, namespace):
        try:
            deployment = self._apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
            status = deployment.status
            spec = deployment.spec

            self._logger.info(f"Deployment '{deployment_name}' status: {status}\n"
                              f"Replicas Spec: {spec.replicas}")

            if (status.updated_replicas == spec.replicas and
                status.replicas == spec.replicas and
                status.available_replicas == spec.replicas and
                status.observed_generation >= deployment.metadata.generation):
                    return True

            return False
        except Exception as e:
            self._logger.info(f"Error checking deployment rollout status: {e}")
            return False

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
            # DBACLD-157604 added the mapping for 24.0.1
            versions = {
                "21.0.3": "5.5.8",
                "22.0.1": "5.5.9",
                "22.0.2": "5.5.10",
                "23.0.1": "5.5.11",
                "23.0.2": "5.5.12",
                "24.0.0": "5.6.0",
                "24.0.1": "5.6.0",
                "25.0.0": "5.7.0"
            }

            # Making sure there is always a version value
            if cr_details["appVersion"] in versions:
                cr_details["version"] = versions[cr_details["appVersion"]]
            else:
                cr_details["version"] = "Unknown"

            cr_details["storage_classes"] = self.extract_storage_classes()

            # Extract User Secrets
            cr_details["user_secrets"] = self.calculate_user_secrets(components)

            # Extract User Configmaps
            cr_details["user_configmaps"] = self.calculate_user_configmaps(components)

            self._cr_details = cr_details
            return cr_details
        except Exception as e:
            self._logger.info(f"Error parsing CR: {e}")
            self._cr_details = cr_details
            return cr_details

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
            auto_scaling_v2_resource_types = ["horizontal_pod_autoscaler"]
            policy_v1_resource_types = ["pod_disruption_budget"]
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
                        # Check if owner references exist
                        reference = item["metadata"].get("ownerReferences", None)
                        if reference is not None:
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

            for resource_type in policy_v1_resource_types:
                resource_type_dict[resource_type] = []
                try:
                    response = getattr(
                        self._policy_v1,
                        f"list_namespaced_{resource_type}"
                    )(namespace=namespace)

                    for item in response.items:
                        if item.metadata.owner_references is not None:
                            if item.metadata.owner_references[0].name == filter:
                                resource_type_dict[resource_type].append(item.metadata.name)

                        if item.metadata.labels is not None:
                            if item.metadata.labels.get("app.kubernetes.io/instance") == filter:
                                resource_type_dict[resource_type].append(item.metadata.name)

                    resource_type_dict[resource_type] = list(
                        set(resource_type_dict[resource_type])
                    )

                except client.exceptions.ApiException as e:
                    self._logger.info(f"Error listing {resource_type}: {e}")

            for resource_type in auto_scaling_v2_resource_types:
                resource_type_dict[resource_type] = []
                try:
                    response = getattr(self._auto_scaling_v2, f"list_namespaced_{resource_type}")(namespace=namespace)
                    for item in response.items:
                        if item.metadata.owner_references is not None:
                            if item.metadata.owner_references[0].name == filter:
                                resource_type_dict[resource_type].append(item.metadata.name)
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
            
            self._resource_type_dict = resource_type_dict
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
                "subscription": subscription["metadata"].get("name", ""),
                "namespace": subscription["metadata"].get("namespace", ""),
                "installedCSV": subscription["status"].get("installedCSV", ""),
                "catalogSource": subscription["spec"].get("source", ""),
                "channel": subscription["spec"].get("channel", ""),
                "sourceNamespace": subscription["spec"].get("sourceNamespace",),
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

    def delete_secret (self, namespace="", name=""):
        try:
            # Delete the Secret
            self._core_v1.delete_namespaced_secret(name, namespace)
            self._logger.info(f"Secret {name} deleted successfully")

        except Exception as e: 
            self._logger.info(f"Error in utilities.py from the delete_secret: {e}")
            

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

    # Get the Kubernetes server version
    def get_kubernetes_version(self):
        try:

            connected = True
            # Get the server version information
            server_version = self._version_v1.get_code(_request_timeout=10)

            if server_version:
                connected = True
                self._logger.info(f"Connected to kubernetes cluster successfully.")
                self._logger.info(f"Kubernetes Server Major Version: {server_version.major}")
                self._logger.info(f"Kubernetes Server Minor Version: {server_version.minor}")
                self._logger.info(f"Kubernetes Server Git Version: {server_version.git_version}")
                self._logger.info(f"Kubernetes Server Platform: {server_version.platform}")

                return server_version.git_version, connected

            else:
                connected = False
                self._logger.info(f"Could not connect to kubernetes cluster.")
                return "Unknown", connected

        except (ConnectTimeout, ConnectionError) as e:
            connected = False
            self._logger.info(f"Could not connect to kubernetes cluster: {e}")
            return "Unknown", connected
        except Exception as e:
            connected = False
            self._logger.info(f"Error in utilities.py from the get_kubernetes_version: {e}")
            return "Unknown", connected

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
            elif resource_type.lower() == "network_policy":
                if namespace:
                    api_method = self._networking_v1.create_namespaced_network_policy
                    api_patch_method = self._networking_v1.patch_namespaced_network_policy
            elif resource_type.lower() == "image policy":
                api_method = self._custom_api.create_cluster_custom_object
                group = "operator.openshift.io"
                version = "v1alpha1"
                plural = "ImageContentSourcePolicy"
                api_patch_method = self._custom_api.patch_namespaced_custom_object
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

            elif resource_type.lower() == 'pvc':
                if namespace:
                    api_method = self._core_v1.create_namespaced_persistent_volume_claim
                    api_patch_method = self._core_v1.patch_namespaced_persistent_volume_claim

            elif resource_type.lower() == 'secret':
                if namespace:
                    api_method = self._core_v1.create_namespaced_secret
                    api_patch_method = self._core_v1.patch_namespaced_secret

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

    # Function to describe horizontal pod autoscaler
    def describe_hpa(self, hpa_name, namespace):
        try:
            hpa = self.auto_scaling_v2.read_namespaced_horizontal_pod_autoscaler(
                name=hpa_name, namespace=namespace,
            )
            return hpa
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the describe_hpa: {e}")
            return {}
        
    # Function to describe PodDisruptionBudget
    def describe_pdb(self, pdb_name, namespace):
        try:
            pdb = self.policy_v1.read_namespaced_pod_disruption_budget(
                name=pdb_name,
                namespace=namespace,
            )
            return pdb
        except Exception as e:
            self._logger.info(
                f"Error in utilities.py from the describe_pdb: {e}"
            )
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
    
    def remove_network_policy_owner_reference(self, progress, network_policy_name, namespace):
        try:
            policy = self.networking_v1.read_namespaced_network_policy(
                name=network_policy_name, namespace=namespace,
            )
            if policy.metadata.owner_references:
                body = {
                    "metadata": {
                        "ownerReferences": None
                    }
                }
                self.networking_v1.patch_namespaced_network_policy(
                    name=policy.metadata.name,
                    namespace=namespace,
                    body=body,
                )
                progress.log(f"Owner references has been removed in  {network_policy_name}")
                progress.log()
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

    # Function to collect container logs
    def get_container_logs(self, pod_name, namespace, container):
        try:
            logs = self.core_v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, container=container)
            return logs
        except Exception as e:
            return ""

    # Function to collect pod metrics
    def get_pod_metrics(self, pod_name, namespace):
        try:
            metrics = self.custom_api.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
                name=pod_name,
            )
            return metrics
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the get_pod_metrics: {e}")
            return {}

    # Function to collect pod events
    def get_pod_events(self, pod_name, namespace):
        try:
            field_selector = f'involvedObject.name={pod_name}'
            events = self.core_v1.list_namespaced_event(namespace=namespace, field_selector=field_selector)
            return events
        except Exception as e:
            return ""

    # Function to collect init-container logs
    def get_init_container_logs(self, pod_name, namespace, ini_container):
        try:
            logs = self.core_v1.read_namespaced_pod_log(name=pod_name, namespace=namespace, container=ini_container)
            return logs
        except Exception as e:
            return ""

    def pod_exec(self, pod_name, namespace, command):
        try:
            self._logger.info(f"Executing command {command} in pod {pod_name}")
            self._logger.info(f"Namespace: {namespace}")
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
            og = self._custom_api.get_namespaced_custom_object(
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

    # Function to list all Operator Groups in a namespace
    def list_operator_groups(self, namespace):
        try:
            ogs = self._custom_api.list_namespaced_custom_object(
                group="operators.coreos.com",
                version="v1",
                namespace=namespace,
                plural="operatorgroups"
            )
            return ogs.get('items', [])
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the list_operator_groups: {e}")
            return []


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
                    return group["metadata"]['name'], group["metadata"]['annotations']['olm.providedAPIs']

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


    # Function to check if PVC is bound
    def check_pvc_bound(self, namespace, pvc_name):
        try:
            pvc = self._core_v1.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)
            if pvc.status.phase == "Bound":
                return True
            else:
                return False
        except client.ApiException as e:
            if e.status == 404:
                return False
            else:
                self._logger.info(f"Error in utilities.py from the check_pvc_bound: {e}")
                return False


    # Function to list all storage classes
    def list_storage_classes(self):
        try:
            storage_classes = self._storage_v1.list_storage_class()

            # Print the names of the storage classes
            storage_classes = [sc.metadata.name for sc in storage_classes.items]
            return storage_classes
        except Exception as e:
            self._logger.info(f"Error in utilities.py from the list_storage_classes: {e}")
            return {}

    def delete_pvc(self, namespace, name):
        try:
            self._core_v1.delete_namespaced_persistent_volume_claim(name=name, namespace=namespace)
            self._logger.info(f"PVC '{name}' deleted successfully in namespace '{namespace}'.")
            return True
        except client.ApiException as e:
            self._logger.info(f"Error in utilities.py from the delete_pvc: {e}")
            return False

    def delete_catalog_source(self, namespace, name):
        try:
            self._custom_api.delete_namespaced_custom_object(
                group="operators.coreos.com", version="v1alpha1", namespace=namespace, plural="catalogsources", name=name
            )
            self._logger.info(f"Catalog Source '{name}' deleted successfully in namespace '{namespace}'.")
            return True
        except client.ApiException as e:
            self._logger.info(f"Error in utilities.py from the delete_catalog_source: {e}")
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
                                           "release": deployment.spec.template.metadata.labels.get("release", "5.7.0")}

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
            if e.status == 403:
                if self._in_cluster:
                    self._logger.info("Namespace is where the pod is running")
                    return True
                return False
            if e.status == 404:
                return False
            else:
                print(f"An error occurred: {e}")
                exit(0)

    # Function to describe the role
    def describe_role(self, name, namespace):
        try:
            role = self._rbac_v1.read_namespaced_role(name=name, namespace=namespace)

            return role
        except client.ApiException as e:
            if e.status == 404:
                return False

    # Function to describe the rolebinding
    def describe_role_binding(self, name, namespace):
        try:
            rolebinding = self._rbac_v1.read_namespaced_role_binding(name=name, namespace=namespace)

            return rolebinding
        except client.ApiException as e:
            if e.status == 404:
                return False

    # Function to get the service account
    def describe_service_account(self, name, namespace):
        try:
            service_account = self._core_v1.read_namespaced_service_account(name=name, namespace=namespace)

            return service_account
        except client.ApiException as e:
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
                operator_details["operatorGroup"], operator_details["providedAPIs"] = self.get_operator_group(namespace)

            # Add Permissions
            operator_details["role"] = self.get_rolename(namespace)
            operator_details["rolebinding"] = self.get_rolebinding(namespace)
            operator_details["service_account"] = self.get_service_account(namespace)

            self._operator_details = operator_details
            return operator_details

        except Exception as e:
            self._logger.info(f"Operator details: {operator_details}")
            self._logger.info(f"Error in kubernetes_utilities.py from the get_operator_details: {e}")
            return {}


    # Function to copy files or folders from a pod to the local filesystem
    def copy_files_from_pod(self, pod_name, namespace, src_path, dest_path, file_filter=''):
        try:
            exec_command = ["tar", "czf", '-', file_filter, "-C", src_path, '.' ]

            self._logger.info(f"Copying files from pod {pod_name} to {dest_path}")
            self._logger.info(f"Exec command: {exec_command}")

            # Execute the command and get the stream
            resp = stream(
                self.core_v1.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                command=exec_command,
                stderr=True,
                stdin=True,
                stdout=True,
                tty=False,
                _preload_content=False,
                binary=True
            )

            self._logger.info(f"Response: {resp}")

            # Read the streamed tar data
            tar_data = b""
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    chunk = resp.read_stdout()
                    tar_data += chunk  # Ensure the chunk is in bytes

            resp.close()

            # Process the tar data (e.g., extract to a local directory)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with io.BytesIO(tar_data) as tar_buffer:
                    with tarfile.open(fileobj=tar_buffer, mode="r") as tar_archive:
                        tar_archive.extractall(path=dest_path)

            return True
        except Exception as e:
            self._logger.info(f"Error in kubernetes_utilities.py from the copy_files_from_pod: {e}")
            return False

    # Function to update the operator group to remove cas.ibm.com/v1 from providedAPIs
    def update_operator_group(self, namespace, operator_group, provided_apis, api_to_remove="FNCMCluster.v1.fncm.ibm.com"):
        # Check if the operator group exists
        if not operator_group:
            self._logger.info("Operator group does not exist, skipping update.")
            return

        # Remove the "cas.ibm.com/v1" API from providedAPIs
        if api_to_remove in provided_apis:
            provided_apis.remove(api_to_remove)

        # Update the operator group with the modified providedAPIs
        self._logger.info(f"Updating operator group '{operator_group}' in namespace '{namespace}' "
                          f"to remove {api_to_remove} from providedAPIs.")

        try:
            og = self.describe_operator_group(name=operator_group, namespace=namespace)
            if not og:
                self._logger.info(f"Operator group '{operator_group}' not found in namespace '{namespace}'.")
                return
            og['metadata']['annotations']['olm.providedAPIs'] = ','.join(provided_apis)
            self._custom_api.patch_namespaced_custom_object(
                group="operators.coreos.com",
                version="v1",
                namespace=namespace,
                plural="operatorgroups",
                name=operator_group,
                body=og
            )
            self._logger.info(f"Operator group '{operator_group}' updated successfully in namespace '{namespace}'.")
        except client.ApiException as e:
            self._logger.info(f"Error updating operator group: {e}")
        except Exception as e:
            self._logger.info(f"Unexpected error while updating operator group: {e}")
            return


    # Function to get CR file from a Content Assistant deployment
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
                self._logger.info("Cleaning up the Custom Resource file before returning it.")
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
