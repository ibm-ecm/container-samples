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
from click import style
from rich import print
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn, \
    TimeElapsedColumn
from rich.prompt import Confirm
from rich.text import Text
from typing_extensions import Annotated

from helper_scripts.gather import gather as g
from helper_scripts.gather import silent_gather as sg
from helper_scripts.loadimages import load_extract as le
from helper_scripts.utilities.interface import clear, display_issues, display_prereq_passed, \
    generate_loadimages_results, generate_loadimage_results, display_airgap_vars, display_manifest_results
from helper_scripts.utilities.utilities import validate_image_details_file, prereq_checks, read_version_toml, \
    validate_airgap_details_file

__version__ = "7.1.6"

app = typer.Typer()

state = {
    "verbose": False,
    "silent": False,
    "logger": logging,
    "dev": False,
    "setup": None,
    "image_details": "",
    "dryrun": False,
    "airgap": False,
    "version_data": {},
    "tls_verify": True
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
    file_handler = logging.FileHandler("loadimages.log")
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
        print(f"FileNet Content Manager Load Images CLI: {__version__}")
        raise typer.Exit()


def push_airgap_images():
    load = le.LoadExtract(console, state["logger"], silent=state["silent"], dev=state["dev"], airgap=state["airgap"],
                          folder_path=state["image_details"], version_data=state["version_data"], tls_verify=state["tls_verify"])

    # Check and validate the airgap details file
    airgap_detail_file = os.path.join(state["image_details"], "airgap_variables.sh")

    airgap_vars = validate_airgap_details_file(logger=state["logger"], airgap_details_file=airgap_detail_file)

    # Set the airgap variables
    load.airgap_vars = airgap_vars

    print(display_airgap_vars(airgap_vars))

    if not state["silent"]:
        print()
        start_copy = Confirm.ask("Do you want to to proceed with Generating the Mirror Manifests?",
                                 default=True)

        if not start_copy:
            exit(1)

    print()
    print(Panel.fit(Text("Starting Airgap Mirror Manifest Generation"), style="cyan"))
    print()
    state["logger"].info(f"Starting Airgap Mirror Manifest Generation")

    with Progress(SpinnerColumn(),
                  TextColumn("[progress.description]{task.description}"),
                  BarColumn(),
                  transient=True,
                  console=console) as progress:
        task1 = progress.add_task("Enable OC Mirror", total=1)
        task2 = progress.add_task("Generating Image Mirror Manifest", total=None)

        # Enable OC mirror tool
        oc_enabled = load.enable_oc_image(progress, task1)

        # Generate Mirror Manifests
        manifest_results = load.generate_mirror_manifests(progress, task2)

    if not oc_enabled:
        print(Text("OC Mirror tool is not available. Please install the tool and try again.", style("bold red")))
        state["logger"].info(f"OC Mirror tool is not available. Please install the tool and try again.")
        exit(1)

    if not manifest_results:
        print(Text("Mirror manifest failed to generate. Please check error logs for more information", style("bold red")))
        state["logger"].info(f"Mirror manifest failed to generate.")
        exit(1)

    clear(console)

    # Print mirror manifests results
    print(display_manifest_results(manifest_results))

    # Check image channels
    # Let customer select which channel to mirror
    load.collect_image_channels()

    if not state["silent"]:
        print()
        start_copy = Confirm.ask("Do you want to to proceed with Airgap Mirroring?",
                                 default=True)

        if not start_copy:
            exit(1)
    if state["dryrun"]:
        exit()

    clear(console)

    print(Panel.fit("Starting FileNet Content Manager Airgap Image Mirror", style="cyan"))
    state["logger"].info(f"Starting FileNet Content Manager Airgap Image Mirroring")
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
    ) as progress:

        task1 = progress.add_task("[green]Airgap Setup", total=1)
        task2 = progress.add_task("[green]Mirror Images", total=None)

        while not progress.finished:
            load.apply_image_mirror_policy(progress, task1)
            load.mirror_images(progress, task2)


    # print(generate_loadimage_results(load.image_push_summary))


def push_cncf_images():
    load = le.LoadExtract(console, state["logger"], silent=state["silent"], dev=state["dev"], airgap=state["airgap"],
                          folder_path=state["image_details"])

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

    print(Panel.fit("Starting FileNet Content Manager Image Push", style="cyan"))
    state["logger"].info(f"Starting FileNet Content Manager Image Push")
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


def generate_cncf_images():
    extract = le.LoadExtract(console, state["logger"], silent=state["silent"], dev=state["dev"], airgap=state["airgap"],
                             folder_path=state["image_details"], version_data=state["version_data"], tls_verify=state["tls_verify"])
    extract.parse_content_template()
    extract.parse_operator_template()
    extract.create_image_details_file()

    layout = generate_loadimages_results(state["image_details"])
    print(layout)


def generate_airgap_images():
    extract = le.LoadExtract(console, state["logger"], silent=state["silent"], dev=state["dev"], airgap=state["airgap"],
                             folder_path=state["image_details"], version_data=state["version_data"], tls_verify=state["tls_verify"])

    # Determine CASE Package version to download
    # Check if version was provided via CLI
    casepackage_version = state.get("casepackage_version", "")

    # If not, check if version was provided via version file
    if not casepackage_version:
        # Collect CASEPackage Version from version.toml
        # Collect base version from version.toml
        if state["version_data"]:
            fncm_version = state["version_data"]["VERSION"].split('-')[0]
            extract.fncm_version = fncm_version
            if "CASE_VERSION" in state["version_data"]:
                casepackage_version = state["version_data"]["CASE_VERSION"]

    # If still not set, exit with error
    if not casepackage_version:
        print(Text("CASE Package version not specified. Please provide a version via --casepackage-version or "
                   "in the version.toml file.", style="bold red"))
        exit(1)

    # Validate the provided CASE Package version from the index.yaml download
    # Retrieve available CASE Package versions in a list
    extract.collect_case_versions()
    if extract.case_versions:
        extract.validate_case_package_version(casepackage_version)

    casepackage_version = extract.casepackage_version

    extract.ibmpak_home = os.path.join(os.getcwd())

    airgap_vars = {
        "IBMPAK_HOME": extract.ibmpak_home,
        "CASE_NAME": 'ibm-cp-fncm-case',
        "CASE_VERSION": casepackage_version,
        "CASE_INVENTORY_SETUP": 'fncmOperatorSetup',
    }

    extract.airgap_vars = airgap_vars

    if not state["silent"]:
        print()
        start_download = Confirm.ask("Do you want to to proceed with CASE Package Download?",
                                 default=True)

        if not start_download:
            exit(1)

    if not state["dryrun"]:
        # Download CASE Package
        case_output = extract.download_case()
        clear(console)
        print(case_output)

    # Check podman availability
    podman = state["setup"].podman_available

    # Check if XDG_RUNTIME_DIR is set
    # This is needed to be defined before login
    if not podman:
        registry_auth = os.path.join(os.environ.get("HOME"), ".docker", "config.json")
    else:
        if os.environ.get("XDG_RUNTIME_DIR"):
            registry_auth = os.path.join(os.environ.get("XDG_RUNTIME_DIR"), "containers", "auth.json")
            extract.add_airgap_vars('XDG_RUNTIME_DIR', os.environ.get("XDG_RUNTIME_DIR"))
        else:
            registry_auth = os.path.join(os.getcwd(), '.ibm-pak', 'auth.json')

    extract.add_airgap_vars('REGISTRY_AUTH_FILE', registry_auth)
    os.environ['REGISTRY_AUTH_FILE'] = registry_auth

    # Collect Private and Registry info
    state["setup"].collect_verify_entitlement_key()
    state["setup"].collect_verify_private_registry()

    private_registry = state["setup"].private_registry_server

    extract.private_registry_server = private_registry
    extract.add_airgap_vars('TARGET_REGISTRY', private_registry)

    # Create Airgap Details file
    extract.create_airgap_details_file()

    layout = generate_loadimages_results(state["image_details"], airgap=True)
    print(layout)


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

    if state["airgap"]:
        msg += "\nOpenShift Airgap Mode Enabled"

    if state["silent"]:
        msg += "\nSilent Mode Enabled"

    if state["verbose"]:
        msg += "\nVerbose Logging Enabled"

    if not state["tls_verify"]:
        msg += "\nTLS Verification Disabled for Podman Operations"

    print(Panel.fit(msg, title="FileNet Content Manager Load Images CLI", border_style="green"))
    print()


@app.command()
def generate():
    """
        Generate the image details file.
    """
    if state['airgap']:
        generate_airgap_images()
    else:
        generate_cncf_images()


@app.command()
def push():
    """
        Push images to a registry based on existing image details file.
    """

    if state['airgap']:
        push_airgap_images()
    else:
        push_cncf_images()


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
         tls_verify: Annotated[bool, typer.Option(
             help="Enable TLS verification for Podman operations.",
             rich_help_panel="Customization and Utils")] = True,
         airgap: Annotated[bool, typer.Option(
             help="Enable OCP Airgap mode.",
             rich_help_panel="Customization and Utils")] = False,
         dryrun: Annotated[bool, typer.Option(
             help="Perform a dry run",
             rich_help_panel="Customization and Utils")] = False,
         casepackage_version: Annotated[str, typer.Option(
                help="Specify CASE Package version to download (Airgap mode only).",
                rich_help_panel="Customization and Utils")] = "",
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
    if airgap:
        state["airgap"] = True
    if casepackage_version:
        state["casepackage_version"] = casepackage_version
    if not tls_verify:
        state["tls_verify"] = False

    if airgap:
        state["image_details"] = os.path.join(os.getcwd(), "airgapDetails")
    else:
        state["image_details"] = os.path.join(os.getcwd(), "imageDetails")

    if not os.path.exists(state["image_details"]):
        os.mkdir(state["image_details"])

    if airgap:
        if ctx.invoked_subcommand is None:
            display_mode_version("Airgap CASE and Image Mirror",
                                 "Download CASE Package and Mirror Images to Private Registry")
            checks = ["podman", 'oc', 'connection', 'ibm-pak', 'mirror']
            files = []

        elif ctx.invoked_subcommand == "push":
            display_mode_version("Airgap Image Mirror", "Mirror Images to Private Registry Only")
            checks = ["podman", 'oc', 'connection', 'mirror']
            files = []


        elif ctx.invoked_subcommand == "generate":
            display_mode_version("Airgap CASE Setup", "Download and Setup CASE Package Only")
            checks = ["podman", 'oc', 'ibm-pak']
            files = []
    else:
        if ctx.invoked_subcommand is None:
            display_mode_version("Extract and Push Images",
                                 "Generate ImageDetails and Push images to Private Registry")
            checks = ["podman", "skopeo"]
            files = ["ibm_fncm_cr_production_FC_content.yaml"]

        elif ctx.invoked_subcommand == "push":
            display_mode_version("Push Images", "Push Images to Private Registry Only")
            checks = ["podman", "skopeo"]
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

    # Read Version File
    version_path = os.path.join(os.path.dirname(os.getcwd()), "version.toml")
    if not os.path.exists(version_path):
        version_path = os.path.join(os.path.dirname(os.path.dirname(os.getcwd())), "version.toml")

    if os.path.exists(version_path):
        state["version_data"] = read_version_toml(version_path, state["logger"])
        state["version_data"]["VERSION"] = state["version_data"]["VERSION"].split('-')[0]
    else:
        state["version_data"] = {}

    if not state["silent"]:
        # this is the user details object which does pre-checks and collects some necessary details
        state["setup"] = g.GatherOptions(state["logger"], console, script_type="load_extract", dev=state["dev"], tls_verify=state["tls_verify"])

        state["setup"].podman_available = results["podman"]
    else:
        # this is the user details object which does pre-checks and collects some necessary details
        silent_path = os.path.join("silent_config", "silent_install_loadimages.toml")
        state["setup"] = sg.SilentGatherOptions(state["logger"], silent_path, script_type="load_extract", dev=state["dev"], tls_verify=state["tls_verify"])
        state["setup"].silent_parse_load_images_file(airgap)

        # Retrieve silent version and channel selection
        fncm_version = state["setup"].fncm_version
        all_channels = state["setup"].all_channels

        state["version_data"]["VERSION"] = fncm_version
        state["version_data"]["ALL_CHANNELS"] = all_channels

        state["setup"].podman_available = results["podman"]

    if ctx.invoked_subcommand is None:
        generate()
        push()


if __name__ == "__main__":
    app()
