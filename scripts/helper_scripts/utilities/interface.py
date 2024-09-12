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

import os
import pathlib
import platform
from enum import Enum

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

from .prerequisites_utilites import parse_required_fields


# Create a method to print directory tree
def print_directory_tree(name: str, path: str) -> Tree:
    """Print a directory tree."""
    tree = Tree(f"  [bold blue] {name} [/bold blue]", guide_style="blue")
    walk_directory(pathlib.Path(path), tree)
    return tree


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


def mustgather_details(cr_details: dict, components: [], operator_details: dict) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    msg = Text("MustGather Collection Details", style="bold green", justify="center")
    msg_panel = Panel(msg)
    layout["upper"].update(msg_panel)

    summary_msg = (
        "\nThe FNCM Standalone MustGather collections a set of files that will help the IBM support team diagnose"
        " and resolve issues with your deployment.\n\n"
        "The collection includes the following artifacts:\n"
        "- Cluster Information and Resource Usage\n")

    right_panels = []
    left_panels = []

    if not operator_details:
        operator_error = Panel.fit("No Operator Details Found", style="bold red")
        right_panels.append(operator_error)

        summary_msg += ("\nNo Operator Details were found in your namespace:\n"
                        "No Operator Logs will be collected\n")
    else:
        operator_table = Table(title="Operator Details")
        operator_table.add_column("Parameter", style="cyan")
        operator_table.add_column("Value", style="red")

        operator_table.add_row("Operator Name", operator_details["deployment"])
        operator_table.add_row("Release", operator_details["release"])
        operator_table.add_row("Install Type", operator_details["type"])

        summary_msg += ("- FNCM Operator Deployment & Ansible Logs\n")

        if operator_details["type"] == "OLM":
            operator_table.add_row("Installed CSV", operator_details["installedCSV"])
            operator_table.add_row("Channel", operator_details["channel"])
            operator_table.add_row("Catalog Source", operator_details["catalogSource"])
            operator_table.add_row("Catalog Install Type", operator_details["catalogType"])

            summary_msg += ("- Subscription and Catalog Source Details\n")

        right_panels.append(operator_table)

    if not cr_details:
        cr_error = Panel.fit("No Custom Resource Found", style="bold red")
        right_panels.append(cr_error)

        summary_msg += ("\nNo Custom Resource was found in your namespace:\n"
                        "\nNo Deployment Details will be collected\n")

    else:

        summary_msg += ("- The FNCM Standalone Custom Resource (CR) file\n"
                        "- Components Logs\n"
                        "- Workloads: Deployment & Pod Details\n"
                        "- Networking: Route, Ingress & Services\n"
                        "- Storage: PVCs, PVs & StorageClasses\n"
                        "- Configuration: If approved, Configmaps and Secrets\n"
                        "\n\n")

        version = cr_details["version"]
        namespace = cr_details["namespace"]
        platform = cr_details["platform"]
        if cr_details["platform"] == "other":
            platform = "CNCF"
        else:
            platform = cr_details["platform"].upper()
        appVersion = cr_details["appVersion"]
        details_table = Table(title="Project Details")
        details_table.add_column("Parameter", style="cyan")
        details_table.add_column("Value", style="red")

        details_table.add_row("Deployed Version", version)
        details_table.add_row("Namespace", namespace)
        details_table.add_row("Platform", platform)

        left_panels.append(details_table)

    if len(components) > 0:

        components.sort()

        component_table = Table(title="Components")

        component_table.add_column(header="Selected", style="blue")
        for item in components:
            parameters = ""
            parameters += f":heavy_check_mark: {item}"
            component_table.add_row(parameters)

        right_panels.append(component_table)

    right_group = Columns(right_panels)
    left_panels.append(Text(summary_msg))
    left_group = Group(*left_panels)


    layout["right"].update(right_group)
    layout["left"].update(left_group)

    return layout


def upgrade_details(deployment_details: dict, version_details: dict, current_operator: dict) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    msg = Text("Operator Upgrade Details", style="bold green", justify="center")
    msg_panel = Panel(msg)
    layout["upper"].update(msg_panel)

    summary_msg = ("\nThe FNCM Standalone Operator Deployment will upgrade\n"
                   "the following artifacts to your cluster:\n\n")

    left_panels = []
    right_panels = []

    if current_operator:
        current_operator_table = Table(title="Current Operator Details")
        current_operator_table.add_column("Parameter", style="cyan")
        current_operator_table.add_column("Value", style="red")

        current_operator_table.add_row("Operator Name", current_operator["deployment"])
        current_operator_table.add_row("Release", current_operator["release"])
        current_operator_table.add_row("Install Type", current_operator["type"])
        current_operator_table.add_row("Registry", current_operator["registry"])

        if current_operator["type"] == "OLM":
            current_operator_table.add_row("Installed CSV", current_operator["installedCSV"])
            current_operator_table.add_row("Channel", current_operator["channel"])
            current_operator_table.add_row("Catalog Source", current_operator["catalogSource"])
            current_operator_table.add_row("Catalog Install Type", current_operator["catalogType"])

        right_panels.append(current_operator_table)

    if deployment_details:
        deployment_table = Table(title="Upgraded Operator Details")
        deployment_table.add_column("Parameter", style="cyan")
        deployment_table.add_column("Value", style="red")

        deployment_table.add_row("Operator Name", deployment_details["deployment"])
        deployment_table.add_row("Release", deployment_details["release"])
        deployment_table.add_row("Install Type", deployment_details["type"])
        deployment_table.add_row("Registry", deployment_details["registry"])

        summary_msg += ("- FNCM Operator Deployment\n"
                        "- Role, RoleBinding & Service Account\n"
                        "- FNCM Custom Resource Definition (CRD)\n")

        if deployment_details["type"] == "OLM":
            deployment_table.add_row("Installed CSV", deployment_details["installedCSV"])
            deployment_table.add_row("Channel", deployment_details["channel"])
            deployment_table.add_row("Catalog Source", deployment_details["catalogSource"])
            deployment_table.add_row("Catalog Install Type", deployment_details["catalogType"])

            summary_msg += ("- Cluster Role & Cluster Role Binding\n"
                            "- FNCM Operator Catalog Source\n"
                            "- Subscription and Operator Group\n")

        right_panels.append(deployment_table)

    if version_details:
        version_table = Table(title="Project Details")
        version_table.add_column("Parameter", style="cyan")
        version_table.add_column("Value", style="red")

        version_table.add_row("Namespace", version_details["namespace"])
        version_table.add_row("Platform", version_details["platform"])

        left_panels.append(version_table)


    if deployment_details and current_operator:
        if deployment_details["type"] == "OLM" and current_operator["type"] == "YAML":
            msg = Text("Operator Upgrade will change the Operator Install Type\n"
                       "from YAML to OLM (Operator Lifecycle Management)", style="bold cyan")
            msg_panel = Panel.fit(msg)
            left_panels.append(msg_panel)

    deploy_msg = Text(summary_msg)
    left_panels.append(deploy_msg)

    right_group = Columns(right_panels)
    left_group = Group(*left_panels)

    layout["right"].update(right_group)

    layout["left"].update(left_group)

    return layout


def deploy_details(deployment_details: dict, version_details: dict) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    msg = Text("Operator Deployment Details", style="bold green", justify="center")
    msg_panel = Panel(msg)
    layout["upper"].update(msg_panel)

    summary_msg = ("\nThe FNCM Standalone Operator Deployment will apply\n"
                   "the following artifacts to your cluster:\n\n")

    right_panels = []
    left_panels = []

    if deployment_details:
        deployment_table = Table(title="Operator Details")
        deployment_table.add_column("Parameter", style="cyan")
        deployment_table.add_column("Value", style="red")

        deployment_table.add_row("Operator Name", deployment_details["deployment"])
        deployment_table.add_row("Release", deployment_details["release"])
        deployment_table.add_row("Install Type", deployment_details["type"])
        deployment_table.add_row("Registry", deployment_details["registry"])

        summary_msg += ("- FNCM Operator Deployment\n"
                        "- FNCM Custom Resource Definition (CRD)\n"
                        "- Role, RoleBinding & Service Account\n")

        if deployment_details["type"] == "OLM":
            deployment_table.add_row("Installed CSV", deployment_details["installedCSV"])
            deployment_table.add_row("Channel", deployment_details["channel"])
            deployment_table.add_row("Catalog Source", deployment_details["catalogSource"])
            deployment_table.add_row("Catalog Install Type", deployment_details["catalogType"])

            summary_msg += ("- Cluster Role & Cluster Role Binding\n"
                            "- FNCM Operator Catalog Source\n"
                            "- Subscription and Operator Group\n")

        left_panels.append(deployment_table)

    if version_details:
        version_table = Table(title="Project Details")
        version_table.add_column("Parameter", style="cyan")
        version_table.add_column("Value", style="red")

        version_table.add_row("Namespace", version_details["namespace"])
        version_table.add_row("Platform", version_details["platform"])

        right_panels.append(version_table)

    deploy_msg = Text(summary_msg)
    right_panels.append(deploy_msg)

    right_group = Group(*right_panels)
    left_group = Columns(left_panels)

    layout["right"].update(left_group)

    layout["left"].update(right_group)

    return layout


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
        "7. Run the following command to generate SQL, secrets and CR file\n".strip()
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


def upgrade_cr_details(update_list: list, version_details: dict, cr_folder_path: ""):
    right_panels = []
    msg = Text("FNCM Standalone Custom Resource Preparation", style="bold green")
    msg_panel = Panel.fit(msg)

    summary_msg = Text("The FNCM Standalone Custom Resource (CR) has been upgraded.\n\n"
                       "1. The current and upgraded CR have been copied to ./FNCMCustomResource folder\n"
                       "2. Review the following tables for changes made to the current CR")
    summary_panel = Panel.fit(summary_msg)

    right_panels.append(msg_panel)
    right_panels.append(summary_panel)

    left_panels = []

    if update_list:
        update_table = Table(title="Custom Resource Upgrade Details")
        update_table.add_column("Updates", style="cyan")

        for update in update_list:
            update_table.add_row(f"- {update}")

        left_panels.append(update_table)

    if version_details:
        version_table = Table(title="Upgrade Details")
        version_table.add_column("Parameter", style="cyan")
        version_table.add_column("Value", style="red")

        version_table.add_row("FNCM Version", version_details["version"])
        version_table.add_row("Namespace", version_details["namespace"])
        version_table.add_row("Platform", version_details["platform"])
        version_table.add_row("AppVersion", version_details["appVersion"])

        left_panels.append(version_table)

    if cr_folder_path:
        cr_tree = print_directory_tree("Custom Resource Folder", cr_folder_path)
        left_panels.append(cr_tree)

    right_group = Group(*right_panels)
    left_group = Columns(left_panels)

    cr_info = Columns([right_group, left_group], equal=True)

    return cr_info

def display_prereq_passed(prereqs=None):
    # loop through prereq dict and build a list of passed prereqs

    if prereqs is None:
        prereqs = {}

    msg_panel = Panel.fit("All Prerequisites Passed", style="bold green")

    check_list = []
    if 'podman' in prereqs:
        if prereqs['podman']:
            check_list.append("Podman Daemon")
    if 'docker' in prereqs:
        if prereqs['docker']:
            check_list.append("Docker Daemon")
    if 'kubectl' in prereqs:
        if prereqs['kubectl']:
            check_list.append("Kubectl CLI")
    if 'java' in prereqs:
        if prereqs['java']:
            check_list.append("Java")
    if "skopeo" in prereqs:
        if prereqs["skopeo"]:
            check_list.append("Skopeo CLI")
    if "connection" in prereqs:
        if prereqs["connection"]:
            check_list.append("K8s Cluster Connection")
    if "descriptor_files" in prereqs:
        if prereqs["descriptor_files"]:
            check_list.append("All Required Descriptor Files")

    if len(check_list) == 0:
        return msg_panel

    checklist_msg = ""
    if len(check_list) > 0:
        for check in check_list:
            checklist_msg += f":heavy_check_mark: {check}\n\n"
    else:
        checklist_msg += f":heavy_check_mark: {check_list[0]}"

    checklist_panel = Panel.fit(checklist_msg.strip())

    left_group = Group(msg_panel, checklist_panel)

    version_list = [
        prereqs['kubectl'],
        prereqs['java'],
        prereqs['skopeo']
    ]

    if any(version_list):

        cli_version_table = Table(title="CLI Versions")
        cli_version_table.add_column("Tool", style="cyan", no_wrap=True)
        cli_version_table.add_column("Version", style="blue")

        if 'kubectl' in prereqs:
            if prereqs['kubectl']:
                cli_version_table.add_row("Kubectl CLI", prereqs["kubectl_version"])

        if 'java' in prereqs:
            if prereqs['java']:
                cli_version_table.add_row("Java", prereqs["java_version"])

        if 'skopeo' in prereqs:
            if prereqs['skopeo']:
                cli_version_table.add_row("Skopeo CLI", prereqs["skopeo_version"])

        version_panel = Panel(cli_version_table)

        prereq_info = Columns([left_group, version_panel], equal=True)

        return prereq_info

    return left_group


def display_issues(generate_folder=None, required_fields=None,
                   certs=None, incorrect_certs=None,
                   masterkey_present=True, invalid_trusted_certs=None,
                   keystore_password_valid=True, incorrect_naming_conv=None,
                   mode=None, tools=None, invalid_db_password_list=None, correct_ssl_mode=True,
                   deployment_prop=None, descriptors=None) -> Layout:
    # Build Layout for display
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

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
    if required_fields is not None:
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
    if required_fields is not None:
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

    if descriptors:
        instruction_list.append(
            "Missing Descriptor files need to be added to respective folder under ../descriptors")
        error_table = Table(title="Files Missing")
        error_table.add_column("Missing", style="red")
        for file in descriptors:
            error_table.add_row(file)

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
                "- Postgresql Database password length needs to be at least 16 characters long when FIPS is enabled")
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
        if "Windows Machine" in tools:
            instruction_list.append("Load Images Script is not supported on a Windows Machine")
            error_tables.append(Panel.fit("Windows Machine not supported for this script", style="bold cyan"))
            tools.remove("Windows Machine")

        if "java_version" in tools:
            instruction_list.append(
                "Make sure you have the correct Java version installed, refer to the table on the right for the correct Java version to install.\n")
            error_table = Table(title="Correct Java Version to use")
            error_table.add_column("FNCM S Version", style="green")
            error_table.add_column("Java Version", style="green")
            if deployment_prop["FNCM_Version"] == "5.5.8":
                error_table.add_row("5.5.8", "Java 8")
            if deployment_prop["FNCM_Version"] == "5.5.11":
                error_table.add_row("5.5.11", "Java 11")
            if deployment_prop["FNCM_Version"] == "5.5.12" or deployment_prop["FNCM_Version"] == "5.6.0":
                error_table.add_row("5.5.12 & 5.6.0", "Java 17")
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

    instructions = Panel.fit(instruction_msg.strip())
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

    layout["upper"].size = 3

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


def generate_loadimage_results(summary: {}) -> Layout:
    # Build Layout for display
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    left_panel_list = []

    right_panel_list = []

    # Create the left side panel
    # Create next steps panel
    total = summary["total"]
    if 0 < len(summary["failed"]) < total:
        message = Text("Image Push Completed with Errors", style="bold yellow", justify="center")
    elif len(summary["failed"]) == total:
        message = Text("Image Push Failed", style="bold red", justify="center")
    else:
        message = Text("Image Push Completed Successfully", style="bold green", justify="center")

    result_panel = Panel(message)

    layout["upper"].update(result_panel)

    next_steps_panel = Panel.fit("Next Steps")
    instructions = Panel.fit(
        "1. If any failures review the generated image details TOML file\n"
        "2. To configure your FNCM Standalone deployment to use the private registry set the following in your Custom Resource File"
    )
    private_registry = summary["private_registry"]
    code = f"spec:\n" \
           f"  shared_configuration:\n" \
           f"    sc_image_repository: {private_registry}"

    command = Panel.fit(
        Syntax(code, "yaml", theme="ansi_dark")
    )

    left_panel_list.append(next_steps_panel)
    left_panel_list.append(instructions)
    left_panel_list.append(command)

    left_panel = Group(*left_panel_list)

    if len(summary["failed"]) > 0:
        failed_table = Table(title="Failed Images")
        failed_table.add_column("Image", style="red")
        for image in summary["failed"]:
            element = f"- {image}"
            failed_table.add_row(element)
        right_panel_list.append(failed_table)

    if len(summary["completed"]) > 0:
        pushed_table = Table(title="Pushed Images")
        pushed_table.add_column("Image", style="green")
        for image in summary["completed"]:
            element = f"- {image}"
            pushed_table.add_row(element)
        right_panel_list.append(pushed_table)

    right_panel = Group(*right_panel_list)

    layout["lower"]["right"].update(right_panel)
    layout["lower"]["left"].update(left_panel)

    return layout


def generate_loadimages_results(imageDetailFolder: str) -> Layout:
    # Build Layout for display
    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    left_panel_list = []

    right_panel_list = []

    # Create the left side panel
    # Create next steps panel
    message = Text("ImageDetail Files Generated Successfully", style="bold cyan", justify="center")
    result_panel = Panel(message)

    layout["upper"].update(result_panel)

    next_steps_panel = Panel.fit("Next Steps")
    instructions = Panel.fit(
        "1. Review the elements of the ImageDetails file: \n"
        "  - Image Repositories\n"
        "  - Image Tags \n"
        "  - All Components Images to be pushed\n"
        "2. Remove or update any repositories or tags \n"
        "3. Run the following command to push selected images"
    )

    code = "python3 loadimages.py push"

    command = Panel.fit(
        Syntax(code, "bash", theme="ansi_dark")
    )

    left_panel_list.append(next_steps_panel)
    left_panel_list.append(instructions)
    left_panel_list.append(command)

    left_panel = Group(*left_panel_list)

    right_panel_list.append(Panel.fit("ImageDetails Files Structure"))
    right_panel_list.append(print_directory_tree("ImageDetails", imageDetailFolder))

    right_panel = Group(*right_panel_list)

    layout["lower"]["right"].update(right_panel)
    layout["lower"]["left"].update(left_panel)

    return layout


class ldap_entry_types(Enum):
    USER = 0
    GROUP = 1
    USER_GROUP = 2


# Function to display ldap search results
def ldap_search_results(entries_result_dict):
    user_table_list = []
    group_table_list = []
    user_group_table_list = []

    # Build lists of users found, missing and duplicated
    users_found = []
    users_missing = []
    users_duplicated = []

    # Build lists of groups found, missing and duplicated
    groups_found = []
    groups_missing = []
    groups_duplicated = []

    user_or_group_missing = []

    missing = False
    duplicated = False

    for entry, value in entries_result_dict.items():
        if value["type"] == ldap_entry_types.USER:
            if value["count"] == 1:
                users_found.append(entry)
            elif value["count"] == 0:
                users_missing.append(entry)
            else:
                users_duplicated.append(entry)
        elif value["type"] == ldap_entry_types.GROUP:
            if value["count"] == 1:
                groups_found.append(entry)
            elif value["count"] == 0:
                groups_missing.append(entry)
            else:
                groups_duplicated.append(entry)
        else:
            user_or_group_missing.append(entry)

    # Build tables for users and groups
    if len(users_found) > 0:
        users_found_table = Table(title="Users Found")
        users_found_table.add_column("User", style="green")
        users_found_table.add_column("Found in", style="green")
        for user in users_found:
            users_found_table.add_row(user, entries_result_dict[user]["ldap_id"][0])

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
            for i in entries_result_dict[user]["ldap_id"]:
                ldaps += "- " + i + "\n"
            user_duplicate_table.add_row(user, ldaps)

        user_table_list.append(user_duplicate_table)
        duplicated = True

    if len(groups_found) > 0:
        groups_found_table = Table(title="Groups Found")
        groups_found_table.add_column("Group", style="green")
        groups_found_table.add_column("Found in", style="green")
        for group in groups_found:
            groups_found_table.add_row(group, entries_result_dict[group]["ldap_id"][0])

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
            for i in entries_result_dict[group]["ldap_id"]:
                ldaps += "- " + i + "\n"
            group_duplicate_table.add_row(group, entries_result_dict[group]["ldap_id"])

        group_table_list.append(group_duplicate_table)
        duplicated = True

    if len(user_or_group_missing) > 0:
        user_group_missing_table = Table(title="Users or Groups Missing")
        user_group_missing_table.add_column("Users or Groups", style="yellow")
        for entry in user_or_group_missing:
            user_group_missing_table.add_row(entry)

        user_group_table_list.append(user_group_missing_table)
        missing = True

    panel_list = []

    if len(user_table_list) != 0:
        user_table_output = Group(*user_table_list)
        user_panel = Panel.fit(user_table_output, title="Users Search Results")
        panel_list.append(user_panel)

    if len(group_table_list) != 0:
        group_table_output = Group(*group_table_list)
        group_panel = Panel.fit(group_table_output, title="Groups Search Results")
        panel_list.append(group_panel)

    if len(user_group_table_list) != 0:
        user_group_table_output = Group(*user_group_table_list)
        user_group_panel = Panel.fit(user_group_table_output, title="User or Groups Search Results")
        panel_list.append(user_group_panel)

    if duplicated:
        panel_list.append(Panel.fit(":x: Duplicated users and groups found!\n"
                                    "This can causes issue when logging in.", style="bold red"))

    if missing:
        panel_list.append(Panel.fit(":exclamation_mark: Some users and groups where not found!\n"
                                    "Please review Property Files.", style="bold yellow"))

    if not duplicated and not missing:
        panel_list.append(Panel.fit(":white_heavy_check_mark: All users and groups where found!", style="bold green"))

    result_group = Group(*panel_list)

    return result_group


def display_deployment_resources(logger, deployment_resources=None, deployment_details=None, operator_details=None, version_details=None):
    # Build Layout for display
    if version_details is None:
        version_details = {}

    if deployment_resources is None:
        deployment_resources = {}

    if deployment_details is None:
        deployment_details = {}

    if operator_details is None:
        operator_details = {}

    layout = Layout()
    layout.split_column(
        Layout(name="upper"),
        Layout(name="lower"),
    )

    layout["upper"].size = 3

    layout["lower"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["left"].minimum_size = 50
    layout["right"].ratio = 9

    message = Text("FNCM Standalone Deployment Resources to be Deleted", style="bold blue", justify="center")
    result_panel = Panel(message)
    layout["upper"].update(result_panel)

    layout["upper"].update(result_panel)

    left_panel_list = []

    if version_details:
        version_table = Table(title="Project Details")
        version_table.add_column("Parameter", style="cyan")
        version_table.add_column("Value", style="red")

        version_table.add_row("Namespace", version_details["namespace"])
        version_table.add_row("Platform", version_details["platform"])

        left_panel_list.append(version_table)

    instructions_msg = "The following aspects of your deployment will be cleaned up:"

    left_behind_msg = "\n\nThe following resources will not be deleted:\n\n"

    right_panel_list = []

    if deployment_details:
        resource_tables = []

        for key, value in deployment_resources.items():
            if key != "persistent_volume_claim":
                if value:
                    tableResource = Table(title=key)
                    tableResource.add_column("Name", style="cyan")
                    for item in value:
                        resource = ""
                        resource += "- " + item
                        tableResource.add_row(resource)
                    resource_tables.append(tableResource)

        right_panel_list.extend(resource_tables)

        # Deployment Details Panel
        details_header_panel = Panel.fit("Deployment Details", style="bold cyan", border_style="cyan")

        left_panel_list.append(details_header_panel)

        deployment_details_list = ""

        for key, value in deployment_details.items():
            deployment_details_list += f"- {key}: {value}\n\n"

        details_panel = Panel.fit(deployment_details_list.strip())
        left_panel_list.append(details_panel)

        instructions_msg += ("\n\nFNCM Standalone Deployment: \n"
                             "  - Deployments\n"
                             "  - Services\n"
                             "  - Operator Generated ConfigMap\n"
                             "  - Operator Generated Secrets\n"
                             "  - Network Policies\n"
                             "  - Ingress or Routes")

        left_behind_msg += ("  - Persistent Volume Claims\n"
                            "  - Persistent Volumes\n"
                            "  - User Created ConfigMaps\n"
                            "  - User Created Secrets\n")
    else:
        deployment_missing = Panel.fit("No FNCM Deployment Found", style="bold red")
        left_panel_list.append(deployment_missing)

    # Operator Details Panel
    if operator_details:
        instructions_msg += ("\n\nFNCM Standalone Operator: \n"
                             "  - Operator Deployment\n"
                             "  - Role, RoleBinding & Service Account\n")

        if operator_details["type"] == "OLM":
            instructions_msg += "  - Subscription and Operator Group\n"
            left_behind_msg += ("  - Operator Catalog Source\n"
                                "  - Cluster Role & Cluster Role Binding\n"
                                "  - Custom Resource Definition (CRD)\n")
        else:
            left_behind_msg += "  - Custom Resource Definition (CRD)\n"


        operator_table = Table(title="Operator Details")
        operator_table.add_column("Parameter", style="cyan")
        operator_table.add_column("Value", style="red")

        operator_table.add_row("Operator Name", operator_details["deployment"])
        operator_table.add_row("Release", operator_details["release"])
        operator_table.add_row("Install Type", operator_details["type"])

        if operator_details["type"] == "OLM" and "Installed CSV" in operator_details.keys():
            operator_table.add_row("Installed CSV", operator_details["installedCSV"])
            operator_table.add_row("Channel", operator_details["channel"])
            operator_table.add_row("Catalog Source", operator_details["catalogSource"])
            operator_table.add_row("Catalog Install Type", operator_details["catalogType"])

        right_panel_list.append(operator_table)
    else:
        operator_missing = Panel.fit("No Operator Deployment Found", style="bold red")
        right_panel_list.append(operator_missing)

    left_panel_list.append(Text(instructions_msg.strip()))
    left_panel_list.append(Text(left_behind_msg.rstrip()))

    left_panel = Group(*left_panel_list)
    to_be_deleted_tables = Columns(right_panel_list)

    layout["lower"]["right"].update(to_be_deleted_tables)
    layout["lower"]["left"].update(left_panel)

    return layout
