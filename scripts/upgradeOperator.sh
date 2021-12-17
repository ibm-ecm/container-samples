#!/bin/bash
###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2021. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################
# CUR_DIR set to full path to scripts folder
CUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_FOLDER=${CUR_DIR}/.tmp
BAK_FOLDER=${CUR_DIR}/.bak
mkdir -p $TEMP_FOLDER >/dev/null 2>&1
mkdir -p $BAK_FOLDER >/dev/null 2>&1

# Import common utilities and environment variables
source ${CUR_DIR}/helper/common.sh

OPERATOR_PVC_FILE=${PARENT_DIR}/descriptors/operator-shared-pvc.yaml
OPERATOR_PVC_FILE_TMP1=$TEMP_FOLDER/.operator-shared-pvc_tmp1.yaml
OPERATOR_PVC_FILE_TMP=$TEMP_FOLDER/.operator-shared-pvc_tmp.yaml
OPERATOR_PVC_FILE_BAK=$BAK_FOLDER/.operator-shared-pvc.yaml

CLUSTER_ROLE_FILE=${PARENT_DIR}/descriptors/cluster_role.yaml
CLUSTER_ROLE_BINDING_FILE=${PARENT_DIR}/descriptors/cluster_role_binding.yaml
CLUSTER_ROLE_BINDING_FILE_TEMP=${TEMP_FOLDER}/.cluster_role_binding.yaml

LOG_FILE=${CUR_DIR}/operator_upgrade.log

LICENSE_FILE=${PARENT_DIR}/LICENSE
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
  echo "  -i  Optional: Operator image name, by default it is cp.icr.io/cp/cp4a/icp4a-operator:21.0.3"
  echo -e "  -p  Optional: Pull secret to use to connect to the registry, by default it is admin.registrykey\n"

}

if [[ $1 == "" ]]; then
  show_help
  exit -1
else
  while getopts "h?i:p:a:n:m:" opt; do
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
    m)
      RUNTIME_MODE=$OPTARG
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

[ -f ${CUR_DIR}/../upgradeOperator.yaml ] && rm ${CUR_DIR}/../upgradeOperator.yaml
cp ${CUR_DIR}/../descriptors/operator.yaml ${CUR_DIR}/../upgradeOperator.yaml

PLATFORM_SELECTED=$(eval echo $(kubectl get fncmcluster $(kubectl get fncmcluster -n $NAMESPACE | grep NAME -v | awk '{print $1}') -n $NAMESPACE -o yaml | grep sc_deployment_platform | tail -1 | cut -d ':' -f 2))
if [[ "$PLATFORM_SELECTED" == "OCP" || "$PLATFORM_SELECTED" == "ROKS" ]]; then
  CLI_CMD=oc
else
  CLI_CMD=kubectl
fi
if [[ ! ($PLATFORM_SELECTED == "OCP" || $PLATFORM_SELECTED == "ROKS" || $PLATFORM_SELECTED == "other") ]]; then
  clear
  echo -e "\x1B[1;31mA deployed custom resource cannot be found.\n\x1B[0m"
  echo -e "\x1B[1;31mYou must apply an instance of a custom resource before you can upgrade. The script is exiting...\n\x1B[0m"
  exit 1
fi

# Show license file
function readLicense() {
  echo -e "\033[32mYou need to read the International Program License Agreement before start\033[0m"
  sleep 3
  more ${LICENSE_FILE}
}

# Get user's input on whether accept the license
function userInput() {
  while true; do
    echo -e "\033[32mDo you accept the International Program License?(Yes/No): \033[0m"
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

function create_new_shared_logs_pvc() {
  if [[ $(${CLI_CMD} get fncmcluster -n $NAMESPACE) == '' ]]; then
    echo -e "\033[31mIf you don't have a CR deployed, we can't upgrade FNCM Operator only, pls run deleteOperator.sh and then deployOperator.sh to redeploy Operator.\033[0m"
    exit 1
  fi
  DEPLOYMENT_TYPE=$(eval echo $(${CLI_CMD} get fncmcluster $(${CLI_CMD} get fncmcluster -n $NAMESPACE | grep NAME -v | awk '{print $1}') -n $NAMESPACE -o yaml | grep sc_deployment_type | tail -1 | cut -d ':' -f 2))
  STORAGE_CLASS_NAME=$(eval echo $(${CLI_CMD} get fncmcluster $(${CLI_CMD} get fncmcluster -n $NAMESPACE | grep NAME -v | awk '{print $1}') -n $NAMESPACE -o yaml | grep sc_dynamic_storage_classname | tail -1 | cut -d ':' -f 2))
  SLOW_STORAGE_CLASS_NAME=$(eval echo $(${CLI_CMD} get fncmcluster $(${CLI_CMD} get fncmcluster -n $NAMESPACE | grep NAME -v | awk '{print $1}') -n $NAMESPACE -o yaml | grep sc_slow_file_storage_classname | tail -1 | cut -d ':' -f 2))
  FAST_STORAGE_CLASS_NAME=$(eval echo $(${CLI_CMD} get fncmcluster $(${CLI_CMD} get fncmcluster -n $NAMESPACE | grep NAME -v | awk '{print $1}') -n $NAMESPACE -o yaml | grep sc_fast_file_storage_classname | tail -1 | cut -d ':' -f 2))
  ${COPY_CMD} -rf "${OPERATOR_PVC_FILE}" "${OPERATOR_PVC_FILE_BAK}"
  allocate_operator_pvc
}

function cncf_install() {
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
    sed -e "s|admin.registrykey|$PULLSECRET|g" ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
    mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  else
    sed -e '/imagePullSecrets:/{N;d;}' ${CUR_DIR}/../upgradeOperator.yaml >${CUR_DIR}/../upgradeOperatorsav.yaml
    mv ${CUR_DIR}/../upgradeOperatorsav.yaml ${CUR_DIR}/../upgradeOperator.yaml
  fi

  sed -e "s/<NAMESPACE>/${NAMESPACE}/g" ${CLUSTER_ROLE_BINDING_FILE} >${CLUSTER_ROLE_BINDING_FILE_TEMP}
  echo
  echo -ne "Creating the custom resource definition (CRD) and a service account that has the permissions to manage the resources..."
  ${CLI_CMD} apply -f ${CRD_FILE} -n ${NAMESPACE} --validate=false >/dev/null 2>&1
  echo " Done!"
  ${CLI_CMD} apply -f ${CLUSTER_ROLE_FILE} -n ${NAMESPACE} --validate=false >>${LOG_FILE}
  ${CLI_CMD} apply -f ${CLUSTER_ROLE_BINDING_FILE_TEMP} -n ${NAMESPACE} --validate=false >>${LOG_FILE}

  ${CLI_CMD} apply -f ${CUR_DIR}/../descriptors/service_account.yaml -n ${NAMESPACE} --validate=false
  ${CLI_CMD} apply -f ${CUR_DIR}/../descriptors/role.yaml -n ${NAMESPACE} --validate=false
  ${CLI_CMD} apply -f ${CUR_DIR}/../descriptors/role_binding.yaml -n ${NAMESPACE} --validate=false
  ${CLI_CMD} apply -f ${CUR_DIR}/../upgradeOperator.yaml -n ${NAMESPACE} --validate=false
}

if [[ $LICENSE_ACCEPTED == "" ]]; then
  readLicense
  userInput
fi

if [[ $LICENSE_ACCEPTED == "accept" ]]; then
  if [[ $(${CLI_CMD} get pvc -n ${NAMESPACE} | grep cp4a-shared-log-pvc) == '' ]]; then
    create_new_shared_logs_pvc
  fi
  cncf_install
  echo -e "\033[32mAll descriptors have been successfully applied. Monitor the pod status with '${CLI_CMD} get pods -w'.\033[0m"
fi
