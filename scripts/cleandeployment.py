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
'''
Script to clean FNCM Standalone Operator and deployments
- The default behaviour is to just clean up the deployment
- An additional mode called operator can be run to uninstall the operator as well
- Silent and Verbose mode supported
'''
import logging
import os

import typer
from rich import print
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TimeElapsedColumn,
    MofNCompleteColumn, BarColumn, TaskProgressColumn, TextColumn,
)
from rich.prompt import Confirm
from typing_extensions import Annotated

from helper_scripts.cleanup import cleanup as dc
from helper_scripts.gather import gather as g
from helper_scripts.gather import silent_gather as sg
from helper_scripts.utilities.interface import display_prereq_passed, display_issues, clear, \
    display_deployment_resources
from helper_scripts.utilities.utilities import prereq_checks, create_version_info, read_version_toml

__version__ = "3.1.0"

app = typer.Typer()

state = {
    "verbose": False,
    "silent": False,
    "logger": logging,
    "setup": None,
    "clean": None,
    "dryrun": False,
    "version_details": {}
}

console = Console(record=True)


def setup_logger(file_log_level, verbose=False):
    # Create a logger object
    logger = logging.getLogger("fncm-cleanup")

    shell_handler = RichHandler()
    file_handler = logging.FileHandler("fncm-cleanup.log")

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
        print(f"FileNet Content Manager Cleanup CLI: {__version__}")
        raise typer.Exit()


# Create a function to display the mode and version
def display_mode_version(mode: str, description: str):
    """
        Display the mode and version of the script.
    """
    clear(console)
    print()
    msg = (f"Version: {__version__}\n"
           f"Mode: {mode}\n"
           f"{description}")

    if state["dryrun"]:
        msg += "\nDry Run Enabled"

    print(Panel.fit(msg, title="FileNet Content Manager Cleanup CLI", border_style="green"))
    print()


# main function
@app.command()
def operator():
    """
        Uninstall FNCM Operator Only.
    """
    operator_dict = state["clean"].collect_operator_details()
    if not operator_dict:
        print()
        print(Panel.fit("FNCM Standalone Operator not found in {namespace}".format(
            namespace=state["clean"]._deployment_prerequisites.namespace), border_style="red"))
        exit()

    cleanup_summary = display_deployment_resources(logger=state['logger'],
                                                   operator_details=operator_dict,
                                                   version_details=state["version_details"])

    print()
    print()
    print(cleanup_summary)

    # ask to delete CR from deployment only for non silent mode
    if not state["silent"]:
        clean_deployment = Confirm.ask(
            "Do you want to proceed and cleanup the above FNCM Standalone Operator?")
    else:
        clean_deployment = True

    if state["dryrun"]:
        clean_deployment = False

    if clean_deployment:
        clear(console)

        if operator_dict["type"] == "OLM":
            operator_task_num = 4
        else:
            operator_task_num = 5

        print(Panel.fit("Starting FNCM Standalone Operator Cleanup", style="cyan"))
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

            task1 = progress.add_task("[green]Uninstalling FNCM Standalone Operator", total=operator_task_num)

            while not progress.finished:
                state["clean"].delete_operator(task1, progress)


@app.command()
def deployment():
    """
        Uninstall FNCM Deployment Only.
    """
    deployment_dict, resource_dict = state["clean"].collect_cr_details()

    if not deployment_dict:
        print()
        print(Panel.fit(
            "FNCM Standalone Deployment not found in {namespace}".format(
                namespace=state["clean"]._deployment_prerequisites.namespace),
            border_style="red"))
        exit()

    cleanup_summary = display_deployment_resources(logger=state['logger'],
                                                   deployment_resources=resource_dict,
                                                   deployment_details=deployment_dict,
                                                   version_details=state["version_details"])

    print()
    print()
    print(cleanup_summary)

    # ask to delete CR from deployment only for non silent mode
    if not state["silent"]:
        clean_deployment = Confirm.ask(
            "Do you want to proceed and cleanup the above FNCM Standalone Deployment?")
    else:
        clean_deployment = True

    if state["dryrun"]:
        clean_deployment = False

    if clean_deployment:
        clear(console)

        print(Panel.fit("Starting FNCM Standalone Deployment Cleanup", style="cyan"))
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

            task1 = progress.add_task("[yellow]Cleaning FNCM Standalone Deployment", total=8)

            while not progress.finished:
                state["clean"].delete_CR(task1, progress)


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
             rich_help_panel="Customization and Utils")] = False):
    """
        FileNet Content Manager Deployment Cleanup CLI.
    """
    if verbose:
        state["verbose"] = True
        FILE_LOG_LEVEL = logging.DEBUG
    else:
        FILE_LOG_LEVEL = logging.WARNING

    state["logger"] = setup_logger(FILE_LOG_LEVEL)

    if dryrun:
        state["dryrun"] = True

    if ctx.invoked_subcommand is None:
        display_mode_version("Deployment and Operator Cleanup",
                             "Clean up of the FNCM Deployment and FNCM Standalone Operator")

    elif ctx.invoked_subcommand == "operator":
        display_mode_version("Operator Cleanup", "Clean up of the FNCM Operator Only")

    elif ctx.invoked_subcommand == "deployment":
        display_mode_version("Deployment Cleanup", "Clean up of the FNCM Deployment Only")

    checks = ["kubectl", "podman", "docker"]
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

    # Read Version File
    version_path = os.path.join(os.path.dirname(os.getcwd()), "version.toml")

    if os.path.exists(version_path):
        state["version_data"] = read_version_toml(version_path, state["logger"])
    else:
        state["version_data"] = {}

    if silent:
        state["silent"] = True
        silent_path = os.path.join("silent_config", "silent_install_cleandeployment.toml")
        state["setup"] = sg.SilentGatherOptions(state["logger"], silent_path, script_type="cleanup")
        state["setup"].podman_available = results["podman"]
        state["setup"].docker_available = results["docker"]
        state["setup"].silent_platform()
        state["setup"].silent_namespace()

    else:
        state["setup"] = g.GatherOptions(state["logger"], console, script_type="cleanup")
        state["setup"].podman_available = results["podman"]
        state["setup"].docker_available = results["docker"]
        state["setup"].collect_platform()
        state["setup"].collect_namespace()

    state["clean"] = dc.CleanDeployment(console, state["setup"], state["logger"], silent=state["silent"])
    state["version_details"] = create_version_info(state["setup"], state["version_data"])

    if ctx.invoked_subcommand is None:
        deployment_dict, resource_dict = state["clean"].collect_cr_details()
        operator_dict = state["clean"].collect_operator_details()

        if not operator_dict and not deployment_dict:
            print()
            print(Panel.fit("FNCM Standalone Operator or FNCM Standalone Deployment not found in {namespace}".format(
                namespace=state["clean"]._deployment_prerequisites.namespace), border_style="red"))
            exit(1)
        cleanup_summary = display_deployment_resources(logger=state['logger'],
                                                       deployment_resources=resource_dict,
                                                       deployment_details=deployment_dict,
                                                       operator_details=operator_dict,
                                                       version_details=state["version_details"])

        print()
        print()
        print(cleanup_summary)

        # ask to delete CR from deployment only for non silent mode
        if not state["silent"]:
            if operator_dict and deployment_dict:
                msg = "Do you want to proceed and cleanup the above FNCM Standalone Deployment and Operator?"
            elif operator_dict:
                msg = "Do you want to proceed and cleanup the above FNCM Standalone Operator?"
            else:
                msg = "Do you want to proceed and cleanup the above FNCM Standalone Deployment?"
            clean_deployment = Confirm.ask(msg)
        else:
            clean_deployment = True
        # Dry run flow ends here
        if state["dryrun"]:
            exit()

        if clean_deployment:
            clear(console)

            if operator_dict["type"] == "OLM":
                operator_task_num = 3
            else:
                operator_task_num = 5

            print(Panel.fit("Starting FNCM Standalone Deployment and Operator Cleanup", style="cyan"))
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

                if operator_dict:
                    task1 = progress.add_task("[green]Uninstalling FNCM Standalone Operator", total=operator_task_num)
                if deployment_dict:
                    task2 = progress.add_task("[yellow]Cleaning FNCM Standalone Deployment", total=8)

                while not progress.finished:
                    if operator_dict:
                        state["clean"].delete_operator(task1, progress)
                    if deployment_dict:
                        state["clean"].delete_CR(task2, progress)


if __name__ == "__main__":
    app()
