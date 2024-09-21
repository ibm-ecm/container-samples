#!/bin/bash
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
# CUR_DIR set to full path to scripts folder
#set -x
CUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_FOLDER=${CUR_DIR}/.tmp
BAK_FOLDER=${CUR_DIR}/.bak
mkdir -p $TEMP_FOLDER >/dev/null 2>&1
mkdir -p $BAK_FOLDER >/dev/null 2>&1

# Import common utilities and environment variables
source ${CUR_DIR}/helper/common.sh

CLUSTER_ROLE_FILE=${PARENT_DIR}/descriptors/cluster_role.yaml
CLUSTER_ROLE_BINDING_FILE=${PARENT_DIR}/descriptors/cluster_role_binding.yaml
CLUSTER_ROLE_BINDING_FILE_TEMP=${TEMP_FOLDER}/.cluster_role_binding.yaml

LOG_FILE=${CUR_DIR}/operator_upgrade.log

OLM_CATALOG=${PARENT_DIR}/descriptors/op-olm/catalogsource.yaml
OLM_OPT_GROUP=${PARENT_DIR}/descriptors/op-olm/operator_group.yaml
OLM_SUBSCRIPTION=${PARENT_DIR}/descriptors/op-olm/subscription.yaml
# the source is different for stage of development and final public
online_source="ibm-fncm-operator-catalog"


OLM_OPT_GROUP_TMP=${TEMP_FOLDER}/.operator_group.yaml
OLM_SUBSCRIPTION_TMP=${TEMP_FOLDER}/.subscription.yaml
OLM_SUBSCRIPTION_NAME="ibm-fncm-operator-catalog-subscription"
PROJ_NAME_ALL_NAMESPACE="openshift-operators"

echo '' >$LOG_FILE

LICENSE_ACCEPTED=""

function show_help {
  echo -e "\nPrerequisite:"
  echo -e "1. Login your cluster and switch to your target project;"
  echo -e "2. CR was applied in your project."
  echo -e "Usage: upgradeOperator.sh -a accept -n namespace -i operator_image -p secret_name\n"
  echo "Options:"
  echo "  -h  Display help"
  echo "  -n  The namespace to deploy Operator"
  echo "  -a  accept"
  echo "  -i  Optional: Operator image name, by default it is icr.io/cpopen/icp4a-content-operator:22.0.2"
  echo -e "  -p  Optional: Pull secret to use to connect to the registry, by default it is ibm-entitlement-key\n"

}

if [[ $1 == "" ]]; then
  show_help
  exit -1
else
  while getopts "h?i:p:a:n:" opt; do
    case "$opt" in
    h | \?)
      show_help
      exit 0
      ;;
    i)
      IMAGEREGISTRY=$OPTARG
      ;;
    p)
      PULLSECRET=$OPTARG
      ;;
    n)
      NAMESPACE=$OPTARG
      ;;
    a)
      LICENSE_ACCEPTED=$OPTARG
      ;;
    :)
      echo "Invalid option: -$OPTARG requires an argument"
      show_help
      exit -1
      ;;
    esac
  done
fi

if [ -z "$NAMESPACE" ]; then
  echo -e "\x1B[1;31mPlease input value for \"-n <NAMESPACE>\" option.\n\x1B[0m"
  exit 1
fi

function upgrade_prereq_check() {
  clear
  printf "\n"
  while true; do
    # TODO Add prereq link
    echo -e "\x1B[1mPlease see FileNet Content Manager Knowledge Center for important upgrade prerequisites: https://www.ibm.com/docs/en/filenet-p8-platform/5.5.x?topic=uvlo-checking-deployment-type-license \x1B[0m"
    echo -e "\x1B[1mHave you completed FileNet Content Manager Operator upgrade prerequisites (Yes/No)? \x1B[0m"
    # printf "\x1B[1mand 'loadPrereqImages.sh' (Db2 and OpenLDAP for demo) scripts (Yes/No)? \x1B[0m"
    read -rp "" ans
    case "$ans" in
    "y" | "Y" | "yes" | "Yes" | "YES")
      break
      ;;
    "n" | "N" | "no" | "No" | "NO")
      echo -e "\x1B[1;31mPlease complete upgrade prerequisites before continuing\n\x1B[0m"
      exit 1
      ;;
    *)
      echo -e "Answer must be \"Yes\" or \"No\"\n"
      ;;
    esac
  done
}

upgrade_prereq_check

[ -f ${CUR_DIR}/../upgradeOperator.yaml ] && rm ${CUR_DIR}/../upgradeOperator.yaml
cp ${CUR_DIR}/../descriptors/operator.yaml ${CUR_DIR}/../upgradeOperator.yaml
CLI_CMD=kubectl
PLATFORM_SELECTED=$(eval echo $(${CLI_CMD} get fncmcluster $(${CLI_CMD} get fncmcluster -n $NAMESPACE | grep NAME -v | awk '{print $1}') -n $NAMESPACE -o yaml | grep sc_deployment_platform | tail -1 | cut -d ':' -f 2))
if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
  CLI_CMD=oc
else
  CLI_CMD=${CLI_CMD}
fi
if [[ ! ($PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" || $PLATFORM_SELECTED == "other") ]]; then
  clear
  echo -e "\x1B[1;31mA deployed custom resource cannot be found.\n\x1B[0m"
  echo -e "\x1B[1;31mYou must apply an instance of a custom resource before you can upgrade. The script is exiting...\n\x1B[0m"
  exit 1
fi

# Show license file
function readLicense() {
  echo -e "\x1B[1;31mYou need to read the International Program License Agreement before start\n\x1B[0m"
  echo -e "\x1B[1;31mIMPORTANT: Review the license information for the product bundle you are deploying. \n\x1B[0m"
  echo -e "\x1B[1;31mIBM FileNet Content Manager license information here: https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-CHZ6NL \n\x1B[0m"
  echo -e "\x1B[1;31mIBM Content Foundation license information here: https://www14.software.ibm.com/cgi-bin/weblap/lap.pl?li_formnum=L-LSWS-CHZ6V7 \n\x1B[0m"
  sleep 3
}

function apply_operator_olm() {
  local maxRetry=20
  local temp_project_name=""

  if [[ $ALL_NAMESPACE == "Yes" ]]; then
    temp_project_name=$PROJ_NAME_ALL_NAMESPACE
  else
    temp_project_name=$project_name
  fi

  OLM_CATALOG=${PARENT_DIR}/descriptors/op-olm/catalogsource.yaml

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
        echo -e "\x1B[1mPlease check the status of Pod by issue cmd: \x1B[0m"
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

  if ${CLI_CMD} get subscription -n "${temp_project_name}" | grep ibm-fncm-operator; then
    echo "Found IBM FileNet Content Manager Operator Subscription, updating it"
    OLM_SUBSCRIPTION_NAME=$(${CLI_CMD} get subscription -n "${temp_project_name}" | grep ibm-fncm-operator | awk '{print $1}')
  fi
  sed  -e "s/REPLACE_NAMESPACE/$temp_project_name/g" -e "s/ibm-fncm-operator-catalog-subscription/$OLM_SUBSCRIPTION_NAME/g" ${OLM_SUBSCRIPTION} >${OLM_SUBSCRIPTION_TMP}

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
        echo -e "\x1B[1mPlease check the status of Pod by issue cmd:\x1B[0m"
        echo "oc describe pod $(oc get pod -n $temp_project_name | grep ibm-fncm-operator | awk '{print $1}') -n $temp_project_name"
        printf "\n"
        echo -e "\x1B[1mPlease check the status of ReplicaSet by issue cmd:\x1B[0m"
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
  echo -ne Checking ibm-fncm-operator role...
  role_name_olm=$(${CLI_CMD} get role -n "$temp_project_name" --no-headers | grep ibm-fncm-operator.v | awk '{print $1}')
  if [[ -z $role_name_olm ]]; then
    echo "No role found for IBM FileNet Content Manager Operator"
    exit 1
  fi
  echo
  echo -ne Label the default namespace to allow network policies to open traffic to the ingress controller using a namespaceSelector...
  ${CLI_CMD} label --overwrite namespace default 'network.openshift.io/policy-group=ingress'
  echo "Done"
}

# Get user's input on whether accept the license
function userInput() {
  while true; do
    echo -e "\033[32mDo you accept the International Program License? (Yes/No): \033[0m"
    read -rp "" ans
    case "$ans" in
    "y" | "Y" | "yes" | "Yes" | "YES")
      LICENSE_ACCEPTED="accept"
      break
      ;;
    "n" | "N" | "no" | "No" | "NO")
      echo -e "\033[31mScript will exit ...\033[0m"
      sleep 2
      exit 0
      ;;
    *)
      echo -e "Answer must be \"Yes\" or \"No\"\n"
      ;;
    esac
  done
}

function select_user() {
  user_result=$(${CLI_CMD} get user 2>&1)
  user_substring="No resources found"
  if [[ $user_result == *"$user_substring"* ]]; then
    clear
    echo -e "\x1B[1;31mAt least one user must be available in order to proceed.\n\x1B[0m"
    echo -e "\x1B[1;31mRefer to Knowledge Center documentation for details.  The script will now exit.!\n\x1B[0m"
    exit 1
  fi
  echo
  if [ -z "$FNCM_CLUSTER_USER" ]; then
    userlist=$(${CLI_CMD} get user | awk '{if(NR>1){if(NR==2){ arr=$1; }else{ arr=arr" "$1; }} } END{ print arr }')
    COLUMNS=12
    echo -e "\x1B[1mHere are the existing users on this cluster: \x1B[0m"
    options=($userlist)
    usernum=${#options[*]}
    PS3='Enter an existing username in your cluster, valid option [1 to '${usernum}'], non-admin is suggested: '
    select opt in "${options[@]}"; do
      if [[ -n "$opt" && "${options[@]}" =~ $opt ]]; then
        user_name=$opt
        break
      else
        echo "invalid option $REPLY"
      fi
    done
  else
    ${CLI_CMD} get user ${FNCM_CLUSTER_USER} >/dev/null 2>&1
    returnValue=$?
    if [ "$returnValue" == 1 ]; then
      echo -e "\x1B[1;31mNo found user \"${FNCM_CLUSTER_USER}\", please set a valid user. The script will exit...!\n\x1B[0m"
      exit 1
    else
      user_name=$FNCM_CLUSTER_USER
      echo -e "\x1B[1mSelected the existing users: \x1B[0m${FNCM_CLUSTER_USER}"
    fi
  fi
}

function collect_input() {
  project_name=""
  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
    select_all_namespace
    user_name=""
    #    select_user
  fi

  if [[ "$NAMESPACE" == openshift* ]]; then
    echo -e "\x1B[1;31mEnter a valid project name, project name should not be 'openshift' or start with 'openshift' \x1B[0m"
    exit 1
  elif [[ "$NAMESPACE" == kube* ]]; then
    echo -e "\x1B[1;31mEnter a valid project name, project name should not be 'kube' or start with 'kube' \x1B[0m"
    exit 1
  fi
  project_name=$NAMESPACE
}

function select_all_namespace() {
  printf "\n"
  while true; do
    if [ -z "$FNCM_AUTO_ALL_NAMESPACES" ]; then
      printf "\x1B[1mDo you want IBM FileNet Content Manager Operator support 'All Namespaces'? (Yes/No, default: No) \x1B[0m"

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
      printf "\x1B[1mDo you want IBM FileNet Content Manager Operator support 'All Namespaces'? (Yes/No, default: No)  \x1B[0m$FNCM_AUTO_ALL_NAMESPACES\n"
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

function upgrade_cncf() {
  sed -e '/dba_license/{n;s/value:.*/value: accept/;}' ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
  mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  sed -e '/baw_license/{n;s/value:.*/value: accept/;}' ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
  mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  sed -e '/fncm_license/{n;s/value:.*/value: accept/;}' ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
  mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  sed -e '/ier_license/{n;s/value:.*/value: accept/;}' ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
  mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml

  if [ ! -z ${IMAGEREGISTRY} ]; then
    # Change the location of the image
    echo "Using the operator image name: $IMAGEREGISTRY"
    sed -e "s|image: .*|image: \"$IMAGEREGISTRY\" |g" ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
    mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  fi

  # Change the pullSecrets if needed
  if [ ! -z ${PULLSECRET} ]; then
    echo "Setting pullSecrets to $PULLSECRET"
    cp ${CUR_DIR}/../upgradeOperator.yaml ${CUR_DIR}/../upgradeOperatorsav.yaml
    ${YQ_CMD} ".spec.template.spec.imagePullSecrets + {\"name\": $PULLSECRET}" ${CUR_DIR}/../upgradeOperatorsav.yaml
    mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  fi

  sed -e "s/<NAMESPACE>/${NAMESPACE}/g" ${CLUSTER_ROLE_BINDING_FILE} >${CLUSTER_ROLE_BINDING_FILE_TEMP}
  echo
  echo -ne "Creating the custom resource definition (CRD) and a service account that has the permissions to manage the resources..."
  ${CLI_CMD} apply -f ${CRD_FILE} -n ${NAMESPACE} --validate=false >/dev/null 2>&1
  echo " Done!"
  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
    ${CLI_CMD} apply -f ${CLUSTER_ROLE_FILE} -n ${NAMESPACE} --validate=false >>${LOG_FILE}
    ${CLI_CMD} apply -f ${CLUSTER_ROLE_BINDING_FILE_TEMP} -n ${NAMESPACE} --validate=false >>${LOG_FILE}
  fi

  ${CLI_CMD} apply -f ${CUR_DIR}/../descriptors/service_account.yaml -n ${NAMESPACE} --validate=false
  ${CLI_CMD} apply -f ${CUR_DIR}/../descriptors/role.yaml -n ${NAMESPACE} --validate=false
  ${CLI_CMD} apply -f ${CUR_DIR}/../descriptors/role_binding.yaml -n ${NAMESPACE} --validate=false
  ${CLI_CMD} apply -f ${CUR_DIR}/../upgradeOperator.yaml -n ${NAMESPACE} --validate=false
}

function uninstall_cncf_fncm() {
  printf "\n"
  printf "\x1B[1mUninstall IBM FileNet Content Manager Operator...\n\x1B[0m"
  ${CLI_CMD} delete -f ${CUR_DIR}/../descriptors/operator.yaml -n $NAMESPACE >/dev/null 2>&1
  ${CLI_CMD} delete -f ${CUR_DIR}/../descriptors/role_binding.yaml -n $NAMESPACE >/dev/null 2>&1
  ${CLI_CMD} delete -f ${CUR_DIR}/../descriptors/role.yaml -n $NAMESPACE >/dev/null 2>&1
  ${CLI_CMD} delete -f ${CUR_DIR}/../descriptors/service_account.yaml -n $NAMESPACE >/dev/null 2>&1
  echo "All descriptors have been successfully deleted."
}

if [[ $LICENSE_ACCEPTED == "" ]]; then
  readLicense
  userInput
fi

collect_input

if [[ $LICENSE_ACCEPTED == "accept" ]]; then
  if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ocp" || "$PLATFORM_SELECTED" == "ROKS" || "$PLATFORM_SELECTED" == "roks" ]]; then
    ${CLI_CMD} get subscription -n $NAMESPACE | grep ibm-fncm-operator >/dev/null 2>&1
    returnValue=$?
    if [ "$returnValue" == 1 ]; then
      uninstall_cncf_fncm
    fi
    apply_operator_olm
  else
    upgrade_cncf
  fi
  echo -e "\033[32mAll descriptors have been successfully applied. Monitor the pod status with '${CLI_CMD} get pods -w'.\033[0m"
fi
