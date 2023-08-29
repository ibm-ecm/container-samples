###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2023. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################

import os
import pathlib
import platform
import shutil

from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.filesize import decimal
from rich.layout import Layout
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree


# Create a method to zip a folder and return the path to the zip file
def zip_folder(zip_file_name: str, folder_path: str) -> str:
    """Zip a folder and return the path to the zip file."""
    zip_file = shutil.make_archive(zip_file_name, "zip", folder_path, )
    return zip_file


# Create a method to print directory tree
def print_directory_tree(name: str, path: str) -> Tree:
    """Print a directory tree."""
    tree = Tree(f"  [bold blue] {name} [/bold blue]", guide_style="blue")
    walk_directory(pathlib.Path(path), tree)
    return tree


# Create a method to create the generatedfiles folder structure and zip it up if it is present
def create_generate_folder() -> None:
    generate_folder = os.path.join(os.getcwd(), "generatedFiles")
    generate_secrets_folder = os.path.join(generate_folder, "secrets")
    generate_ssl_secrets_folder = os.path.join(generate_folder, "ssl")
    os.mkdir(generate_folder)
    os.mkdir(generate_secrets_folder)
    os.mkdir(generate_ssl_secrets_folder)


# Clear console based on system OS
def clear(console):
    if platform.system() == 'Windows':
        os.system('cls')
    else:
        console.clear()


def walk_directory(directory: pathlib.Path, tree: Tree) -> None:
    """Recursively build a Tree with directory contents."""
    # Sort dirs first then by filename
    paths = sorted(
        pathlib.Path(directory).iterdir(),
        key=lambda path: (path.is_file(), path.name.lower()),
    )
    for path in paths:
        # Remove hidden files
        if path.name.startswith("."):
            continue
        if path.parts[-1] == "venv":
            continue
        if path.is_dir():
            style = "dim" if path.name.startswith("__") else ""
            branch = tree.add(
                f"[bold blue]  {escape(path.name)}",
                style=style,
                guide_style=style,
            )
            walk_directory(path, branch)
        else:
            text_filename = Text(path.name, "cyan")
            text_filename.highlight_regex(r"\..*$", "bold cyan")
            text_filename.stylize(f"link file://{path}")
            file_size = path.stat().st_size
            text_filename.append(f" ({decimal(file_size)})", "cyan")
            if path.suffix == ".py":
                icon = " "
            elif path.suffix == ".toml":
                icon = " "
            elif path.suffix == ".yaml":
                icon = "󱃾 "
            elif path.suffix == ".sql":
                icon = " "
            else:
                icon = " "
            tree.add(Text(icon) + text_filename)


# Create a selection summary table for the user to review
def db_summary_table(selection_summary: dict) -> Table:
    """Create a selection summary table for the user to review."""
    tableDB = Table(title="Database Selection")

    tableDB.add_column("Type", justify="right", style="cyan", no_wrap=True)
    tableDB.add_column("No. Object Stores", style="magenta")
    tableDB.add_column("SSL Enabled", justify="right", style="green")

    tableDB.add_row(selection_summary["db_type"], str(selection_summary["os_number"]), str(selection_summary["db_ssl"]))

    return tableDB


# Create a selection summary table for the user to review
def ldap_summary_table(selection_summary: dict) -> Table:
    """Create a selection summary table for the user to review."""
    tableldap = Table(title="LDAP Selection")

    tableldap.add_column("Type", justify="right", style="cyan", no_wrap=True)
    tableldap.add_column("ID", style="magenta")
    tableldap.add_column("SSL Enabled", justify="right", style="green")

    for ldap in selection_summary["ldap_info"]:
        tableldap.add_row(ldap["type"], ldap["id"], str(ldap["ssl"]))

    return tableldap


def selection_tree(selection_summary: dict) -> Tree:
    """Create a selection summary tree for the user to review."""
    tree = Tree("Selection Summary", guide_style="cyan")

    license_tree = Tree("License Model")
    license_tree.add(selection_summary["license_model"])

    tree.add(license_tree)

    platform_tree = Tree("Platform")
    platform_tree.add(selection_summary["platform"])

    if selection_summary["ingress"]:
        ingress_tree = Tree("Ingress")
        ingress_tree.add(str(selection_summary["ingress"]))
        platform_tree.add(ingress_tree)

    tree.add(platform_tree)

    if selection_summary["optional_components"]:
        components_tree = Tree("Components")
        for component in selection_summary["optional_components"]:
            components_tree.add(component)
        tree.add(components_tree)

    init_tree = Tree("Content Initialization")
    init_tree.add(str(selection_summary["content_initialize"]))
    tree.add(init_tree)

    verify_tree = Tree("Content Verification")
    verify_tree.add(str(selection_summary["content_verification"]))
    tree.add(verify_tree)
    return tree


def generate_gather_results(property_folder: str, selection_summary: dict, movedb: bool, moveldap: bool) -> Layout:
    # Build Layout for display
    layout = Layout()
    layout.split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    left_panel_list = []
    right_panel_list = []

    # Create the left side panel
    # Create next steps panel
    next_steps_panel = Panel.fit("Next Steps")
    instructions = Panel.fit(
        "1. Review the toml files in the propertyFiles folder\n"
        "2. Fill the <Required> values\n"
        "3. If SSL is enabled, copy the certificate into the respective folder: ./propertyFile/ssl-certs\n"
        "4. If ICC for email was enabled, then make sure masterkey.txt file has been added under ./propertyFile/icc\n"
        "5. Run the following command to generate SQL, secrets and CR file\n"
    )
    command = Panel.fit(
        Syntax("python3 prerequisites.py generate", "bash", theme="ansi_dark")
    )

    left_panel_list.append(next_steps_panel)
    left_panel_list.append(instructions)
    left_panel_list.append(command)
    left_panel_list.append(Panel.fit(selection_tree(selection_summary)))

    left_panel = Group(*left_panel_list)

    right_panel_list.append(Panel.fit("Property Files Structure"))
    right_panel_list.append(print_directory_tree("propertyFiles", property_folder))

    # Create the right side panel
    right_panel_list.append(Panel.fit(db_summary_table(selection_summary)))
    if movedb:
        right_panel_list.append(Panel.fit("Database properties moved"))

    right_panel_list.append(Panel.fit(ldap_summary_table(selection_summary)))
    if moveldap:
        right_panel_list.append(Panel.fit("LDAP properties moved"))

    right_panel = Group(*right_panel_list)

    layout["right"].update(right_panel)
    layout["left"].update(left_panel)

    return layout


def generate_generate_results(generate_folder: str, required_fields: dict, certs=[],masterkey_present=True) -> Layout:
    # Build Layout for display
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = None
    layout["lower"].ratio = 9

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].size = None
    layout["right"].ratio = 2

    left_panel_list = []

    # Display error screen if there are missing values
    if len(required_fields) != 0 or len(certs) != 0 or masterkey_present == False:

        message = Text("Issues Found", style="bold red", justify="center")
        result_panel = Panel(message)

        layout["upper"].update(result_panel)
        # Create the left side panel
        # Create next steps panel
        next_steps_panel = Panel.fit("Remediation Steps")
        instructions = Panel.fit(
            "1. Use the tables to fix the missing values for the toml files \n"
            "2. If there are missing SSL certificates, add them to respective folder under ./propertyFile/ssl-certs\n"
            "3. If ICC for email set up was requested then make sure masterkey.txt file has been added under ./propertyFile/icc\n"
            "4. Rerun the below command once all the <\"Required\"> values are filled \n"
        )
        command = Panel.fit(
            Syntax("python3 prerequisites.py generate", "bash", theme="ansi_dark")
        )

        left_panel_list.append(next_steps_panel)
        left_panel_list.append(instructions)
        left_panel_list.append(command)

        left_panel = Group(*left_panel_list)

        section_files = ['fncm_db_server.toml',
                         'fncm_ldap_server.toml',
                         'fncm_custom_component_properties.toml']
        unsectioned_files = ['fncm_user_group.toml',
                             'fncm_deployment.toml',
                             'fncm_ingress.toml']

        error_tables = []

        for file in required_fields:
            if file in section_files:
                parsed_parameters = parse_required_fields(required_fields[file])
                error_table = Table(title=file)
                error_table.add_column("Section", style="cyan", no_wrap=True)
                error_table.add_column("Parameters", style="blue")
                for section in parsed_parameters:
                    parameters = ""
                    for i in parsed_parameters[section]:
                        parameters += "- " + i + "\n"
                    error_table.add_row(section, parameters)

                error_tables.append(error_table)

            elif file in unsectioned_files:
                error_table = Table(title=file)
                error_table.add_column("Parameters", style="blue")
                for section in required_fields[file]:
                    parameters = ""
                    parameters += "- " + section[0][0]
                    error_table.add_row(parameters)

                error_tables.append(error_table)

        if len(certs) > 0:
            error_table = Table(title="SSL Certificates Missing")
            error_table.add_column("Connection", style="magenta")
            error_table.add_column("Missing", style="red")
            for connection in certs:
                files = ""
                for i in certs[connection]:
                    files += "- " + i + "\n"
                error_table.add_row(connection, files)

            error_tables.append(error_table)

        if not masterkey_present:
            error_table = Table(title="ICC Setup")
            error_table.add_column("Missing", style="red")
            error_table.add_row("masterkey.txt")

            error_tables.append(error_table)

        error_table_output = Columns(error_tables)

        layout["lower"]["right"].update(error_table_output)
        layout["lower"]["left"].update(left_panel)

    else:

        right_panel_list = []

        # Create the left side panel
        # Create next steps panel
        message = Text("Files Generated Successfully", style="bold cyan", justify="center")
        result_panel = Panel(message)

        layout["upper"].update(result_panel)

        next_steps_panel = Panel.fit("Next Steps")
        instructions = Panel.fit(
            "1. Review the Generated files: \n"
            "  - Database SQL files\n"
            "  - Deployment Secrets \n"
            "  - SSL Certs in yaml format\n"
            "  - Custom Resource (CR) file\n"
            "2. Use the SQL files to create the databases \n"
            "3. Run the following command to validate \n"
        )
        command = Panel.fit(
            Syntax("python3 prerequisites.py validate", "bash", theme="ansi_dark")
        )

        left_panel_list.append(next_steps_panel)
        left_panel_list.append(instructions)
        left_panel_list.append(command)

        left_panel = Group(*left_panel_list)

        right_panel_list.append(Panel.fit("Generated Files Structure"))
        right_panel_list.append(print_directory_tree("generatedFiles", generate_folder))

        right_panel = Group(*right_panel_list)

        layout["lower"]["right"].update(right_panel)
        layout["lower"]["left"].update(left_panel)

    return layout


def parse_required_fields(required_fields):
    parsed_fields = {}
    for entry in required_fields:
        section = entry[0][0]
        paramter = entry[0][1]
        # check if section exists
        if section not in parsed_fields:
            parsed_fields[section] = []
        parsed_fields[section].append(paramter)
    return parsed_fields


def generate_validate_results(required_fields: dict, tools: list, certs: list) -> Layout:
    # Build Layout for display
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = None
    layout["lower"].ratio = 9

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    message = Text("Issues Found", style="bold red", justify="center")
    Align(message, align="center")
    result_panel = Panel(message)

    layout["upper"].update(result_panel)

    left_panel_list = []

    # Create the left side panel
    # Create next steps panel
    next_steps_panel = Panel.fit("Remediation Steps")
    instructions = Panel.fit(
        "1. Use the tables to fix the missing values for the toml files\n"
        "2. If there are any tools missing, install them\n"
        "3. If there are missing SSL certificates, add them to respective folder under ./propertyFile/ssl-certs\n"
        "4. Make sure you are connected to a K8s Cluster for Storage Validation \n"
        "5. Rerun the below command once all the <\"Required\"> values are filled \n"
    )
    command = Panel.fit(
        Syntax("python3 prerequisites.py validate", "bash", theme="ansi_dark")
    )

    left_panel_list.append(next_steps_panel)
    left_panel_list.append(instructions)
    left_panel_list.append(command)

    left_panel = Group(*left_panel_list)

    section_files = ['fncm_db_server.toml',
                     'fncm_ldap_server.toml']
    unsectioned_files = ['fncm_deployment.toml']

    error_tables = []

    for file in required_fields:
        if file in section_files:
            parsed_parameters = parse_required_fields(required_fields[file])
            error_table = Table(title=file)
            error_table.add_column("Section", style="cyan", no_wrap=True)
            error_table.add_column("Parameters", style="blue")
            for section in parsed_parameters:
                parameters = ""
                for i in parsed_parameters[section]:
                    parameters += "- " + i + "\n"
                error_table.add_row(section, parameters)

            error_tables.append(error_table)

        elif file in unsectioned_files:
            error_table = Table(title=file)
            error_table.add_column("Parameters", style="blue")
            for section in required_fields[file]:
                parameters = ""
                parameters += "- " + section[0][0]
                error_table.add_row(parameters)

            error_tables.append(error_table)

    if len(tools) > 0:
        if "connection" in tools:
            error_tables.append(Panel.fit("K8s Cluster not Connected", style="bold cyan"))
            tools.remove("connection")

        if len(tools) > 0:
            error_table = Table(title="Tools Missing")
            error_table.add_column("Tools", style="green")
            for tool in tools:
                if tool != "connection":
                    error_table.add_row("- " + tool)
            error_tables.append(error_table)

    if len(certs) > 0:
        error_table = Table(title="SSL Certificates Missing")
        error_table.add_column("Connection", style="magenta")
        error_table.add_column("Missing", style="red")
        for connection in certs:
            files = ""
            for i in certs[connection]:
                files += "- " + i + "\n"
            error_table.add_row(connection, files)

        error_tables.append(error_table)

    error_table_output = Columns(error_tables)

    layout["lower"]["right"].update(error_table_output)
    layout["lower"]["left"].update(left_panel)

    return layout


# Function to check if ssl certs are added to the respective folders
def check_ssl_folders(db_prop, ldap_prop, ssl_cert_folder) -> list:
    missing_cert = {}
    # if any ssl cert folders exists that means ssl was enabled for either ldap or DB
    if os.path.exists(ssl_cert_folder):
        ssl_folders = os.listdir(ssl_cert_folder)

        # remove any hidden files that might be picked up
        for folder in ssl_folders:
            if folder.startswith("."):
                ssl_folders.remove(folder)

        # checking to see if any changes to ssl value have been made after folders were created
        skipped_folders = []
        for folder in ssl_folders:
            if "ldap" in folder:
                if "LDAP_SSL_ENABLED" not in list(ldap_prop[folder.upper()].keys()):
                    skipped_folders.append(folder)
                else:
                    if not ldap_prop[folder.upper()]["LDAP_SSL_ENABLED"]:
                        skipped_folders.append(folder)
            else:
                if "DATABASE_SSL_ENABLE" not in list(db_prop.keys()):
                    skipped_folders.append(folder)
                else:
                    if not db_prop["DATABASE_SSL_ENABLE"]:
                        skipped_folders.append(folder)
        ssl_folders = [item for item in ssl_folders if item not in skipped_folders]

        # if db type is not postgres we have a standard folder structure of ssl certs
        if db_prop["DATABASE_TYPE"].lower() != "postgresql":
            for folder in ssl_folders:
                ssl_certs = os.listdir(os.path.join(ssl_cert_folder, folder))
                if not ssl_certs:
                    missing_cert[folder] = ["certificate"]
        else:
            # if db type is postgres we have three sub folders inside the db ssl cert folders which need to be checked for ssl certs
            for folder in ssl_folders:
                if "ldap" not in folder.lower():
                    sub_folder_path = os.path.join(ssl_cert_folder, folder)
                    sub_folders = os.listdir(sub_folder_path)
                    for sub_folder in sub_folders:
                        if sub_folder.startswith("."):
                            sub_folders.remove(sub_folder)

                server_ca = False
                clientkey = False
                clientcert = False
                for sub_folder in sub_folders:
                    if "serverca" in sub_folder.lower():
                        server_ca_items = os.listdir(os.path.join(sub_folder_path, sub_folder))
                        if server_ca_items:
                            server_ca = True
                    if "clientkey" in sub_folder.lower():
                        clientkey_items = os.listdir(os.path.join(sub_folder_path, sub_folder))
                        if clientkey_items:
                            clientkey = True
                    if "clientcert" in sub_folder.lower():
                        clientcert_items = os.listdir(os.path.join(sub_folder_path, sub_folder))
                        if clientcert_items:
                            clientcert = True

                if db_prop["SSL_MODE"].lower() == "verify-full":
                    # All certs are required for "verify-full" mode
                    if not server_ca:
                        if folder not in missing_cert:
                            missing_cert[folder] = []
                            missing_cert[folder].append("serverca")
                        else:
                            missing_cert[folder].append("serverca")
                    if not clientkey:
                        if folder not in missing_cert:
                            missing_cert[folder] = []
                            missing_cert[folder].append("clientkey")
                        else:
                            missing_cert[folder].append("clientkey")
                    if not clientcert:
                        if folder not in missing_cert:
                            missing_cert[folder] = []
                            missing_cert[folder].append("clientcert")
                        else:
                            missing_cert[folder].append("clientcert")
                elif db_prop["SSL_MODE"].lower() == "require":
                    # Require mode can be either Client or Server Authentication
                    # Selected Client Authentication
                    if clientcert or clientkey:
                        if not clientkey:
                            if folder not in missing_cert:
                                missing_cert[folder] = []
                                missing_cert[folder].append("clientkey")
                            else:
                                missing_cert[folder].append("clientkey")
                        if not clientcert:
                            if folder not in missing_cert:
                                missing_cert[folder] = []
                                missing_cert[folder].append("clientcert")
                            else:
                                missing_cert[folder].append("clientcert")
                    # Selected Server Authentication
                    elif not server_ca:
                        if folder not in missing_cert:
                            missing_cert[folder] = []
                            missing_cert[folder].append("serverca")
                        else:
                            missing_cert[folder].append("serverca")
                elif db_prop["SSL_MODE"].lower() == "verify-ca":
                    # Verify-ca mode requires a server-ca cert
                    if clientcert or clientkey:
                        if not server_ca:
                            if folder not in missing_cert:
                                missing_cert[folder] = []
                                missing_cert[folder].append("serverca")
                            else:
                                missing_cert[folder].append("serverca")

                        if not clientkey:
                            if folder not in missing_cert:
                                missing_cert[folder] = []
                                missing_cert[folder].append("clientkey")
                            else:
                                missing_cert[folder].append("clientkey")

                        if not clientcert:
                            if folder not in missing_cert:
                                missing_cert[folder] = []
                                missing_cert[folder].append("clientcert")
                            else:
                                missing_cert[folder].append("clientcert")
                    else:
                        if not server_ca:
                            if folder not in missing_cert:
                                missing_cert[folder] = []
                                missing_cert[folder].append("serverca")
                            else:
                                missing_cert[folder].append("serverca")
                    # base logic for ldap cert folder
                else:
                    ssl_certs = os.listdir(os.path.join(ssl_cert_folder, folder))
                    if not ssl_certs:
                        if folder not in missing_cert:
                            missing_cert[folder] = []
                            missing_cert[folder].append("certificate")
                        else:
                            missing_cert[folder].append("certificate")

    return missing_cert


# Function to check if icc masterkey file is present
def check_icc_masterkey(custom_component_prop,icc_folder):
    # if custom component property file is empty then we know icc is not present and we can skip the check
    if not custom_component_prop:
        return True
    if custom_component_prop and "CSS" not in custom_component_prop.keys():
        return True
    #the file to create the secret has to be in .txt format
    if os.path.exists(icc_folder):
        file_list = os.listdir(icc_folder)
        if not file_list:
            return False
        else:
            for file in file_list:
                if file.endswith('.txt'):
                    return True
            return False