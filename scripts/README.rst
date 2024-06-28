=====================================================
FileNet Deployment DevOps Suite Readme
=====================================================

------------
Introduction
------------

Welcome to the FileNet Deployment DevOps Suite!

This suite provides a set of tools and scripts to streamline the deployment / management / troubleshooting of FileNet Standalone systems in containerized environments.

The FNCM Standalone Suite includes the following tools:

- Deployment Prerequisite
    Building a FileNet Standalone system in a containerized environment requires gathering information about your desired deployment, generating SQL templates and YAML files based on the gathered information, and validating the connections to external services and the usage of storage classes. The FileNet Deployment Preparation Script helps you automate these tasks and streamline the preparation phase for deploying FileNet in containerized environments.
- Operator Deployment
    The Operator Deployment Script helps you deploy the FileNet Standalone Operator. This script automates the deployment process and simplifies the setup of a Operator.
- Deployment Upgrade
    The Deployment Upgrade Script helps you upgrade both the Operator and your deployed Custom Resource. This script automates the upgrade process and simplifies the upgrade of a FileNet Standalone deployment.
- Deployment Cleanup
    The Cleanup Script helps you clean up a FileNet Standalone deployment including the Operator. This script automates the cleanup process and simplifies the removal of a FileNet Standalone deployment from a Kubernetes cluster.
- LoadImages
    The LoadImages script helps you load the FileNet Standalone images into your private image registry. This script automates the loading of images for Offline CNCF deployments.
- MustGather
    The MustGather script helps you gather information about your FileNet Standalone deployment. This script automates the collection of logs, configuration files, and other diagnostic information to help troubleshoot issues with your FileNet Standalone Install.


Prerequisites
-------------

Before proceeding with the installation, please ensure that you have the following prerequisites in place:

- Operating System: Windows, Linux, or macOS
- Java 8, Semeru 11, Semeru 17: Installed and properly configured on your system (Prerequisite Script only)
- Kubernetes: Installed and properly configured on your system
- Python: Installed on your system (Python 3.8 or later)
- FileNet Standalone Container Github: Downloaded and available for installation

    .. note::

        The Deployment Prerequisites Script can also be run from the FileNet Standalone Operator, where all the prerequisites are already in place.

------------------
Installation Steps
------------------


Follow the steps below to prepare your python environment::

1. Extract the contents of the container Github repo to a directory of your choice.
2. Open a terminal or command prompt and navigate to the directory where the installer package was extracted::

    cd container-samples/scripts

4. Run the following command to install the required Python packages from the `requirements.txt` file::

    python3 -m pip install -r requirements.txt

--------
Overview
--------

All python scripts provided in the FNCM DevOps Suite has the following features:

- **Help**: Provides information about the script and its usage.
- **Silent Mode**: Runs the script without any prompts.
- **Verbose Mode**: Provides detailed information about the script execution.
- **Dry Run Mode**: Simulates the script execution without making any changes to the system.
- **Automatic Backups**: If a mode is rerun, and the output files already exist, the script will automatically backup the existing files `scripts/backups`.

To use verbose and / or dryrun mode, you can include the `--verbose` and / or `--dryrun` flag in the command. For example::

    python3 upgradedeployment.py --verbose --dryrun deployment

To use silent mode, fill out the corresponding configuration file and include the `--silent` flag in the command. For example::

    python3 upgradedeployment.py --silent deployment

.. note::
    All silent configuration files are located in the `scripts/silent_config` directory.

Usage
-----

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Deployment Prerequisites: `prerequisites.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the Deployment Preparation Script in the following modes:

1. **Gather Mode**: This mode helps gather information about your desired deployment.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 prerequisites.py gather

   - Follow the prompts and provide the required information about your desired deployment.
   - Optionally, include the `--move <folder-location>` flag to indicate that you are moving your existing traditional deployment to a containerized environment.

    .. note::
        All passwords, usernames and client secrets are triple quoted to preserve special characters.
        If your passwords, usernames or client secrets contain a '\\' they will be need to escaped with an additional '\\'.

        For example:

        `"\"\";?.*\\\\)[&^%'$\"\"\#\@!~\"\"" -> ';?.*\\)[&^%'$\"\"\#\@!~'`


2. **Generate Mode**: This mode generates SQL templates and YAML files based on the gathered information.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 prerequisites.py generate

   - Review the generated files and modify them if necessary.

3. **Validate Mode**: This mode validates the connections to external services and the usage of storage classes.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 prerequisites.py validate

   - The script will validate the connections to external services such as the database services and directory services (LDAPs), as well as the usage of the provided storage classes.

    .. note::
        The FileNet Deployment Preparation Script can also be run from the FileNet Standalone Operator.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Operator Deployment: `deployoperator.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 deployoperator.py

   - Follow the prompts and provide the required information.

For more information on running the Operator Deployment Script, refer to the `documentation <https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.dba.install/filenet_containers_install_topics/containers_tsk_setup_enterp_silent.html>`_.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Deployment Upgrade: `upgradedeployment.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the Deployment Upgrade Script in the following modes:

1. **Operator Mode**: This mode upgrades the FileNet Standalone Operator Only.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 upgradedeployment.py operator

For more information on running the Upgrade Script in Operator Mode, refer to the `documentation <https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.p8.containers.doc/containers_tsk_setup_enterp_upgrade.htm>`_.

2. **Deployment Mode**: This mode upgrades the deployed Custom Resource with the option to scale down and apply the updated custom resource.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 upgradedeployment.py deployment

    .. tip::
        Run the upgrade script in dryrun mode `--dryrun` to simulate the upgrade process without making any changes to the system.

3. **All Mode**: This mode upgrades both the Operator and the deployed Custom Resource.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 upgradedeployment.py

For more information on running the Upgrade Script in Deployment Mode, refer to the `documentation <https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.p8.containers.doc/containers_upg_deployment_script.htm>`_.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Deployment Cleanup: `cleandeployment.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the Deployment Cleanup Script in the following modes:

1. **Operator Mode**: This mode cleans up the FileNet Standalone Operator.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 cleandeployment.py operator

2. **Deployment Mode**: This mode cleans up the deployed Custom Resource.

    - Open a terminal or command prompt.
    - Navigate to the installation directory of the script.
    - Run the script using the following command::

         python3 cleandeployment.py deployment

    .. tip::
        Run the cleanup script in dryrun mode `--dryrun` to simulate the cleanup process without making any changes to the system.

3. **All Mode**: This mode cleans up both the Operator and the deployed Custom Resource.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 cleandeployment.py

For more information on running the Cleanup Script, refer to the `documentation <https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.dba.install/filenet_containers_install_topics/containers_tsk_uninstall_enterp.html>`_.

^^^^^^^^^^^^^^^^^^^^^^^^^^^
LoadImages: `loadimages.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the LoadImages Script in the following modes:

1. **Generate Mode**: This mode generated a list of images to be loaded into your private image registry.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 loadimages.py generate

   - Follow the prompts and provide the required information about your desired deployment.

   .. note::
       - The generated file will be saved in the `scripts/imageDetails` directory.
       - You can adjust the generated file to include only the images you want to load.

2. **Push Mode**: This mode loads the generated file and starts pushing the images into your private image registry.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 loadimages.py push

   - Follow the prompts and provide the required information about your desired deployment.

3. **All Mode**: This mode combines the Generate and Push modes to generate a list of images and push them into your private image registry.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 loadimages.py

For more information on running the LoadImages Script, refer to the `documentation <https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.dba.install/filenet_containers_install_topics/containers_tsk_images_enterp.html>`_.

^^^^^^^^^^^^^^^^^^^^^^^^^^^
MustGather: `mustgather.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 mustgather.py

   - Follow the prompts and provide the required information.

   .. note::
         After the mustgather scripts completes, the zipped up file will be located in `scripts/MustGather.tar.gz`.

   .. tip::
        You can select the components you want to gather information for by selecting the corresponding options in the script.
        Deployment artifacts and Operator logs will be gathered by default.

For more information on running the MustGather Script, refer to the `documentation <https://www.ibm.com/support/pages/node/7152864>`_.


Troubleshooting
---------------

If you encounter any issues during the installation or usage of the FileNet Deployment DevOps Suite, please refer to the troubleshooting section in the provided `documentation <https://www.ibm.com/docs/SSNW2F_5.6.0/com.ibm.p8.containers.doc/containers_tsk_script_prep.htm>`_. Additionally, feel free to reach out to our support team for further assistance.

Conclusion
----------

Congratulations! You have successfully installed the FileNet Deployment DevOps Suite.

Thank you for choosing our solution, and we hope these script enhances your FileNet deployment experience.
