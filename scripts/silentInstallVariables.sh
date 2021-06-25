#!/bin/bash
# set -x
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

# FNCM_PLATFORM: valid value is `ROKS`, `OCP`, `other`
export FNCM_PLATFORM="<Required>"

# target namespace to deploy FNCM Standalone Operator
export FNCM_NAMESPACE="<Required>"

# FNCM_CLUSTER_USER need an existing user in OCP/ROKS cluster, `other` platform does not need this one
export FNCM_CLUSTER_USER="<Required>"

# Do you accept the FNCM Standalone Operator License: valid value is "Accept" 
export FNCM_LICENSE_ACCEPT="<Required>"

# set FNCM_STORAGE_CLASS for OCP or other
# set FNCM_STORAGE_CLASS_FAST_ROKS for ROKS
export FNCM_STORAGE_CLASS="<Required>"
#export FNCM_STORAGE_CLASS_FAST_ROKS="<Required>"

# choose either entitlement key or local registry
# set for entitlement registry
export FNCM_ENTITLEMENT_KEY="<Required>"

# set for external docker registry
### confirm pushed PPA into the local registry for the CNCF platform
#export FNCM_PUSH_IMAGE_LOCAL_REGISTRY=true
#export FNCM_REGISTRY_TYPE=external
#export FNCM_LOCAL_PUBLIC_REGISTRY="<Required>"
#export FNCM_LOCAL_REGISTRY_USER="<Required>"
#export FNCM_LOCAL_REGISTRY_PASSWORD="<Required>"

# set for internal OCP registry
### confirm pushed PPA into the local registry for the CNCF platform
#export FNCM_PUSH_IMAGE_LOCAL_REGISTRY=true
#export FNCM_REGISTRY_TYPE="internal"
#export FNCM_LOCAL_PRIVATE_REGISTRY="<Required>"
#export FNCM_LOCAL_PUBLIC_REGISTRY="<Required>"
#export FNCM_LOCAL_REGISTRY_USER="<Required>"
#export FNCM_LOCAL_REGISTRY_PASSWORD="<Required>"


