# EODAG Server

This chart bootstraps a [EODAG Server](https://github.com/CS-SI/eodag) deployment on a [Kubernetes](http://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

## TL;DR

```console
helm install my-release oci://registry-1.docker.io/csspace/eodag-server
```

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+

## Installing the Chart

To install the chart with the release name `my-release`:

```console
helm install my-release oci://registry-1.docker.io/csspace/eodag-server
```

These commands deploy EODAG Server on the Kubernetes cluster in the default configuration.

> **Tip**: List all releases using `helm list`

## Uninstalling the Chart


To uninstall the `my-release` deployment:

```bash
helm uninstall my-release
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

## Parameters

### Global parameters

| Name                      | Description                                     | Value |
| ------------------------- | ----------------------------------------------- | ----- |
| `global.imageRegistry`    | Global Docker image registry                    | `""`  |
| `global.imagePullSecrets` | Global Docker registry secret names as an array | `[]`  |
| `global.storageClass`     | Global StorageClass for Persistent Volume(s)    | `""`  |

### Common parameters

| Name                | Description                                                          | Value           |
| ------------------- | -------------------------------------------------------------------- | --------------- |
| `kubeVersion`       | Force target Kubernetes version (using Helm capabilities if not set) | `""`            |
| `nameOverride`      | String to partially override common.names.fullname                   | `""`            |
| `fullnameOverride`  | String to fully override common.names.fullname                       | `""`            |
| `namespaceOverride` | String to fully override common.names.namespaceapi                   | `""`            |
| `commonLabels`      | Labels to add to all deployed objects                                | `{}`            |
| `commonAnnotations` | Annotations to add to all deployed objects                           | `{}`            |
| `clusterDomain`     | Kubernetes cluster domain name                                       | `cluster.local` |
| `extraDeploy`       | Array of extra objects to deploy with the release                    | `[]`            |

### EODAG Server parameters

| Name                                                | Description                                                                                                               | Value                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `image.registry`                                    | EODAG Server image registry                                                                                               | `docker.io`              |
| `image.repository`                                  | EODAG Server image repository                                                                                             | `csspace/eodag-server`   |
| `image.tag`                                         | EODAG Server image tag (immutable tags are recommended)                                                                   | `2.10.0`                 |
| `image.digest`                                      | EODAG Server image digest in the way sha256:aa.... Please note this parameter, if set, will override the tag              | `""`                     |
| `image.pullPolicy`                                  | EODAG Server image pull policy                                                                                            | `IfNotPresent`           |
| `image.pullSecrets`                                 | Specify docker-registry secret names as an array                                                                          | `[]`                     |
| `replicaCount`                                      | Number of EODAG Server replicas                                                                                           | `1`                      |
| `startupProbe.enabled`                              | Enable startupProbe on EODAG Server containers                                                                            | `false`                  |
| `startupProbe.initialDelaySeconds`                  | Initial delay seconds for startupProbe                                                                                    | `10`                     |
| `startupProbe.periodSeconds`                        | Period seconds for startupProbe                                                                                           | `10`                     |
| `startupProbe.timeoutSeconds`                       | Timeout seconds for startupProbe                                                                                          | `1`                      |
| `startupProbe.failureThreshold`                     | Failure threshold for startupProbe                                                                                        | `3`                      |
| `startupProbe.successThreshold`                     | Success threshold for startupProbe                                                                                        | `1`                      |
| `livenessProbe.enabled`                             | Enable livenessProbe on EODAG Server containers                                                                           | `false`                  |
| `livenessProbe.initialDelaySeconds`                 | Initial delay seconds for livenessProbe                                                                                   | `3`                      |
| `livenessProbe.periodSeconds`                       | Period seconds for livenessProbe                                                                                          | `10`                     |
| `livenessProbe.timeoutSeconds`                      | Timeout seconds for livenessProbe                                                                                         | `1`                      |
| `livenessProbe.failureThreshold`                    | Failure threshold for livenessProbe                                                                                       | `3`                      |
| `livenessProbe.successThreshold`                    | Success threshold for livenessProbe                                                                                       | `1`                      |
| `readinessProbe.enabled`                            | Enable readinessProbe on EODAG Server containers                                                                          | `false`                  |
| `readinessProbe.initialDelaySeconds`                | Initial delay seconds for readinessProbe                                                                                  | `3`                      |
| `readinessProbe.periodSeconds`                      | Period seconds for readinessProbe                                                                                         | `10`                     |
| `readinessProbe.timeoutSeconds`                     | Timeout seconds for readinessProbe                                                                                        | `1`                      |
| `readinessProbe.failureThreshold`                   | Failure threshold for readinessProbe                                                                                      | `3`                      |
| `readinessProbe.successThreshold`                   | Success threshold for readinessProbe                                                                                      | `1`                      |
| `customLivenessProbe`                               | Custom livenessProbe that overrides the default one                                                                       | `{}`                     |
| `customReadinessProbe`                              | Custom readinessProbe that overrides the default one                                                                      | `{}`                     |
| `resources.limits`                                  | The resources limits for the EODAG Server containers                                                                      | `{}`                     |
| `resources.requests`                                | The requested resources for the EODAG Server containers                                                                   | `{}`                     |
| `podSecurityContext.enabled`                        | Enabled EODAG Server pods' Security Context                                                                               | `false`                  |
| `podSecurityContext.fsGroup`                        | Set EODAG Server pod's Security Context fsGroup                                                                           | `1001`                   |
| `containerSecurityContext.enabled`                  | Enabled EODAG Server containers' Security Context                                                                         | `false`                  |
| `containerSecurityContext.runAsUser`                | Set EODAG Server containers' Security Context runAsUser                                                                   | `1001`                   |
| `containerSecurityContext.allowPrivilegeEscalation` | Set EODAG Server containers' Security Context allowPrivilegeEscalation                                                    | `false`                  |
| `containerSecurityContext.capabilities.drop`        | Set EODAG Server containers' Security Context capabilities to be dropped                                                  | `["all"]`                |
| `containerSecurityContext.readOnlyRootFilesystem`   | Set EODAG Server containers' Security Context readOnlyRootFilesystem                                                      | `false`                  |
| `containerSecurityContext.runAsNonRoot`             | Set EODAG Server container's Security Context runAsNonRoot                                                                | `true`                   |
| `command`                                           | Override default container command (useful when using custom images)                                                      | `[]`                     |
| `args`                                              | Override default container args (useful when using custom images). Overrides the defaultArgs.                             | `[]`                     |
| `containerPorts.http`                               | EODAG Server application HTTP port number                                                                                 | `5000`                   |
| `persistence.enabled`                               | Enable persistence using PVC                                                                                              | `false`                  |
| `persistence.medium`                                | Provide a medium for `emptyDir` volumes.                                                                                  | `""`                     |
| `persistence.sizeLimit`                             | Set this to enable a size limit for `emptyDir` volumes.                                                                   | `8Gi`                    |
| `persistence.storageClass`                          | PVC Storage Class for Matomo volume                                                                                       | `""`                     |
| `persistence.accessModes`                           | PVC Access Mode for Matomo volume                                                                                         | `["ReadWriteOnce"]`      |
| `persistence.size`                                  | PVC Storage Request for Matomo volume                                                                                     | `8Gi`                    |
| `persistence.dataSource`                            | Custom PVC data source                                                                                                    | `{}`                     |
| `persistence.existingClaim`                         | A manually managed Persistent Volume Claim                                                                                | `""`                     |
| `persistence.hostPath`                              | If defined, the matomo-data volume will mount to the specified hostPath.                                                  | `""`                     |
| `persistence.annotations`                           | Persistent Volume Claim annotations                                                                                       | `{}`                     |
| `persistence.labels`                                | Additional custom labels for the PVC                                                                                      | `{}`                     |
| `persistence.selector`                              | Selector to match an existing Persistent Volume for Matomo data PVC                                                       | `{}`                     |
| `hostAliases`                                       | EODAG Server pods host aliases                                                                                            | `[]`                     |
| `podLabels`                                         | Extra labels for EODAG Server pods                                                                                        | `{}`                     |
| `podAnnotations`                                    | Annotations for EODAG Server pods                                                                                         | `{}`                     |
| `podAffinityPreset`                                 | Pod affinity preset. Ignored if `affinity` is set. Allowed values: `soft` or `hard`                                       | `""`                     |
| `podAntiAffinityPreset`                             | Pod anti-affinity preset. Ignored if `affinity` is set. Allowed values: `soft` or `hard`                                  | `soft`                   |
| `nodeAffinityPreset.type`                           | Node affinity preset type. Ignored if `affinity` is set. Allowed values: `soft` or `hard`                                 | `""`                     |
| `nodeAffinityPreset.key`                            | Node label key to match. Ignored if `affinity` is set                                                                     | `""`                     |
| `nodeAffinityPreset.values`                         | Node label values to match. Ignored if `affinity` is set                                                                  | `[]`                     |
| `affinity`                                          | Affinity for EODAG Server pods assignment                                                                                 | `{}`                     |
| `nodeSelector`                                      | Node labels for EODAG Server pods assignment                                                                              | `{}`                     |
| `tolerations`                                       | Tolerations for EODAG Server pods assignment                                                                              | `[]`                     |
| `schedulerName`                                     | Name of the k8s scheduler (other than default)                                                                            | `""`                     |
| `shareProcessNamespace`                             | Enable shared process namespace in a pod.                                                                                 | `false`                  |
| `topologySpreadConstraints`                         | Topology Spread Constraints for pod assignment                                                                            | `[]`                     |
| `updateStrategy.type`                               | EODAG Server statefulset strategy type                                                                                    | `RollingUpdate`          |
| `priorityClassName`                                 | EODAG Server pods' priorityClassName                                                                                      | `""`                     |
| `runtimeClassName`                                  | Name of the runtime class to be used by pod(s)                                                                            | `""`                     |
| `lifecycleHooks`                                    | for the EODAG Server container(s) to automate configuration before or after startup                                       | `{}`                     |
| `extraEnvVars`                                      | Array with extra environment variables to add to EODAG Server nodes                                                       | `[]`                     |
| `extraEnvVarsCM`                                    | Name of existing ConfigMap containing extra env vars for EODAG Server nodes                                               | `""`                     |
| `extraEnvVarsSecret`                                | Name of existing Secret containing extra env vars for EODAG Server nodes                                                  | `""`                     |
| `extraVolumes`                                      | Optionally specify extra list of additional volumes for the EODAG Server pod(s)                                           | `[]`                     |
| `extraVolumeMounts`                                 | Optionally specify extra list of additional volumeMounts for the EODAG Server container(s)                                | `[]`                     |
| `sidecars`                                          | Add additional sidecar containers to the EODAG Server pod(s)                                                              | `[]`                     |
| `initContainers`                                    | Add additional init containers to the EODAG Server pod(s)                                                                 | `[]`                     |
| `logLevel`                                          | Supported values are 0 (no log), 1 (no logging but progress bar), 2 (INFO) or 3 (DEBUG).                                  | `2`                      |
| `productTypes`                                      | Optional overwrite of product types default configuration                                                                 | `""`                     |
| `providers`                                         | Optional overwrite of providers default configuration                                                                     | `""`                     |
| `config`                                            | EODAG configuration                                                                                                       | `{}`                     |
| `configExistingSecret.name`                         | Existing secret name for EODAG config. If this is set, value config will be ignored                                       | `nil`                    |
| `configExistingSecret.key`                          | Existing secret key for EODAG config. If this is set, value config will be ignored                                        | `nil`                    |
| `service.type`                                      | Kubernetes service type                                                                                                   | `ClusterIP`              |
| `service.http.enabled`                              | Enable http port on service                                                                                               | `true`                   |
| `service.ports.http`                                | EODAG Server service HTTP port                                                                                            | `8080`                   |
| `service.nodePorts`                                 | Specify the nodePort values for the LoadBalancer and NodePort service types.                                              | `{}`                     |
| `service.sessionAffinity`                           | Control where client requests go, to the same pod or round-robin                                                          | `None`                   |
| `service.sessionAffinityConfig`                     | Additional settings for the sessionAffinity                                                                               | `{}`                     |
| `service.clusterIP`                                 | EODAG Server service clusterIP IP                                                                                         | `""`                     |
| `service.loadBalancerIP`                            | loadBalancerIP for the SuiteCRM Service (optional, cloud specific)                                                        | `""`                     |
| `service.loadBalancerSourceRanges`                  | Address that are allowed when service is LoadBalancer                                                                     | `[]`                     |
| `service.externalTrafficPolicy`                     | Enable client source IP preservation                                                                                      | `Cluster`                |
| `service.annotations`                               | Additional custom annotations for EODAG Server service                                                                    | `{}`                     |
| `service.extraPorts`                                | Extra port to expose on EODAG Server service                                                                              | `[]`                     |
| `ingress.enabled`                                   | Enable the creation of an ingress for the EODAG Server                                                                    | `false`                  |
| `ingress.pathType`                                  | Path type for the EODAG Server ingress                                                                                    | `ImplementationSpecific` |
| `ingress.apiVersion`                                | Ingress API version for the EODAG Server ingress                                                                          | `""`                     |
| `ingress.hostname`                                  | Ingress hostname for the EODAG Server ingress                                                                             | `eodag.local`            |
| `ingress.annotations`                               | Annotations for the EODAG Server ingress. To enable certificate autogeneration, place here your cert-manager annotations. | `{}`                     |
| `ingress.tls`                                       | Enable TLS for the EODAG Server ingress                                                                                   | `false`                  |
| `ingress.extraHosts`                                | Extra hosts array for the EODAG Server ingress                                                                            | `[]`                     |
| `ingress.path`                                      | Path array for the EODAG Server ingress                                                                                   | `/`                      |
| `ingress.extraPaths`                                | Extra paths for the EODAG Server ingress                                                                                  | `[]`                     |
| `ingress.extraTls`                                  | Extra TLS configuration for the EODAG Server ingress                                                                      | `[]`                     |
| `ingress.secrets`                                   | Secrets array to mount into the Ingress                                                                                   | `[]`                     |
| `ingress.ingressClassName`                          | IngressClass that will be be used to implement the Ingress (Kubernetes 1.18+)                                             | `""`                     |
| `ingress.selfSigned`                                | Create a TLS secret for this ingress record using self-signed certificates generated by Helm                              | `false`                  |
| `ingress.servicePort`                               | Backend service port to use                                                                                               | `http`                   |
| `ingress.extraRules`                                | Additional rules to be covered with this ingress record                                                                   | `[]`                     |
| `serviceAccount.create`                             | Specifies whether a ServiceAccount should be created                                                                      | `true`                   |
| `serviceAccount.name`                               | The name of the ServiceAccount to use.                                                                                    | `""`                     |
| `serviceAccount.annotations`                        | Additional custom annotations for the ServiceAccount                                                                      | `{}`                     |
| `serviceAccount.automountServiceAccountToken`       | Automount service account token for the server service account                                                            | `true`                   |


```console
$ helm install my-release \
  --set image.pullPolicy=Always \
    my-repo/eodag-server
```

The above command sets the `image.pullPolicy` to `Always`.

Alternatively, a YAML file that specifies the values for the parameters can be provided while installing the chart. For example,

```console
helm install my-release -f values.yaml my-repo/eodag-server
```

> **Tip**: You can use the default [values.yaml](values.yaml)

## Configuration and installation details

### [Rolling VS Immutable tags](https://docs.bitnami.com/containers/how-to/understand-rolling-tags-containers/)

It is strongly recommended to use immutable tags in a production environment. This ensures your deployment does not change automatically if the same tag is updated with a different image.

CS Group will release a new chart updating its containers if a new version of the main container, significant changes, or critical vulnerabilities exist.
