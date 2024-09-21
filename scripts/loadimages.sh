#!/bin/bash
# set -x

CUR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

echo -e "\033[1;31mImportant! The load image sample script is for x86_64, amd64, or i386 platforms only. \033[0m"
echo -e "\033[1;31mImportant! Please ensure that: \n\
    1. you had login to the target Docker registry in advance. \n\
    2. you had login to IBM Entitiled Image Registry in advance.  \n\
    3. you had skopeo installed in advance. \033[0m \n" 


ARCH=$(arch)
case ${ARCH} in
    amd64|x86_64|i386)
        echo "Supported arch: ${ARCH}"
    ;;
    *)
        echo "Unsupported arch: ${ARCH}"
        exit -1
    ;;
esac

function showHelp {
    echo -e "\nUsage: loadimages.sh -r docker_registry \n"
    echo "Options:"
    echo "  -h  Display help"
    echo "  -r  Target Docker registry"
    echo "      For example: mycorp-docker-local.mycorp.com"
}


# initialize variables
unset ppa_path
unset target_docker_repo
unset DEPLOYMENT_TYPE
unset SCRIPT_MODE
unset PATTERNS_SELECTED
PLATFORM_SELECTED="other" # This is the default value and will be reset by select_pattern.sh

unset CR_FILES
OPTIND=1         # Reset in case getopts has been used previously in the shell.
LOG_FILE="${CUR_DIR}/loadimages.log" # Keep image upload logs
touch $LOG_FILE && echo '' > $LOG_FILE # Reset log content

if [[ $1 == "" ]]
then
    showHelp
    exit -1
else
    while getopts ":h:m:r:" opt; do
        case "$opt" in
        h|\?)
            showHelp
            exit 0
            ;;
        r)  target_docker_repo=${OPTARG}
            ;;
        :)  echo "Invalid option: -$OPTARG requires an argument"
            showHelp
            exit -1
            ;;
      esac
    done
fi

# check required parameters
echo "target_docker_repo: $target_docker_repo"
if [ -z "$target_docker_repo" ]
then
    echo "Need to input target Docker registry and namespace value."
    showHelp
    exit -1
fi

function prepare_pattern_file(){
    DEPLOY_TYPE_IN_FILE_NAME="production_FC"
    CONTENT_PATTERN_FILE=${PARENT_DIR}/descriptors/ibm_fncm_cr_${DEPLOY_TYPE_IN_FILE_NAME}_content.yaml
    CR_FILES=(${CONTENT_PATTERN_FILE})
}

function push_images(){
    prepare_pattern_file
    DEPLOY_TYPE_IN_FILE_NAME="production_FC"
    source ${CUR_DIR}/helper/extract_and_push_images.sh $CR_FILES $target_docker_repo 2>&1| tee -a $LOG_FILE
}

source ${CUR_DIR}/helper/common.sh
validate_cli # Make sure user install yq
push_images
