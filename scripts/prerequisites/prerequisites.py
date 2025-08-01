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


# Write a main function that parses command line arguments
#  - the main should take a mode as an argument
#  - the modes can are gather, generate, validate
#  - the gather mode accepts a migration option
#  - the migration option accept a folder location
#  - the main should call the appropriate function based on the mode
#  - the main should pass the parsed arguments to the function
#  - the main should print the output of the function

import fnmatch
import logging
import os
import shutil
from datetime import datetime
from typing import Optional
import re

import typer
from rich import print
from rich.columns import Columns
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
from rich.syntax import Syntax
from rich.text import Text
from toml.decoder import TomlDecodeError

from helper_scripts.gather import gather_prerequisites as g
from helper_scripts.gather import silent_gather_prerequisites as sg
from helper_scripts.generate.generate_cr import GenerateCR
from helper_scripts.generate.generate_secrets import GenerateSecrets
from helper_scripts.generate.generate_sql import GenerateSql
from helper_scripts.property import property as p
from helper_scripts.property.read_prop import *
from helper_scripts.utilities.interface import clear, generate_gather_results, generate_generate_results, display_issues
from helper_scripts.utilities.prerequisites_utilites import zip_folder, \
    create_generate_folder, check_ssl_folders, check_icc_masterkey, check_trusted_certs, check_dbname, \
    check_keystore_password_length, collect_visible_files, check_db_password_length, check_db_ssl_mode, \
    add_idp_to_trusted_certs
from helper_scripts.validate import validate as v

__version__ = "5.1.1"

app = typer.Typer()
state = {
    "verbose": False,
    "silent": False,
    "logger": logging
}

console = Console(record=True)


def version_callback(value: bool):
    if value:
        print(f"FileNet Content Manager Deployment Prerequisites CLI: {__version__}")
        raise typer.Exit()



@app.callback()
def main(version: Optional[bool] = typer.Option(None, "--version", help="Show version and exit.",
                                                callback=version_callback, is_eager=True),
         silent: bool = typer.Option(False, help="Enable Silent Install (no prompts).",
                                     rich_help_panel="Customization and Utils"),
         verbose: bool = typer.Option(False, help="Enable verbose logging.",
                                      rich_help_panel="Customization and Utils")):
    """
    FileNet Content Manager Deployment Prerequisites CLI.
    """
    if verbose:
        state["verbose"] = True
        FILE_LOG_LEVEL = logging.DEBUG
    else:
        FILE_LOG_LEVEL = logging.WARNING

    state["logger"] = setup_logger(FILE_LOG_LEVEL)

    if silent:
        state["silent"] = True


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
    file_handler = logging.FileHandler("prerequisites.log")
    file_handler.setLevel(logging.DEBUG)
    formatter_file = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)-100s - %(filename)s:%(lineno)d", "%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter_file)

    # Add handlers to the logger
    logger.addHandler(shell_handler)
    logger.addHandler(file_handler)

    return logger


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

    print(Panel.fit(msg, title="FileNet Content Manager Deployment Prerequisites CLI", border_style="green"))
    print()


@app.command()
def gather(
        move: str = typer.Option("", help="Folder location of the migration files", rich_help_panel="Mode Options",
                                 dir_okay=True),
):
    """
    Gather the prerequisites for FileNet Content Manager Deployment.
    """
    clear(console)
    display_mode_version("Gather",
                         "FileNet Content Manager Deployment Prerequisites CLI")

    if move != '':
        dir_exists = os.path.isdir(move)

        if not dir_exists:
            state["logger"].error("The directory does not exist. Please check the directory and try again.")
            raise typer.Exit()

    move_db = False
    move_ldap = False

    # this is the user details object
    deploy1 = g.GatherPrereqOptions(state["logger"], console)

    if not state["silent"]:
        if move == '':
            deploy1.collect_fncm_version()
            clear(console)
            deploy1.collect_license_model()

            clear(console)
            deploy1.collect_platform_ingress()

            clear(console)
            deploy1.collect_auth_type()

            clear(console)
            deploy1.collect_fips_info()

            clear(console)
            deploy1.collect_egress_info()

            clear(console)
            deploy1.collect_networkpolicy_info()

            clear(console)
            deploy1.collect_optional_components()

            clear(console)
            deploy1.collect_db_info()

            if deploy1.auth_type in ("LDAP", "LDAP_IDP"):
                clear(console)
                deploy1.collect_ldap_number()
                deploy1.collect_ldap_type()

            if deploy1.auth_type in ("LDAP_IDP", "SCIM_IDP"):
                clear(console)
                deploy1.collect_idp_number()
                deploy1.collect_idp_discovery()

            clear(console)
            deploy1.collect_init_verify_content()
        else:
            deploy1.collect_fncm_version()
            clear(console)
            deploy1.collect_license_model()

            clear(console)
            deploy1.collect_platform_ingress()

            clear(console)
            deploy1.collect_optional_components()

            clear(console)
            # Get all files in the directory as list by type
            files = collect_visible_files(move)
            gcd_file = fnmatch.filter(files, "*gcd*.xml")
            os_files = fnmatch.filter(files, "*os*.xml")
            ldap_files = fnmatch.filter(files, "*ldap*.xml")
            icn_files = fnmatch.filter(files, "*ecm*.xml")

            move_dict = {}

            if len(icn_files) > 1:
                state["logger"].error(
                    "More than one Navigator file found. Please remove the extra files and try again.")
                raise typer.Exit()
            elif len(icn_files) == 0:
                move_dict["ICN"] = []
            else:
                move_dict["ICN"] = icn_files

            if len(gcd_file) > 1:
                state["logger"].error("More than one GCD file found. Please remove the extra files and try again.")
                raise typer.Exit()
            elif len(gcd_file) == 0:
                move_dict["GCD"] = []
            else:
                move_dict["GCD"] = gcd_file

            if len(ldap_files) > 0:
                ldap_number = len(ldap_files)
                deploy1.ldap_number = ldap_number
                deploy1.parse_ldap_files(os.path.abspath(move), ldap_files)
                move_dict["LDAP"] = ldap_files
                move_ldap = True
            else:
                deploy1.collect_ldap_number()
                deploy1.collect_ldap_type()
                move_dict["LDAP"] = []

            # Determine DB type
            all_db_files = []
            all_db_files.extend(gcd_file)
            all_db_files.extend(os_files)
            all_db_files.extend(icn_files)
            if len(all_db_files) > 0:
                deploy1.parse_db_files(os.path.abspath(move), all_db_files)
                move_db = True
            else:
                deploy1.collect_db_type()

            # Determine number of OS's
            if len(os_files) > 0:
                os_number = len(os_files)
                deploy1.os_number = os_number
                move_dict["OS"] = os_files
            else:
                print()
                print(Panel.fit("Database"))
                deploy1.collect_os_number()
                move_dict["OS"] = []

            # Determine SSL Enabled
            deploy1.collect_db_ssl_info()

    else:
        # add logic to populate user_details using silent mode

        # deploy1 = s.SilentGather(state["logger"])
        # above line is for default silent installation file path
        # below line is for custom silent install config file
        deploy1 = sg.SilentGatherPrereqOptions(state["logger"],
                                  os.path.join("silent_config", "silent_install_prerequisites.toml"))

        # The following will run through the whole env file for silent install
        # deploy1.parse_envfile()

        # Individual components instead:
        deploy1.silent_version()
        deploy1.silent_platform()
        deploy1.silent_auth_type()
        if deploy1.auth_type in ("LDAP", "LDAP_IDP"):
            deploy1.silent_ldap()

        if deploy1.auth_type in ("LDAP_IDP", "SCIM_IDP"):
            deploy1.silent_idp()

        deploy1.silent_fips_support()
        deploy1.silent_egress_support()
        deploy1.silent_optional_components()
        deploy1.silent_sendmail_support()
        deploy1.silent_icc_support()
        deploy1.silent_tm_support()
        deploy1.silent_db()
        deploy1.silent_license_model()
        deploy1.silent_initverify()
        deploy1.error_check()
        deploy1.silent_networkpolicy_support()

    # Zip up previous propertyFile if it exists
    # Remove the propertyFile folder
    if os.path.exists(os.path.join(os.getcwd(), "propertyFile")):
        if not os.path.exists(os.path.join(os.getcwd(), "backups")):
            os.mkdir(os.path.join(os.getcwd(), "backups"))
        now = datetime.now()
        dt_string = now.strftime("%Y-%m-%d_%H-%M")
        zip_folder(os.path.join(os.getcwd(), "backups", "propertyFile_" + dt_string),
                   os.path.join(os.getcwd(), "propertyFile"))
        shutil.rmtree(os.path.join(os.getcwd(), "propertyFile"))

    # function call to create property files
    property_obj = p.Property(deploy1, os.getcwd(), state["logger"], console)
    property_obj.create_property_structure()

    db_properties = property_obj.populate_db_propertyfile()
    if move_db:
        db_properties = property_obj.move_database(os.path.abspath(move), move_dict, db_properties)
    property_obj.create_db_propertyfile(db_properties)

    if deploy1.auth_type in ("LDAP", "LDAP_IDP"):
        ldap_properties = property_obj.populate_ldap_propertyfile()
        if move_ldap:
            ldap_properties = property_obj.move_ldap(os.path.abspath(move), move_dict, ldap_properties)
        property_obj.create_ldap_propertyfile(ldap_properties)

    if deploy1.auth_type in ("LDAP_IDP", "SCIM_IDP"):
        idp_properties = property_obj.populate_idp_propertyfile()
        property_obj.create_idp_propertyfile(idp_properties)

    if deploy1.auth_type in ("SCIM_IDP"):
        scim_properties = property_obj.populate_scim_propertyfile()
        property_obj.create_scim_propertyfile(scim_properties)

    if deploy1.ingress:
        property_obj.create_ingress_propertyfile()
    property_obj.create_deployment_propertyfile()
    property_obj.create_user_group_propertyfile()

    # this is a property file generated for custom properties such as sendmail, icc , task manager groups etc
    if deploy1.sendmail_support or deploy1.icc_support or deploy1.tm_custom_groups:
        property_obj.create_custom_component_propertyfile()

    # Commented out the line below as it was removing error messages
    clear(console)
    layout = generate_gather_results(property_obj.property_folder,
                                     deploy1.to_dict(),
                                     move_db,
                                     move_ldap)

    print(layout)


@app.command()
def generate():
    """
    Generate the prerequisites for FileNet Content Manager Deployment.
    """

    clear(console)
    display_mode_version("Generate",
                         "FileNet Content Manager Deployment Prerequisites CLI")


    # Loading property folder locations
    prop_folder = os.path.join(os.getcwd(), "propertyFile")

    if not os.path.exists(prop_folder):
        state["logger"].info("Property files are missing. Please run the gather command first.")
        print(Panel.fit(Text("Property files are missing.\n"
                             "Please run the python3 prerequisites.py gather command first."), style="bold red"))
        raise typer.Exit()

    ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs")
    icc_folder = os.path.join(os.getcwd(), "propertyFile", "icc")
    trusted_certs_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs", "trusted-certs")

    # Loading generated folder location
    generated_folder = os.path.join(os.getcwd(), "generatedFiles")

    # Loading property files locations
    db_prop_file = os.path.join(prop_folder, "fncm_db_server.toml")
    ldap_prop_file = os.path.join(prop_folder, "fncm_ldap_server.toml")
    idp_prop_file = os.path.join(prop_folder, "fncm_identity_provider.toml")
    usergroup_prop_file = os.path.join(prop_folder, "fncm_user_group.toml")
    deployment_prop_file = os.path.join(prop_folder, "fncm_deployment.toml")
    ingress_prop_file = os.path.join(prop_folder, "fncm_ingress.toml")
    customcomponent_prop_file = os.path.join(prop_folder, "fncm_components_options.toml")
    scim_prop_file = os.path.join(prop_folder, "fncm_scim_server.toml")

    # Set defaults for property files
    db_prop = None
    ldap_prop = None
    idp_prop = None
    usergroup_prop = None
    deployment_prop = None
    ingress_prop = None
    customcomponent_prop = None
    scim_prop = None

    try:
        # Load property files if they exist
        if os.path.exists(db_prop_file):
            db_prop = ReadPropDb(os.path.join(prop_folder, "fncm_db_server.toml"), state["logger"])

        if os.path.exists(ldap_prop_file):
            ldap_prop = ReadPropLdap(os.path.join(prop_folder, "fncm_ldap_server.toml"), state["logger"])

        if os.path.exists(idp_prop_file):
            idp_prop = ReadPropIdp(os.path.join(prop_folder, "fncm_identity_provider.toml"), state["logger"])

        if os.path.exists(usergroup_prop_file):
            usergroup_prop = ReadPropUsergroup(os.path.join(prop_folder, "fncm_user_group.toml"), state["logger"])

        if os.path.exists(deployment_prop_file):
            deployment_prop = ReadPropDeployment(os.path.join(prop_folder, "fncm_deployment.toml"), state["logger"])

        if os.path.exists(ingress_prop_file):
            ingress_prop = ReadPropIngress(os.path.join(prop_folder, "fncm_ingress.toml"), state["logger"])

        if os.path.exists(customcomponent_prop_file):
            customcomponent_prop = ReadPropCustomComponent(os.path.join(prop_folder, "fncm_components_options.toml"),
                                                           state["logger"])
        if os.path.exists(scim_prop_file):
            scim_prop = ReadPropSCIM(os.path.join(prop_folder, "fncm_scim_server.toml"), state["logger"])

        # Create dictionaries for property files if not None
        if db_prop:
            db_prop_dict = db_prop.to_dict()
        else:
            db_prop_dict = {}

        if scim_prop:
            scim_prop_dict = scim_prop.to_dict()
        else:
            scim_prop_dict = {}

        if ldap_prop:
            ldap_prop_dict = ldap_prop.to_dict()
        else:
            ldap_prop_dict = {}

        if idp_prop:
            idp_prop_dict = idp_prop.to_dict()
        else:
            idp_prop_dict = {}

        if usergroup_prop:
            usergroup_prop_dict = usergroup_prop.to_dict()
        else:
            usergroup_prop_dict = {}

        if deployment_prop:
            deployment_prop_dict = deployment_prop.to_dict()
        else:
            deployment_prop_dict = {}

        if ingress_prop:
            ingress_prop_dict = ingress_prop.to_dict()
        else:
            ingress_prop_dict = {}

        if customcomponent_prop:
            customcomponent_prop_dict = customcomponent_prop.to_dict()
        else:
            customcomponent_prop_dict = {}

    except TomlDecodeError:
        state["logger"].exception(
            f"Exception when reading Property Files\n"
            f"Please Review your Property files for missing quotes and formatting.\n\n")
        exit(1)
    except Exception as e:
        state["logger"].exception(
        f"Exception when reading Property Files\n"
        f"Please Review your Property files for missing quotes and formatting.\n\n")
        exit(1)

    incorrect_naming_convention = check_dbname(db_prop_dict)
    # Check if SSL certificates are present and correct format
    missing_certs, incorrect_certs = check_ssl_folders(db_prop=db_prop_dict,
                                                       ldap_prop=ldap_prop_dict,
                                                       ssl_cert_folder=ssl_cert_folder,
                                                       deploy_prop=deployment_prop_dict,
                                                       idp_prop=idp_prop_dict,
                                                       scim_prop=scim_prop_dict)
    masterkey_present = check_icc_masterkey(customcomponent_prop_dict, icc_folder)
    trusted_certs_present, invalid_trusted_certs = check_trusted_certs(trusted_certs_folder)
    keystore_password_valid = check_keystore_password_length(usergroup_prop_dict, deployment_prop_dict)
    invalid_db_password_list = check_db_password_length(db_prop_dict,deployment_prop_dict)
    correct_ssl_mode = check_db_ssl_mode(db_prop_dict,deployment_prop_dict)

    cert_failed = len(missing_certs) > 0 or len(incorrect_certs) > 0 or (
            trusted_certs_present and len(invalid_trusted_certs) > 0)

    incorrect_entries = len(incorrect_naming_convention) > 0

    # Collect missing fields
    # All missing required fields are collected in each instance
    required_fields = {}
    if db_prop.missing_required_fields():
        required_fields = db_prop.required_fields

    if db_prop.missing_required_fields() or cert_failed or not masterkey_present or incorrect_entries or not keystore_password_valid or len(invalid_db_password_list)> 0 or not correct_ssl_mode:
        layout = display_issues(generate_folder=generated_folder, required_fields=required_fields,
                                certs=missing_certs, incorrect_certs=incorrect_certs,
                                masterkey_present=masterkey_present, invalid_trusted_certs=invalid_trusted_certs,
                                keystore_password_valid=keystore_password_valid, mode="generate",
                                incorrect_naming_conv=incorrect_naming_convention,invalid_db_password_list=invalid_db_password_list,correct_ssl_mode=correct_ssl_mode)
        print(layout)
        exit(1)
    else:
        # creating folder structure for generate folder
        if os.path.exists(generated_folder):
            if not os.path.exists(os.path.join(os.getcwd(), "backups")):
                os.mkdir(os.path.join(os.getcwd(), "backups"))
            now = datetime.now()
            dt_string = now.strftime("%Y-%m-%d_%H-%M")
            zip_folder(os.path.join(os.getcwd(), "backups", "generatedFiles_" + dt_string),
                       os.path.join(os.getcwd(), "generatedFiles"))
            shutil.rmtree(generated_folder)

        create_generate_folder(trusted_certs_present)

        generate_secrets = GenerateSecrets(db_properties=db_prop_dict,
                                           ldap_properties=ldap_prop_dict,
                                           idp_properties=idp_prop_dict,
                                           usergroup_properties=usergroup_prop_dict,
                                           customcomponent_properties=customcomponent_prop_dict,
                                           scim_properties=scim_prop_dict,
                                           deployment_properties=deployment_prop_dict,
                                           logger=state["logger"])

        # generate ban secret only if navigator is selected and generate fncm secret only if cpe is present
        # ban secret created if release version is 5.5.8 or navigator has been selected as a component in 5.5.11
        ban_present = False
        cpe_present = False
        if deployment_prop.to_dict()["FNCM_Version"] == "5.5.8":
            ban_present = True
        else:
            if "BAN" in deployment_prop.to_dict().keys():
                if deployment_prop.to_dict()["BAN"]:
                    ban_present = True
        # FNCM secret created if release version is 5.5.8 or CPE has been selected as a component in 5.5.11
        if deployment_prop.to_dict()["FNCM_Version"] == "5.5.8":
            cpe_present = True
        else:
            if "CPE" in deployment_prop.to_dict().keys():
                if deployment_prop.to_dict()["CPE"]:
                    cpe_present = True

        # Added for 5.6.0 and above. Checking for IER / ICCSAP.
        if deployment_prop.to_dict()["FNCM_Version"] not in ["5.5.8", "5.5.11", "5.5.12"]:
            if "IER" in deployment_prop.to_dict().keys():
                if deployment_prop.to_dict()["IER"]:
                    generate_secrets.create_ier_secret()

            if "ICCSAP" in deployment_prop.to_dict().keys():
                if deployment_prop.to_dict()["ICCSAP"]:
                    generate_secrets.create_iccsap_secret()

        if ban_present:
            generate_secrets.create_ban_secret()
        if ldap_prop:
            generate_secrets.create_ldap_secret()
            generate_secrets.create_ldap_ssl_secrets()
        if idp_prop:
            generate_secrets.create_idp_secret()
            generate_secrets.create_idp_ssl_secrets()

        if scim_prop:
            generate_secrets.create_scim_secret()
            generate_secrets.create_scim_ssl_secrets()

        # if icc for email set up is supported, then we create icc related secrets
        if customcomponent_prop_dict:
            if "ICC" in customcomponent_prop_dict.keys():
                generate_secrets.create_icc_secrets()
        if cpe_present:
            generate_secrets.create_fncm_secret()

        if db_prop:
            if db_prop_dict["DATABASE_SSL_ENABLE"]:
                generate_secrets.create_ssl_db_secrets()

        if trusted_certs_present:
            generate_secrets.create_trusted_secrets()

        generate_sql = GenerateSql(db_prop.to_dict(), state["logger"])
        if cpe_present:
            generate_sql.create_gcd()
            generate_sql.create_os()
        if ban_present:
            generate_sql.create_icn()

        # generate CR

        cr = GenerateCR(db_properties=db_prop_dict,
                        ldap_properties=ldap_prop_dict,
                        usergroup_properties=usergroup_prop_dict,
                        deployment_properties=deployment_prop_dict,
                        ingress_properties=ingress_prop_dict,
                        customcomponent_properties=customcomponent_prop_dict,
                        idp_properties=idp_prop_dict,
                        scim_properties=scim_prop_dict,
                        logger=state["logger"])

        cr.generate_cr()

    layout = generate_generate_results(generated_folder)

    print(layout)


@app.command()
def validate(
        apply: bool = typer.Option(False, help="Apply all generated artifacts to the cluster"),
        skip_storage_class: bool = typer.Option(False, "--skip-storageclass", "-sc", help="Skip storage class validation"),
        skip_database: bool = typer.Option(False, "--skip-database", "-db", help="Skip database validation"),
        skip_ldap: bool = typer.Option(False, "--skip-ldap", "-l", help="Skip LDAP validation"),
        skip_idp: bool = typer.Option(False, "--skip-idp", "-idp", help="Skip IDP validation"),
        skip_scim: bool = typer.Option(False, "--skip-scim", "-scim", help="Skip SCIM validation"),
        pvc_size: str = typer.Option('10Mi', "--pvc-size", "-pvc", help="Set size for sample persitant volume validation"),
):
    """
    Validate the prerequisites for FileNet Content Manager Deployment.
    """

    # By default, all validations are executed
    validate_storage_class = not skip_storage_class
    validate_database = not skip_database
    validate_ldap = not skip_ldap
    validate_idp = not skip_idp
    validate_scim = not skip_scim
    
    clear(console)
    display_mode_version("Validate",
                         "FileNet Content Manager Deployment Prerequisites CLI")

    hint_panel = Panel.fit(
        "- Run the validation from the FNCM Standalone Operator \n"
        "- All tools and libraries are installed \n"
        "- Validation from within the your cluster can test private connections \n"
        "- See the below command to copy the folder and run the validation.",
        title="Hint"
    )

    command_panel = (Panel.fit(
        Syntax("cd ..\n"
               "export OPERATOR=$(kubectl get pods -l 'name=ibm-fncm-operator' | awk 'NR>1 {print $1}')\n"
               "kubectl cp scripts  $OPERATOR:/opt/ansible\n"
               "kubectl exec -it $OPERATOR -- bash\n"
               "cd /opt/ansible/scripts\n"
               "python3 prerequisites.py validate",
               "bash", theme="ansi_dark"
               ),
        title="Command"
    ))

    operator_panel = Panel(Columns([hint_panel, command_panel], align="center", equal=True),
                           title="FNCM Standalone Operator", border_style="cyan")
    print(operator_panel)
    print()

    # Loading property folder locations
    prop_folder = os.path.join(os.getcwd(), "propertyFile")

    # Loading property folder locations
    prop_folder = os.path.join(os.getcwd(), "propertyFile")

    if not os.path.exists(prop_folder):
        state["logger"].info("Property files are missing. Please run the gather command first.")
        print(Panel.fit(Text("Property files are missing.\n"
                             "Please run the python3 prerequisites.py gather command first."), style="bold red"))
        raise typer.Exit()
    
    # Validate passed pvc_size 
    # Write a regex match for pvc_size 
    pvc_pattern = re.compile(r'^[0-9]+(mi|gi)$')
    if not re.match(pvc_pattern, pvc_size.lower()):
        print(Panel.fit(Text("Invalid pvc_size.\n"
                             "Size needs to be either ending in Mi or Gi"), style="bold red"))
        state["logger"].info("The passed pvc_size is not valid. Size needs to be either ending in Mi or Gi")
        raise typer.Exit()

    ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs")
    icc_folder = os.path.join(os.getcwd(), "propertyFile", "icc")
    trusted_certs_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs", "trusted-certs")

    # Loading generated folder location
    os.path.join(os.getcwd(), "generatedFiles")
    generated_folder = os.path.join(os.getcwd(), "generatedFiles")

    # Loading property files locations
    db_prop_file = os.path.join(prop_folder, "fncm_db_server.toml")
    ldap_prop_file = os.path.join(prop_folder, "fncm_ldap_server.toml")
    idp_prop_file = os.path.join(prop_folder, "fncm_identity_provider.toml")
    scim_prop_file = os.path.join(prop_folder, "fncm_scim_server.toml")
    usergroup_prop_file = os.path.join(prop_folder, "fncm_user_group.toml")
    deployment_prop_file = os.path.join(prop_folder, "fncm_deployment.toml")
    ingress_prop_file = os.path.join(prop_folder, "fncm_ingress.toml")
    customcomponent_prop_file = os.path.join(prop_folder, "fncm_components_options.toml")

    # Set defaults for property files
    db_prop = None
    ldap_prop = None
    idp_prop = None
    scim_prop = None
    usergroup_prop = None
    deployment_prop = None
    ingress_prop = None
    customcomponent_prop = None
    try:
        # Load property files if they exist
        if os.path.exists(db_prop_file):
            db_prop = ReadPropDb(os.path.join(prop_folder, "fncm_db_server.toml"), state["logger"])

        if os.path.exists(ldap_prop_file):
            ldap_prop = ReadPropLdap(os.path.join(prop_folder, "fncm_ldap_server.toml"), state["logger"])

        if os.path.exists(idp_prop_file):
            idp_prop = ReadPropIdp(os.path.join(prop_folder, "fncm_identity_provider.toml"), state["logger"])

        if os.path.exists(scim_prop_file):
            scim_prop = ReadPropSCIM(os.path.join(prop_folder, "fncm_scim_server.toml"), state["logger"])

        if os.path.exists(usergroup_prop_file):
            usergroup_prop = ReadPropUsergroup(os.path.join(prop_folder, "fncm_user_group.toml"), state["logger"])

        if os.path.exists(deployment_prop_file):
            deployment_prop = ReadPropDeployment(os.path.join(prop_folder, "fncm_deployment.toml"), state["logger"])

        if os.path.exists(ingress_prop_file):
            ingress_prop = ReadPropIngress(os.path.join(prop_folder, "fncm_ingress.toml"), state["logger"])

        if os.path.exists(customcomponent_prop_file):
            customcomponent_prop = ReadPropCustomComponent(os.path.join(prop_folder, "fncm_components_options.toml"),
                                                           state["logger"])

        # Create dictionaries for property files if not None
        if db_prop:
            db_prop_dict = db_prop.to_dict()
        else:
            db_prop_dict = {}

        if ldap_prop:
            ldap_prop_dict = ldap_prop.to_dict()
        else:
            ldap_prop_dict = {}

        if idp_prop:
            idp_prop_dict = idp_prop.to_dict()
        else:
            idp_prop_dict = {}

        if scim_prop:
            scim_prop_dict = scim_prop.to_dict()
        else:
            scim_prop_dict = {}

        if usergroup_prop:
            usergroup_prop_dict = usergroup_prop.to_dict()
        else:
            usergroup_prop_dict = {}

        if deployment_prop:
            deployment_prop_dict = deployment_prop.to_dict()
        else:
            deployment_prop_dict = {}

        if ingress_prop:
            ingress_prop_dict = ingress_prop.to_dict()
        else:
            ingress_prop_dict = {}

        if customcomponent_prop:
            customcomponent_prop_dict = customcomponent_prop.to_dict()
        else:
            customcomponent_prop_dict = {}
    except TomlDecodeError:
        state["logger"].exception(
            f"Exception when reading Property Files\n"
            f"Please Review your Property files for missing quotes and formatting.\n\n")
        exit(1)
    except Exception as e:
        state["logger"].exception(
        f"Exception when reading Property Files\n"
        f"Please Review your Property files for missing quotes and formatting.\n\n")
        exit(1)



    vobject = v.Validate(state["logger"],
                         db_prop=db_prop_dict,
                         ldap_prop=ldap_prop_dict,
                         deploy_prop=deployment_prop_dict,
                         idp_prop=idp_prop_dict,
                         scim_prop=scim_prop_dict,
                         component_prop=customcomponent_prop_dict,
                         user_group_prop=usergroup_prop_dict, 
                         pvc_size=pvc_size)

    db_number = 0
    if deployment_prop_dict["FNCM_Version"] == "5.5.8":
        db_number += 1
        db_number += len(db_prop_dict["_os_ids"])
        db_number += 1
    else:
        if "CPE" in deployment_prop_dict.keys():
            if deployment_prop_dict["CPE"]:
                db_number += 1
                db_number += len(db_prop_dict["_os_ids"])

        if "BAN" in deployment_prop_dict.keys():
            if deployment_prop_dict["BAN"]:
                db_number += 1

    storageclass_number = len(vobject.get_unique_storageclass())

    missing_certs, incorrect_certs = check_ssl_folders(db_prop=db_prop_dict, ldap_prop=ldap_prop_dict,
                                                       ssl_cert_folder=ssl_cert_folder,
                                                       deploy_prop=deployment_prop_dict,
                                                       idp_prop=idp_prop_dict,
                                                       scim_prop=scim_prop_dict)
    # Collect missing fields
    # All missing required fields are collected in each instance
    required_fields = {}
    if db_prop.missing_required_fields():
        required_fields = db_prop.required_fields

    if db_prop.missing_required_fields() or len(vobject.missing_tools) > 0 or len(missing_certs) > 0 or len(
            incorrect_certs) > 0:
        layout = display_issues(required_fields=required_fields, tools=vobject.missing_tools, certs=missing_certs,
                                incorrect_certs=incorrect_certs, mode="validate",deployment_prop=deployment_prop_dict)
        print(layout)
        exit(1)
    else:

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

            # Adding storage classes validation task only if storageclass flag is True
            if validate_storage_class:
                task3 = progress.add_task("[green]Validate Storage Class", total=storageclass_number)
            # Adding databases validation task only if database flag is True
            if validate_database:
                if db_number > 0:
                    task4 = progress.add_task("[yellow]Validate Database", total=db_number)
            # Adding ldaps validation task only if ldap flag is True
            if validate_ldap:
                if ldap_prop:
                    task1 = progress.add_task("[cyan]Validate LDAP", total=ldap_prop_dict["ldap_number"])
            # Adding idp validation task only if idp flag is True
            if validate_idp:
                if idp_prop:
                    task5 = progress.add_task("[blue]Validate IDP", total=(idp_prop_dict["idp_number"]+1))
            # Adding scim validation task only if scim flag is True
            if validate_scim:
                if scim_prop:
                    task6 = progress.add_task("[slate_blue1]Validate SCIM", total=scim_prop_dict["scim_number"])

            while not progress.finished:
                if (deployment_prop_dict["FNCM_Version"] not in ["5.5.8", "5.5.11"])  and deployment_prop_dict["FIPS_SUPPORT"]:
                    progress.log(Panel.fit(Text("Validating all connections with FIPS protocol.\n"
                                            "These tests will only pass on FIPS enabled platforms."), style="bold purple"))
                if validate_database or validate_ldap:
                    vobject.create_truststore(progress)
                # Validating storage classes only if storageclass flag is True
                if validate_storage_class:
                    vobject.validate_all_storage_classes(task3, progress)
                # Validating databases only if database flag is True
                if validate_database:
                    if db_number > 0:
                        vobject.validate_all_db(task4, progress)
                # Validating ldaps only if ldap flag is True
                if validate_ldap:
                    if ldap_prop:
                        ldaps_validated = vobject.validate_all_ldap(task1, progress)
                        if ldaps_validated:
                            task2 = progress.add_task("[purple]Validate LDAP Users and Groups", total=1)
                            vobject.validate_ldap_users_groups(task2, progress)
                # # Validating IDP using LDAP bind DN credentials
                if validate_idp:
                    if idp_prop:
                        vobject.validate_all_idps(task5, progress)

                # Validating SCIM using IDP token
                if validate_scim:
                    if scim_prop:
                        vobject.validate_scim(task6, progress)

        if all(vobject.is_validated.values()):
            print()
            print(Panel.fit(Text("All prerequisites are validated"), style="bold green"))
            print()
            if apply:
                vobject.auto_apply_secrets_ssl()
                vobject.auto_apply_cr()
            else:
                apply_ssls_secrets = Confirm.ask("Do you want to apply the SSL & Secrets?")
                if apply_ssls_secrets:
                    vobject.auto_apply_secrets_ssl()
                apply_cr = Confirm.ask("Do you want to apply the CR?")
                if apply_cr:
                    vobject.auto_apply_cr()
        else:
            print()
            print(Panel.fit(Text("All prerequisites checks have not passed!"), style="bold red"))
            print()
            if apply:
                vobject.auto_apply_secrets_ssl()
                vobject.auto_apply_cr()
            else:
                apply_ssls_secrets = Confirm.ask("Do you want to apply the SSL & Secrets?")
                if apply_ssls_secrets:
                    vobject.auto_apply_secrets_ssl()
                apply_cr = Confirm.ask("Do you want to apply the CR?")
                if apply_cr:
                    vobject.auto_apply_cr()


if __name__ == "__main__":
    app()
