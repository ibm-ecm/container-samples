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

import logging
import os

import typer
from rich import print
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn, \
    TimeElapsedColumn
from rich.prompt import Confirm
from typing_extensions import Annotated

from helper_scripts.deploy import deploy as d
from helper_scripts.gather import gather as g
from helper_scripts.gather import silent_gather as sg
from helper_scripts.utilities.interface import clear, display_issues, display_prereq_passed, deploy_details
from helper_scripts.utilities.utilities import prereq_checks, read_version_toml, create_deployment_info, \
    create_version_info

__version__ = "3.1.0"

app = typer.Typer()
state = {
    "verbose": False,
    "logger": logging,
    "dev": False,
    "setup": None,
    "silent": False,
    "version": None,
    "dryrun": False
}

console = Console(record=True)


def version_callback(value: bool):
    if value:
        print(f"FileNet Content Manager Deploy Operator CLI: {__version__}")
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

    if state["dryrun"]:
        msg += "\nDry Run Enabled"

    if state["dev"]:
        msg += "\nDevelopment Mode Enabled"

    print(Panel.fit(msg, title="FileNet Content Manager Deploy Operator CLI", border_style="green"))
    print()


def setup_logger(file_log_level, verbose=False):
    # Create a logger object
    logger = logging.getLogger("deployoperator")

    shell_handler = RichHandler()
    file_handler = logging.FileHandler("deployoperator.log")

    logger.setLevel(file_log_level)
    shell_handler.setLevel(file_log_level)
    file_handler.setLevel(logging.DEBUG)

    # the formatter determines what our logs will look like
    fmt_shell = '%(message)s'
    fmt_file = '%(levelname)s %(asctime)s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s'

    shell_formatter = logging.Formatter(fmt_shell)
    file_formatter = logging.Formatter(fmt_file)

    # here we hook everything together
    shell_handler.setFormatter(shell_formatter)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(shell_handler)
    logger.addHandler(file_handler)

    return logger


def deploy():
    files = [
        "fncm_v1_fncm_crd.yaml",
        "cluster_role.yaml",
        "role.yaml",
        "role_binding.yaml",
        "cluster_role_binding.yaml",
        "service_account.yaml",
        "operator.yaml",
        os.path.join("op-olm", "catalogsource.yaml"),
        os.path.join("op-olm", "operator_group.yaml"),
        os.path.join("op-olm", "subscription.yaml")
    ]

    descriptor_path = os.path.join(os.path.dirname(os.getcwd()), "descriptors")

    # Read Version File
    version_path = os.path.join(os.path.dirname(os.getcwd()), "version.toml")

    if os.path.exists(version_path):
        version_data = read_version_toml(version_path, state["logger"])
    else:
        version_data = {}

    required_files = []
    for file in files:
        required_files.append(os.path.join(descriptor_path, file))

    checks = ["kubectl", "podman", "docker"]
    missing_tools, results, files = prereq_checks(logger=state["logger"], prereqs=checks, files=required_files)

    # Print table of prerequisites that are missing
    if len(missing_tools) > 0 or len(files) > 0:
        layout = display_issues(tools=missing_tools, descriptors=files)
        print(layout)
        exit(1)
    else:
        prereq_summary = display_prereq_passed(results)
        print(prereq_summary)
        print()
    if not state["silent"]:
        state["setup"] = g.GatherOptions(state["logger"], console, script_type="deploy", dev=state["dev"])
        state["setup"].podman_available = results["podman"]
        state["setup"].docker_available = results["docker"]
        state["setup"].collect_license_model()
        state["setup"].collect_platform()
        state["setup"].collect_verify_entitlement_key()
        state["setup"].collect_namespace()
        state["setup"].collect_private_catalog()
    else:
        silent_path = os.path.join("silent_config", "silent_install_deployoperator.toml")
        state["setup"] = sg.SilentGatherOptions(state["logger"],
                                                silent_path, script_type="deploy", dev=state["dev"])
        state["setup"].podman_available = results["podman"]
        state["setup"].docker_available = results["docker"]
        state["setup"].silent_parse_deploy_operator_file()

    deployment_details = create_deployment_info(state["setup"], version_data)
    version_details = create_version_info(state["setup"], version_data)

    clear(console)
    layout = deploy_details(deployment_details, version_details)
    print(layout)

    if not state["silent"]:
        print()
        start_deploy = Confirm.ask("Do you want to to proceed with the FNCM Operator Deployment?",
                                   default=True)

        if not start_deploy:
            exit(1)
    if state["dryrun"]:
        exit()

    deploy = d.Deploy(console, state["setup"], state["logger"], required_files=required_files)

    tasks = deploy.task_numbers
    deployment_type = deploy.deployment_type

    print(Panel.fit("Starting FNCM Standalone Operator Deployment", style="cyan"))
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
    ) as progress:

        task1 = progress.add_task("[green]Cluster Setup", total=tasks["ClusterSetup"])
        if deployment_type == "olm":
            task2 = progress.add_task("[purple]OLM Setup", total=tasks["DeploymentSetup"])
        else:
            task2 = progress.add_task("[yellow]CRD & Permission Setup", total=tasks["DeploymentSetup"])
        task3 = progress.add_task("[cyan]Deploying Operator", total=tasks["Install"])

        while not progress.finished:

            deploy.cluster_setup(progress, task1)
            if deployment_type == "olm":
                deploy.apply_olm(progress, task2)
                deploy.apply_operator_olm(progress, task3)
            else:
                deploy.apply_cncf(progress, task2)
                deploy.apply_operator_cncf(progress, task3)


# main function
def main(version: Annotated[bool, typer.Option(
    "--version", help="Show version and exit.",
    callback=version_callback, is_eager=True)] = None,
         silent: Annotated[bool, typer.Option(
             help="Enable Silent Install (no prompts).",
             rich_help_panel="Customization and Utils")] = False,
         verbose: Annotated[bool, typer.Option(
             help="Enable verbose logging.",
             rich_help_panel="Customization and Utils")] = False,
         dryrun: Annotated[bool, typer.Option(
             help="Perform a dry run",
             rich_help_panel="Customization and Utils")] = False,
         dev: Annotated[bool, typer.Option(hidden=True)] = False):
    """
    FileNet Content Manager Operator Deployment CLI.
    """
    if verbose:
        state["verbose"] = True
        FILE_LOG_LEVEL = logging.DEBUG
    else:
        FILE_LOG_LEVEL = logging.WARNING

    state["logger"] = setup_logger(FILE_LOG_LEVEL)

    if silent:
        state["silent"] = True

    if dev:
        state["dev"] = True

    if dryrun:
        state["dryrun"] = True

    clear(console)
    display_mode_version("Deploy FNCM Operator",
                         "Install FNCM Operator")
    deploy()


if __name__ == "__main__":
    typer.run(main)
