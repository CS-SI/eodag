{{/*
Create the name of the service account to use
*/}}
{{- define "eodag-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{ default (include "common.names.fullname" .) .Values.serviceAccount.name | trunc 63 | trimSuffix "-" }}
{{- else -}}
    {{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "eodag-server.imagePullSecrets" -}}
{{- include "common.images.pullSecrets" (dict "images" (list .Values.image) "global" .Values.global) -}}
{{- end -}}

{{/*
Get the config secret.
*/}}
{{- define "eodag-server.configSecretName" -}}
{{- if .Values.configExistingSecret.name }}
    {{- printf "%s" (tpl .Values.configExistingSecret.name $) -}}
{{- else -}}
    {{- printf "%s-config" (include "common.names.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Get the client secret key.
*/}}
{{- define "eodag-server.configSecretKey" -}}
{{- if .Values.configExistingSecret.key }}
    {{- printf "%s" (tpl .Values.configExistingSecret.key $) -}}
{{- else -}}
    {{- "eodag.yml" -}}
{{- end -}}
{{- end -}}

{{/*
Return  the proper Storage Class
*/}}
{{- define "eodag-server.storageClass" -}}
{{- include "common.storage.class" (dict "persistence" .Values.persistence "global" .Values.global) -}}
{{- end -}}
