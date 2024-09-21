#!/bin/bash
# set -x
###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2022. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################
CUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Import common utilities and environment variables
source ${CUR_DIR}/helper/common.sh
RUNTIME_MODE=$1

TEMP_FOLDER=${CUR_DIR}/.tmp
CRD_FILE=${PARENT_DIR}/descriptors/fncm_v1_fncm_crd.yaml
SA_FILE=${PARENT_DIR}/descriptors/service_account.yaml
CLUSTER_ROLE_FILE=${PARENT_DIR}/descriptors/cluster_role.yaml
CLUSTER_ROLE_BINDING_FILE=${PARENT_DIR}/descriptors/cluster_role_binding.yaml
CLUSTER_ROLE_BINDING_FILE_TEMP=${TEMP_FOLDER}/.cluster_role_binding.yaml
ROLE_FILE=${PARENT_DIR}/descriptors/role.yaml
ROLE_BINDING_FILE=${PARENT_DIR}/descriptors/role_binding.yaml
BRONZE_STORAGE_CLASS=${PARENT_DIR}/descriptors/fncm-bronze-storage-class.yaml
SILVER_STORAGE_CLASS=${PARENT_DIR}/descriptors/fncm-silver-storage-class.yaml
GOLD_STORAGE_CLASS=${PARENT_DIR}/descriptors/fncm-gold-storage-class.yaml
LOG_FILE=${CUR_DIR}/prepare_install.log
PLATFORM_SELECTED=""
PLATFORM_VERSION=""
PROJ_NAME=""
PROJ_NAME_ALL_NAMESPACE="openshift-operators"
DOCKER_RES_SECRET_NAME="ibm-entitlement-key"
REGISTRY_IN_FILE="icr.io"
OPERATOR_FILE=${PARENT_DIR}/descriptors/operator.yaml
OPERATOR_FILE_TMP=$TEMP_FOLDER/.operator_tmp.yaml
SCRIPT_MODE=""

# Make temporary folder
mkdir -p $TEMP_FOLDER >/dev/null 2>&1

# During the development cycle we will need to apply cp4a_catalogsource.yaml
# catalog_source.yaml is the final deliver yaml.

OLM_CATALOG=${PARENT_DIR}/descriptors/op-olm/catalogsource.yaml
OLM_OPT_GROUP=${PARENT_DIR}/descriptors/op-olm/operator_group.yaml
OLM_SUBSCRIPTION=${PARENT_DIR}/descriptors/op-olm/subscription.yaml
# the source is different for stage of development and final public
online_source="ibm-fncm-operator-catalog"

OLM_OPT_GROUP_TMP=${TEMP_FOLDER}/.operator_group.yaml
OLM_SUBSCRIPTION_TMP=${TEMP_FOLDER}/.subscription.yaml

echo '' >$LOG_FILE

function validate_cli() {
  clear
  echo -e "\x1b[1mThis script prepares the environment for the deployment of some FileNet Content Management capabilities \x1b[0m"
  echo
  if [[ $PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" ]]; then
    which oc &>/dev/null
    [[ $? -ne 0 ]] &&
      echo "Unable to locate an OpenShift CLI. You must install it to run this script." &&
      exit 1
  fi
  if [[ $PLATFORM_SELECTED == "other" ]]; then
    which kubectl &>/dev/null
    [[ $? -ne 0 ]] &&
      echo "Unable to locate Kubernetes CLI, please install it first." &&
      exit 1
  fi
}

function select_all_namespace() {
  printf "\n"
  while true; do
    if [ -z "$FNCM_AUTO_ALL_NAMESPACES" ]; then
      printf "\x1b[1mDo you want IBM FileNet Content Manager Operator support 'All Namespaces'? (Yes/No, default: No) \x1b[0m"

      read -rp "" ans
      case "$ans" in
      "y" | "Y" | "yes" | "Yes" | "YES")
        ALL_NAMESPACE="Yes"
        break
        ;;
      "n" | "N" | "no" | "No" | "NO" | "")
        ALL_NAMESPACE="No"
        break
        ;;
      *)
        ALL_NAMESPACE=""
        echo -e "Answer must be \"Yes\" or \"No\"\n"
        ;;
      esac
    else
      printf "\x1b[1mDo you want IBM FileNet Content Manager Operator support 'All Namespaces'? (Yes/No, default: No)  \x1b[0m$FNCM_AUTO_ALL_NAMESPACES\n"
      case "$FNCM_AUTO_ALL_NAMESPACES" in
      "y" | "Y" | "yes" | "Yes" | "YES")
        ALL_NAMESPACE="Yes"
        break
        ;;
      "n" | "N" | "no" | "No" | "NO")
        ALL_NAMESPACE="No"
        break
        ;;
      *)
        ALL_NAMESPACE=""
        echo -e "Answer must be \"Yes\" or \"No\"\n"
        exit 1
        ;;
      esac
    fi
  done
}

function collect_input() {
  project_name=""
  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
    select_all_namespace
    user_name=""
    select_user
  fi

  while [[ $project_name == "" ]]; do
    if [ -z "$FNCM_NAMESPACE" ]; then
      echo
      read -p "Enter the name for a new project or an existing project (namespace): " project_name
    else
      if [[ "$FNCM_NAMESPACE" == openshift* ]]; then
        echo -e "\x1b[1;31mEnter a valid project name, project name should not be 'openshift' or start with 'openshift' \x1b[0m"
        exit 1
      elif [[ "$FNCM_NAMESPACE" == kube* ]]; then
        echo -e "\x1b[1;31mEnter a valid project name, project name should not be 'kube' or start with 'kube' \x1b[0m"
        exit 1
      fi
      project_name=$FNCM_NAMESPACE
    fi
    if [ -z "$project_name" ]; then
      echo -e "\x1b[1;31mEnter a valid project name, project name can not be blank\x1b[0m"
    elif [[ "$project_name" == openshift* ]]; then
      echo -e "\x1b[1;31mEnter a valid project name, project name should not be 'openshift' or start with 'openshift' \x1b[0m"
      project_name=""
    elif [[ "$project_name" == kube* ]]; then
      echo -e "\x1b[1;31mEnter a valid project name, project name should not be 'kube' or start with 'kube' \x1b[0m"
      project_name=""
    else
      create_project
    fi
  done
}

function create_project() {

  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
    isProjExists=$(${CLI_CMD} get project $project_name --ignore-not-found | wc -l) >/dev/null 2>&1

    if [ $isProjExists -ne 2 ]; then
      ${CLI_CMD} new-project ${project_name} >>${LOG_FILE}
      returnValue=$?
      if [ "$returnValue" == 1 ]; then
        if [ -z "$FNCM_NAMESPACE" ]; then
          echo -e "\x1b[1;31mInvalid project name, please enter a valid name...\x1b[0m"
          project_name=""
        else
          echo -e "\x1b[1;31mInvalid project name \"$FNCM_NAMESPACE\", please set a valid name...\x1b[0m"
          exit 1
        fi
      else
        echo -e "\x1b[1mUsing project ${project_name}...\x1b[0m"
      fi
    else
      echo -e "\x1b[1mProject \"${project_name}\" already exists! Continue...\x1b[0m"
    fi
  elif [[ "$PLATFORM_SELECTED" == "other" ]]; then
    isProjExists=$(kubectl get namespace $project_name --ignore-not-found | wc -l) >/dev/null 2>&1

    if [ $isProjExists -ne 2 ]; then
      kubectl create namespace ${project_name} >>${LOG_FILE}
      returnValue=$?
      if [ "$returnValue" == 1 ]; then
        if [ -z "$FNCM_NAMESPACE" ]; then
          echo -e "\x1b[1;31mInvalid namespace name, please enter a valid name...\x1b[0m"
          project_name=""
        else
          echo -e "\x1b[1;31mInvalid namespace name \"$FNCM_NAMESPACE\", please set a valid name...\x1b[0m"
          exit 1
        fi
      else
        echo -e "\x1b[1mUsing namespace ${project_name}...\x1b[0m"
      fi
    else
      echo -e "\x1b[1mName space \"${project_name}\" already exists! Continue...\x1b[0m"
    fi
  fi
  PROJ_NAME=${project_name}
}

function check_user_exist() {
  ${CLI_CMD} get user | grep "${user_name}" >/dev/null 2>&1
  returnValue=$?
  if [ "$returnValue" == 1 ]; then
    echo -e "\x1b[1mUser \"${user_name}\" NOT exists! Please enter an existing username in your cluster...\x1b[0m"
    user_name=""
  else
    echo -e "\x1b[1mUser \"${user_name}\" exists! Continue...\x1b[0m"
  fi
}

function bind_scc() {
  echo
  echo -ne Binding the 'privileged' role to the 'ibm-fncm-operator' service account...
  dba_scc=$(${CLI_CMD} get scc privileged | awk '{print $1}')
  if [ -n "$dba_scc" ]; then
    ${CLI_CMD} adm policy add-scc-to-user privileged -z ibm-fncm-operator >>${LOG_FILE}
  else
    echo "The 'privileged' security context constraint (SCC) does not exist in the cluster. Make sure that you update your environment to include this SCC."
    exit 1
  fi
  echo "Done"
}

function prepare_install() {
  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
    ${CLI_CMD} project ${project_name} >>${LOG_FILE}
  fi
  sed -e "s/<NAMESPACE>/${project_name}/g" ${CLUSTER_ROLE_BINDING_FILE} >${CLUSTER_ROLE_BINDING_FILE_TEMP}
  echo
  echo -ne "Creating the custom resource definition (CRD) and a service account that has the permissions to manage the resources..."
  ${CLI_CMD} apply -f ${CRD_FILE} -n ${project_name} --validate=false >/dev/null 2>&1
  echo " Done!"
  if [[ $PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" ]]; then
    ${CLI_CMD} apply -f ${CLUSTER_ROLE_FILE} --validate=false >>${LOG_FILE}
    ${CLI_CMD} apply -f ${CLUSTER_ROLE_BINDING_FILE_TEMP} --validate=false >>${LOG_FILE}
  fi
  ${CLI_CMD} apply -f ${SA_FILE} -n ${project_name} --validate=false >>${LOG_FILE}
  ${CLI_CMD} apply -f ${ROLE_FILE} -n ${project_name} --validate=false >>${LOG_FILE}

  echo -n "Creating ibm-fncm-operator role ..."
  while true; do
    result=$(${CLI_CMD} get role -n $project_name | grep ibm-fncm-operator)
    if [[ "$result" == "" ]]; then
      sleep 5
      echo -n "..."
    else
      echo " Done!"
      break
    fi
  done
  echo -n "Creating ibm-fncm-operator role binding ..."
  ${CLI_CMD} apply -f ${ROLE_BINDING_FILE} -n ${project_name} --validate=false >>${LOG_FILE}
  echo "Done!"

  # Add non-administrator user to role if chosen from prompt
  if [[ "$PLATFORM_SELECTED" == "OCP" && -n "$user_name" || "$PLATFORM_SELECTED" == "ROKS" && -n "$user_name" ]]; then
    echo
    echo -ne Adding the user ${user_name} to the ibm-fncm-operator role...
    ${CLI_CMD} project ${project_name} >>${LOG_FILE}
    ${CLI_CMD} adm policy add-role-to-user edit ${user_name} >>${LOG_FILE}
    ${CLI_CMD} adm policy add-role-to-user registry-editor ${user_name} >>${LOG_FILE}
    ${CLI_CMD} adm policy add-role-to-user ibm-fncm-operator ${user_name} >/dev/null 2>&1
    ${CLI_CMD} adm policy add-role-to-user ibm-fncm-operator ${user_name} >>${LOG_FILE}
    echo "Done!"
  fi
  echo
  echo -ne Label the default namespace to allow network policies to open traffic to the ingress controller using a namespaceSelector...
  ${CLI_CMD} label --overwrite namespace default 'network.openshift.io/policy-group=ingress'
  echo "Done!"
}

function apply_operator_cncf() {
  ${COPY_CMD} -rf ${OPERATOR_FILE} ${OPERATOR_FILE_TMP}

  printf "\n"
  echo -e "\x1b[1mInstalling the FileNet Content Management operator...\x1b[0m"
  # set db2_license
  ${SED_COMMAND} '/fncm_license/{n;s/value:.*/value: accept/;}' ${OPERATOR_FILE_TMP}
  # Set operator image pull secret
  ${SED_COMMAND} "s/ibm-entitlement-key/$DOCKER_RES_SECRET_NAME/g" ${OPERATOR_FILE_TMP}

  if [ "$use_entitlement" = "yes" ]; then
    if [[ "$RUNTIME_MODE" == "dev" || $RUNTIME_MODE == "baw-dev" ]]; then
      ${SED_COMMAND} "s/$REGISTRY_IN_FILE\/cpopen/$DOCKER_REG_SERVER\/cp/g" ${OPERATOR_FILE_TMP}
    fi
  else
    ${SED_COMMAND} "s/$REGISTRY_IN_FILE/$CONVERT_LOCAL_REGISTRY_SERVER/g" ${OPERATOR_FILE_TMP}
  fi
  INSTALL_OPERATOR_CMD="${CLI_CMD} apply -f ${OPERATOR_FILE_TMP} -n $project_name"
  sleep 5
  if $INSTALL_OPERATOR_CMD; then
    echo -e "\x1b[1mDone\x1b[0m"
  else
    echo -e "\x1b[1;31mFailed\x1b[0m"
  fi

  # ${COPY_CMD} -rf ${OPERATOR_FILE_TMP} ${OPERATOR_FILE_BAK}
  printf "\n"
  # Check deployment rollout status every 5 seconds (max 10 minutes) until complete.
  echo -e "\x1b[1mWaiting for the FileNet Content Management operator to be ready. This might take a few minutes... \x1b[0m"
  ATTEMPTS=0
  ROLLOUT_STATUS_CMD="${CLI_CMD} rollout status deployment/ibm-fncm-operator -n $project_name"
  until $ROLLOUT_STATUS_CMD || [ $ATTEMPTS -eq 120 ]; do
    $ROLLOUT_STATUS_CMD
    ATTEMPTS=$((ATTEMPTS + 1))
    sleep 5
  done
  if $ROLLOUT_STATUS_CMD; then
    echo -e "\x1b[1mDone\x1b[0m"
  else
    echo -e "\x1b[1;31mFailed\x1b[0m"
  fi
  printf "\n"
}

function check_existing_sc() {
  # Check existing storage class
  sc_result=$(${CLI_CMD} get sc 2>&1)

  sc_substring="No resources found"
  if [[ $sc_result == *"$sc_substring"* ]]; then
    clear
    echo -e "\x1b[1;31mAt least one dynamic storage class must be available in order to proceed.\n\x1b[0m"
    echo -e "\x1b[1;31mRefer to Knowledge Center documentation for details.  The script will now exit!.\n\x1b[0m"
    exit 1
  fi
}

function validate_docker_podman_cli() {
  if [[ $PLATFORM_VERSION == "3.11" || "$machine" == "Mac" || $PLATFORM_SELECTED == "other" ]]; then
    which docker &>/dev/null
    [[ $? -ne 0 ]] &&
      echo -e "\x1b[1;31mUnable to locate docker, please install it first.\x1b[0m" &&
      exit 1
  elif [[ $PLATFORM_VERSION == "4.4OrLater" ]]; then
    which podman &>/dev/null
    [[ $? -ne 0 ]] &&
      echo -e "\x1b[1;31mUnable to locate podman, please install it first.\x1b[0m" &&
      exit 1
  fi
}

function get_entitlement_registry() {

  # For Entitlement Registry key
  entitlement_key=""
  printf "\n"
  printf "\n"
  printf "\x1b[1;31mFollow the instructions on how to get your Entitlement Key: \n\x1b[0m"
  printf "\x1b[1;31mhttps://www.ibm.com/docs/en/filenet-p8-platform/5.5.x?topic=images-getting-access-container\n\x1b[0m"
  printf "\n"
  while true; do
    if [[ ! -z "$FNCM_ENTITLEMENT_KEY" && ! -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]]; then
      echo -e "\x1b[1;31mPlease set either one of environment variables [FNCM_ENTITLEMENT_KEY] or [FNCM_LOCAL_REGISTRY]\x1b[0m"
      echo -e "Exiting..."
      exit 1
    fi

    if [[ -z "$FNCM_ENTITLEMENT_KEY" && ! -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]]; then
      printf "\x1b[1mDo you have an IBM Entitlement Registry key (Yes/No, default: No):\x1b[0m No"
      ans="No"
    fi
    if [[ -z "$FNCM_LOCAL_PUBLIC_REGISTRY" && ! -z "$FNCM_ENTITLEMENT_KEY" ]]; then
      printf "\x1b[1mDo you have an IBM Entitlement Registry key (Yes/No, default: No):\x1b[0m Yes"
      ans="Yes"
    fi

    if [[ -z "$FNCM_ENTITLEMENT_KEY" && -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]]; then
      printf "\x1b[1mDo you have an IBM Entitlement Registry key (Yes/No, default: No): \x1b[0m"
      read -rp "" ans
    fi

    case "$ans" in
    "y" | "Y" | "yes" | "Yes" | "YES")
      use_entitlement="yes"
      printf "\n"
      printf "\x1b[1mEnter your Entitlement Registry key: \x1b[0m"
      # During dev, OLM uses stage image repo
      if [[ "$RUNTIME_MODE" == "dev" || $RUNTIME_MODE == "baw-dev" ]]; then
        DOCKER_REG_SERVER="cp.stg.icr.io"
      else
        DOCKER_REG_SERVER="cp.icr.io"
      fi
      # During dev, OLM uses stage image repo
      while [[ $entitlement_key == '' ]]; do
        if [ -z "$FNCM_ENTITLEMENT_KEY" ]; then
          read -rsp "" entitlement_key
        else
          entitlement_key=$FNCM_ENTITLEMENT_KEY
        fi
        if [ -z "$entitlement_key" ]; then
          printf "\n"
          echo -e "\x1b[1;31mEnter a valid Entitlement Registry key\x1b[0m"
        else
          if [[ $entitlement_key == iamapikey:* ]]; then
            DOCKER_REG_USER="iamapikey"
            DOCKER_REG_KEY="${entitlement_key#*:}"
          else
            DOCKER_REG_USER="cp"
            DOCKER_REG_KEY=$entitlement_key

          fi
          entitlement_verify_passed=""
          while [[ $entitlement_verify_passed == '' ]]; do
            printf "\n"
            printf "\x1b[1mVerifying the Entitlement Registry key...\n\x1b[0m"

            which podman &>/dev/null
            if [[ $? -eq 0 ]]; then
              cli_command="podman"
            else
              cli_command="docker"
            fi

            if $cli_command login -u "$DOCKER_REG_USER" -p "$DOCKER_REG_KEY" "$DOCKER_REG_SERVER"; then
              printf 'Entitlement Registry key is valid.\n'
              entitlement_verify_passed="passed"
            else
              printf '\x1b[1;31mThe Entitlement Registry key failed.\n\x1b[0m'
              printf '\x1b[1mEnter a valid Entitlement Registry key.\n\x1b[0m'
              entitlement_key=''
              entitlement_verify_passed="failed"
            fi
          done
        fi
      done
      break
      ;;
    "n" | "N" | "no" | "No" | "NO" | "")
      use_entitlement="no"
      DOCKER_REG_KEY="None"
      break
      ;;
    *)
      echo -e "Answer must be \"Yes\" or \"No\"\n"
      ;;
    esac
  done
}

function create_secret_entitlement_registry() {
  # Create docker-registry secret for Entitlement Registry Key in target project
  printf "\x1b[1mCreating docker-registry secret for Entitlement Registry key in project $project_name...\n\x1b[0m"

  ${CLI_CMD} delete secret "$DOCKER_RES_SECRET_NAME" -n "${project_name}" >/dev/null 2>&1
  CREATE_SECRET_CMD="${CLI_CMD} create secret docker-registry $DOCKER_RES_SECRET_NAME --docker-server=$DOCKER_REG_SERVER --docker-username=$DOCKER_REG_USER --docker-password=$DOCKER_REG_KEY --docker-email=ecmtest@ibm.com -n $project_name"
  if $CREATE_SECRET_CMD; then
    echo -e "\x1b[1mDone\x1b[0m"
  else
    echo -e "\x1b[1mFailed\x1b[0m"
  fi
}

function display_storage_classes() {
  echo
  echo "Storage classes are needed by the CR file when deploying FNCM Standalone.   You will be asked for three (3) storage classes to meet the "slow", "medium", and "fast" storage for the configuration of FNCM components.  If you don't have three (3) storage classes, you can use the same one for "slow", "medium", or fast.  Note that you can get the existing storage class(es) in the environment by running the following command: oc get storageclass. Take note of the storage classes that you want to use for deployment. "
  ${CLI_CMD} get storageclass
}

function display_node_name() {
  echo
  if [[ $PLATFORM_VERSION == "3.11" ]]; then
    echo "Below is the host name of the Infrastructure Node for the environment, which is required as an input during the execution of the deployment script for the creation of routes in OCP.  You can also get the host name by running the following command: ${CLI_CMD} get nodes --selector node-role.kubernetes.io/infra=true -o custom-columns=":metadata.name". Take note of the host name. "
    ${CLI_CMD} get nodes --selector node-role.kubernetes.io/infra=true -o custom-columns=":metadata.name"
  elif [[ $PLATFORM_VERSION == "4.4OrLater" ]]; then
    echo "Below is the route host name for the environment, which is required as an input during the execution of the deployment script for the creation of routes in OCP. You can also get the host name by running the following command: oc get IngressController default -n openshift-ingress-operator -o yaml|grep \" domain\". Take note of the host name. "
    ${CLI_CMD} get IngressController default -n openshift-ingress-operator -o yaml | grep " domain" | head -1 | cut -d ' ' -f 4
  fi
}

function clean_up() {
  rm -rf ${TEMP_FOLDER} >/dev/null 2>&1
}

function select_platform() {
  if [ -z "$FNCM_PLATFORM" ]; then
    COLUMNS=12
    echo -e "\x1b[1mSelect the cloud platform to deploy: \x1b[0m"
    options=("RedHat OpenShift Kubernetes Service (ROKS) - Public Cloud" "Openshift Container Platform (OCP) - Private Cloud" "Other (Certified Kubernetes Cloud Platform / CNCF)")
    PS3='Enter a valid option [1 to 3]: '
    select opt in "${options[@]}"; do
      case $opt in
      "RedHat OpenShift Kubernetes Service (ROKS) - Public Cloud")
        PLATFORM_SELECTED="ROKS"
        break
        ;;
      "Openshift Container Platform (OCP) - Private Cloud")
        PLATFORM_SELECTED="OCP"
        break
        ;;
      "Other (Certified Kubernetes Cloud Platform / CNCF)")
        PLATFORM_SELECTED="other"
        break
        ;;
      *) echo "invalid option $REPLY" ;;
      esac
    done
  else
    PLATFORM_SELECTED=$FNCM_PLATFORM
    echo -e "\x1b[1mWhat type of cloud platform is selected?\x1b[0m $FNCM_PLATFORM"
  fi
  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
    SCRIPT_MODE="OLM"
    CLI_CMD=oc
  elif [[ "$PLATFORM_SELECTED" == "other" ]]; then
    CLI_CMD=kubectl
  fi
}

function select_deployment_type() {
  COLUMNS=12
  echo -e "\x1b[1mWhat type of deployment is being performed?\x1b[0m"
  if [[ $PLATFORM_SELECTED == "other" ]]; then
    options=("Enterprise")
    PS3='Enter a valid option [1 to 1]: '
    select opt in "${options[@]}"; do
      case $opt in
      "Enterprise")
        DEPLOYMENT_TYPE="enterprise"
        break
        ;;
      *) echo "invalid option $REPLY" ;;
      esac
    done
  else
    options=("Demo" "Enterprise")
    PS3='Enter a valid option [1 to 2]: '
    select opt in "${options[@]}"; do
      case $opt in
      "Demo")
        DEPLOYMENT_TYPE="demo"
        break
        ;;
      "Enterprise")
        DEPLOYMENT_TYPE="enterprise"
        break
        ;;
      *) echo "invalid option $REPLY" ;;
      esac
    done
  fi
}

function select_user() {
  echo
  # Silent install
  if [[ ! -z "${FNCM_ADD_CLUSTER_USER}" ]]; then
    case "$FNCM_ADD_CLUSTER_USER" in
    "y" | "Y" | "yes" | "Yes" | "YES")
      printf "\x1b[1mDo you want to add a non-administrator user to manage the namespace (Yes/No): \x1b[0m$FNCM_ADD_CLUSTER_USER\n"
      if [[ ! -z "${FNCM_CLUSTER_USER}" ]]; then
        ${CLI_CMD} get user ${FNCM_CLUSTER_USER} >/dev/null 2>&1
        returnValue=$?
        if [ "$returnValue" == 1 ]; then
          echo -e "\x1b[31mThe user \"${FNCM_CLUSTER_USER}\" was not found, please set a valid user.\x1b[0m"
          echo -e "\x1b[31mThe script will now exit...\x1b[0m"
          exit 1
        else
          user_name=$FNCM_CLUSTER_USER
          echo -e "\x1b[1mSelected the existing user: \x1b[0m${user_name}"
        fi
      else
        echo -e "\x1b[31mNo user input found for [FNCM_CLUSTER_USER], please set a valid user.\x1b[0m"
        echo -e "\x1b[31mHere are the existing users on this cluster:\x1b[0m"
        userlist=$(${CLI_CMD} get user | awk '{if(NR>1){if(NR==2){ arr=$1; }else{ arr=arr" "$1; }} } END{ print arr }')
        for user in $userlist; do
          echo $user
        done
        echo -e "\x1b[31mThe script will now exit...\x1b[0m"
        exit 1
      fi
      ;;
    "n" | "N" | "no" | "No" | "NO")
      printf "\x1b[1mDo you want to add a non-administrator user to manage the namespace (Yes/No): \x1b[0m$FNCM_ADD_CLUSTER_USER\n"
      FNCM_CLUSTER_USER=""
      user_name=""
      ;;
    *)
      printf "\x1b[1mDo you want to add a non-administrator user to manage the namespace (Yes/No): \x1b[0m$FNCM_ADD_CLUSTER_USER\n"
      echo -e "\x1b[31m\"Yes\" or \"No\" are valid values for the environment variable [FNCM_ADD_CLUSTER_USER].\x1b[0m"
      echo -e "\x1b[31mThe script will now exit...\x1b[0m"
      exit 1
      ;;
    esac
  # Interactive install
  else
    while true; do
      if [ -z "$FNCM_CLUSTER_USER" ]; then
        printf "\x1b[1mDo you want to add a non-administrator user to manage the namespace (Yes/No, default: No): \x1b[0m"
        read -rp "" selectuserans
        case "$selectuserans" in
        "n" | "N" | "no" | "No" | "NO" | "")
          user_name=""
          break
          ;;
        "y" | "Y" | "yes" | "Yes" | "YES")
          user_substring="No resources found"
          user_result=$(${CLI_CMD} get user 2>&1)
          if [[ ${user_result} == *"$user_substring"* ]]; then
            echo -e "\x1b[31mNo additional users found on the cluster. At least one is required to proceed.\n\x1b[0m"
            echo -e "\x1b[31mThis script will now exit...\n\x1b[0m"
            exit 1
          fi

          printf "\n"
          userlist=$(${CLI_CMD} get user | awk '{if(NR>1){if(NR==2){ arr=$1; }else{ arr=arr" "$1; }} } END{ print arr }')
          COLUMNS=12
          echo -e "\x1b[1mHere are the existing users on this cluster: \x1b[0m"
          options=($userlist)
          usernum=${#options[*]}
          PS3='Select an existing user in your cluster, valid options are [1 to '${usernum}']: '
          select opt in "${options[@]}"; do
            if [[ -n "$opt" && "${options[@]}" =~ $opt ]]; then
              user_name=$opt
              break
            else
              echo "Invalid input: $REPLY"
            fi
          done
          break
          ;;
        *)
          echo -e "Answer must be \"Yes\" or \"No\"\n"
          ;;
        esac
      fi
    done
  fi
}

function check_storage_class() {
  if [[ $PLATFORM_SELECTED == "ROKS" ]]; then
    create_storage_classes_roks
  fi
  display_storage_classes
}

function create_storage_classes_roks() {
  echo
  echo -ne "\x1b[1mCreate storage classes for deployment: \x1b[0m"
  ${CLI_CMD} apply -f ${BRONZE_STORAGE_CLASS} --validate=false >/dev/null 2>&1
  ${CLI_CMD} apply -f ${SILVER_STORAGE_CLASS} --validate=false >/dev/null 2>&1
  ${CLI_CMD} apply -f ${GOLD_STORAGE_CLASS} --validate=false >/dev/null 2>&1
  echo -e "\x1b[1mDone \x1b[0m"

}

function display_storage_classes_roks() {
  sc_bronze_name=fncm-file-retain-bronze-gid
  sc_silver_name=fncm-file-retain-silver-gid
  sc_gold_name=fncm-file-retain-gold-gid
  echo -e "\x1b[1;31m    $sc_bronze_name \x1b[0m"
  echo -e "\x1b[1;31m    $sc_silver_name \x1b[0m"
  echo -e "\x1b[1;31m    $sc_gold_name \x1b[0m"
}

function check_platform_version() {
  currentver=$(kubectl get nodes | awk 'NR==2{print $5}')
  requiredver="v1.17.1"
  if [ "$(printf '%s\n' "$requiredver" "$currentver" | sort -V | head -n1)" = "$requiredver" ]; then
    PLATFORM_VERSION="4.4OrLater"
  else
    PLATFORM_VERSION="4.4OrLater"
    echo -e "\x1b[1;31mIMPORTANT: Only support OCp4.4 or Later, exit...\n\x1b[0m"
    read -rsn1 -p"Press any key to continue"
    echo
    exit 1
  fi
}

function prepare_common_service() {

  echo
  echo -e "\x1b[1mThe script is preparing the custom resources (CR) files for OCP Common Services.  You are required to update (fill out) the necessary values in the CRs and deploy Common Services prior to the deployment. \x1b[0m"
  echo -e "The prepared CRs for IBM common Services are located here: "${COMMON_SERVICES_CRD_DIRECTORY}
  echo -e "After making changes to the CRs, execute the 'deploy_CS.sh' script to install Common Services."
  echo -e "Done"
}

function show_summary() {

  printf "\n"
  echo -e "\x1b[1m*******************************************************\x1b[0m"
  echo -e "\x1b[1m                    Summary of input                   \x1b[0m"
  echo -e "\x1b[1m*******************************************************\x1b[0m"
  if [[ ${PLATFORM_VERSION} == "4.4OrLater" ]]; then
    echo -e "\x1b[1;31m1. Cloud platform to deploy: ${PLATFORM_SELECTED} 4.X\x1b[0m"
  else
    echo -e "\x1b[1;31m1. Cloud platform to deploy: ${PLATFORM_SELECTED} ${PLATFORM_VERSION}\x1b[0m"
  fi
  echo -e "\x1b[1;31m2. Project to deploy: ${project_name}\x1b[0m"
  if [[ $PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" ]]; then
    echo -e "\x1b[1;31m3. User selected: ${user_name}\x1b[0m"
  fi
  if [[ $PLATFORM_SELECTED == "ROKS" ]]; then
    echo -e "\x1b[1;31m5. Storage Class created: \x1b[0m"
    display_storage_classes_roks
  fi
  echo -e "\x1b[1m*******************************************************\x1b[0m"
}

function get_local_registry_server() {
  # For internal/external Registry Server
  printf "\n"
  if [[ "${REGISTRY_TYPE}" == "internal" ]]; then
    if [[ "${PLATFORM_VERSION}" == "4.4OrLater" ]]; then
      #This is required for docker/podman login validation.
      if [ ! -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]; then
        printf "\x1b[1mEnter the public image registry or route: \x1b[0m$FNCM_LOCAL_PUBLIC_REGISTRY"
        #printf "\x1b[1mThis is required for docker/podman login validation: \x1b[0m"
        local_public_registry_server=$FNCM_LOCAL_PUBLIC_REGISTRY
      else
        printf "\x1b[1mEnter the public image registry or route (e.g., default-route-openshift-image-registry.apps.<hostname>). \n\x1b[0m"
        printf "\x1b[1mThis is required for docker/podman login validation: \x1b[0m"
        local_public_registry_server=""
        while [[ $local_public_registry_server == "" ]]; do
          read -rp "" local_public_registry_server
          if [ -z "$local_public_registry_server" ]; then
            echo -e "\x1b[1;31mEnter a valid service name or the URL for the docker registry.\x1b[0m"
          fi
        done
      fi

      if [[ -z "$FNCM_LOCAL_PRIVATE_REGISTRY" ]]; then
        local_registry_server=""
        if [[ "${REGISTRY_TYPE}" == "internal" && "${PLATFORM_VERSION}" == "4.4OrLater" ]]; then
          printf "\x1b[1mEnter the local image registry (e.g., image-registry.openshift-image-registry.svc:5000/<project>)\n\x1b[0m"
          printf "\x1b[1mThis is required to pull container images and Kubernetes secret creation: \x1b[0m"

          while [[ $local_registry_server == "" ]]; do
            read -rp "" local_registry_server
            if [ -z "$local_registry_server" ]; then
              echo -e "\x1b[1;31mEnter a valid service name or the URL for the docker registry.\x1b[0m"
            fi
          done
        elif [[ "${PLATFORM_VERSION}" != "4.4OrLater" ]]; then
          printf "\n"
          printf "\x1b[1mEnter the local image registry: \x1b[0m$FNCM_LOCAL_PRIVATE_REGISTRY"
          local_registry_server=$FNCM_LOCAL_PRIVATE_REGISTRY
        fi
      fi
    fi

  else
    if [ ! -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]; then
      printf "\x1b[1mEnter the docker image registry or route: \x1b[0m$FNCM_LOCAL_PUBLIC_REGISTRY"
      #printf "\x1b[1mThis is required for docker/podman login validation: \x1b[0m"
      local_public_registry_server=$FNCM_LOCAL_PUBLIC_REGISTRY
    else
      printf "\x1b[1mEnter the URL to the docker registry, for example: abc.xyz.com: \n\x1b[0m"
      printf "\x1b[1mThis is required for docker/podman login validation: \x1b[0m"
      local_public_registry_server=""
      while [[ $local_public_registry_server == "" ]]; do
        read -rp "" local_public_registry_server
        if [ -z "$local_public_registry_server" ]; then
          echo -e "\x1b[1;31mEnter a valid service name or the URL for the docker registry.\x1b[0m"
        fi
      done
    fi
    local_registry_server=$local_public_registry_server
  fi

  LOCAL_REGISTRY_SERVER=${local_registry_server}
  OIFS=$IFS
  IFS='/' read -r -a docker_reg_url_array <<<"$local_registry_server"
  delim=""
  joined=""
  for item in "${docker_reg_url_array[@]}"; do
    joined="$joined$delim$item"
    delim="\/"
  done
  IFS=$OIFS
  CONVERT_LOCAL_REGISTRY_SERVER=${joined}

}

function get_local_registry_user() {
  # For Local Registry User
  printf "\n"
  if [ -z "$FNCM_LOCAL_REGISTRY_USER" ]; then
    printf "\x1b[1mEnter the user name for your docker registry: \x1b[0m"
    local_registry_user=""
    while [[ $local_registry_user == "" ]]; do
      read -rp "" local_registry_user
      if [ -z "$local_registry_user" ]; then
        echo -e "\x1b[1;31mEnter a valid user name.\x1b[0m"
      fi
    done
  else
    echo -e "\x1b[1mEnter the user name for your docker registry: \x1b[0m$FNCM_LOCAL_REGISTRY_USER"
    local_registry_user=$FNCM_LOCAL_REGISTRY_USER
  fi
  LOCAL_REGISTRY_USER=${local_registry_user}
}

function get_local_registry_password() {
  printf "\n"
  if [ -z "$FNCM_LOCAL_REGISTRY_PASSWORD" ]; then
    printf "\x1b[1mEnter the password for your docker registry: \x1b[0m"
    local_registry_password=""
    while [[ $local_registry_password == "" ]]; do
      read -rsp "" local_registry_password
      if [ -z "$local_registry_password" ]; then
        echo -e "\x1b[1;31mEnter a valid password\x1b[0m"
      fi
    done
  else
    printf "\x1b[1mEnter the password for your docker registry: \x1b[0m\n"
    local_registry_password=$FNCM_LOCAL_REGISTRY_PASSWORD
  fi
  LOCAL_REGISTRY_PWD=${local_registry_password}
  printf "\n"
}

function verify_local_registry_password() {
  # require to preload image for CP4A image
  printf "\n"
  while true; do
    if [ -z "$FNCM_PUSH_IMAGE_LOCAL_REGISTRY" ]; then
      printf "\x1b[1mHave you pushed the operator image to docker registry using 'loadimages.sh' (FNCM Operator image) (Yes/No)? \x1b[0m"
      read -rp "" ans
    else
      case "$FNCM_PUSH_IMAGE_LOCAL_REGISTRY" in
      "y" | "Y" | "yes" | "Yes" | "YES" | "True" | "TRUE" | "true")
        echo -e "\x1b[1mHave you pushed the operator image to the docker registry using 'loadimages.sh' (FNCM Operator image) (Yes/No)? \x1b[0m$FNCM_PUSH_IMAGE_LOCAL_REGISTRY"
        ans="Yes"
        ;;
      "n" | "N" | "no" | "No" | "NO" | "false" | "False" | "FALSE")
        echo -e "\x1b[1mHave you pushed the operator image to the docker registry using 'loadimages.sh' (FNCM Operator image) (Yes/No)? \x1b[0m$FNCM_PUSH_IMAGE_LOCAL_REGISTRY"
        echo -e "\x1b[1;31mPlease push the image to a docker registry to proceed.\n\x1b[0m"
        ans="No"
        exit 1
        ;;
      *)
        echo -e "Answer must be \"Yes\" or \"No\"\n"
        ;;
      esac
    fi
    case "$ans" in
    "y" | "Y" | "yes" | "Yes" | "YES")
      PRE_LOADED_IMAGE="Yes"
      break
      ;;
    "n" | "N" | "no" | "No" | "NO")
      echo -e "\x1b[1;31mPlease push the image to a docker registry to proceed.\n\x1b[0m"
      exit 1
      ;;
    *)
      echo -e "Answer must be \"Yes\" or \"No\"\n"
      ;;
    esac
  done

  if [ -z "$FNCM_REGISTRY_TYPE" ]; then
    # Select which type of image registry to use.
    if [[ "${PLATFORM_SELECTED}" == "OCP" ]]; then
      printf "\n"
      echo -e "\x1b[1mSelect the type of image registry to use: \x1b[0m"
      COLUMNS=12
      options=("Other ( External image registry: abc.xyz.com )" "Openshift Container Platform (OCP) - Internal image registry")

      PS3='Enter a valid option [1 to 2]: '
      select opt in "${options[@]}"; do
        case $opt in
        "Openshift Container Platform (OCP) - Internal image registry")
          REGISTRY_TYPE="internal"
          break
          ;;
        "Other ( External image registry: abc.xyz.com )")
          REGISTRY_TYPE="external"
          break
          ;;
        *) echo "invalid option $REPLY" ;;
        esac
      done
    else
      REGISTRY_TYPE="external"
    fi
  else
    local reg_type_array=("internal" "external")
    if [[ ! " ${reg_type_array[@]} " =~ " ${FNCM_REGISTRY_TYPE} " ]]; then
      echo -e "\x1b[1;31mOnly \"internal\" or \"external\" is valid value for environment variable [FNCM_REGISTRY_TYPE].\n\x1b[0m"
      exit 1
    fi
    echo -e "\x1b[1mSelect the type of image registry to use: \x1b[0m$FNCM_REGISTRY_TYPE"
    REGISTRY_TYPE=$FNCM_REGISTRY_TYPE
  fi

  while [[ $verify_passed == "" && $PRE_LOADED_IMAGE == "Yes" ]]; do
    get_local_registry_server
    get_local_registry_user
    get_local_registry_password

    if [[ $LOCAL_REGISTRY_SERVER == docker-registry* || $LOCAL_REGISTRY_SERVER == image-registry* || $LOCAL_REGISTRY_SERVER == default-route-openshift-image-registry* ]]; then
      if [[ $PLATFORM_VERSION == "3.11" ]]; then
        if docker login -u "$LOCAL_REGISTRY_USER" -p $(${CLI_CMD} whoami -t) "$LOCAL_REGISTRY_SERVER"; then
          printf 'Verifying Local Registry passed...\n'
          verify_passed="passed"
        else
          printf '\x1b[1;31mLogin failed...\n\x1b[0m'
          verify_passed=""
          local_registry_user=""
          local_registry_server=""
          echo -e "\x1b[1;31mCheck the local docker registry information and try again.\x1b[0m"
        fi
      elif [[ "$machine" == "Mac" ]]; then
        if docker login "$local_public_registry_server" -u "$LOCAL_REGISTRY_USER" -p $(${CLI_CMD} whoami -t); then
          printf 'Verifying Local Registry passed...\n'
          verify_passed="passed"
        else
          printf '\x1b[1;31mLogin failed...\n\x1b[0m'
          verify_passed=""
          local_registry_user=""
          local_registry_server=""
          local_public_registry_server=""
          echo -e "\x1b[1;31mCheck the local docker registry information and try again.\x1b[0m"
        fi
      elif [[ $PLATFORM_VERSION == "4.4OrLater" ]]; then
        which podman &>/dev/null
        if [[ $? -eq 0 ]]; then
          if podman login "$local_public_registry_server" -u "$LOCAL_REGISTRY_USER" -p $(${CLI_CMD} whoami -t) --tls-verify=false; then
            printf 'Verifying Local Registry passed...\n'
            verify_passed="passed"
          else
            printf '\x1b[1;31mLogin failed...\n\x1b[0m'
            verify_passed=""
            local_registry_user=""
            local_registry_server=""
            local_public_registry_server=""
            echo -e "\x1b[1;31mCheck the local docker registry information and try again.\x1b[0m"
          fi
        else
          if docker login "$local_public_registry_server" -u "$LOCAL_REGISTRY_USER" -p $(${CLI_CMD} whoami -t); then
            printf 'Verifying Local Registry passed...\n'
            verify_passed="passed"
          else
            printf '\x1b[1;31mLogin failed...\n\x1b[0m'
            verify_passed=""
            local_registry_user=""
            local_registry_server=""
            local_public_registry_server=""
            echo -e "\x1b[1;31mCheck the local docker registry information and try again.\x1b[0m"
            if [ -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]; then
              verify_passed=""
              local_registry_user=""
              local_registry_server=""
            else
              exit 1
            fi
          fi
        fi
      fi
    else
      which podman &>/dev/null
      if [[ $? -eq 0 ]]; then
        if podman login -u "$LOCAL_REGISTRY_USER" -p "$LOCAL_REGISTRY_PWD" "$LOCAL_REGISTRY_SERVER" --tls-verify=false; then
          printf 'Verifying the information for the local docker registry...\n'
          verify_passed="passed"
        else
          printf '\x1b[1;31mLogin failed...\n\x1b[0m'
          echo -e "\x1b[1;31mCheck the local docker registry information and try again.\x1b[0m"
          if [ -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]; then
            verify_passed=""
            local_registry_user=""
            local_registry_server=""
          else
            exit 1
          fi
        fi
      else
        if docker login -u "$LOCAL_REGISTRY_USER" -p "$LOCAL_REGISTRY_PWD" "$LOCAL_REGISTRY_SERVER"; then
          printf 'Verifying the information for the local docker registry...\n'
          verify_passed="passed"
        else
          printf '\x1b[1;31mLogin failed...\n\x1b[0m'
          echo -e "\x1b[1;31mCheck the local docker registry information and try again.\x1b[0m"
          if [ -z "$FNCM_LOCAL_PUBLIC_REGISTRY" ]; then
            verify_passed=""
            local_registry_user=""
            local_registry_server=""
          else
            exit 1
          fi
        fi
      fi
    fi
  done

}

function create_secret_local_registry() {
  echo -e "\x1b[1mCreating the secret based on the local docker registry information...\x1b[0m"

  ${CLI_CMD} delete secret "$DOCKER_RES_SECRET_NAME" -n $project_name >/dev/null 2>&1
  CREATE_SECRET_CMD="${CLI_CMD} create secret docker-registry $DOCKER_RES_SECRET_NAME --docker-server=$LOCAL_REGISTRY_SERVER --docker-username=$LOCAL_REGISTRY_USER --docker-password=$LOCAL_REGISTRY_PWD --docker-email=ecmtest@ibm.com -n $project_name"
  if $CREATE_SECRET_CMD; then
    echo -e "\x1b[1mDone\x1b[0m"
  else
    echo -e "\x1b[1;31mFailed\x1b[0m"
  fi
}

function prompt_license() {
  echo -e "\x1b[1;31mYou need to read the International Program License Agreement before start\n\x1b[0m"
  echo -e "\x1b[1;31mIMPORTANT: Review the license information for the product bundle you are deploying. \n\x1b[0m"
  echo -e "\x1b[1;31mIBM FileNet Content Manager license information here: https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-CHZ6NL \n\x1b[0m"
  echo -e "\x1b[1;31mIBM Content Foundation license information here: https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-CHZ6V7 \n\x1b[0m"

  if [[ ! -z "${FNCM_LICENSE_ACCEPT}" ]]; then
    local accept_array=("accept" "ACCEPT" "Accept")
    if [[ ! " ${accept_array[@]} " =~ " ${FNCM_LICENSE_ACCEPT}" ]]; then
      echo -e "\x1b[1;31mOnly \"Accept\" is valid value for environment variable [FNCM_LICENSE_ACCEPT].\n\x1b[0m"
      exit 1
    else
      echo -e "\x1b[1mInternational Program License accepted through silent install\x1b[0m"
      echo
    fi
  else
    read -rsn1 -p"Press any key to continue"
    echo

    printf "\n"
    while true; do
      printf "\x1b[1mDo you accept the International Program License (Yes/No, default: No): \x1b[0m"
      read -rp "" ans
      case "$ans" in
      "y" | "Y" | "yes" | "Yes" | "YES")
        printf "\n"
        echo -e "Starting to Install the IBM FileNet Standalone Operator...\n"
        break
        ;;
      "n" | "N" | "no" | "No" | "NO" | "")
        echo -e "Exiting...\n"
        exit 0
        ;;
      *)
        echo -e "Answer must be \"Yes\" or \"No\"\n"
        ;;
      esac
    done
  fi
}

function verify_silence_install() {
  if [[ ! -z "${FNCM_PLATFORM}" ]]; then
    local platform_array=("OCP" "ROKS" "other")
    echo "==========================================================================="
    echo -e "\x1b[1mStarting silent installation for FileNet Standalone Operator\x1b[0m"
    echo "==========================================================================="
    if [[ ! " ${platform_array[@]} " =~ " ${FNCM_PLATFORM} " ]]; then
      echo -e "\x1b[1;31mOnly \"OCP\" or \"ROKS\" or \"other\" is valid value for environment variable [FNCM_PLATFORM].\n\x1b[0m"
      exit 1
    fi
  fi

}

function apply_operator_olm() {
  local maxRetry=20
  local temp_project_name=""

  if [[ $ALL_NAMESPACE == "Yes" ]]; then
    temp_project_name=$PROJ_NAME_ALL_NAMESPACE
  else
    temp_project_name=$project_name
  fi

  if ${CLI_CMD} get catalogsource -n openshift-marketplace | grep $online_source; then
    echo "Found existing ibm operator catalog source, updating it"
    ${CLI_CMD} apply -f $OLM_CATALOG
    if [ $? -eq 0 ]; then
      echo "IBM FileNet Content Manager Operator Catalog source updated!"
    else
      echo "IBM FileNet Content Manager Operator catalog source update failed"
      exit 1
    fi
  else
    ${CLI_CMD} apply -f $OLM_CATALOG
    if [ $? -eq 0 ]; then
      echo "IBM FileNet Content Manager Operator Catalog source created!"
    else
      echo "IBM FileNet Content Manager Operator catalog source creation failed"
      exit 1
    fi
  fi

  for ((retry = 0; retry <= ${maxRetry}; retry++)); do
    echo "Waiting for IBM FileNet Content Manager Operator Catalog pod initialization"

    isReady=$(${CLI_CMD} get pod -n openshift-marketplace --no-headers | grep $online_source | grep "Running")
    if [[ -z $isReady ]]; then
      if [[ $retry -eq ${maxRetry} ]]; then
        echo "Timeout Waiting for IBM FileNet Content Manager Operator Catalog pod to start"
        echo -e "\x1b[1mPlease check the status of Pod by issue cmd: \x1b[0m"
        echo "oc describe pod $(oc get pod -n openshift-marketplace | grep $online_source | awk '{print $1}') -n openshift-marketplace"
        exit 1
      else
        sleep 30
        continue
      fi
    else
      echo "IBM FileNet Content Manager Operator Catalog is running $isReady"
      break
    fi
  done

  if [[ $(${CLI_CMD} get og -n "${temp_project_name}" -o=go-template --template='{{len .items}}') -gt 0 ]]; then
    echo "Found operator group"
    ${CLI_CMD} get og -n "${temp_project_name}"
  else
    sed "s/REPLACE_NAMESPACE/$temp_project_name/g" ${OLM_OPT_GROUP} >${OLM_OPT_GROUP_TMP}
    ${CLI_CMD} apply -f ${OLM_OPT_GROUP_TMP}
    if [ $? -eq 0 ]; then
      echo "IBM FileNet Content Manager Operator Group Created!"
    else
      echo "IBM FileNet Content Manager Operator Group creation failed"
    fi
  fi

  sed "s/REPLACE_NAMESPACE/$temp_project_name/g" ${OLM_SUBSCRIPTION} >${OLM_SUBSCRIPTION_TMP}

  ${CLI_CMD} apply -f ${OLM_SUBSCRIPTION_TMP}

  if [ $? -eq 0 ]; then
    echo "IBM FileNet Content Manager Operator Subscription Created!"
  else
    echo "IBM FileNet Content Manager Operator Subscription creation failed"
    exit 1
  fi

  printf "\n"
  for ((retry = 0; retry <= ${maxRetry}; retry++)); do
    echo "Waiting for IBM FileNet Content Manager Operator pod initialization"

    isReady=$(${CLI_CMD} get pod -n "$temp_project_name" --no-headers | grep ibm-fncm-operator | grep "Running")
    if [[ -z $isReady ]]; then
      if [[ $retry -eq ${maxRetry} ]]; then
        echo "Timeout Waiting for IBM FileNet Content Manager Operator to start"
        echo -e "\x1b[1mPlease check the status of Pod by issue cmd:\x1b[0m"
        echo "oc describe pod $(oc get pod -n $temp_project_name | grep ibm-fncm-operator | awk '{print $1}') -n $temp_project_name"
        printf "\n"
        echo -e "\x1b[1mPlease check the status of ReplicaSet by issue cmd:\x1b[0m"
        echo "oc describe rs $(oc get rs -n $temp_project_name | grep ibm-fncm-operator | awk '{print $1}') -n $temp_project_name"
        exit 1
      else
        sleep 30
        continue
      fi
    else
      echo "IBM FileNet Content Manager Operator is running $isReady"
      break
    fi
  done

  echo
  # Add user to role if chosen from prompt
  if [[ -n "$user_name" ]]; then
    echo -ne Adding the user ${user_name} to the ibm-fncm-operator role...
    role_name_olm=$(${CLI_CMD} get role -n "$temp_project_name" --no-headers | grep ibm-fncm-operator.v | awk '{print $1}')
    if [[ -z $role_name_olm ]]; then
      echo "No role found for IBM FileNet Content Manager Operator"
      exit 1
    else
      ${CLI_CMD} project ${temp_project_name} >>${LOG_FILE}
      ${CLI_CMD} adm policy add-role-to-user edit ${user_name} >>${LOG_FILE}
      ${CLI_CMD} adm policy add-role-to-user registry-editor ${user_name} >>${LOG_FILE}
      ${CLI_CMD} adm policy add-role-to-user $role_name_olm ${user_name} >/dev/null 2>&1
      ${CLI_CMD} adm policy add-role-to-user $role_name_olm ${user_name} >>${LOG_FILE}
      echo "Done!"
    fi
  fi
  echo
  echo -ne Label the default namespace to allow network policies to open traffic to the ingress controller using a namespaceSelector...
  ${CLI_CMD} label --overwrite namespace default 'network.openshift.io/policy-group=ingress'
  echo "Done"
}

clear

verify_silence_install
prompt_license

select_platform
validate_cli
if [[ $PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" ]]; then
  check_platform_version
fi

# Ask for Project Name + all Namspaces + Deployment User
collect_input

validate_docker_podman_cli
# TODO: Remove local image pull option for OCP
get_entitlement_registry
if [[ "$use_entitlement" == "no" ]]; then
  verify_local_registry_password
fi

if [[ "$use_entitlement" == "yes" ]]; then
  create_secret_entitlement_registry
fi
if [[ "$use_entitlement" == "no" ]]; then
  create_secret_local_registry
fi

prepare_install
if [[ "$SCRIPT_MODE" == "OLM" ]]; then
  apply_operator_olm
else
  apply_operator_cncf
fi

check_storage_class

show_summary

clean_up
#set the project context back to the user generated one
if [[ $PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" ]]; then
  ${CLI_CMD} project ${PROJ_NAME} >/dev/null
else
  ${CLI_CMD} config set-context --current --namespace=${PROJ_NAME} >/dev/null
fi
