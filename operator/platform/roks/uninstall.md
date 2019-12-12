# Uninstalling IBM FileNet Content Manager 5.5.4 on Red Hat OpenShift

## Delete the operator

To uninstall the deployments and the FileNet Content Manager operator, use the 'deleteOperator.sh' command to delete all the resources that are linked to the operator.

```bash
   ./scripts/deleteOperator.sh
```

Verify that all pods created with the deployment are terminated and deleted.

## Delete deployments

If you want to delete the custom resource deployment, you can delete the corresponding YAML file.

For example:
```bash
  $ oc delete -f descriptors/my_fncm_v1_fncm_cr.yaml
```

To uninstall an instance of the operator, you must delete all of the manifest files in the cluster:

```bash
  $ oc delete -f descriptors/operator.yaml
  $ oc delete -f descriptors/role_binding.yaml
  $ oc delete -f descriptors/role.yaml
  $ oc delete -f descriptors/service_account.yaml
  $ oc delete -f descriptors/fncm_v1_fncm_crd.yaml
```


