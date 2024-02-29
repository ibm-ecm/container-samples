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
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from rich.align import Align
from rich.columns import Columns
from rich.console import Group, Console
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
def create_generate_folder(trusted_certs_present) -> None:
    generate_folder = os.path.join(os.getcwd(), "generatedFiles")
    generate_secrets_folder = os.path.join(generate_folder, "secrets")
    generate_ssl_secrets_folder = os.path.join(generate_folder, "ssl")
    generate_trusted_secrets_folder = os.path.join(generate_folder, "ssl", "trusted-certs")
    os.mkdir(generate_folder)
    os.mkdir(generate_secrets_folder)
    os.mkdir(generate_ssl_secrets_folder)
    if trusted_certs_present:
        os.mkdir(generate_trusted_secrets_folder)


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
def idp_summary_table(selection_summary: dict) -> Table:
    """Create a selection summary table for the user to review."""
    tableIdp = Table(title="Identity Provider Selection")

    tableIdp.add_column("Discovery Enabled", justify="right", style="cyan", no_wrap=True)
    tableIdp.add_column("ID", style="magenta")
    tableIdp.add_column("Validation Method", justify="right", style="green")

    for idp in selection_summary["idp_info"]:
        tableIdp.add_row(str(idp["discovery_enabled"]), idp["id"], str(idp["validation_method"]))

    return tableIdp


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
        "3. If SSL is enabled, add the certificate to ./propertyFile/ssl-certs\n"
        "4. If ICC for email was enabled, then make sure masterkey.txt file has been added under ./propertyFile/icc\n"
        "5. If trusted certificates are needed, add them to ./propertyFile/trusted-certs \n"
        "6. All SSL and trusted certificates need to be in PEM (Privacy Enhanced Mail) format\n"
        "7. Run the following command to generate SQL, secrets and CR file\n"
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

    if len(selection_summary["idp_info"]) > 0:
        right_panel_list.append(Panel.fit(idp_summary_table(selection_summary)))

    if len(selection_summary["ldap_info"]) > 0:
        right_panel_list.append(Panel.fit(ldap_summary_table(selection_summary)))
        if moveldap:
            right_panel_list.append(Panel.fit("LDAP properties moved"))

    right_panel = Group(*right_panel_list)

    layout["right"].update(right_panel)
    layout["left"].update(left_panel)

    return layout


def display_issues(generate_folder=None, required_fields=None,
                   certs=None, incorrect_certs=None,
                   masterkey_present=True, invalid_trusted_certs=None,
                   keystore_password_valid=True, incorrect_naming_conv=None,
                   mode=None, tools=None, invalid_db_password_list=None, correct_ssl_mode=True,
                   deployment_prop=None) -> Layout:
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

    message = Text("Issues Found", style="bold red", justify="center")
    result_panel = Panel(message)
    layout["upper"].update(result_panel)
    # Create the left side panel
    # Create next steps panel

    # Redemption steps are built based on what issues are found
    next_steps_panel = Panel.fit("Remediation Steps")
    instruction_list = []

    section_files = ['fncm_db_server.toml',
                     'fncm_ldap_server.toml',
                     'fncm_components_options.toml',
                     'fncm_identity_provider.toml',
                     'fncm_scim_server.toml']
    unsectioned_files = ['fncm_user_group.toml',
                         'fncm_deployment.toml',
                         'fncm_ingress.toml']

    error_tables = []

    # Build the tables based on issues with required fields missing in toml files
    instruction_list.append("Use the tables to fix the missing values for the toml files")
    # adding keystore password to list of fields to be fixed if fips is enabled and keystore password is less than 16 characters
    if not keystore_password_valid:
        instruction_list.append("Keystore password length should be at least 16 characters long when FIPS is enabled.")
        if "fncm_user_group.toml" in required_fields:
            if (["KEYSTORE_PASSWORD"], "<Required>") not in required_fields["fncm_user_group.toml"]:
                required_fields["fncm_user_group.toml"].append((["KEYSTORE_PASSWORD"], "Incorrect Length"))
        else:
            required_fields["fncm_user_group.toml"] = []
            required_fields["fncm_user_group.toml"].append((["KEYSTORE_PASSWORD"], "Incorrect Length"))
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

    if certs:
        instruction_list.append(
            "Missing SSL certificates need to be added to respective folder under ./propertyFile/ssl-certs")
        error_table = Table(title="SSL Certificates Missing")
        error_table.add_column("Connection", style="magenta")
        error_table.add_column("Missing", style="red")
        for connection in certs:
            files = ""
            for i in certs[connection]:
                files += "- " + i + "\n"
            error_table.add_row(connection, files)

        error_tables.append(error_table)

    if incorrect_certs:
        instruction_list.append("All SSL certificates need to be in PEM (Privacy Enhanced Mail) format")
        error_table = Table(title="Incorrect SSL Certificates")
        error_table.add_column("Connection", style="magenta")
        error_table.add_column("Incorrect", style="red")
        for connection in incorrect_certs:
            files = ""
            for i in incorrect_certs[connection]:
                files += "- " + i + "\n"
            error_table.add_row(connection, files)

        error_tables.append(error_table)

    if not masterkey_present:
        instruction_list.append(
            "Make sure masterkey.txt file has been added under ./propertyFile/icc for ICC for Email setup")
        error_table = Table(title="ICC Setup")
        error_table.add_column("Missing", style="red")
        error_table.add_row("masterkey.txt")

        error_tables.append(error_table)

    if invalid_trusted_certs:
        instruction_list.append("All trusted certificates need to be in PEM (Privacy Enhanced Mail) format")
        error_table = Table(title="Incorrect Trusted Certificates")
        error_table.add_column("Missing", style="red")
        for cert in invalid_trusted_certs:
            error_table.add_row(cert)
        error_tables.append(error_table)

    if incorrect_naming_conv or (invalid_db_password_list is not None and len(invalid_db_password_list) > 0):
        incorrect_dbs = []
        error_table = Table(title="Database Requirements")
        error_table.add_column("Database(s)", style="red")
        instruction_list.append("Review the list of database requirements below:\n")
        if incorrect_naming_conv:
            instruction_list.append("- DB2 Database name needs to be less than 9 characters\n")
            for db in incorrect_naming_conv:
                incorrect_dbs.append(db)
        if len(invalid_db_password_list) > 0:
            instruction_list.append(
                "- Postgresql Database password length needs to be atleast 16 characters long when FIPS is enabled")
            for db in invalid_db_password_list:
                incorrect_dbs.append(db)
        for db in incorrect_dbs:
            error_table.add_row(db)
        error_tables.append(error_table)

    if not correct_ssl_mode:
        instruction_list.append("SSL Mode for Postgresql can only be \"require\" when FIPS is enabled")

    if tools:
        if "connection" in tools:
            instruction_list.append("Make sure you are connected to a K8s Cluster")
            error_tables.append(Panel.fit("K8s Cluster not Connected", style="bold cyan"))
            tools.remove("connection")

        if "java_version" in tools:
            instruction_list.append(
                "Make sure you have the correct Java version installed , refer to the table on the right for the correct Java version to install.\n")
            error_table = Table(title="Correct Java Version to use")
            error_table.add_column("FNCM S Version", style="green")
            error_table.add_column("Java Version", style="green")
            if deployment_prop["FNCM_Version"] == "5.5.8":
                error_table.add_row("5.5.8", "Java 8")
            if deployment_prop["FNCM_Version"] == "5.5.11":
                error_table.add_row("5.5.11", "Java 11")
            if deployment_prop["FNCM_Version"] == "5.5.12":
                error_table.add_row("5.5.12", "Java 17")
            error_tables.append(error_table)
            tools.remove("java_version")
        if tools:
            instruction_list.append("Install any missing tools")
            error_table = Table(title="Tools Missing")
            error_table.add_column("Tools", style="green")
            for tool in tools:
                if tool != "connection":
                    error_table.add_row("- " + tool)
            error_tables.append(error_table)

    error_table_output = Columns(error_tables)

    layout["lower"]["right"].update(error_table_output)

    left_panel_list.append(next_steps_panel)

    # Build instructions message from the list of instructions
    instruction_msg = ""
    for instruction in instruction_list:
        instruction_msg += f":x: {instruction}\n\n"

    instructions = Panel.fit(instruction_msg)
    left_panel_list.append(instructions)

    # Add note on rerunning generate if property files are fixed
    # Add generate command to rerun
    if mode == "validate":
        validate_instruction_list = []
        note = Panel.fit(
            "Important: Rerun the below command once all issues have been resolved to update the generated files.")
        validate_instruction_list.append(note)

        code = "python3 prerequisites.py generate"
        command = Panel.fit(
            Syntax(code, "bash", theme="ansi_dark")
        )
        validate_instruction_list.append(command)
        validate_group = Group(*validate_instruction_list)
        left_panel_list.append(validate_group)

    left_panel = Group(*left_panel_list)

    layout["lower"]["left"].update(left_panel)

    return layout


def generate_generate_results(generate_folder: str) -> Layout:
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

    code = "python3 prerequisites.py validate"

    command = Panel.fit(
        Syntax(code, "bash", theme="ansi_dark")
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


# Function to check if private key is of pem format
def check_pem_key_format(ssl_cert):
    try:
        with open(ssl_cert, 'rb') as file:
            data = file.read()
        # Attempt to load it as a private key
        serialization.load_pem_private_key(data, password=None, backend=default_backend())
        # If successful, it's a valid PEM file
        return True
    except Exception as e:
        try:
            # Attempt to load it as a public key
            serialization.load_pem_public_key(data, backend=default_backend())
            # If successful, it's a valid PEM file
            return True
        except Exception:
            # Not a valid PEM file
            return False


# Function to check if ssl cert is of pem format
def check_pem_cert_format(ssl_cert):
    try:
        with open(ssl_cert, 'rb') as file:
            data = file.read()
        x509.load_pem_x509_certificate(data, default_backend())
        return True
    except Exception as e:
        return False


# Function to check all cert formats recursively for postgres SSL
def check_ssl_certs_postgres(folder_list, cert_path):
    for cert in folder_list:
        if cert.startswith("."):
            os.remove(os.path.join(cert_path, cert))
        else:
            pem_cert_check = check_pem_cert_format(os.path.join(cert_path, cert))
            if not pem_cert_check:
                pem_key_check = check_pem_key_format(os.path.join(cert_path, cert))
                if not pem_key_check:
                    return False
                else:
                    return True
            else:
                return True


# Function to check if ssl certs are added to the respective folders
def check_ssl_folders(db_prop=None, ldap_prop=None, ssl_cert_folder=None, deploy_prop=None) -> tuple:
    missing_cert = {}
    incorrect_cert = {}
    # if any ssl cert folders exists that means ssl was enabled for either ldap or DB
    if os.path.exists(ssl_cert_folder):
        ssl_folders = collect_visible_files(ssl_cert_folder)

        # remove any hidden files that might be picked up and remove the trusted-certs folder
        for folder in ssl_folders.copy():
            if folder == "trusted-certs":
                ssl_folders.remove(folder)

        # checking to see if any changes to ssl value have been made after folders were created
        ldap_folders = list(filter(lambda x: "ldap" in x, ssl_folders))
        db_folders = list(filter(lambda x: "ldap" not in x, ssl_folders))

        # if db type is not postgres we have a standard folder structure of ssl certs
        if db_prop["DATABASE_SSL_ENABLE"]:
            if db_prop["DATABASE_TYPE"].lower() != "postgresql":
                for folder in db_folders:
                    ssl_certs = collect_visible_files(os.path.join(ssl_cert_folder, folder))
                    if not ssl_certs:
                        missing_cert[folder] = ["certificate"]
                    # logic to check if the cert is the right pem format
                    else:
                        for cert in ssl_certs:
                            if cert.startswith("."):
                                os.remove(os.path.join(ssl_cert_folder, folder, cert))
                            else:
                                pem_cert_check = check_pem_cert_format(os.path.join(ssl_cert_folder, folder, cert))
                                if not pem_cert_check:
                                    pem_key_check = check_pem_key_format(os.path.join(ssl_cert_folder, folder, cert))
                                    if not pem_key_check:
                                        incorrect_cert[folder] = ["certificate"]
            else:
                # if db type is postgres we have three sub folders inside the db ssl cert folders which need to be checked for ssl certs
                for folder in db_folders:

                    sub_folder_path = os.path.join(ssl_cert_folder, folder)
                    sub_folders = collect_visible_files(sub_folder_path)

                    server_ca = False
                    clientkey = False
                    clientcert = False
                    for sub_folder in sub_folders:
                        if "serverca" in sub_folder.lower():
                            server_ca_items = collect_visible_files(os.path.join(sub_folder_path, sub_folder))
                            if server_ca_items:
                                server_ca = True
                                incorrect_cert_present = check_ssl_certs_postgres(server_ca_items,
                                                                                  os.path.join(sub_folder_path,
                                                                                               sub_folder))
                                if not incorrect_cert_present:
                                    if folder not in incorrect_cert:
                                        incorrect_cert[folder] = []
                                        incorrect_cert[folder].append("serverca")
                                    else:
                                        incorrect_cert[folder].append("serverca")

                        if "clientkey" in sub_folder.lower():
                            clientkey_items = collect_visible_files(os.path.join(sub_folder_path, sub_folder))
                            if clientkey_items:
                                clientkey = True
                                incorrect_cert_present = check_ssl_certs_postgres(clientkey_items,
                                                                                  os.path.join(sub_folder_path,
                                                                                               sub_folder))
                                if not incorrect_cert_present:
                                    if folder not in incorrect_cert:
                                        incorrect_cert[folder] = []
                                        incorrect_cert[folder].append("clientkey")
                                    else:
                                        incorrect_cert[folder].append("clientkey")
                        if "clientcert" in sub_folder.lower():
                            clientcert_items = collect_visible_files(os.path.join(sub_folder_path, sub_folder))
                            if clientcert_items:
                                clientcert = True
                                incorrect_cert_present = check_ssl_certs_postgres(clientcert_items,
                                                                                  os.path.join(sub_folder_path,
                                                                                               sub_folder))
                                if not incorrect_cert_present:
                                    if folder not in incorrect_cert:
                                        incorrect_cert[folder] = []
                                        incorrect_cert[folder].append("clientcert")
                                    else:
                                        incorrect_cert[folder].append("clientcert")
                    if db_prop["DATABASE_SSL_ENABLE"]:
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
                            if (clientcert or clientkey) and deploy_prop["FNCM_Version"] != "5.5.8":
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
                        elif db_prop["SSL_MODE"].lower() == "verify-ca" and folder != "ldap":
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
        for folder in ldap_folders:
            if ldap_prop[folder.upper()]["LDAP_SSL_ENABLED"]:
                ssl_certs = collect_visible_files(os.path.join(ssl_cert_folder, folder))
                if not ssl_certs:
                    if folder not in missing_cert:
                        missing_cert[folder] = []
                        missing_cert[folder].append("certificate")
                    else:
                        missing_cert[folder].append("certificate")
                else:
                    for cert in ssl_certs:
                        if cert.startswith("."):
                            os.remove(os.path.join(ssl_cert_folder, folder, cert))
                        else:
                            pem_cert_check = check_pem_cert_format(os.path.join(ssl_cert_folder, folder, cert))
                            if not pem_cert_check:
                                pem_key_check = check_pem_key_format(os.path.join(ssl_cert_folder, folder, cert))
                                if not pem_key_check:
                                    incorrect_cert[folder] = ["certificate"]

    return missing_cert, incorrect_cert


# Function to check if icc masterkey file is present
def check_icc_masterkey(custom_component_prop, icc_folder):
    # if custom component property file is empty then we know icc is not present and we can skip the check
    if not custom_component_prop:
        return True
    if custom_component_prop and "ICC" not in custom_component_prop.keys():
        return True
    # the file to create the secret has to be in .txt format
    if os.path.exists(icc_folder):
        file_list = collect_visible_files(icc_folder)
        if not file_list:
            return False
        else:
            for file in file_list:
                if file.endswith('.txt'):
                    return True
            return False


# Function to check if there are certs in the trusted cert folder
def check_trusted_certs(trusted_certs_folder):
    # the certs have to be in .pem , .crt , .cert
    invalid_certs = []
    if os.path.exists(trusted_certs_folder):
        file_lists = collect_visible_files(trusted_certs_folder)
        if len(file_lists) > 0:
            # some certs have been added
            for file in file_lists:
                if file.startswith("."):
                    continue
                if not (file.endswith('.pem') or file.endswith('.crt') or file.endswith('.cert')):
                    invalid_certs.append(file)
            return True, invalid_certs
        else:
            return False, invalid_certs
    else:
        return True, invalid_certs


def check_dbname(db_prop):
    incorrect_naming_convention = []
    if db_prop["DATABASE_TYPE"].lower() == "db2":
        for db in db_prop["db_list"]:
            if len(db_prop[db]["DATABASE_NAME"]) > 8:
                incorrect_naming_convention.append(db)
    return incorrect_naming_convention


# Function to check if keystore password is atleast 16characters long for FIPS enabled
def check_keystore_password_length(user_group_prop, deploy_prop):
    # checking if fips support is enabled
    if "FIPS_SUPPORT" in deploy_prop.keys():
        if deploy_prop["FIPS_SUPPORT"]:
            if len(user_group_prop["KEYSTORE_PASSWORD"]) < 16:
                return False
    return True


# Function to check if db password is atleast 16 characters long for FIPS enabled
def check_db_password_length(db_prop, deploy_prop):
    # checking if fips support is enabled
    incorrect_password_dbs = []
    if "FIPS_SUPPORT" in deploy_prop.keys():
        if deploy_prop["FIPS_SUPPORT"] and db_prop["DATABASE_TYPE"].lower() == "postgresql":
            for db in db_prop["db_list"]:
                if len(db_prop[db]["DATABASE_PASSWORD"]) < 16:
                    incorrect_password_dbs.append(db)
    return incorrect_password_dbs


# Function to check if db ssl mode is require for postgres for FIPS enabled
def check_db_ssl_mode(db_prop, deploy_prop):
    # checking if fips support is enabled
    correct_ssl_mode = True
    if "FIPS_SUPPORT" in deploy_prop.keys():
        if deploy_prop["FIPS_SUPPORT"] and db_prop["DATABASE_TYPE"].lower() == "postgresql" and db_prop[
            "DATABASE_SSL_ENABLE"]:
            if db_prop["SSL_MODE"].lower() != "require":
                correct_ssl_mode = False
    return correct_ssl_mode


# Function to display ldap search results
def ldap_search_results(user_result_dict, group_result_dict):
    user_table_list = []
    group_table_list = []

    # Build lists of users found, missing and duplicated
    users_found = []
    users_missing = []
    users_duplicated = []

    # Build lists of groups found, missing and duplicated
    groups_found = []
    groups_missing = []
    groups_duplicated = []

    missing = False
    duplicated = False

    for user, value in user_result_dict.items():
        if value["count"] == 1:
            users_found.append(user)
        elif value["count"] == 0:
            users_missing.append(user)
        else:
            users_duplicated.append(user)

    for group, value in group_result_dict.items():
        if value["count"] == 1:
            groups_found.append(group)
        elif value["count"] == 0:
            groups_missing.append(group)
        else:
            groups_duplicated.append(group)

    # Build tables for users and groups
    if len(users_found) > 0:
        users_found_table = Table(title="Users Found")
        users_found_table.add_column("User", style="green")
        users_found_table.add_column("Found in", style="green")
        for user in users_found:
            users_found_table.add_row(user, user_result_dict[user]["ldap_id"][0])

        user_table_list.append(users_found_table)

    if len(users_missing) > 0:
        user_missing_table = Table(title="Users Missing")
        user_missing_table.add_column("User", style="yellow")
        for user in users_missing:
            user_missing_table.add_row(user)

        user_table_list.append(user_missing_table)
        missing = True

    if len(users_duplicated) > 0:
        user_duplicate_table = Table(title="Users Duplicated")
        user_duplicate_table.add_column("User", style="red")
        user_duplicate_table.add_column("Found in", style="red")
        for user in users_duplicated:
            ldaps = ""
            for i in user_result_dict[user]["ldap_id"]:
                ldaps += "- " + i + "\n"
            user_duplicate_table.add_row(user, ldaps)

        user_table_list.append(user_duplicate_table)
        duplicated = True

    if len(groups_found) > 0:
        groups_found_table = Table(title="Groups Found")
        groups_found_table.add_column("Group", style="green")
        groups_found_table.add_column("Found in", style="green")
        for group in groups_found:
            groups_found_table.add_row(group, group_result_dict[group]["ldap_id"][0])

        group_table_list.append(groups_found_table)

    if len(groups_missing) > 0:
        group_missing_table = Table(title="Groups Missing")
        group_missing_table.add_column("Group", style="yellow")
        for group in groups_missing:
            group_missing_table.add_row(group)

        group_table_list.append(group_missing_table)
        missing = True

    if len(groups_duplicated) > 0:
        group_duplicate_table = Table(title="Groups Duplicated")
        group_duplicate_table.add_column("Group", style="red")
        group_duplicate_table.add_column("Found in", style="red")
        for group in groups_duplicated:
            ldaps = ""
            for i in group_result_dict[group]["ldap_id"]:
                ldaps += "- " + i + "\n"
            group_duplicate_table.add_row(group, group_result_dict[group]["ldap_id"])

        group_table_list.append(group_duplicate_table)
        duplicated = True

    panel_list = []

    if len(user_table_list) != 0:
        user_table_output = Group(*user_table_list)
        user_panel = Panel.fit(user_table_output, title="Users Search Results")
        panel_list.append(user_panel)

    if len(group_table_list) != 0:
        group_table_output = Group(*group_table_list)
        group_panel = Panel.fit(group_table_output, title="Groups Search Results")
        panel_list.append(group_panel)

    if duplicated:
        panel_list.append(Panel.fit(f":x: Duplicated users and groups found!\n"
                                    f"This can causes issue when logging in.", style="bold red"))

    if missing:
        panel_list.append(Panel.fit(f":exclamation_mark: Some users and groups where not found!\n"
                                    f"Please review Property Files.", style="bold yellow"))

    if not duplicated and not missing:
        panel_list.append(Panel.fit(f":white_heavy_check_mark: All users and groups where found!", style="bold green"))

    result_group = Group(*panel_list)

    return result_group


def collect_visible_files(folder_path: str) -> [str]:
    return [file for file in os.listdir(folder_path) if not file.startswith('.')]
