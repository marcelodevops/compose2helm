import os
import sys
import yaml
import re

# Sensitive env var detection
SENSITIVE_PATTERNS = re.compile(r"(PASSWORD|PASS|SECRET|KEY|TOKEN)", re.IGNORECASE)

# Database detection and defaults
DB_DEFAULTS = {
    "postgres": {
        "storage": "5Gi",
        "env": {
            "POSTGRES_USER": "admin",
            "POSTGRES_PASSWORD": "changeme",
            "POSTGRES_DB": "appdb"
        }
    },
    "mysql": {
        "storage": "5Gi",
        "env": {
            "MYSQL_ROOT_PASSWORD": "changeme",
            "MYSQL_DATABASE": "appdb",
            "MYSQL_USER": "admin",
            "MYSQL_PASSWORD": "changeme"
        }
    },
    "mariadb": {
        "storage": "5Gi",
        "env": {
            "MARIADB_ROOT_PASSWORD": "changeme",
            "MARIADB_DATABASE": "appdb",
            "MARIADB_USER": "admin",
            "MARIADB_PASSWORD": "changeme"
        }
    },
    "mongodb": {
        "storage": "5Gi",
        "env": {
            "MONGO_INITDB_ROOT_USERNAME": "admin",
            "MONGO_INITDB_ROOT_PASSWORD": "changeme"
        }
    },
    "redis": {
        "storage": "1Gi",
        "env": {}
    },
    "cassandra": {
        "storage": "10Gi",
        "env": {
            "CASSANDRA_USER": "admin",
            "CASSANDRA_PASSWORD": "changeme"
        }
    }
}

BASE_HELM = {
    "Chart.yaml": """apiVersion: v2
name: compose-chart
description: Generic Helm chart converted from Docker Compose
version: 0.5.0
appVersion: "1.0"
""",
    "templates/deployment.yaml": """{{- range $name, $svc := .Values.services }}
{{- if not $svc.isDatabase }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ $.Release.Name }}-{{ $name }}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{ $.Release.Name }}-{{ $name }}
  template:
    metadata:
      labels:
        app: {{ $.Release.Name }}-{{ $name }}
    spec:
      containers:
        - name: {{ $name }}
          image: {{ $svc.image }}
          ports:
            {{- range $svc.ports }}
            - containerPort: {{ .containerPort }}
            {{- end }}
          env:
            {{- range $key, $val := $svc.env }}
            {{- if $val.secretName }}
            - name: {{ $key }}
              valueFrom:
                secretKeyRef:
                  name: {{ $val.secretName }}
                  key: {{ $val.secretKey }}
            {{- else }}
            - name: {{ $key }}
              value: {{ $val | quote }}
            {{- end }}
            {{- end }}
          volumeMounts:
            {{- range $svc.volumeMounts }}
            - name: {{ $.Release.Name }}-{{ $name }}-pvc
              mountPath: {{ .mountPath }}
              subPath: {{ .subPath | default "" }}
            {{- end }}
      volumes:
        {{- if $svc.storage }}
        - name: {{ $.Release.Name }}-{{ $name }}-pvc
          persistentVolumeClaim:
            claimName: {{ $.Release.Name }}-{{ $name }}-pvc
        {{- end }}
---
{{- end }}
{{- end }}
""",
    "templates/statefulset.yaml": """{{- range $name, $svc := .Values.services }}
{{- if $svc.isDatabase }}
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ $.Release.Name }}-{{ $name }}
spec:
  serviceName: {{ $.Release.Name }}-{{ $name }}
  replicas: 1
  selector:
    matchLabels:
      app: {{ $.Release.Name }}-{{ $name }}
  template:
    metadata:
      labels:
        app: {{ $.Release.Name }}-{{ $name }}
    spec:
      containers:
        - name: {{ $name }}
          image: {{ $svc.image }}
          ports:
            {{- range $svc.ports }}
            - containerPort: {{ .containerPort }}
            {{- end }}
          env:
            {{- range $key, $val := $svc.env }}
            {{- if $val.secretName }}
            - name: {{ $key }}
              valueFrom:
                secretKeyRef:
                  name: {{ $val.secretName }}
                  key: {{ $val.secretKey }}
            {{- else }}
            - name: {{ $key }}
              value: {{ $val | quote }}
            {{- end }}
            {{- end }}
          volumeMounts:
            {{- range $svc.volumeMounts }}
            - name: {{ $.Release.Name }}-{{ $name }}-storage
              mountPath: {{ .mountPath }}
              subPath: {{ .subPath | default "" }}
            {{- end }}
  volumeClaimTemplates:
    {{- if $svc.storage }}
    - metadata:
        name: {{ $.Release.Name }}-{{ $name }}-storage
      spec:
        accessModes: [ "ReadWriteOnce" ]
        resources:
          requests:
            storage: {{ $svc.storage }}
    {{- end }}
---
{{- end }}
{{- end }}
""",
    "templates/service.yaml": """{{- range $name, $svc := .Values.services }}
{{- if $svc.ports }}
apiVersion: v1
kind: Service
metadata:
  name: {{ $.Release.Name }}-{{ $name }}
spec:
  type: ClusterIP
  ports:
    {{- range $svc.ports }}
    - port: {{ .containerPort }}
      targetPort: {{ .containerPort }}
      {{- if .servicePort }}
      nodePort: {{ .servicePort }}
      {{- end }}
    {{- end }}
  selector:
    app: {{ $.Release.Name }}-{{ $name }}
---
{{- end }}
{{- end }}
""",
    "templates/pvc.yaml": """{{- range $name, $svc := .Values.services }}
{{- if and $svc.storage (not $svc.isDatabase) }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ $.Release.Name }}-{{ $name }}-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {{ $svc.storage }}
---
{{- end }}
{{- end }}
""",
    "templates/secrets.yaml": """{{- range $name, $svc := .Values.services }}
{{- if $svc.secrets }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ $.Release.Name }}-{{ $name }}-secret
type: Opaque
stringData:
  {{- range $key, $val := $svc.secrets }}
  {{ $key }}: {{ $val | quote }}
  {{- end }}
---
{{- end }}
{{- end }}
"""
}
BASE_HELM.update({
    "templates/externalsecret.yaml": """{{- if eq .Values.secretProvider "external" }}
{{- range $name, $svc := .Values.services }}
{{- if $svc.secrets }}
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: {{ $.Release.Name }}-{{ $name }}-externalsecret
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: SecretStore
    name: {{ $.Values.externalSecretStore | default "default-secret-store" }}
  target:
    name: {{ $.Release.Name }}-{{ $name }}-secret
  data:
    {{- range $key, $_ := $svc.secrets }}
    - secretKey: {{ $key }}
      remoteRef:
        key: {{ printf "%s/%s/%s" $.Release.Name $name $key | lower }}
    {{- end }}
---
{{- end }}
{{- end }}
{{- end }}
"""
})
BASE_HELM.update({
    "templates/secretstore.yaml": """{{- if eq .Values.secretProvider "external" }}
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: {{ .Values.externalSecretStore | default "default-secret-store" }}
spec:
  {{- if eq .Values.externalSecretStore "vault" }}
  provider:
    vault:
      server: {{ .Values.externalSecretConfig.vault.server | quote }}
      path: {{ .Values.externalSecretConfig.vault.path | quote }}
      version: v2
      auth:
        tokenSecretRef:
          name: {{ .Values.externalSecretConfig.vault.auth.tokenSecretRef }}
          key: token
  {{- else if eq .Values.externalSecretStore "aws" }}
  provider:
    aws:
      service: SecretsManager
      region: {{ .Values.externalSecretConfig.aws.region | quote }}
      auth:
        secretRef:
          accessKeyIDSecretRef:
            name: {{ .Values.externalSecretConfig.aws.auth.secretRef }}
            key: access-key
          secretAccessKeySecretRef:
            name: {{ .Values.externalSecretConfig.aws.auth.secretRef }}
            key: secret-access-key
  {{- else if eq .Values.externalSecretStore "gcp" }}
  provider:
    gcpsm:
      projectID: {{ .Values.externalSecretConfig.gcp.projectID | quote }}
      auth:
        secretRef:
          secretAccessKeySecretRef:
            name: {{ .Values.externalSecretConfig.gcp.auth.secretRef }}
            key: secret-access-key
  {{- end }}
{{- end }}
"""
})

# When writing helm chart, skip internal secrets if external is chosen
def write_helm_chart(output_dir, values):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "templates"), exist_ok=True)

    with open(os.path.join(output_dir, "values.yaml"), "w") as f:
        yaml.dump(values, f, default_flow_style=False, sort_keys=False)

    for filename, content in BASE_HELM.items():
        if values.get("secretProvider", "internal") == "external" and filename.endswith("secrets.yaml"):
            continue  # skip internal secrets
        path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)


def docker_compose_to_values(compose_file):
    with open(compose_file, "r") as f:
        compose = yaml.safe_load(f)

    services = {}
    for name, svc in compose.get("services", {}).items():
        image = svc.get("image", "")
        image_lower = image.lower()
        matched_db = next((db for db in DB_DEFAULTS if db in image_lower), None)
        is_db = matched_db is not None

        service_entry = {
            "image": image,
            "ports": [],
            "env": {},
            "volumeMounts": [],
            "isDatabase": is_db,
            "secrets": {}
        }

        # Ports
        for p in svc.get("ports", []):
            if isinstance(p, str):
                if ":" in p:
                    host, container = p.split(":")
                    service_entry["ports"].append({
                        "containerPort": int(container),
                        "servicePort": int(host)
                    })
                else:
                    service_entry["ports"].append({"containerPort": int(p)})
            elif isinstance(p, int):
                service_entry["ports"].append({"containerPort": p})

        # Environment
        env = svc.get("environment", {})
        if isinstance(env, list):  # ["A=1", "B=2"]
            for e in env:
                k, v = e.split("=", 1)
                env[k] = v

        if isinstance(env, dict):
            for k, v in env.items():
                if SENSITIVE_PATTERNS.search(k):
                    secret_name = f"{{{{ $.Release.Name }}}}-{name}-secret"
                    service_entry["env"][k] = {"secretName": secret_name, "secretKey": k}
                    service_entry["secrets"][k] = v
                else:
                    service_entry["env"][k] = v

        # Volumes
        for v in svc.get("volumes", []):
            if isinstance(v, str):
                parts = v.split(":")
                if len(parts) == 2:
                    host, container = parts
                    service_entry["volumeMounts"].append({
                        "mountPath": container,
                        "subPath": os.path.basename(host)
                    })
                    if "storage" not in service_entry:
                        service_entry["storage"] = "1Gi"
                else:
                    service_entry["volumeMounts"].append({"mountPath": v})

        # Database defaults
        if matched_db:
            db_defaults = DB_DEFAULTS[matched_db]
            service_entry.setdefault("storage", db_defaults["storage"])
            for k, v in db_defaults["env"].items():
                if SENSITIVE_PATTERNS.search(k):
                    secret_name = f"{{{{ $.Release.Name }}}}-{name}-secret"
                    service_entry["env"].setdefault(k, {"secretName": secret_name, "secretKey": k})
                    service_entry["secrets"].setdefault(k, v)
                else:
                    service_entry["env"].setdefault(k, v)

        services[name] = service_entry

    return {"services": services}


def write_helm_chart(output_dir, values):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "templates"), exist_ok=True)

    # values.yaml
    with open(os.path.join(output_dir, "values.yaml"), "w") as f:
        yaml.dump(values, f, default_flow_style=False, sort_keys=False)

    # templates
    for filename, content in BASE_HELM.items():
        path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python compose2helm.py <docker-compose.yml> <output-dir>")
        sys.exit(1)

    compose_file = sys.argv[1]
    output_dir = sys.argv[2]

    values = docker_compose_to_values(compose_file)
    write_helm_chart(output_dir, values)
    print(f"✅ Helm chart with Secrets (values-driven) generated in {output_dir}")
