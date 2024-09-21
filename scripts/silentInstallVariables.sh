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

# FNCM_LICENSE_ACCEPT: Do you accept the IBM FileNet Content Manager Operator License?
# Valid value is: "Accept"
export FNCM_LICENSE_ACCEPT="<Required>"

# FNCM_PLATFORM: Platform to deploy IBM FileNet Content Manager Operator to
# Valid values are: `ROKS`, `OCP`, `other`
export FNCM_PLATFORM="<Required>"

# FNCM_NAMESPACE: Target namespace to deploy the IBM FileNet Content Manager Operator to
export FNCM_NAMESPACE="<Required>"

# FNCM_AUTO_ALL_NAMESPACES: Choose either "Yes" or "No" to install the IBM FileNet Content Manager Operator into all namespaces
export FNCM_AUTO_ALL_NAMESPACES="<Required>"

# FNCM_ADD_CLUSTER_USER: Choose "Yes" or "No" to add a non-administator user to manage the namespace
# FNCM_CLUSTER_USER: (Optional) An existing [non-administrator] user in the OCP/ROKS cluster
export FNCM_ADD_CLUSTER_USER="<Required>"
export FNCM_CLUSTER_USER=""

# FNCM_ENTITLEMENT_KEY: Choose either entitlement key or local registry
# Set for entitlement registry
export FNCM_ENTITLEMENT_KEY="<Required>"

# Optional - Set for external docker registry
# Confirm the PPA is pushed into the local registry for the CNCF platform
#export FNCM_PUSH_IMAGE_LOCAL_REGISTRY=true
#export FNCM_REGISTRY_TYPE=external
#export FNCM_LOCAL_PUBLIC_REGISTRY="<Required>"
#export FNCM_LOCAL_REGISTRY_USER="<Required>"
#export FNCM_LOCAL_REGISTRY_PASSWORD="<Required>"

# Optional - Set for internal OCP registry
# Confirm the PPA is pushed into the local registry for the OCP platform
#export FNCM_PUSH_IMAGE_LOCAL_REGISTRY=true
#export FNCM_REGISTRY_TYPE="internal"
#export FNCM_LOCAL_PRIVATE_REGISTRY="<Required>"
#export FNCM_LOCAL_PUBLIC_REGISTRY="<Required>"
#export FNCM_LOCAL_REGISTRY_USER="<Required>"
#export FNCM_LOCAL_REGISTRY_PASSWORD="<Required>"


