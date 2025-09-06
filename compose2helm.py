import os
import yaml
import shutil

# --------------------------
# Config
# --------------------------
SENSITIVE_KEYS = ["PASSWORD", "SECRET", "KEY", "TOKEN"]
BASE_HELM_TEMPLATES = ["deployment.yaml", "secrets.yaml", "externalsecret.yaml", "secretstore.yaml"]

# --------------------------
# Helper Functions
# --------------------------
def is_sensitive(key: str) -> bool:
    return any(word in key.upper() for word in SENSITIVE_KEYS)

def safe_mkdir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def detect_ingress(name, svc):
    ingress_conf = None
    rules = []

    # Case 1: Ports
    for port in svc.get("ports", []):
        if isinstance(port, dict):
            container_port = port.get("target") or port.get("containerPort")
            published = port.get("published")
        else:
            # Docker shorthand "80:80"
            if ":" in str(port):
                published, container_port = str(port).split(":")
            else:
                container_port = str(port)
                published = None

        container_port = int(container_port)

        if container_port in [80, 443]:
            rules.append({
                "host": f"{name}.local",  # default host, override later in values.yaml
                "path": "/",
                "port": container_port
            })

    # Case 2: Labels
    annotations = {}
    for key, val in (svc.get("labels", {}) or {}).items():
        if key.startswith("traefik.") or key.startswith("nginx.ingress."):
            annotations[key] = val

    if rules or annotations:
        ingress_conf = {
            "annotations": annotations,
            "rules": rules,
            "tls": []  # left empty, user can override
        }

    return ingress_conf


# --------------------------
# Compose Parser
# --------------------------
def parse_compose(compose_file):
    with open(compose_file) as f:
        compose = yaml.safe_load(f)

    values = {
        "secretProvider": "internal",
        "externalSecretStore": "default-secret-store",
        "externalSecretScope": "namespace",
        "services": {}
    }

    top_secrets = compose.get("secrets", {})

    for name, svc in compose.get("services", {}).items():
        service_conf = {
            "image": svc.get("image"),
            "env": {},
            "secrets": {},
            "secretMounts": [],
            "ports": svc.get("ports", []),
            "storage": svc.get("volumes", []),
            "volumeMounts": svc.get("volume_mounts", []),
        }

        # Environment variables
        for env, val in (svc.get("environment", {}) or {}).items():
            if is_sensitive(env):
                service_conf["secrets"][env] = "<to-be-generated>"
            else:
                service_conf["env"][env] = val

        # Secrets (file-based)
        for sec in svc.get("secrets", []):
            if isinstance(sec, dict):
                source = sec["source"]
                mount_path = sec.get("target", f"/run/secrets/{source}")
            else:
                source = sec
                mount_path = f"/run/secrets/{source}"

            sec_def = top_secrets.get(source, {})
            service_conf["secretMounts"].append({
                "name": source,
                "mountPath": mount_path,
                "items": [{"key": source, "path": os.path.basename(mount_path)}]
            })

            if "file" in sec_def:
                service_conf["secrets"][source.upper()] = f"<from-file:{sec_def['file']}>"
            else:
                service_conf["secrets"][source.upper()] = "<to-be-generated>"

        # Ingress detection
        ingress_conf = detect_ingress(name, svc)
        if ingress_conf:
            service_conf["ingress"] = ingress_conf

        values["services"][name] = service_conf

    return values

# --------------------------
# Helm Chart Writer
# --------------------------
def write_helm_chart(values, output_dir="helm-chart"):
    safe_mkdir(output_dir)
    templates_dir = os.path.join(output_dir, "templates")
    safe_mkdir(templates_dir)

    # values.yaml
    with open(os.path.join(output_dir, "values.yaml"), "w") as f:
        yaml.dump(values, f, default_flow_style=False, sort_keys=False)

    # Copy templates
    for template in BASE_HELM_TEMPLATES:
        src = os.path.join("helm_templates", template)
        dst = os.path.join(templates_dir, template)
        shutil.copyfile(src, dst)

    print(f"Helm chart generated at: {output_dir}")

# --------------------------
# Main
# --------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Docker Compose → Helm Chart Generator")
    parser.add_argument("compose_file", help="Path to docker-compose.yml")
    parser.add_argument("--output", default="helm-chart", help="Output directory for Helm chart")
    args = parser.parse_args()

    values = parse_compose(args.compose_file)
    write_helm_chart(values, args.output)
