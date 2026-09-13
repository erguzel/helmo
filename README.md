# helmo

[![ci](https://github.com/erguzel/helmo/actions/workflows/ci.yml/badge.svg)](https://github.com/erguzel/helmo/actions/workflows/ci.yml)

A small CLI around `helm` and `kubectl` for pinned, versioned, multi-environment
Helm deployments.

One release is one `.helmo` file. helmo asks the chart for its values, writes a
manifest per environment next to that file, archives the previous manifest with
a timestamp on every run, and names the target cluster on every single command
it issues. Releases can be driven one at a time, or as an ordered set described
by a `releases.yaml`.

It exists because a values file that nobody archives gets overwritten, and a
`kubectl config use-context` that nobody restores sends the next command to the
wrong cluster.

## Requirements

- Python 3.12.1 or newer
- [uv](https://docs.astral.sh/uv/)
- `helm` and `kubectl` on `PATH`
- A kubeconfig with a context per environment

## Install

```
git clone https://github.com/erguzel/helmo.git
cd helmo
uv sync
uv run helmo --version
```

Or install it as a tool: `uv tool install .`, then call `helmo` directly. The
examples below use `helmo`; prefix them with `uv run` inside a clone.

## The `.helmo` file

Everything about a release lives in one env-style file. **The release name is
the file stem** — `qdrant.helmo` installs a release called `qdrant`. There is no
`RELEASE_NAME` field, so there is one source of truth for the name.

```
TEST_CONTEXT=colima-helmo-test
PROD_CONTEXT=replace-with-your-prod-context
CHART_VERSION=1.19.1
APP_VERSION=v1.19.1
REPO_URL=https://qdrant.github.io/qdrant-helm
REPOSITORY_NAME=qdrant
CHART_NAME=qdrant
NAMESPACE=qdrant
```

`-e test` selects `TEST_CONTEXT`, `-e prod` selects `PROD_CONTEXT`; those are
the only two environments. Every field is required and validated before any
command runs — a malformed URL or a missing context fails at parse time, not
half way through a deployment.

`REPO_URL` is recorded and validated but helmo does not run `helm repo add` for
you yet; see [What helmo does not do](#what-helmo-does-not-do).

## Quick start

`examples/rag-vectorstores/` is a two-release set — qdrant and weaviate, each
pinned, each in its own namespace. This transcript is from a real run against a
disposable k3s cluster.

```
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo add weaviate https://weaviate.github.io/weaviate-helm
helm repo update

cd examples/rag-vectorstores
helmo init -i qdrant/qdrant.helmo -e test
helmo init -i weaviate/weaviate.helmo -e test
helmo serial install -f releases.yaml -y qdrant weaviate
```

```
NAME    	NAMESPACE	REVISION	UPDATED                              	STATUS  	CHART          	APP VERSION
qdrant  	qdrant   	1       	2026-09-13 10:16:04.050317 +0200 CEST	deployed	qdrant-1.19.1  	v1.19.1
weaviate	weaviate 	1       	2026-09-13 10:16:16.006682 +0200 CEST	deployed	weaviate-17.8.3	1.38.2
```

Taking it back down, namespaces included:

```
helmo serial uninstall -f releases.yaml -y -del qdrant weaviate
```

Running this inside a clone generates manifests under `examples/`; those
generated files are gitignored, so trying the examples does not dirty the
repository.

`examples/erpnext-test/` is the large counterpart: thirteen releases with
secrets and cluster-scoped resource manifests.

## What `init` generates

`helmo init` runs `helm show values` for the pinned chart version and writes one
manifest per environment beside the `.helmo` file:

```
qdrant/
├── config/
│   └── qdrant/                      secrets and resource manifests go here
├── qdrant.helmo
├── qdrant_default_1.19.1.yaml       refreshed from the chart on every init
├── qdrant_prod_1.19.1.yaml          yours to edit
└── qdrant_test_1.19.1.yaml          yours to edit
```

The environment manifests are the file helm is handed, so hand-written
overrides live in them. A second `init` therefore does **not** overwrite them —
it copies each one aside under a timestamp and leaves the live one alone:

```
qdrant_test_1.19.1.yaml
qdrant_test_1.19.1_20260913040158.yaml
qdrant_test_1.19.1_20260913040237.yaml
```

Only `_default_` is rewritten from the chart, so it always shows the upstream
defaults for the pinned version and can be diffed against your overrides.

If the `.helmo` file sits in a directory whose name is not `NAMESPACE`, init
**moves** it into a `NAMESPACE/` folder first. Put it in a matching folder to
keep it where you left it.

`-s <text>` appends text to the archive timestamp
(`qdrant_test_1.19.1_20260913040158.release-42.yaml`); `-q` drops the
per-release progress lines. Both are also accepted by `manual`, and `-s` by
`serial`.

## Deploying one release

```
helmo init   -i qdrant/qdrant.helmo -e test
helmo manual -i qdrant/qdrant.helmo -e test -a install -w 5m
helmo manual -i qdrant/qdrant.helmo -e test -a upgrade -w 5m
helmo manual -i qdrant/qdrant.helmo -e test -a uninstall -w 5m
```

`manual` deploys the environment manifest, it does not bootstrap it: if
`<release>_<env>_<version>.yaml` is not there yet, `-a install` and `-a upgrade`
stop with a pointer to `init` before any helm command is built. So the first
deployment of a release is always `init` then `manual`. After that, `-a install`
and `-a upgrade` re-run `init` themselves, which archives the current manifest
before helm is called.

`-a uninstall` does neither: there is nothing to initialise, and it needs no
environment manifest — a release can be removed after its generated files are
gone. Values files passed with `-v` are ignored on that path, with a warning,
because `helm uninstall` takes none.

`-e prod` prompts for confirmation; `-y` skips the prompt. `-v extra.yaml`
(repeatable) adds `--values` files on top of the environment manifest.

## Deploying a set

`releases.yaml` lists releases by path, with their environment and the files
each one needs. Release names are the `.helmo` stems, and you pass the ones you
want as arguments — the file describes the whole stack, the command line picks
the slice:

```yaml
releases:
  - initFile: maintenance/cert-manager/cert-manager.helmo
    environment: test
    secretFileNames:
      - secret-cloudflare-allzone-api-token.env
    resourceManifestNames:
      - clusterissuer-letsencrypt-prod.yaml
      - clusterissuer-local.yaml

  - initFile: common/ingress-nginx/ingress-nginx.helmo
    environment: test
    secretFileNames: []
    resourceManifestNames: []
```

```
helmo serial install   -f releases.yaml cert-manager ingress-nginx
helmo serial upgrade   -f releases.yaml cert-manager
helmo serial uninstall -f releases.yaml -del ingress-nginx
```

All three ask for confirmation before anything runs — in every environment, not
only `prod` — and abort on anything but yes. `-y` skips the prompt, as the
Quick start above does.

Each release takes three optional lists: `secretFileNames`,
`resourceManifestNames` and `additionalValuesNames`. All three name files inside
that release's `config/<release>/` directory, not paths relative to
`releases.yaml`. `install` and `upgrade` also take `-v`, which appends
`--values` files to every release in the run; unlike the yaml entries, those are
resolved against the current directory.

Releases are processed in the order you name them, not the order in the file.
Every named release is validated — files present, formats correct — before the
first helm command runs, so a typo in the last one stops the run before the
first one is touched.

Set `HELMO_SERIAL_RELEASES_YAML` to the file's absolute path to drop `-f`.

Note that `serial` reuses the `manual` path, so each release is re-initialised
as it is deployed: a `serial install` right after an `init` leaves a second
archived copy of each manifest.

## Secrets and resource manifests

Both, and any `additionalValuesNames`, are looked up in that release's
`config/<release>/` directory — `qdrant/config/qdrant/` for a release called
`qdrant`.

Under `serial`, **a secret takes its name from the file stem** —
`secret-grafana-ui.env` becomes a secret called `secret-grafana-ui`. The
standalone `create-file-secret` names it after `-t` instead, so the two can
differ; the example below creates `grafana-ui` from that same file.

A `.env` file is loaded with `--from-env-file`, anything else with
`--from-file`, and a `.dockerconfigjson` file gets the matching secret type.
Serial deployment overwrites an existing secret; the standalone command leaves
it in place, and warns, unless you pass `-o`. Either way the target namespace is
created first if it does not exist:

```
helmo create-file-secret -t grafana-ui -f config/kube-prometheus-stack/secret-grafana-ui.env \
  -c colima-helmo-test -n monitoring -o
```

Resource manifests listed in `resourceManifestNames` are applied with
`kubectl apply -f` before the chart is installed, which is where cluster-scoped
objects belong — a `ClusterIssuer`, a `StorageClass`. They are only available
through `serial`.

## Dry runs

`-d` on `init`, `manual` and `serial` reports what would happen and changes
nothing: no namespace, no file written, no manifest archived, no secret, no
`kubectl apply`, no helm command.
It still asks the chart repository for the values, which is the read-only half
and confirms the pinned chart version actually resolves:

```
WARNING | Dry run for qdrant: nothing is created, moved or written.
WARNING | Would ensure directories .../qdrant and .../qdrant/config/qdrant
WARNING | Would ensure namespace qdrant in colima-helmo-test context
WARNING | Would write chart values to .../qdrant_prod_1.19.1.yaml
WARNING | Would write chart values to .../qdrant_test_1.19.1.yaml
WARNING | Would write chart values to .../qdrant_default_1.19.1.yaml
WARNING | Dry run completed for qdrant.
```

## Contexts

helmo never runs `kubectl config use-context`. The context chosen by `-e` is
passed on the command itself — `--context` for kubectl, `--kube-context` for
helm — so your global kubeconfig is left exactly as it was, two environments can
be driven at once, and helm and kubectl cannot end up disagreeing about the
target cluster:

```
['helm', 'install', 'qdrant', 'qdrant/qdrant', '--namespace', 'qdrant',
 '--create-namespace', '--version', '1.19.1', '--values', '.../qdrant_test_1.19.1.yaml',
 '--kube-context', 'colima-helmo-test', '--wait', '--timeout', '5m']
```

The `helm install`, `upgrade` and `uninstall` argv is printed in full before it
runs. The rest is not echoed: `helm show values` during `init`, and every
`kubectl` call — namespace create and delete, `apply -f`, secret create and
delete — carry the same `--context` but run silently.

A failure prints its message, not an annotated traceback. `HELMO_DEBUG=1` turns
loguru's full traceback back on; it annotates every frame with the values
appearing in its source line, which on the registry path can include a
`~/.netrc` credential, so keep it out of shared terminals and CI logs.

## Registry commands

`helmo registry` talks to a Docker registry over HTTP. Credentials come from
`~/.netrc`, and the first `machine` entry there is also the default registry
url; override it with `-u` or `HELMO_REGISTRY_URL`.

```
helmo registry catalog
helmo registry tags myimage
helmo registry get-digest -r myimage v1.2.3
helmo registry delete-tags -r myimage v1.2.0
helmo registry gc-collect -c my-context -n registry -p registry-0
```

Deletions prompt for confirmation unless `-y` is given. `gc-collect` runs the
registry's garbage collector inside the pod; it is the one path that uses the
Kubernetes API client rather than a subprocess, because `kubectl exec` through
a subprocess is awkward to stream.

## What helmo does not do

- **OCI charts.** The model assumes a classic repository you can `helm repo add`,
  addressed as `REPOSITORY_NAME/CHART_NAME`.
- **`helm repo add`.** `REPO_URL` is recorded and validated, but adding the
  repository is still yours to do.
- **Resource manifests from `manual`.** That path exists only in `serial`.
- **Environments beyond `prod` and `test`.** Each one needs a matching
  `<ENV>_CONTEXT` field.

## Development

```
uv sync
uv run ruff check .
uv run pytest
```

The suite runs without a cluster: `kubectl` and `helm` invocations are
intercepted before `subprocess`, HTTP goes through a mock transport, and `HOME`
and `KUBECONFIG` are redirected at throwaway paths so no real credential or
context can be picked up. The destructive paths are covered by asserting the
argv that *would* have been executed, which is the only way to test "it did not
delete anything" without risking a delete.

Integration tests are skipped unless `HELMO_TEST_CLUSTER` names a sandbox
context (`colima-helmo-test`, `k3d-helmo-test`, `kind-helmo-test`).

## License

MIT. See [LICENSE](LICENSE).
