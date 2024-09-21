#!/bin/bash
#set -x
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
###############################################################################

CUR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
TEMP_FOLDER=${CUR_DIR}/.tmp
unset IFS #This is to reset using "," as separate in map_pattern_and_CR.sh
#################debug##########################
# PLATFORM_SELECTED="OCP"
# SCRIPT_MODE="dev"
# IMAGE_REGISTRY="hyc-dba-base-image-docker-local.artifactory.swg-devops.com/gyfguo"
#################debug###d######################
CPE_REPO=cp.icr.io/cp/cp4a/fncm/cpe
BAN_REPO=cp.icr.io/cp/cp4a/ban/navigator
CPE_PRESENT_FLAG="false"
BAN_PRESENT_FLAG="false"

OPERATOR_FILE=${PARENT_DIR}/../descriptors/operator.yaml

if [[ $1 == "" ]]; then
  # This is for debug purpose only
  DEPLOY_TYPE_IN_FILE_NAME="production_FC"
  CONTENT_PATTERN_FILE=${PARENT_DIR}/../descriptors/patterns/ibm_fncm_cr_${DEPLOY_TYPE_IN_FILE_NAME}_content.yaml
  CR_FILES=(${CONTENT_PATTERN_FILE})
else
  CR_FILES=$1
fi

if [[ $2 == "" ]]; then
  IMAGE_REGISTRY="localhost:5000"
else
  IMAGE_REGISTRY=$2
fi

if [ ! -d "${TEMP_FOLDER}" ]; then
  mkdir $TEMP_FOLDER
fi
IMAGE_REPOSITORY_LIST_FILE=${TEMP_FOLDER}/image_repository_list.properties
IMAGE_TAG_LIST_FILE=${TEMP_FOLDER}/image_tag_list.properties

function extract_image_list_from_CR(){
  # clean the list content
  echo '' > ${IMAGE_REPOSITORY_LIST_FILE}
  echo '' > ${IMAGE_TAG_LIST_FILE}
  ecm_products=("cpe" "css" "graphql" "es" "cmis" "tm")

  # extract repository and tag for each CR
  for item in "${CR_FILES[@]}"
  do
    echo "Extracting images from $item..."
    for product in "${ecm_products[@]}"
    do
      ${YQ_CMD} ".spec.ecm_configuration.$product.*.repository" ${item} | grep -v null  >> ${IMAGE_REPOSITORY_LIST_FILE}
      ${YQ_CMD} ".spec.ecm_configuration.$product.*.tag" ${item} | grep -v null  >> ${IMAGE_TAG_LIST_FILE}
    done
    ${YQ_CMD} ".spec.navigator_configuration.*.repository" ${item} | grep -v null  >> ${IMAGE_REPOSITORY_LIST_FILE}
    ${YQ_CMD} ".spec.navigator_configuration.*.tag" ${item} | grep -v null  >> ${IMAGE_TAG_LIST_FILE}
  done
}

function add_sso_images(){
  IMAGE_REPOSITORY_LIST1=($(cat $IMAGE_REPOSITORY_LIST_FILE))
  IMAGE_TAG_LIST1=($(cat $IMAGE_TAG_LIST_FILE))
  #to get the current tag of sso images
  for i in "${!IMAGE_REPOSITORY_LIST1[@]}"
  do
    if [[ "${IMAGE_REPOSITORY_LIST1[$i]}" == "${CPE_REPO}" ]]; then
      CPE_IMAGE_TAG=${IMAGE_TAG_LIST1[$i]}
      CPE_PRESENT_FLAG="present"
    fi
    if [[ "${IMAGE_REPOSITORY_LIST1[$i]}" == "${BAN_REPO}" ]]; then
      BAN_IMAGE_TAG=${IMAGE_TAG_LIST1[$i]}
      BAN_PRESENT_FLAG="present"
    fi
  done

  if [[ "${CPE_PRESENT_FLAG}" =~ "present" ]]; then
    echo "cp.icr.io/cp/cp4a/fncm/cpe-sso" >> ${IMAGE_REPOSITORY_LIST_FILE}
    echo ${CPE_IMAGE_TAG} >> ${IMAGE_TAG_LIST_FILE}
  fi
  if [[ "${BAN_PRESENT_FLAG}" =~ "present" ]]; then
    echo "cp.icr.io/cp/cp4a/ban/navigator-sso" >> ${IMAGE_REPOSITORY_LIST_FILE}
    echo ${BAN_IMAGE_TAG} >> ${IMAGE_TAG_LIST_FILE}
  fi

}

function push_images(){
  IMAGE_REPOSITORY_LIST=($(cat $IMAGE_REPOSITORY_LIST_FILE))
  IMAGE_TAG_LIST=($(cat $IMAGE_TAG_LIST_FILE))

  if [ ${#IMAGE_REPOSITORY_LIST[@]} != ${#IMAGE_TAG_LIST[@]} ]; then
    echo "Image repository number doesn't match image tag number, exit now...."
    exit 1
  else
    i=0
    for item in "${IMAGE_REPOSITORY_LIST[@]}"
    do  
      # DBACLD-31777: remove image context and --src-creds comment
      new_image_repo="${IMAGE_REPOSITORY_LIST[i]##*/}"
      echo "Pushing $i: ${IMAGE_REPOSITORY_LIST[i]}:${IMAGE_TAG_LIST[i]} to ${IMAGE_REGISTRY}/${new_image_repo}:${IMAGE_TAG_LIST[i]}"
      skopeo copy \
        docker://"${IMAGE_REPOSITORY_LIST[i]}:${IMAGE_TAG_LIST[i]}" \
        docker://"${IMAGE_REGISTRY}/${new_image_repo}:${IMAGE_TAG_LIST[i]}" \
        --all \
        --dest-tls-verify=false \
        --remove-signatures
      ((i++))
    done
  fi
}

function add_operator_image(){
  OPERATOR_IMAGE=$(${YQ_CMD} ".spec.template.spec.containers[0].image" ${OPERATOR_FILE})
  IFS=':'
  read -a repoAndTag <<< "${OPERATOR_IMAGE}"
  OPERATOR_REPO="${repoAndTag[0]}"
  OPERATOR_TAG="${repoAndTag[1]}"

  if [[ "${SCRIPT_MODE}" =~ "dev" ]]; then
    OPERATOR_REPO='cp.stg.icr.io/cp/icp4a-content-operator'
  else
    echo "${OPERATOR_REPO}" >> ${IMAGE_REPOSITORY_LIST_FILE}
  fi
  echo "${OPERATOR_TAG}" >> ${IMAGE_TAG_LIST_FILE}

  IFS='/'
  read -a repoAndFolder <<< "${OPERATOR_REPO}"

  imageFolder="${repoAndFolder[2]}"

  echo "Pushing Operator Image: ${OPERATOR_REPO}:${OPERATOR_TAG} to ${IMAGE_REGISTRY}/cpopen/${imageFolder}:${OPERATOR_TAG}"

   skopeo copy \
        docker://"${OPERATOR_REPO}:${OPERATOR_TAG}" \
        docker://"${IMAGE_REGISTRY}/cpopen/${imageFolder}:${OPERATOR_TAG}" \
        --all \
        --dest-tls-verify=false \
        --remove-signatures
}

extract_image_list_from_CR
add_sso_images
if [[ "${SCRIPT_MODE}" =~ "dev" ]]; then
  sed -i "repo.bak" 's/cp.icr.io/cp.stg.icr.io/g' ${IMAGE_REPOSITORY_LIST_FILE}
fi
push_images
add_operator_image