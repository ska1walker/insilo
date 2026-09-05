{{/*
Prüfsumme des gemeinsamen Geheimnisses.

Steht als Annotation an beiden Pod-Vorlagen, damit ein neu gewürfelter
Wert auch wirklich in beiden Pods ankommt.
*/}}
{{- define "insilo.internalChecksum" -}}
{{ .Release.Name }}-{{ .Release.Revision }}
{{- end -}}
