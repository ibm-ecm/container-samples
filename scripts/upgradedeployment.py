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
from rich.syntax import Syntax
from rich.text import Text
from rich.console import Group
from typing_extensions import Annotated

from helper_scripts.upgrade import upgrade as u
from helper_scripts.gather import gather as g
from helper_scripts.gather import silent_gather as sg
from helper_scripts.utilities.interface import clear, display_issues, display_prereq_passed, upgrade_details, \
    upgrade_cr_details
from helper_scripts.utilities.utilities import prereq_checks, read_version_toml, create_deployment_info, \
    create_version_info, create_current_operator_info

__version__ = "3.1.0"

app = typer.Typer()

state = {
    "verbose": False,
    "silent": False,
    "logger": logging,
    "setup": None,
    "upgrade": None,
    "version_details": {},
    "deployment_details": {},
    "dev": False,
    "dryrun": False
}

console = Console(record=True)


def setup_logger(file_log_level, verbose=False):
    # Create a logger object
    logger = logging.getLogger("fncm-upgrade")

    shell_handler = RichHandler()
    file_handler = logging.FileHandler("fncm-upgrade.log")

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


def version_callback(value: bool):
    if value:
        print(f"FileNet Content Manager Upgrade CLI: {__version__}")
        raise typer.Exit()


# Create a function to display the mode and version
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

    print(Panel.fit(msg, title="FileNet Content Manager Upgrade CLI", border_style="green"))
    print()


# This is the context that will be executed when we want to upgrade the operator and deployment
@app.command()
def deployment():
    """
        Upgrade the FNCM Deployment Only.
    """
    if not state["upgrade"]._cr_present:
        print()
        print(Panel.fit(
            "FNCM Standalone Deployment not found in {namespace}.\n"
            "A valid FNCM Standalone Deployment is required for this mode".format(
                namespace=state["setup"]._namespace),
            border_style="red"))
        exit(1)
    clear(console)
    display_deployment_phases()
    state["upgrade"].prepare_upgrade_cr()

    # Get CR update list
    update_list = state["upgrade"].updates_list

    # Get CR Folder Path
    cr_folder_path = state["upgrade"].cr_template_save_location

    clear(console)
    cr_info = upgrade_cr_details(update_list, state["version_details"], cr_folder_path)
    print(cr_info)
    print()

    if not state["silent"]:
        proceed = Confirm.ask("Do you want to continue and prepare the deployed system for upgrade?", default=True)
        if not proceed:
            exit(1)

    clear(console)
    prereq_steps()

    if not state["dryrun"]:
        clear(console)
        print(Panel.fit("Starting FNCM Standalone Deployment Upgrade", style="cyan"))
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
            task1 = progress.add_task("[yellow]Scaling Down Deployments", total=None)
            task2 = progress.add_task("[purple]Applying Upgraded Custom Resource ", total=1)

            while not progress.finished:
                state["upgrade"].scale_pods(scale="down", progress=progress)
                progress.update(task1, total=1, completed=1)

                state["upgrade"].apply_upgraded_cr(progress)
                progress.advance(task2)


def convert_private_catalog():
    clear(console)
    print()
    print(Panel.fit("Private Catalog"))
    print()
    print("The FileNet Content Manager Operator Catalog Source can be installed with the follow options:\n"
          "1. Private Catalog - Install the catalog in the same target namespace\n"
          "2. Global Catalog - Install the catalog in the openshift-marketplace namespace")
    print()
    print("A private catalog can only be used by operator instances in the same namespace.\n"
          "A global catalog can be used by operator instances in any namespace.")
    print()
    print(Text("Your FileNet Content Manager Operator Catalog Source is currently set to use a global catalog.",
               style="bold cyan"))
    print()
    private_catalog = Confirm.ask(
        "Do you want to convert the FileNet Content Manager Operator to use a private catalog?", default=True)

    return private_catalog

def convert_private_registry():
    clear(console)
    print()
    print(Panel.fit("Private Image Registry"))
    print()
    print("The FileNet Content Manager Operator Image can be installed with the follow options:\n\n"
          "1. Online - Pull the Operator image from the IBM Entitlement Registry\n"
          "2. Private - Pull the Operator image from a Private Registry")
    print()
    print("Before you deploying using a Private Registry, use the FNCM Load Images CLI to push the required images.")
    print()
    print(Panel.fit(Syntax("python3 loadimages.py", theme="ansi_dark", lexer="bash"), style="cyan"))
    print()
    private_registry = Confirm.ask(
        "Do you want to pull the FNCM Operator image from a Private Registry?", default=False)

    if private_registry:
        state["setup"].collect_verify_private_registry()

    return private_registry


def display_deployment_phases():
    print()
    print(Panel.fit("Deployment Upgrade Phases"))
    print()
    print("The FileNet Content Manager Deployment Upgrade is a multi-phase process.\n"
          "The upgrade process will be performed in the following phases:\n\n"
          "1. Custom Resource - Prepare the CR for the upgrade\n"
          "2. Environment Preparation - Scale down all deployments\n"
          "3. Upgrade Deployment - Apply the upgraded CR\n"
          "4. Upgrade Operator - Upgrade the FNCM Standalone Operator\n")
    print()

    if not state["silent"]:
        proceed = Confirm.ask("Do you want to continue and prepare the upgraded custom resource?", default=True)
        if not proceed:
            exit(1)


def prereq_steps():
    backup_link = Text(
        "https://www.ibm.com/docs/en/filenet-p8-platform/5.6.0?topic=br-backing-up-data-in-your-filenet-p8-domain",
        style="https://www.ibm.com/docs/en/filenet-p8-platform/5.6.0?topic=br-backing-up-data-in-your-filenet-p8-domain")
    cbr_link = Text(
        "https://www.ibm.com/docs/en/filenet-p8-platform/5.6.0?topic=upgrade-stopping-content-search-services-index-dispatcher",
        style="https://www.ibm.com/docs/en/filenet-p8-platform/5.6.0?topic=upgrade-stopping-content-search-services-index-dispatcher")
    upgrade_prep = Text(
        "https://www.ibm.com/docs/en/filenet-p8-platform/5.6.0?topic=upgrade-checking-deployment-type-license",
        style="https://www.ibm.com/docs/en/filenet-p8-platform/5.6.0?topic=upgrade-checking-deployment-type-license")
    print()
    print(Panel.fit("Preparing for the FileNet Content Manager Deployment Upgrade"))
    print()
    print(
        f"Before you start the FileNet Content Manager Deployment Upgrade, some preparation is required.\n"
        f"To ensure a smooth upgrade, review and complete the following steps on the deployed system:\n\n"
        f"1. Backup your FileNet Content Manager data - {backup_link} \n"
        f"2. Disable the CBR Dispatcher - {cbr_link} \n")

    print(Panel.fit(f"Important: If you have other FNCM Standalone Deployments on the same cluster, ensure that you\n"
                    f"have adjusted each custom resource to be compatible with the new version.\n"
                    f"Please see {upgrade_prep}", style="bold yellow"))
    print()

    tip_text = Panel.fit(Text(
        f"Tip: Run the FNCM Standalone MustGather to collect a backup of all your deployment files and configuration"),
                         style="cyan")
    code = Panel.fit(Syntax("python3 mustgather.py", "bash", theme="ansi_dark"))
    tip_group = Group(tip_text, code)
    print(tip_group)
    print()

    print(
        Panel.fit(f"Important: Proceeding will scale down all deployments and apply the upgraded CR", style="bold red"))
    print()

    if not state["silent"]:
        proceed = Confirm.ask("Have you completed the preparation steps and are ready to proceed with the upgrade?",
                              default=False)
        if not proceed:
            exit(1)


@app.command()
def operator():
    """
        Upgrade the FNCM Operator Only.
    """
    if not state["upgrade"]._operator_present:
        print()
        print(Panel.fit(
            "FNCM Standalone Operator not found in {namespace}.\n"
            "A valid FNCM Standalone Operator is required for this mode".format(
                namespace=state["setup"]._namespace),
            border_style="red"))
        exit(1)
    tasks = state["upgrade"].task_numbers
    deployment_type = state["upgrade"].deployment_type
    catalog_type = state["upgrade"].catalog_type
    namespace = state["setup"].namespace

    current_operator_details = create_current_operator_info(state["upgrade"].operator_details)

    # Check if we need to convert to Private Catalog
    if deployment_type == "olm":
        if catalog_type != "Private":
            private_catalog = convert_private_catalog()
            if private_catalog:
                state["upgrade"].catalog_namespace = namespace
                state["upgrade"].catalog_type = "Private"
                state["deployment_details"]["catalogType"] = "Private"

    else:
        private_registry = convert_private_registry()
        if private_registry:
            state["deployment_details"]["registry"] = state["setup"].private_registry_server
        else:
            if state['dev']:
                state["deployment_details"]["registry"] = "cp.stg.icr.io"
            else:
                state["deployment_details"]["registry"] = "icr.io"

    clear(console)
    layout = upgrade_details(state["deployment_details"], state["version_details"], current_operator_details)
    print(layout)

    if not state["silent"]:
        print()
        start_upgrade = Confirm.ask("Do you want to to proceed with the FNCM Operator Upgrade?",
                                    default=True)

        if not start_upgrade:
            exit(1)
    if state["dryrun"]:
        exit()

    print(Panel.fit("Starting FNCM Standalone Operator Upgrade", style="cyan"))
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
        if state["upgrade"].remove_yaml:
            task1 = progress.add_task("[yellow]Cleanup Yaml Deployment", total=tasks["CleanYaml"])
        if deployment_type == "olm":
            task2 = progress.add_task("[purple]OLM Upgrade", total=tasks["UpgradeSetup"])
        else:
            task2 = progress.add_task("[yellow]CRD & Permission Upgrade", total=tasks["UpgradeSetup"])
        task3 = progress.add_task("[cyan]Upgrade Operator", total=tasks["Upgrade"])

        while not progress.finished:

            if state["upgrade"].remove_yaml:
                state["upgrade"].remove_yaml_deployment(progress, task1)
            if deployment_type == "olm":
                state["upgrade"].apply_olm(progress, task2)
                state["upgrade"].upgrade_operator_olm(progress, task3)
            else:
                state["upgrade"].apply_cncf(progress, task2)
                state["upgrade"].upgrade_operator_cncf(progress, task3)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context,
         version: Annotated[bool, typer.Option(
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
         dev: Annotated[bool, typer.Option(hidden=True)] = False
         ):
    """
        FileNet Content Manager Upgrade CLI.
    """
    if verbose:
        state["verbose"] = True
        FILE_LOG_LEVEL = logging.DEBUG
    else:
        FILE_LOG_LEVEL = logging.WARNING

    if dryrun:
        state["dryrun"] = True

    if dev:
        state["dev"] = True

    state["logger"] = setup_logger(FILE_LOG_LEVEL)

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

    if ctx.invoked_subcommand is None:
        display_mode_version("Operator and Deployment Upgrade",
                             "Upgrade of the FNCM Operator and Deployment")
        files.append("ibm_fncm_cr_production_FC_content.yaml")

    elif ctx.invoked_subcommand == "operator":
        display_mode_version("Operator Upgrade", "Upgrade for the FNCM Operator Only")

    elif ctx.invoked_subcommand == "deployment":
        display_mode_version("Deployment Upgrade", "Upgrade for the FNCM Deployment Only")
        files.append("ibm_fncm_cr_production_FC_content.yaml")

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

    # Read Version File
    version_path = os.path.join(os.path.dirname(os.getcwd()), "version.toml")

    if os.path.exists(version_path):
        state["version_data"] = read_version_toml(version_path, state["logger"])
    else:
        state["version_data"] = {}

    if silent:
        state["silent"] = True
        state["setup"] = sg.SilentGatherOptions(state["logger"],
                                                os.path.join("silent_config",
                                                             "silent_install_upgradedeployment.toml"),
                                                script_type="upgrade", dev=state["dev"])
        state["setup"]._podman_available = results["podman"]
        state["setup"]._docker_available = results["docker"]
        state["setup"].silent_parse_upgrade_variables()
        state["upgrade"] = u.Upgrade(console, state["setup"], state["logger"], silent=True,
                                     required_files=required_files)

    else:
        state["setup"] = g.GatherOptions(state["logger"], console, script_type="upgrade", dev=state["dev"])
        state["setup"]._podman_available = results["podman"]
        state["setup"]._docker_available = results["docker"]
        state["setup"].collect_license_model()
        state["setup"].collect_platform()
        state["setup"].collect_namespace()
        state["upgrade"] = u.Upgrade(console, state["setup"], state["logger"], required_files=required_files)


    state["deployment_details"] = create_deployment_info(state["setup"], state["version_data"])
    state["version_details"] = create_version_info(state["setup"], state["version_data"])

    state["upgrade"].version_details = state["version_details"]
    state["upgrade"].deployment_details = state["deployment_details"]

    if ctx.invoked_subcommand is None:

        if not state["upgrade"]._operator_present and not state["upgrade"]._cr_present:
            print()
            print(Panel.fit(
                "FNCM Standalone Operator or FNCM Standalone Deployment not found in {namespace}.\n"
                "A valid FNCM Standalone Operator or FNCM Standalone Deployment is required for this mode".format(
                    namespace=state["setup"]._namespace),
                border_style="red"))
            exit(1)

        deployment()

        print()
        operator_install = Confirm.ask("Do you want to proceed to preparing for Operator Upgrade?", default=True)
        if operator_install:
            operator()


if __name__ == "__main__":
    app()
