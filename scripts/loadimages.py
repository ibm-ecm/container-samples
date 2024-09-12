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

# Script to copy images to the private registry
'''
This script loads images to a private registry and
generates a set of tags and repositories to be copied
there is an extract mode to create the list of images and a load option to load that list of images
the default mode creates a list and uploads those images to private registry
'''
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

from helper_scripts.gather import gather as g
from helper_scripts.gather import silent_gather as sg
from helper_scripts.loadimages import load_extract as le
from helper_scripts.utilities.interface import clear, display_issues, display_prereq_passed, \
    generate_loadimages_results, generate_loadimage_results
from helper_scripts.utilities.utilities import validate_image_details_file, prereq_checks

__version__ = "3.1.0"

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


def setup_logger(file_log_level, verbose=False):
    # Create a logger object
    logger = logging.getLogger("loadimages")

    shell_handler = RichHandler()
    file_handler = logging.FileHandler("loadimages.log")

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
        print(f"FileNet Content Manager Load Images CLI: {__version__}")
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

    print(Panel.fit(msg, title="FileNet Content Manager Load Images CLI", border_style="green"))
    print()


@app.command()
def generate():
    """
        Generate the image details file.
    """
    if not state["dryrun"]:
        extract = le.LoadExtract(console, state["logger"], silent=state["silent"], dev=state["dev"],
                                 folder_path=state["image_details"], script_mode="generate")
        extract.parse_content_template()
        extract.parse_operator_template()
        extract.create_image_details_file()

    layout = generate_loadimages_results(state["image_details"])
    print(layout)


@app.command()
def push():
    """
        Push images to a registry based on existing image details file.
    """

    load = le.LoadExtract(console, state["logger"], silent=state["silent"], dev=state["dev"],
                          folder_path=state["image_details"], script_mode="load")

    image_detail_file = os.path.join(state["image_details"], "imageDetails.toml")

    image_prop_dict = validate_image_details_file(logger=state["logger"], image_tag_file=image_detail_file)

    load.parse_toml_file(image_details_dict=image_prop_dict)

    state["setup"].collect_verify_entitlement_key()
    state["setup"].collect_verify_private_registry()

    private_registry = state["setup"].private_registry_server

    load.private_registry_server = private_registry

    number_of_images = load.number_of_images

    if not state["silent"]:
        print()
        start_copy = Confirm.ask("Do you want to to proceed with pushing the images to the private registry?",
                                 default=True)

        if not start_copy:
            exit(1)
    if state["dryrun"]:
        exit()

    clear(console)

    print(Panel.fit("Starting FNCM Standalone Image Push", style="cyan"))
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

        task1 = progress.add_task("[green]Pushing Images", total=number_of_images)

        while not progress.finished:
            load.copy_images(progress, task1)

    print(generate_loadimage_results(load.image_push_summary))


# main function
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
         dev: Annotated[bool, typer.Option(hidden=True)] = False):
    """
        FileNet Content Manager Load Images CLI.
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

    state["image_details"] = os.path.join(os.getcwd(), "imageDetails")
    if not os.path.exists(state["image_details"]):
        os.mkdir(state["image_details"])

    if ctx.invoked_subcommand is None:
        display_mode_version("Extract and Push Images",
                             "Generate ImageDetails and Push images to Private Registry")
        checks = ["podman", "docker", "skopeo"]
        files = ["ibm_fncm_cr_production_FC_content.yaml"]

    elif ctx.invoked_subcommand == "push":
        display_mode_version("Push Images", "Push Images to Private Registry Only")
        checks = ["podman", "docker", "skopeo"]
        files = []


    elif ctx.invoked_subcommand == "generate":
        display_mode_version("Generate Image Detail File", "Generate Image Details File Only")
        checks = []
        files = ["ibm_fncm_cr_production_FC_content.yaml"]

    descriptor_path = os.path.join(os.path.dirname(os.getcwd()), "descriptors")

    required_files = []
    for file in files:
        required_files.append(os.path.join(descriptor_path, file))

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
        # this is the user details object which does pre-checks and collects some necessary details
        state["setup"] = g.GatherOptions(state["logger"], console, script_type="load_extract", dev=state["dev"])

        state["setup"].podman_available = results["podman"]
        state["setup"].docker_available = results["docker"]
    else:
        # this is the user details object which does pre-checks and collects some necessary details
        silent_path = os.path.join("silent_config", "silent_install_loadimages.toml")
        state["setup"] = sg.SilentGatherOptions(state["logger"],
                                                silent_path, script_type="load_extract", dev=state["dev"])
        state["setup"].silent_parse_load_images_file()
        state["setup"].podman_available = results["podman"]
        state["setup"].docker_available = results["docker"]


    if ctx.invoked_subcommand is None:
        generate()
        push()


if __name__ == "__main__":
    app()
