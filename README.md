## Scripts to convert docker-compose to helm charts

Helm charts are more structured than Docker Compose files, but the concepts map fairly well:

docker-compose.yml → Helm values.yaml + Kubernetes manifests (templates/)

services → Deployments / StatefulSets + Services

volumes → PersistentVolumeClaims / emptyDir

networks → Kubernetes networking (usually just Services)

environment variables → Pod env in Deployments

✅ Example Conversion
Docker Compose
```yaml
version: "3"
services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
    environment:
      - NGINX_ENV=production
    volumes:
      - ./html:/usr/share/nginx/html
  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=admin
      - POSTGRES_PASSWORD=secret
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

#### Helm Chart Structure

```shell
mychart/
  Chart.yaml
  values.yaml
  templates/
    deployment-web.yaml
    service-web.yaml
    deployment-db.yaml
    service-db.yaml
    pvc-db.yaml
```
Chart.yaml

```yaml
apiVersion: v2
name: mychart
description: A Helm chart converted from Docker Compose
version: 0.1.0
appVersion: "1.0"
values.yaml
web:
  image: nginx:latest
  port: 80
  servicePort: 8080
  env:
    NGINX_ENV: production
  volumeMount: ./html

db:
  image: postgres:15
  env:
    POSTGRES_USER: admin
    POSTGRES_PASSWORD: secret
  storage: 1Gi

```
And generates
- templates/deployment-web.yaml
- templates/service-web.yaml
- templates/deployment-db.yaml
- templates/pvc-db.yaml

This is a basic implementation, then enhanced it with:

- ConfigMaps for configs instead of inline env

- Ingress instead of NodePort

- StatefulSet for databases instead of Deployment

- Resource limits & probes





Improvements
- generic converter template so you can drop in your docker-compose.yml and get Helm scaffolding.
- Build a base Helm chart structure (Chart.yaml, values.yaml, templates/)
- Create template snippets that map Compose services → Deployments, Services, PVCs
- Make it values-driven so you just edit values.yaml instead of modifying manifests

### Helm Chart Structure
```shell
compose-chart/
  Chart.yaml
  values.yaml
  templates/
    _helpers.tpl
    deployment.yaml
    service.yaml
    pvc.yaml
```
### Chart.yaml
```yaml
apiVersion: v2
name: compose-chart
description: Generic Helm chart converted from Docker Compose
version: 0.1.0
appVersion: "1.0"
```
### values.yaml (example input for multiple services)

```yaml
services:
  web:
    image: nginx:latest
    ports:
      - containerPort: 80
        servicePort: 8080
    env:
      NGINX_ENV: production
    volumeMounts:
      - mountPath: /usr/share/nginx/html
        subPath: html
    storage: 1Gi

  db:
    image: postgres:15
    env:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret
    volumeMounts:
      - mountPath: /var/lib/postgresql/data
        subPath: dbdata
    storage: 5Gi
```
### Generates
1. templates/deployment.yaml
2. templates/service.yaml
3. templates/pvc.yaml

✅ With this setup:

You only edit values.yaml to add services.

Each service automatically gets a Deployment, optional Service, and optional PVC.

You can drop in a Docker Compose service definition and just translate its fields into the values.yaml.



- Reads your docker-compose.yml

- Extracts services, environment variables, ports, volumes

- Generates:

- - values.yaml

- - Chart.yaml

- - Kubernetes templates (deployment.yaml, service.yaml, pvc.yaml)


🔧 Usage
```bash
python compose2helm.py docker-compose.yml ./mychart
```
This will create:
```bash
mychart/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
    pvc.yaml
```

⚠️ Limitations:

Maps only basic image, ports, environment, volumes

Doesn’t yet handle networks, configs, secrets, or advanced Compose features

Database services should ideally be StatefulSets (not Deployments)


I’ve extended the script so it detects common databases (postgres, mysql, mariadb, mongodb, redis, cassandra) and generates StatefulSets for them, while everything else stays as a Deployment.

Here’s what added to compose2helm.py:
```python

# List of database images to detect
DB_IMAGES = ["postgres", "mysql", "mariadb", "mongodb", "redis", "cassandra"]

```

🔧 Usage
```bash
python compose2helm.py docker-compose.yml ./mychart

```

### 🆕 Improvements
- Database detection → isDatabase: true added in values.yaml

- Generates StatefulSet (with volumeClaimTemplates) instead of Deployment for DBs

- Regular services remain Deployments

- PVCs skipped for DBs (since StatefulSets already handle PVCs)


- Detects common databases (postgres, mysql, mariadb, mongodb, redis, cassandra)

- Assigns default storage sizes (e.g., Postgres/MySQL → 5Gi)

- Populates default environment variables if missing (e.g., POSTGRES_USER, POSTGRES_PASSWORD)




🔧 Usage
```bash
python compose2helm.py docker-compose.yml ./mychart
```
🆕 New Features
- Auto-detects databases → StatefulSet with volumeClaimTemplates

- Assigns default storage sizes (e.g., postgres → 5Gi)

- Injects default env vars (e.g., Postgres gets POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)

- If you already define env vars in Compose, they override the defaults

⚡ Example:
```yaml
services:
  db:
    image: postgres:15
Produces in values.yaml:

services:
  db:
    image: postgres:15
    ports: []
    env:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: appdb
    volumeMounts: []
    isDatabase: true
    storage: 5Gi

```
 Updated plan

I’ve updated the script so it:

- Detects sensitive environment variables (PASSWORD, PASS, SECRET, KEY, etc.)

- Moves them into Kubernetes Secrets

- Replaces their values with valueFrom.secretKeyRef in Deployments/StatefulSets

- Writes a templates/secrets.yaml file with all secrets


🔧 Usage
```bash
python compose2helm.py docker-compose.yml ./mychart
```
🆕 What Changed
- Detects sensitive vars → generates templates/secrets.yaml

- Deployments/StatefulSets reference secrets with valueFrom.secretKeyRef

- Passwords and tokens are not stored in values.yaml

### ⚡ Example with Postgres:
```yaml
services:
  db:
    image: postgres:15
Produces values.yaml:

services:
  db:
    image: postgres:15
    ports: []
    env:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD:
        secretName: "{{ $.Release.Name }}-db-secret"
        secretKey: POSTGRES_PASSWORD
      POSTGRES_DB: appdb
    volumeMounts: []
    isDatabase: true
    secrets:
      POSTGRES_PASSWORD: changeme
    storage: 5Gi
```
And templates/secrets.yaml:
```yaml

apiVersion: v1
kind: Secret
metadata:
  name: {{ $.Release.Name }}-db-secret
type: Opaque
stringData:
  POSTGRES_PASSWORD: "changeme"

```

Now the secrets configurable via values.yaml.
Instead of hardcoding secret values inside templates/secrets.yaml, we’ll:

Put default secret values in values.yaml (e.g., services.db.secrets.POSTGRES_PASSWORD)

Reference those values in the Helm template with stringData:

Allow overrides at install/upgrade time via --set services.db.secrets.POSTGRES_PASSWORD=supersecret






🔧 Example
docker-compose.yml

```yaml
services:
  db:
    image: postgres:15
Generated values.yaml

services:
  db:
    image: postgres:15
    ports: []
    env:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD:
        secretName: "{{ $.Release.Name }}-db-secret"
        secretKey: POSTGRES_PASSWORD
      POSTGRES_DB: appdb
    volumeMounts: []
    isDatabase: true
    secrets:
      POSTGRES_PASSWORD: changeme
    storage: 5Gi
```
Generated templates/secrets.yaml
```yaml
{{- range $name, $svc := .Values.services }}
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

```
🚀 Usage
Install with default password:
```bash
helm install mydb ./mychart
```
Override password at install:
```bash
helm install mydb ./mychart --set services.db.secrets.POSTGRES_PASSWORD=myStrongPass
```
We’ll extend the generator so you can choose how secrets are managed:

Inline Kubernetes Secret (default)

ExternalSecrets Operator (for AWS Secrets Manager, Vault, GCP, etc.)

🔑 New Features
Added a secretProvider option at the root of values.yaml:
```yaml
secretProvider: internal   # options: internal | external
externalSecretStore: vault # optional: vault | aws | gcp
```
If secretProvider=internal, we generate templates/secrets.yaml (like now).

If secretProvider=external, we instead generate templates/externalsecret.yaml using the Kubernetes External Secrets API.



📝 Example Values
Case 1 – Internal Secrets (default)
```yaml
secretProvider: internal

services:
  db:
    image: postgres:15
    secrets:
      POSTGRES_PASSWORD: changeme
```
→ Generates Secret in templates/secrets.yaml.

Case 2 – External Secrets (Vault)
```yaml
secretProvider: external
externalSecretStore: vault

services:
  db:
    image: postgres:15
    secrets:
      POSTGRES_PASSWORD: placeholder
```
→ Generates an ExternalSecret in templates/externalsecret.yaml:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: myrelease-db-externalsecret
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: SecretStore
    name: vault
  target:
    name: myrelease-db-secret
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: myrelease/db/postgres_password


```
🚀 Usage
Internal secret (Helm-managed):
```

helm install mydb ./mychart --set services.db.secrets.POSTGRES_PASSWORD=myPass

```
External secret (Vault-managed):
```
helm install mydb ./mychart --set secretProvider=external --set externalSecretStore=vault
```

🔑 Plan
Extend values.yaml with a new section:
```yaml
secretProvider: external
externalSecretStore: vault   # vault | aws | gcp
externalSecretConfig:
  vault:
    server: "http://vault.vault:8200"
    path: "secret/"
    auth:
      tokenSecretRef: vault-token
  aws:
    region: "us-east-1"
    auth:
      secretRef: aws-credentials

```
Script generates:

- SecretStore (per provider)

- ExternalSecret (as before)


📝 Example Values
Case 1 – Vault

```yaml
secretProvider: external
externalSecretStore: vault
externalSecretConfig:
  vault:
    server: "http://vault.vault:8200"
    path: "secret/"
    auth:
      tokenSecretRef: vault-token

services:
  db:
    image: postgres:15
    secrets:
      POSTGRES_PASSWORD: placeholder

```
→ Produces SecretStore:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault
spec:
  provider:
    vault:
      server: "http://vault.vault:8200"
      path: "secret/"
      version: v2
      auth:
        tokenSecretRef:
          name: vault-token
          key: token

```

Case 2 – AWS Secrets Manager

```yaml
secretProvider: external
externalSecretStore: aws
externalSecretConfig:
  aws:
    region: "us-east-1"
    auth:
      secretRef: aws-credentials

```
→ Produces SecretStore:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws
spec:
  provider:
    aws:
      service: SecretsManager
      region: "us-east-1"
      auth:
        secretRef:
          accessKeyIDSecretRef:
            name: aws-credentials
            key: access-key
          secretAccessKeySecretRef:
            name: aws-credentials
            key: secret-access-key

```
⚡ This makes the chart fully self-contained: it can bootstrap both the SecretStore and ExternalSecret.

Now it supports cluster-wide SecretStores (ClusterSecretStore) in addition to namespace-local SecretStore

So it can be  fully flexible 🚀

Add support for both namespace-scoped SecretStore and cluster-scoped ClusterSecretStore.

🔑 Plan
Extend values.yaml with a toggle:
```yaml
secretProvider: external
externalSecretStore: vault   # vault | aws | gcp
externalSecretScope: namespace  # or cluster
externalSecretConfig:
  vault:
    server: "http://vault.vault:8200"
    path: "secret/"
    auth:
      tokenSecretRef: vault-token

```
Script generates either a SecretStore (default) or a ClusterSecretStore if externalSecretScope=cluster.




📝 Example Values
Case 1 – Namespace-scoped Vault (default)

```yaml
secretProvider: external
externalSecretStore: vault
externalSecretScope: namespace
externalSecretConfig:
  vault:
    server: "http://vault.vault:8200"
    path: "secret/"
    auth:
      tokenSecretRef: vault-token

```
Produces:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault
spec:
  provider:
    vault:
      server: "http://vault.vault:8200"
      path: "secret/"
      version: v2
      auth:
        tokenSecretRef:
          name: vault-token
          key: token
```


Case 2 – Cluster-scoped AWS

```yaml
secretProvider: external
externalSecretStore: aws
externalSecretScope: cluster
externalSecretConfig:
  aws:
    region: "us-east-1"
    auth:
      secretRef: aws-credentials

```
Produces:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws
spec:
  provider:
    aws:
      service: SecretsManager
      region: "us-east-1"
      auth:
        secretRef:
          accessKeyIDSecretRef:
            name: aws-credentials
            key: access-key
          secretAccessKeySecretRef:
            name: aws-credentials
            key: secret-access-key

```
👉 Now the script can generate both namespaced and cluster-wide SecretStores.



📝 Example Scenarios
Case 1 – Generate new Vault SecretStore (default)

```yaml
secretProvider: external
externalSecretStore: vault
externalSecretScope: namespace
useExistingSecretStore: false
externalSecretConfig:
  vault:
    server: "http://vault.vault:8200"
    path: "secret/"
    auth:
      tokenSecretRef: vault-token

```


✅ Generates a SecretStore and ExternalSecrets.

Case 2 – Use existing ClusterSecretStore

```yaml
secretProvider: external
useExistingSecretStore: true
existingSecretStoreRef:
  kind: ClusterSecretStore
  name: global-vault-store

```
✅ Skips SecretStore generation, makes all ExternalSecrets reference ClusterSecretStore/global-vault-store.

👉 This makes the Helm chart safe for both self-contained deployments and shared enterprise setups.


How the sectres-store.yaml template works:

Only renders if:

- secretProvider: external

- useExistingSecretStore: false

Switches between:

- SecretStore (namespace-scoped, default)

- ClusterSecretStore (cluster-scoped, if externalSecretScope: cluster)

Supports vault, aws, and gcp.

If useExistingSecretStore: true, this template is skipped and your ExternalSecrets will point to the provided existing ref.

And external.secrets.yaml template
🔑 Features

- Loops through each service (.Values.services) and generates an ExternalSecret if it has secrets.

- Supports:

- - Newly created SecretStore/ClusterSecretStore (when useExistingSecretStore: false)

- - Pre-existing SecretStore/ClusterSecretStore (when useExistingSecretStore: true with existingSecretStoreRef)

- Creates a Kubernetes Secret (target.name) for each service to mount/use.

- Secret keys are normalized to release/service/key format for external reference.


Updated features.
- If a service has secrets defined → they’ll be injected as envFrom.secretRef instead of plain-text values.

- Normal non-sensitive env vars still get injected as before.

- This way, the container automatically consumes secrets from ExternalSecret / Secret.

- Plain env vars (safe) → .env section.

- Sensitive vars (secrets) → referenced automatically from generated Secret or ExternalSecret.

### Usasge
values.yaml
```yaml

services:
  db:
    image: postgres:15
    secrets:
      POSTGRES_PASSWORD: placeholder
    secretMounts:
      - name: db-secret-files
        mountPath: /etc/db-secrets
        items:
          - key: POSTGRES_PASSWORD
            path: password.txt



```

Generated deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myrelease-db
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myrelease-db
  template:
    metadata:
      labels:
        app: myrelease-db
    spec:
      containers:
        - name: db
          image: postgres:15
          envFrom:
            - secretRef:
                name: myrelease-db-secret
          volumeMounts:
            - name: myrelease-db-secret-db-secret-files
              mountPath: /etc/db-secrets
              readOnly: true
      volumes:
        - name: myrelease-db-secret-db-secret-files
          secret:
            secretName: myrelease-db-secret
            items:
              - key: POSTGRES_PASSWORD
                path: password.txt

```

Now secrets can be consumed either as env vars or files.
### Usage 
docker-compose.yaml
```yaml
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mydb
      POSTGRES_PASSWORD: supersecret
  web:
    image: nginx
    secrets:
      - ssl_cert
      - ssl_key

secrets:
  ssl_cert:
    file: ./certs/tls.crt
  ssl_key:
    file: ./certs/tls.key

```

Generated values.yaml
```yaml
secretProvider: internal
services:
  db:
    image: postgres:15
    env:
      POSTGRES_DB: mydb
    secrets:
      POSTGRES_PASSWORD: supersecret
  web:
    image: nginx
    secrets:
      SSL_CERT: "<from-file:./certs/tls.crt>"
      SSL_KEY: "<from-file:./certs/tls.key>"
    secretMounts:
      - name: ssl_cert
        mountPath: /run/secrets/ssl_cert
        items:
          - key: ssl_cert
            path: ssl_cert
      - name: ssl_key
        mountPath: /run/secrets/ssl_key
        items:
          - key: ssl_key
            path: ssl_key


```
For msecurity the Python generator does not read the actual secret file contents, it just notes the file path in values.yaml.
 This means:

- No sensitive data ends up in your Git repo.

- You (or your CI/CD) provide the actual secret values at helm install or via an external Secret Manager.

- The Helm chart still generates the correct Secret / ExternalSecret objects.

### Example Flow (with placeholders)

docker-compose.yaml
```yaml
version: "3.9"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: mydb
      POSTGRES_PASSWORD: supersecret
  web:
    image: nginx
    secrets:
      - ssl_cert
      - ssl_key

secrets:
  ssl_cert:
    file: ./certs/tls.crt
  ssl_key:
    file: ./certs/tls.key


```

### Generated values.yaml
```yaml
secretProvider: internal
services:
  db:
    image: postgres:15
    env:
      POSTGRES_DB: mydb
    secrets:
      POSTGRES_PASSWORD: supersecret
  web:
    image: nginx
    secrets:
      SSL_CERT: "<from-file:./certs/tls.crt>"
      SSL_KEY: "<from-file:./certs/tls.key>"
    secretMounts:
      - name: ssl_cert
        mountPath: /run/secrets/ssl_cert
        items:
          - key: ssl_cert
            path: ssl_cert
      - name: ssl_key
        mountPath: /run/secrets/ssl_key
        items:
          - key: ssl_key
            path: ssl_key


```

### Generated. Helm templates
- Secret (internal provider)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: myrelease-web-secret
type: Opaque
stringData:
  SSL_CERT: "<from-file:./certs/tls.crt>"
  SSL_KEY: "<from-file:./certs/tls.key>"
```

- Deployment (mounting secrets as files)
```yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: myrelease-web
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myrelease-web
  template:
    metadata:
      labels:
        app: myrelease-web
    spec:
      containers:
        - name: web
          image: nginx
          volumeMounts:
            - name: myrelease-web-secret-ssl_cert
              mountPath: /run/secrets/ssl_cert
              readOnly: true
            - name: myrelease-web-secret-ssl_key
              mountPath: /run/secrets/ssl_key
              readOnly: true
      volumes:
        - name: myrelease-web-secret-ssl_cert
          secret:
            secretName: myrelease-web-secret
            items:
              - key: ssl_cert
                path: ssl_cert
        - name: myrelease-web-secret-ssl_key
          secret:
            secretName: myrelease-web-secret
            items:
              - key: ssl_key
                path: ssl_key


```
### Benefits of Placeholder Approach

- You never commit secret values to git.

- The generator tells you which secrets are expected and where they came from (<from-file:...>).

- You can override at deploy time with:
```bash

helm install myrelease ./chart \
  --set services.web.secrets.SSL_CERT="$(cat ./certs/tls.crt)" \
  --set services.web.secrets.SSL_KEY="$(cat ./certs/tls.key)"


```