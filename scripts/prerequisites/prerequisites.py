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

from helper_scripts.gather import gather as g
from helper_scripts.gather import silent as sg
from helper_scripts.generate.generate_cr import GenerateCR
from helper_scripts.generate.generate_secrets import GenerateSecrets
from helper_scripts.generate.generate_sql import GenerateSql
from helper_scripts.property import property as p
from helper_scripts.property.read_prop import *
from helper_scripts.utilities.utilites import zip_folder, \
    create_generate_folder, generate_gather_results, generate_generate_results, generate_validate_results, \
    clear, check_ssl_folders , check_icc_masterkey, check_dbname, collect_visible_files
from helper_scripts.validate import validate as v

__version__ = "1.6.7"

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


def setup_logger(file_log_level, verbose=False):
    # Create a logger object
    logger = logging.getLogger("prerequisites")

    shell_handler = RichHandler()
    file_handler = logging.FileHandler("prerequisites.log")

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


@app.command()
def gather(
        move: str = typer.Option("", help="Folder location of the migration files", rich_help_panel="Mode Options",
                                 dir_okay=True),
):
    """
    Gather the prerequisites for FileNet Content Manager Deployment.
    """

    clear(console)
    print()
    print(Panel.fit("Version: {version}\n"
                    "Mode: Gather".format(version=__version__),
                    title="FileNet Content Manager Deployment Prerequisites CLI", border_style="green"))
    print()

    if move != '':
        dir_exists = os.path.isdir(move)

        if not dir_exists:
            state["logger"].error("The directory does not exist. Please check the directory and try again.")
            raise typer.Exit()

    move_db = False
    move_ldap = False

    # this is the user details object
    deploy1 = g.GatherOptions(state["logger"], console)

    if not state["silent"]:
        if move == '':
            deploy1.collect_fncm_version()
            clear(console)
            deploy1.collect_license_model()

            clear(console)
            deploy1.collect_platform_ingress()

            clear(console)
            deploy1.collect_optional_components()

            clear(console)
            deploy1.collect_db_info()

            clear(console)
            deploy1.collect_ldap_number()
            deploy1.collect_ldap_type()

            clear(console)
            deploy1.collect_init_verify_content()
        else:
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
                deploy1.collect_os_number()
                move_dict["OS"] = []

            # Determine SSL Enabled
            deploy1.collect_db_ssl_info()

    else:
        # add logic to populate user_details using silent mode

        # deploy1 = s.SilentGather(state["logger"])
        # above line is for default silent install file path
        # below line is for custom silent install config file
        deploy1 = sg.SilentGather(state["logger"],
                                  os.path.join("helper_scripts", "gather", "silent_config", "silent_install.toml"))

        # The following will run through the whole env file for silent install
        # deploy1.parse_envfile()

        # Individual components instead:
        deploy1.silent_version()
        deploy1.silent_platform()
        deploy1.silent_optional_components()
        deploy1.silent_sendmail_support()
        deploy1.silent_icc_support()
        deploy1.silent_tm_support()
        deploy1.silent_db()
        deploy1.silent_license_model()
        deploy1.silent_ldap()
        deploy1.silent_initverify()
        deploy1.error_check()

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

    ldap_properties = property_obj.populate_ldap_propertyfile()
    if move_ldap:
        ldap_properties = property_obj.move_ldap(os.path.abspath(move), move_dict, ldap_properties)

    property_obj.create_ldap_propertyfile(ldap_properties)
    if deploy1.ingress:
        property_obj.create_ingress_propertyfile()
    property_obj.create_deployment_propertyfile()
    property_obj.create_user_group_propertyfile()
    #this is a property file generated for custom properties such as sendmail, icc , task manager groups etc
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
    print()
    print(Panel.fit("Version: {version}\n"
                    "Mode: Generate".format(version=__version__),
                    title="FileNet Content Manager Deployment Prerequisites CLI", border_style="green"))
    print()

    # Generating secrets
    prop_folder = os.path.join(os.getcwd(), "propertyFile")
    ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs")
    icc_folder = os.path.join(os.getcwd(), "propertyFile", "icc")

    db_prop = ReadPropDb(os.path.join(prop_folder, "fncm_db_server.toml"), state["logger"])
    ldap_prop = ReadPropLdap(os.path.join(prop_folder, "fncm_ldap_server.toml"), state["logger"])
    usergroup_prop = ReadPropUsergroup(os.path.join(prop_folder, "fncm_user_group.toml"), state["logger"])
    deployment_prop = ReadPropDeployment(os.path.join(prop_folder, "fncm_deployment.toml"), state["logger"])
    #if custom component toml file is created , load the data as we might need some info such as javasendmail from it to create the ban secret
    if os.path.exists(os.path.join(prop_folder, "fncm_components_options.toml")):
        customcomponent_prop = ReadPropCustomComponent(os.path.join(prop_folder, "fncm_components_options.toml"), state["logger"])
        customcomponent_prop_dict = customcomponent_prop.to_dict()
    else:
        customcomponent_prop_dict = {}
    # check if ingress prop file has been created
    ingress_prop_present = False
    if os.path.exists(os.path.join(prop_folder, "fncm_ingress.toml")):
        ingress_prop = ReadPropIngress(os.path.join(prop_folder, "fncm_ingress.toml"), state["logger"])
        ingress_prop_present = True

    incorrect_naming_convention = check_dbname(db_prop.to_dict())
    missing_certs = check_ssl_folders(db_prop.to_dict(), ldap_prop.to_dict(), ssl_cert_folder)
    masterkey_present = check_icc_masterkey(customcomponent_prop_dict,icc_folder)
    os.path.join(os.getcwd(), "generatedFiles")
    generated_folder = os.path.join(os.getcwd(), "generatedFiles")

    # check of there are missing values in the property files
    # if there are missing values, then exit the program
    if len(db_prop.required_fields) > 0 or len(missing_certs) > 0 or masterkey_present == False or len(incorrect_naming_convention):
        layout = generate_generate_results(generated_folder, db_prop.required_fields, missing_certs,masterkey_present, incorrect_naming_convention)
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

        create_generate_folder()

        generate_secrets = GenerateSecrets(db_prop.to_dict(), ldap_prop.to_dict(), usergroup_prop.to_dict(),
                                           customcomponent_prop_dict,
                                           state["logger"])
        #generate ban secret only if navigator is selected and generate fncm secret only if cpe is present
        #ban secret created if release version is 5.5.8 or navigator has been selected as a component in 5.5.11
        ban_present = False
        cpe_present = False
        if deployment_prop.to_dict()["FNCM_Version"] == "5.5.8":
            ban_present = True
        else:
            if "BAN" in deployment_prop.to_dict().keys():
                if deployment_prop.to_dict()["BAN"]:
                    ban_present =  True
        # FNCM secret created if release version is 5.5.8 or CPE has been selected as a component in 5.5.11
        if deployment_prop.to_dict()["FNCM_Version"] == "5.5.8":
            cpe_present = True
        else:
            if "CPE" in deployment_prop.to_dict().keys():
                if deployment_prop.to_dict()["CPE"]:
                    cpe_present =  True
        if ban_present:
            generate_secrets.create_ban_secret()
        generate_secrets.create_ldap_secret()
        #if icc for email set up is supported then we create icc related secrets
        if customcomponent_prop_dict:
            if "CSS" in customcomponent_prop_dict.keys():
                generate_secrets.create_icc_secrets()
        if cpe_present:
            generate_secrets.create_fncm_secret()
        generate_secrets.create_ssl_secrets()

        generate_sql = GenerateSql(db_prop.to_dict(), state["logger"])
        if cpe_present:
            generate_sql.create_gcd()
            generate_sql.create_os()
        if ban_present:
            generate_sql.create_icn()

        # generate CR
        if ingress_prop_present:
            cr = GenerateCR(db_prop.to_dict(), ldap_prop.to_dict(), usergroup_prop.to_dict(), deployment_prop.to_dict(),
                            ingress_prop.to_dict(),customcomponent_prop_dict, state["logger"])
            cr.generate_cr()
        else:
            cr = GenerateCR(db_prop.to_dict(), ldap_prop.to_dict(), usergroup_prop.to_dict(), deployment_prop.to_dict(),
                            None,customcomponent_prop_dict,
                            state["logger"])
            cr.generate_cr()

    layout = generate_generate_results(generated_folder, db_prop.required_fields)

    print(layout)


@app.command()
def validate(
        apply: bool = typer.Option(False, help="Apply all generated artifacts to the cluster"),
):
    """
    Validate the prerequisites for FileNet Content Manager Deployment.
    """

    clear(console)
    print()
    print(Panel.fit("Version: {version}\n"
                    "Mode: Validate".format(version=__version__),
                    title="FileNet Content Manager Deployment Prerequisites CLI", border_style="green"))
    print()
    hint_panel = Panel.fit(
        "- Run the validation from the FNCM Standalone Operator \n"
        "- All tools and libraries are installed \n"
        "- Validation from within the your cluster can test private connections \n"
        "- See the below command to copy the folder and run the validation.",
        title="Hint"
    )

    command_panel = (Panel.fit(
        Syntax("cd ..\n"
               "export OPERATOR=$(kubectl get pods | grep operator | awk '{print $1}')\n"
               "kubectl cp prerequisites $OPERATOR:/opt/ansible\n"
               "kubectl exec -it $OPERATOR -- bash\n"
               "cd /opt/ansible\n"
               "python3 prerequisites.py validate",
               "bash", theme="ansi_dark"
               ),
        title="Command"
    ))

    operator_panel = Panel(Columns([hint_panel, command_panel], align="center", equal=True),
                           title="FNCM Standalone Operator", border_style="cyan")
    print(operator_panel)
    print()

    vobject = v.Validate(state["logger"])

    ssl_cert_folder = os.path.join(os.getcwd(), "propertyFile", "ssl-certs")

    db_info = vobject._db_prop
    ldap_info = vobject._ldap_prop
    storageclass_number = len(vobject.get_unique_storageclass())

    missing_certs = check_ssl_folders(db_info, ldap_info, ssl_cert_folder)

    if len(vobject.required_fields) > 0 or len(vobject.missing_tools) > 0 or len(missing_certs) > 0:
        layout = generate_validate_results(vobject.required_fields, vobject.missing_tools, missing_certs)
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

            task1 = progress.add_task("[cyan]Validate LDAP", total=ldap_info["ldap_number"])
            task2 = progress.add_task("[green]Validate Storage Class", total=storageclass_number)
            task3 = progress.add_task("[yellow]Validate Database", total=db_info["db_number"])

            while not progress.finished:
                vobject.validate_all_ldap(task1, progress)
                vobject.validate_all_storage_classes(task2, progress)
                vobject.validate_all_db(task3, progress)
        vobject.cleanup_tmp()

        if all(vobject.is_validated.values()):
            print()
            print(Panel.fit(Text("All prerequisites are validated", style="bold green")))
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
