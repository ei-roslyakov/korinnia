{{- define "korinnia.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "korinnia.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else if contains (include "korinnia.name" .) .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name (include "korinnia.name" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "korinnia.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "korinnia.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector labels for one component: include "korinnia.selectorLabels" (list . "backend") */}}
{{- define "korinnia.selectorLabels" -}}
{{- $ctx := index . 0 -}}
app.kubernetes.io/name: {{ include "korinnia.name" $ctx }}
app.kubernetes.io/instance: {{ $ctx.Release.Name }}
app.kubernetes.io/component: {{ index . 1 }}
{{- end }}

{{- define "korinnia.image" -}}
{{- $ctx := index . 0 -}}
{{- $img := index . 1 -}}
{{- printf "%s/%s:%s" $ctx.Values.image.registry $img.repository (default $ctx.Chart.AppVersion $img.tag) }}
{{- end }}

{{- define "korinnia.secretName" -}}
{{- default (printf "%s-secrets" (include "korinnia.fullname" .)) .Values.secrets.existingSecret }}
{{- end }}

{{- define "korinnia.dbSecretName" -}}
{{- default (printf "%s-db" (include "korinnia.fullname" .)) .Values.database.existingSecret }}
{{- end }}

{{- define "korinnia.mediaClaim" -}}
{{- default (printf "%s-media" (include "korinnia.fullname" .)) .Values.persistence.existingClaim }}
{{- end }}

{{/* Environment shared by backend and worker. */}}
{{- define "korinnia.backendEnv" -}}
- name: APP_VERSION
  value: {{ .Chart.AppVersion | quote }}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "korinnia.dbSecretName" . }}
      key: {{ .Values.database.passwordKey }}
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "korinnia.secretName" . }}
      key: {{ .Values.secrets.keys.secretKey }}
- name: SUPERADMIN_EMAIL
  valueFrom:
    secretKeyRef:
      name: {{ include "korinnia.secretName" . }}
      key: {{ .Values.secrets.keys.superadminEmail }}
      optional: true
- name: SUPERADMIN_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "korinnia.secretName" . }}
      key: {{ .Values.secrets.keys.superadminPassword }}
      optional: true
{{- end }}

{{- define "korinnia.mediaVolume" -}}
- name: media
  persistentVolumeClaim:
    claimName: {{ include "korinnia.mediaClaim" . }}
{{- end }}
