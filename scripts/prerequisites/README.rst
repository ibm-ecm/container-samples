FileNet Deployment Prerequisite Script Installer Readme
=====================================================

Introduction
------------

Welcome to the FileNet Deployment Prerequisite Script Installer! This readme provides instructions for installing and using the script that streamlines the preparation phase for deploying a FileNet Standalone system in containerized environments.
For more details on the script and its usage, please refer to the provided `documentation <https://www.ibm.com/support/pages/node/6999079>`_.

Prerequisites
-------------

Before proceeding with the installation, please ensure that you have the following prerequisites in place:

- Operating System: Windows, Linux, or macOS
- Java Semeru 11: Installed and properly configured on your system
- Kubernetes: Installed and properly configured on your system
- Python: Installed on your system (Python 3.8 or later)
- FileNet Standalone CASE Package: Downloaded and available for installation

**Note:** The FileNet Deployment Prerequisites Script can also be run from the FileNet Standalone Operator, where all the prerequisites are already in place.

Installation Steps
------------------

Follow the steps below to install and set up the FileNet Deployment Preparation Script:

1. Download the installer package from the provided source.
2. Extract the contents of the CASE package to a directory of your choice.
3. Open a terminal or command prompt and navigate to the directory where the installer package was extracted::

    cd ./container-samples/scripts/prerequisites

4. Run the following command to install the required Python packages from the `requirements.txt` file::

    python -m pip install -r requirements.txt

Usage
-----

Once the installation is complete, you can use the FileNet Deployment Preparation Script in the following modes:

1. **Gather Mode**: This mode helps gather information about your desired deployment.

   - Open a terminal or command prompt.
   - Navigate to the installation directory of the script.
   - Run the script using the following command::

       python3 prerequisites.py gather

   - Follow the prompts and provide the required information about your desired deployment.
   - Optionally, include the `--move <folder-location>` flag to indicate that you are moving your existing traditional deployment to a containerized environment.

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

**Note:** The FileNet Deployment Preparation Script can also be run from the FileNet Standalone Operator.


Troubleshooting
---------------

If you encounter any issues during the installation or usage of the FileNet Deployment Preparation Script, please refer to the troubleshooting section in the provided `documentation <https://www.ibm.com/support/pages/node/6999079>`_. Additionally, feel free to reach out to our support team for further assistance.

Conclusion
----------

Congratulations! You have successfully installed the FileNet Deployment Preparation Script. This script will help simplify and optimize the preparation phase for deploying FileNet in containerized environments.

Thank you for choosing our solution, and we hope this script enhances your FileNet deployment experience.
