#!/bin/bash
###############################################################################
#
# Licensed Materials - Property of IBM
#
# (C) Copyright IBM Corp. 2019. All Rights Reserved.
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
#
###############################################################################

while getopts "h?i:p:" opt; do
    case "$opt" in
    h|\?)
        show_help
        exit 0
        ;;
    i)  IMAGEREGISTRY=$OPTARG
        ;;
    p)  PULLSECRET=$OPTARG
    esac
done

[ -f ./deployoperator.yaml ] && rm ./deployoperator.yaml
cp ./descriptors/operator.yaml ./deployoperator.yaml
if [ ! -z ${IMAGEREGISTRY} ]; then
  # Change the location of the image
  echo "Using the operator image name: $IMAGEREGISTRY"
  sed -e "s|image: .*|image: \"$IMAGEREGISTRY\" |g" ./deployoperator.yaml > ./deployoperatorsav.yaml ;  mv ./deployoperatorsav.yaml ./deployoperator.yaml
fi

# Change the pullSecrets if needed
if [ ! -z ${PULLSECRET} ]; then
    echo "Setting pullSecrets to $PULLSECRET"
    sed -e "s|admin.registrykey|$PULLSECRET|g" ./deployoperator.yaml > ./deployoperatorsav.yaml ;  mv ./deployoperatorsav.yaml ./deployoperator.yaml
else
    sed -e '/imagePullSecrets:/{N;d;}' ./deployoperator.yaml > ./deployoperatorsav.yaml ; mv ./deployoperatorsav.yaml ./deployoperator.yaml
fi

kubectl apply -f ./descriptors/fncm_v1_fncm_crd.yaml --validate=false
kubectl apply -f ./descriptors/service_account.yaml --validate=false
kubectl apply -f ./descriptors/role.yaml --validate=false
kubectl apply -f ./descriptors/role_binding.yaml --validate=false
kubectl apply -f ./deployoperator.yaml --validate=false
