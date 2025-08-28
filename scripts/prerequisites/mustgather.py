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

import datetime
import logging
import os
import re
import shutil
import tarfile
from datetime import datetime

import typer
import click
from rich import print
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (BarColumn, Progress,
                           SpinnerColumn, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn)
from rich.prompt import Confirm
from rich.text import Text
from typing_extensions import Annotated

from helper_scripts.gather import gather as g
from helper_scripts.gather import silent_gather as sg
from helper_scripts.mustgather import mustgather as mg
from helper_scripts.utilities import kubernetes_utilites as k
from helper_scripts.utilities.interface import (
    clear,
    display_issues,
    display_prereq_passed, mustgather_details, mustgather_network_results)
from helper_scripts.utilities.utilities import prereq_checks
from pathlib import Path

__version__ = "5.1.2"

app = typer.Typer()

state = {
    "verbose": False,
    "silent": False,
    "logger": logging,
    "dev": False,
    "setup": None,
    "image_details": "",
    "dryrun": False
}

console = Console(record=True)


def setup_logger(file_log_level):
    # Create a logger object
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Setup console logger
    shell_handler = RichHandler()
    shell_handler.setLevel(file_log_level)
    formatter_rich = logging.Formatter("%(message)s")
    shell_handler.setFormatter(formatter_rich)

    # Setup file logger
    file_handler = logging.FileHandler("mustgather.log")
    file_handler.setLevel(logging.DEBUG)
    formatter_file = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)-100s - %(filename)s:%(lineno)d", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter_file)

    # Add handlers to the logger
    logger.addHandler(shell_handler)
    logger.addHandler(file_handler)

    return logger


def version_callback(value: bool):
    if value:
        print(f"FileNet Content Manager MustGather CLI: {__version__}")
        raise typer.Exit()

def display_mode_version(mode: str, description: str):
    """
        Display the mode and version of the script.
    """
    clear(console)
    print()
    msg = f"Version: {__version__}\n" \
          f"Mode: {mode}\n" \
          f"{description}"

    if state["silent"]:
        msg += "\nSilent Mode Enabled"

    print(Panel.fit(msg, title="FileNet Content Manager MustGather CLI", border_style="green"))
    print()


# Function to filter deployments based on component
def filter_deployments(deployment, component):
    if component in deployment:
        return True
    return False


def create_mustgather_folder(progress, platform, components, collect_sensitive_data, cr_present=True,
                             operator_present=True):
    progress.log()
    progress.log("Creating MustGather folder")
    if os.path.exists(os.path.join(os.getcwd(), "MustGather")):
        shutil.rmtree(os.path.join(os.getcwd(), "MustGather"))

    mustgather_folder = os.path.join(os.getcwd(), "MustGather")

    os.mkdir(mustgather_folder)

    progress.log()
    progress.log("Creating MustGather components subfolders")

    folder_names = [
        "cluster"
    ]

    if operator_present:
        folder_names.append("operator")

    if cr_present:
        folder_names.append("deployments")
        folder_names.append("services")
        folder_names.append("pvcs")
        folder_names.append("storageclasses")

        if platform == "other":
            folder_names.append("ingresses")
        else:
            folder_names.append("routes")

        folder_names.extend(components)

        if collect_sensitive_data:
            folder_names.extend(["secrets", "configmaps"])

    for folder_name in folder_names:
        os.mkdir(
            os.path.join(
                mustgather_folder,
                folder_name,
            )
        )
    progress.log()
    progress.log(Panel.fit("MustGather folder created", style="bold green"))
    progress.log()
    return mustgather_folder


# Function to tar the mustgather folder
def tar_mustgather_folder(mustgather_folder, progress, namespace):
    try:
        namespace_no_spaces = re.sub(r"\s+", "", namespace)
        progress.log(Panel.fit("Generating MustGather tarfile", style="bold green"))
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d_%H-%M")
        tar_file_name = mustgather_folder + "_"  + namespace_no_spaces + "_" + dt_string + ".tar.gz"

        # Check if tar file exists move it to a backup folder
        if os.path.exists(tar_file_name):
            if not os.path.exists(os.path.join(os.getcwd(), "backups")):
                os.mkdir(os.path.join(os.getcwd(), "backups"))
            now = datetime.now()
            dt_string = now.strftime("%Y-%m-%d_%H-%M")
            shutil.move(tar_file_name, os.path.join(os.getcwd(), "backups",
                                                    "MustGather_" + namespace_no_spaces + "_" + dt_string + ".tar.gz"))

        with tarfile.open(tar_file_name, "w:gz") as tar:
            tar.add(mustgather_folder, arcname=os.path.basename(mustgather_folder))
        shutil.rmtree(mustgather_folder)
    except Exception as e:
        state["logger"].exception("Unable to tar logs, caught %s Exiting...", e)

@app.callback(invoke_without_command=True)
def main(
        version: Annotated[bool, typer.Option(
            "--version", help="Show version and exit.",
            callback=version_callback, is_eager=True)] = None,
        verbose: Annotated[bool, typer.Option(
            help="Enable verbose logging.",
            rich_help_panel="Customization and Utils")] = False,
        silent: Annotated[bool, typer.Option(
            help="Enable Silent Install (no prompts).",
            rich_help_panel="Customization and Utils")] = False,
        dryrun: Annotated[bool, typer.Option(
            help="Perform Dry Run of the mustgather script",
            rich_help_panel="Customization and Utils")] = False):

    if click.get_current_context().invoked_subcommand == "networkpolicy":
        return
    """
    FileNet Content Manager MustGather
    """
    clear(console)
    display_mode_version("Gather All",
                         "FileNet Content Manager MustGather for Container Deployment")

    if verbose:
        state["verbose"] = True
        FILE_LOG_LEVEL = logging.DEBUG
    else:
        FILE_LOG_LEVEL = logging.WARNING

    state["logger"] = setup_logger(FILE_LOG_LEVEL)

    if silent:
        state["silent"] = True

    if dryrun:
        state["dryrun"] = True

    checks = ["kubectl", "connection"]

    missing_tools, results, files = prereq_checks(logger=state["logger"], prereqs=checks)

    # Print table of prerequisites that are missing
    if len(missing_tools) > 0 or len(files) > 0:
        layout = display_issues(tools=missing_tools, descriptors=files)
        print(layout)
        exit(1)
    else:
        prereq_summary = display_prereq_passed(results)
        print(prereq_summary)
        print()

    if state["silent"]:
        # this is the user details object which does pre-checks and collects some necessary details
        silent_path = os.path.join("silent_config", "silent_install_mustgather.toml")
        setup = sg.SilentGatherOptions(state["logger"], silent_path, script_type="must_gather")
        setup.silent_parse_mustgather_operator_file()
    else:
        setup = g.GatherOptions(state["logger"], console, script_type="must_gather")
        setup.collect_namespace()
        setup.collect_sensitive_data()

    namespace = setup.namespace
    collect_sensitive_data = setup.sensitive_collect

    kube = k.KubernetesUtilities(state["logger"])
    # Collect CR details
    custom_resources = kube.get_deployment_cr(namespace=namespace, logger=state["logger"])
    components = []
    deployment_details = {}

    # Collect Operator details
    operator_deployment = "ibm-fncm-operator"
    operator_details = kube.get_operator_details(namespace, operator_deployment)

    operator_present = bool(operator_details)

    if len(custom_resources) == 0:
        cr_present = False
        print("[prompt.invalid] No custom resources found.")
    else:
        cr_present = True
        deployment_details = kube.cr_details
        version = deployment_details["version"]
        deployments = deployment_details["components"]

        if not state["silent"]:
            clear(console)
            setup.collect_mustgather_components(deployments, version)
            components = list(setup.components)
        else:
            components = list(setup.components)

    summary = mustgather_details(deployment_details, components, operator_details)

    clear(console)
    print(summary)

    if not state["silent"]:
        if not Confirm.ask("Do you want to proceed with the MustGather?"):
            raise typer.Exit()
    if state["dryrun"]:
        exit()
    clear(console)
    print(Panel.fit("Starting FNCM Standalone MustGather", style="cyan"))
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
    ) as progress:
        task1 = progress.add_task("[cyan]Collecting Cluster Info", total=None)
        # Check is operator is present
        if operator_present:
            task2 = progress.add_task("[purple]Collecting FNCM Operator Info", total=None)
            if operator_details["type"] == "YAML":
                platform = "other"
            else:
                platform = "OCP"

        # Check if CR is present
        if cr_present:
            cr_name = deployment_details["name"]
            platform = deployment_details["platform"]
            storage_class = deployment_details["storage_classes"]
            user_secrets = deployment_details["user_secrets"]
            user_configmaps = deployment_details["user_configmaps"]

            resource_type_dict = kube.list_namespace_resources(console=console,
                                                               namespace=namespace,
                                                               platform=platform,
                                                               filter=cr_name)

            # Calculate number of pods per component to be collected
            num_components = len(components)
            num_collections = 0
            if num_components != 0:
                deployment_dict = {}
                for component in components:

                    # Get deployments for each component
                    if component == "ban":
                        deployment_dict[component] = filter(lambda x: filter_deployments(x, "navigator"),
                                                            resource_type_dict["deployment"])
                    else:
                        deployment_dict[component] = filter(lambda x: filter_deployments(x, component),
                                                            resource_type_dict["deployment"])

                pod_count_dict = {}
                for component in components:
                    pod_count_dict[component] = []
                    for deploy in deployment_dict[component]:
                        num_collections += 1
                        details_dict = {}

                        details_dict["deployment"] = deploy
                        pods = kube.get_pod_names_for_deployment(namespace, deploy)
                        init_containers = kube.get_init_containers_for_deployment(namespace, deploy)
                        details_dict["init_containers"] = init_containers
                        details_dict["pods"] = pods
                        details_dict["count"] = len(pods)
                        pod_count_dict[component].append(details_dict)

            task4 = None

            task3 = progress.add_task("[magenta]Collecting Deployment Artifacts", total=None)

        if len(components) > 0:
            if num_collections > 0:
                task4 = progress.add_task(f"[yellow]Collecting Component Logs", total=num_collections)
            else:
                task4 = progress.add_task(f"[yellow]Collecting Component Logs", total=1)

        task5 = progress.add_task("[blue]Creating MustGather Tar File", total=1)

        while not progress.finished:
            mustgather_folder = create_mustgather_folder(progress, platform, components, collect_sensitive_data,
                                                         cr_present, operator_present)

            must_gather = mg.MustGather(console, namespace, state["logger"], mustgather_folder, deployment_details,
                                        operator_details, kube)
            must_gather.collect_cluster_info(progress)

            progress.update(task1, total=2, completed=2)

            if operator_details:
                must_gather.collect_operator_info(progress, collect_sensitive_data, operator_details)

                progress.update(task2, total=1, completed=1)

            if cr_present:
                # Download CR
                must_gather.write_cr_file(progress, deployment_details["name"])

                # Collect all Deployments
                if len(resource_type_dict["deployment"]) > 0:
                    deployments = resource_type_dict["deployment"]
                    must_gather.collect_deployment_info(progress, deployments)

                # Collect all StorageClass Info
                if len(storage_class) > 0:
                    must_gather.collect_storage_class_info(progress, storage_class)

                # Collect all PersistentVolume Info
                if len(resource_type_dict["persistent_volume_claim"]) > 0:
                    pvcs = resource_type_dict["persistent_volume_claim"]
                    must_gather.collect_pvc_info(progress, pvcs)

                # Collect all Service Info
                if len(resource_type_dict["service"]) > 0:
                    services = resource_type_dict["service"]
                    must_gather.collect_service_info(progress, services)

                # Collect all NetworkPolicy Info
                if len(resource_type_dict["network_policy"]) > 0:
                    network_policies = resource_type_dict["network_policy"]
                    must_gather.collect_network_policy_info(progress, network_policies)

                if platform == "other":
                    if len(resource_type_dict["ingress"]) > 0:
                        ingress = resource_type_dict["ingress"]
                        must_gather.collect_ingress_info(progress, ingress)
                else:
                    if len(resource_type_dict["routes"]) > 0:
                        routes = resource_type_dict["routes"]
                        must_gather.collect_route_info(progress, routes)

                if collect_sensitive_data:
                    secrets = resource_type_dict["secret"]
                    secrets.extend(user_secrets)
                    if len(secrets) > 0:
                        must_gather.collect_secret_info(progress, secrets)

                    configmaps = resource_type_dict["config_map"]
                    configmaps.extend(user_configmaps)
                    if len(configmaps) > 0:
                        must_gather.collect_configmap_info(progress, configmaps)

                progress.update(task3, total=1, completed=1)

                if num_collections > 0:
                    for component in components:
                        if component == "ban":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for Navigator", style="bold red"))
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_ban_info(progress, collect_sensitive_data,
                                                                 deploy["pods"],
                                                                 deploy["init_containers"])
                                    progress.advance(task4)
                        if component == "cpe":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for CPE", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_cpe_info(progress,
                                                                 collect_sensitive_data,
                                                                 deploy["pods"],
                                                                 deploy["init_containers"])
                                    progress.advance(task4)

                        if component == "css":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for CSS", style="bold red"))
                                progress.log()
                            else:
                                for i in range(len(pod_count_dict[component])):
                                    must_gather.collect_css_info(progress,
                                                                 collect_sensitive_data,
                                                                 pod_count_dict[component][i]["pods"],
                                                                 pod_count_dict[component][i]["init_containers"], i + 1)
                                    progress.advance(task4)
                        if component == "graphql":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for GraphQL", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_graphql_info(progress,
                                                                     collect_sensitive_data,
                                                                     deploy["pods"],
                                                                     deploy["init_containers"])
                                    progress.advance(task4)
                        if component == "cmis":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for CMIS", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_cmis_info(progress,
                                                                  collect_sensitive_data,
                                                                  deploy["pods"],
                                                                  deploy["init_containers"])
                                    progress.advance(task4)
                        if component == "es":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for External Share", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_es_info(progress,
                                                                collect_sensitive_data,
                                                                deploy["pods"],
                                                                deploy["init_containers"])
                                    progress.advance(task4)
                        if component == "tm":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for Task Manager", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_tm_info(progress,
                                                                collect_sensitive_data,
                                                                deploy["pods"],
                                                                deploy["init_containers"])
                                    progress.advance(task4)

                        if component == "iccsap":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for ICCSAP", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_iccsap_info(progress,
                                                                    collect_sensitive_data,
                                                                    deploy["pods"],
                                                                    deploy["init_containers"])
                                    progress.advance(task4)

                        if component == "ier":
                            if len(pod_count_dict[component]) == 0:
                                progress.log()
                                progress.log(Panel.fit("No Pods Found for IER", style="bold red"))
                                progress.log()
                            else:
                                for deploy in pod_count_dict[component]:
                                    must_gather.collect_ier_info(progress,
                                                                 collect_sensitive_data,
                                                                 deploy["pods"],
                                                                 deploy["init_containers"])
                                    progress.advance(task4)
                else:
                    if components:
                        progress.log()
                        progress.log(Panel.fit("No Pods Found for Selected Components", style="bold red"))
                        progress.log()
                        progress.advance(task4)

            tar_mustgather_folder(mustgather_folder, progress, namespace)
            progress.advance(task5)
            progress.stop()

@app.command()
def networkpolicy(apply: bool = typer.Option(False, help="Apply all generated network policies to the cluster")):
    """
    Collect the Network policy templates from the FNCM Standalone Operator
    """
    clear(console)
    display_mode_version("Gather Network Policies",
                        "FileNet Content Manager MustGather for Container Deployment")

    checks = ["kubectl", "connection"]

    missing_tools, results, files = prereq_checks(logger=state["logger"], prereqs=checks)
    if len(missing_tools) > 0 or len(files) > 0:
        layout = display_issues(tools=missing_tools, descriptors=files)
        print(layout)
        exit(1)
    else:
        prereq_summary = display_prereq_passed(results)
        print(prereq_summary)
        print()
    if apply:
        setup = g.GatherOptions(state["logger"], console, script_type="must_gather")
        setup.collect_namespace()
        kube = k.KubernetesUtilities(state["logger"])
        deployment_details = {}

        # Collect Operator details
        operator_deployment = "ibm-fncm-operator"
        namespace = setup.namespace
        operator_details = kube.get_operator_details(namespace, operator_deployment)
        if operator_details['release'] not in ['5.7.0']:
            print(Text(f"Current operator release is {operator_details['release']}\n"
                    f"Only operators from 5.7.0 and later releases will generate network policy templates", style="red"))
            raise typer.Exit()
        np_folder = os.path.join(os.getcwd(), "FNCMNetworkPolicies")
        must_gather = mg.MustGather(console, namespace, state["logger"], np_folder, deployment_details, operator_details, kube)
        if os.path.exists(np_folder):
            print()
            print(Panel.fit(Text(f"Found {os.path.basename(np_folder)} Folder. Applying existing network policies"), style="cyan"))
            print()
            must_gather.auto_apply_networkpolicy()
        else:
            print()
            print(Panel.fit(Text(f"{os.path.basename(np_folder)} Folder not found. Starting Copying Network policy Templates"), style="cyan"))
            print()
            with Progress(SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        transient=True,
                        console=console) as progress:
                if operator_details:
                    task1 = progress.add_task("[cyan]Collect Network Policies", total=None)
                    must_gather.collect_network_policy_templates(progress,operator_details) 
                    progress.update(task1, total=1, completed=1)
                else:
                    print(Panel.fit(Text("FNCM Standalone Operator not found in namespace."),style="bold red"))
                    raise typer.Exit()

            # Output Network Policy Template folder
            print()
            print(Panel.fit(Text("Applying downloaded network policies"), style="cyan"))
            print()
            must_gather.auto_apply_networkpolicy()
        raise typer.Exit()

    else:        
        setup = g.GatherOptions(state["logger"], console, script_type="must_gather")
        setup.collect_namespace()
        kube = k.KubernetesUtilities(state["logger"])

        deployment_details = {}

        # Collect Operator details
        operator_deployment = "ibm-fncm-operator"
        namespace = setup.namespace
        operator_details = kube.get_operator_details(namespace, operator_deployment)
        if operator_details['release'] not in ['5.7.0']:
            print(Text(f"Current operator release is {operator_details['release']}\n"
                    f"Only operators from 5.7.0 and later releases will generate network policy templates", style="red"))
            raise typer.Exit()
        np_folder = os.path.join(os.getcwd(), "FNCMNetworkPolicies")

        must_gather = mg.MustGather(console, namespace, state["logger"], np_folder, deployment_details,operator_details, kube)
        if os.path.exists(np_folder):
            namespace_no_spaces = re.sub(r"\s+", "", namespace)
            now = datetime.now()
            dt_string = now.strftime("%Y-%m-%d_%H-%M")
            tar_file_name = os.getcwd() + "/backups/" + "FNCMNetworkPolicies" + "_"  + namespace_no_spaces + "_" + dt_string + ".tar.gz"
            if not os.path.exists(os.path.join(os.getcwd(), "backups")):
                os.mkdir(os.path.join(os.getcwd(), "backups"))
            try:
                with tarfile.open(tar_file_name, "w:gz") as tar:
                    tar.add(np_folder, arcname=os.path.basename(np_folder))
                    shutil.rmtree(np_folder)
            except Exception as e:
                 state["logger"].exception("Unable to tar network policies, caught %s Exiting...", e)

        print()
        print(Panel.fit(Text("Starting Copying Network policy Templates"), style="cyan"))
        print()
        with Progress(SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    transient=True,
                    console=console) as progress:
            if operator_details:
                task1 = progress.add_task("[cyan]Collect Network Policies", total=None)
                must_gather.collect_network_policy_templates(progress,operator_details) 
                progress.update(task1, total=1, completed=1)
            else:
                print(Panel.fit(Text("FNCM Standalone Operator not found in namespace."),style="bold red"))
                raise typer.Exit()


        results = mustgather_network_results(np_folder, namespace)
        print(results)
        print()

        apply_networkpolicy = Confirm.ask("Do you want to apply the retrieved network policies to your cluster?", default=False)
        if apply_networkpolicy:
            must_gather.auto_apply_networkpolicy()
        raise typer.Exit()

if __name__ == "__main__":
    app()
