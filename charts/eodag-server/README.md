# EODAG Server

This chart bootstraps a [EODAG Server](https://github.com/CS-SI/eodag) deployment on a [Kubernetes](http://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

## TL;DR

```console
helm repo add eodag TODO --username <username> --password <password>
helm install my-release eodag/eodag-server
```

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure

## Installing the Chart

To install the chart with the release name `my-release`:

```console
helm repo add my-repo TODO
helm install my-release my-repo/eodag-server
```

These commands deploy EODAG Server on the Kubernetes cluster in the default configuration.

> **Tip**: List all releases using `helm list`

## Uninstalling the Chart


To uninstall the `my-release` deployment:

```bash
helm uninstall my-release
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

All components are removed except the PrivateVolumeClaim if you use a persistent storage solution.

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

### EODAG parameters

| Name                                                | Description                                                                                                        | Value                    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------ |
| `image.registry`                                    | EODAG image registry                                                                                               | `TODO`                   |
| `image.repository`                                  | EODAG image repository                                                                                             | `eodag/eodag-server`     |
| `image.tag`                                         | EODAG image tag (immutable tags are recommended)                                                                   | `2.9.0`                  |
| `image.digest`                                      | EODAG image digest in the way sha256:aa.... Please note this parameter, if set, will override the tag              | `""`                     |
| `image.pullPolicy`                                  | EODAG image pull policy                                                                                            | `IfNotPresent`           |
| `image.pullSecrets`                                 | Specify docker-registry secret names as an array                                                                   | `[]`                     |
| `replicaCount`                                      | Number of EODAG replicas                                                                                           | `1`                      |
| `customLivenessProbe`                               | Custom livenessProbe that overrides the default one                                                                | `{}`                     |
| `customReadinessProbe`                              | Custom readinessProbe that overrides the default one                                                               | `{}`                     |
| `resources.limits`                                  | The resources limits for the EODAG containers                                                                      | `{}`                     |
| `resources.requests`                                | The requested resources for the EODAG containers                                                                   | `{}`                     |
| `podSecurityContext.enabled`                        | Enabled EODAG pods' Security Context                                                                               | `true`                   |
| `podSecurityContext.fsGroup`                        | Set EODAG pod's Security Context fsGroup                                                                           | `1001`                   |
| `containerSecurityContext.enabled`                  | Enabled EODAG containers' Security Context                                                                         | `true`                   |
| `containerSecurityContext.runAsUser`                | Set EODAG containers' Security Context runAsUser                                                                   | `1001`                   |
| `containerSecurityContext.allowPrivilegeEscalation` | Set EODAG containers' Security Context allowPrivilegeEscalation                                                    | `false`                  |
| `containerSecurityContext.capabilities.drop`        | Set EODAG containers' Security Context capabilities to be dropped                                                  | `["all"]`                |
| `containerSecurityContext.readOnlyRootFilesystem`   | Set EODAG containers' Security Context readOnlyRootFilesystem                                                      | `false`                  |
| `containerSecurityContext.runAsNonRoot`             | Set EODAG container's Security Context runAsNonRoot                                                                | `true`                   |
| `command`                                           | Override default container command (useful when using custom images)                                               | `[]`                     |
| `args`                                              | Override default container args (useful when using custom images). Overrides the defaultArgs.                      | `[]`                     |
| `containerPorts.http`                               | EODAG application HTTP port number                                                                                 | `8080`                   |
| `hostAliases`                                       | EODAG pods host aliases                                                                                            | `[]`                     |
| `podLabels`                                         | Extra labels for EODAG pods                                                                                        | `{}`                     |
| `podAnnotations`                                    | Annotations for EODAG pods                                                                                         | `{}`                     |
| `podAffinityPreset`                                 | Pod affinity preset. Ignored if `affinity` is set. Allowed values: `soft` or `hard`                                | `""`                     |
| `podAntiAffinityPreset`                             | Pod anti-affinity preset. Ignored if `affinity` is set. Allowed values: `soft` or `hard`                           | `soft`                   |
| `nodeAffinityPreset.type`                           | Node affinity preset type. Ignored if `affinity` is set. Allowed values: `soft` or `hard`                          | `""`                     |
| `nodeAffinityPreset.key`                            | Node label key to match. Ignored if `affinity` is set                                                              | `""`                     |
| `nodeAffinityPreset.values`                         | Node label values to match. Ignored if `affinity` is set                                                           | `[]`                     |
| `affinity`                                          | Affinity for EODAG pods assignment                                                                                 | `{}`                     |
| `nodeSelector`                                      | Node labels for EODAG pods assignment                                                                              | `{}`                     |
| `tolerations`                                       | Tolerations for EODAG pods assignment                                                                              | `[]`                     |
| `schedulerName`                                     | Name of the k8s scheduler (other than default)                                                                     | `""`                     |
| `shareProcessNamespace`                             | Enable shared process namespace in a pod.                                                                          | `false`                  |
| `topologySpreadConstraints`                         | Topology Spread Constraints for pod assignment                                                                     | `[]`                     |
| `updateStrategy.type`                               | EODAG statefulset strategy type                                                                                    | `RollingUpdate`          |
| `priorityClassName`                                 | EODAG pods' priorityClassName                                                                                      | `""`                     |
| `runtimeClassName`                                  | Name of the runtime class to be used by pod(s)                                                                     | `""`                     |
| `lifecycleHooks`                                    | for the EODAG container(s) to automate configuration before or after startup                                       | `{}`                     |
| `extraEnvVars`                                      | Array with extra environment variables to add to EODAG nodes                                                       | `[]`                     |
| `extraEnvVarsCM`                                    | Name of existing ConfigMap containing extra env vars for EODAG nodes                                               | `""`                     |
| `extraEnvVarsSecret`                                | Name of existing Secret containing extra env vars for EODAG nodes                                                  | `""`                     |
| `extraVolumes`                                      | Optionally specify extra list of additional volumes for the EODAG pod(s)                                           | `[]`                     |
| `extraVolumeMounts`                                 | Optionally specify extra list of additional volumeMounts for the EODAG container(s)                                | `[]`                     |
| `sidecars`                                          | Add additional sidecar containers to the EODAG pod(s)                                                              | `[]`                     |
| `initContainers`                                    | Add additional init containers to the EODAG pod(s)                                                                 | `[]`                     |
| `service.type`                                      | Kubernetes service type                                                                                            | `ClusterIP`              |
| `service.http.enabled`                              | Enable http port on service                                                                                        | `true`                   |
| `service.ports.http`                                | EODAG service HTTP port                                                                                            | `8080`                   |
| `service.nodePorts`                                 | Specify the nodePort values for the LoadBalancer and NodePort service types.                                       | `{}`                     |
| `service.sessionAffinity`                           | Control where client requests go, to the same pod or round-robin                                                   | `None`                   |
| `service.sessionAffinityConfig`                     | Additional settings for the sessionAffinity                                                                        | `{}`                     |
| `service.clusterIP`                                 | EODAG service clusterIP IP                                                                                         | `""`                     |
| `service.loadBalancerIP`                            | loadBalancerIP for the SuiteCRM Service (optional, cloud specific)                                                 | `""`                     |
| `service.loadBalancerSourceRanges`                  | Address that are allowed when service is LoadBalancer                                                              | `[]`                     |
| `service.externalTrafficPolicy`                     | Enable client source IP preservation                                                                               | `Cluster`                |
| `service.annotations`                               | Additional custom annotations for EODAG service                                                                    | `{}`                     |
| `service.extraPorts`                                | Extra port to expose on EODAG service                                                                              | `[]`                     |
| `ingress.enabled`                                   | Enable the creation of an ingress for the EODAG                                                                    | `false`                  |
| `ingress.pathType`                                  | Path type for the EODAG ingress                                                                                    | `ImplementationSpecific` |
| `ingress.apiVersion`                                | Ingress API version for the EODAG ingress                                                                          | `""`                     |
| `ingress.hostname`                                  | Ingress hostname for the EODAG ingress                                                                             | `eodag.local`            |
| `ingress.annotations`                               | Annotations for the EODAG ingress. To enable certificate autogeneration, place here your cert-manager annotations. | `{}`                     |
| `ingress.tls`                                       | Enable TLS for the EODAG ingress                                                                                   | `false`                  |
| `ingress.extraHosts`                                | Extra hosts array for the EODAG ingress                                                                            | `[]`                     |
| `ingress.path`                                      | Path array for the EODAG ingress                                                                                   | `/`                      |
| `ingress.extraPaths`                                | Extra paths for the EODAG ingress                                                                                  | `[]`                     |
| `ingress.extraTls`                                  | Extra TLS configuration for the EODAG ingress                                                                      | `[]`                     |
| `ingress.secrets`                                   | Secrets array to mount into the Ingress                                                                            | `[]`                     |
| `ingress.ingressClassName`                          | IngressClass that will be be used to implement the Ingress (Kubernetes 1.18+)                                      | `""`                     |
| `ingress.selfSigned`                                | Create a TLS secret for this ingress record using self-signed certificates generated by Helm                       | `false`                  |
| `ingress.servicePort`                               | Backend service port to use                                                                                        | `http`                   |
| `ingress.extraRules`                                | Additional rules to be covered with this ingress record                                                            | `[]`                     |
| `serviceAccount.create`                             | Specifies whether a ServiceAccount should be created                                                               | `true`                   |
| `serviceAccount.name`                               | The name of the ServiceAccount to use.                                                                             | `""`                     |
| `serviceAccount.annotations`                        | Additional custom annotations for the ServiceAccount                                                               | `{}`                     |
| `serviceAccount.automountServiceAccountToken`       | Automount service account token for the server service account                                                     | `true`                   |


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
