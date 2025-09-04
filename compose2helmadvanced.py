import os
import sys
import yaml

# List of database images to detect
DB_IMAGES = ["postgres", "mysql", "mariadb", "mongodb", "redis", "cassandra"]

BASE_HELM = {
    "Chart.yaml": """apiVersion: v2
name: compose-chart
description: Generic Helm chart converted from Docker Compose
version: 0.2.0
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
            - name: {{ $key }}
              value: {{ $val | quote }}
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
            - name: {{ $key }}
              value: {{ $val | quote }}
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
"""
}


def docker_compose_to_values(compose_file):
    with open(compose_file, "r") as f:
        compose = yaml.safe_load(f)

    services = {}
    for name, svc in compose.get("services", {}).items():
        image = svc.get("image", "")
        is_db = any(db in image.lower() for db in DB_IMAGES)

        service_entry = {
            "image": image,
            "ports": [],
            "env": {},
            "volumeMounts": [],
            "isDatabase": is_db,
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
                service_entry["env"][k] = v
        elif isinstance(env, dict):
            service_entry["env"] = env

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
                    service_entry["storage"] = "1Gi"  # default size
                else:
                    service_entry["volumeMounts"].append({"mountPath": v})

        services[name] = service_entry

    return {"services": services}


def write_helm_chart(output_dir, values):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "templates"), exist_ok=True)

    # values.yaml
    with open(os.path.join(output_dir, "values.yaml"), "w") as f:
        yaml.dump(values, f, default_flow_style=False, sort_keys=False)

    # static files
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
    print(f"✅ Helm chart generated in {output_dir}")
