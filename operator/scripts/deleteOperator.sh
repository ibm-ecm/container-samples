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
kubectl delete -f descriptors/operator.yaml
kubectl delete -f descriptors/role_binding.yaml
kubectl delete -f descriptors/role.yaml
kubectl delete -f descriptors/service_account.yaml

kubectl patch crd/fncmclusters.fncm.ibm.com -p '{"metadata":{"finalizers":[]}}' --type=merge
kubectl delete crd fncmclusters.fncm.ibm.com
