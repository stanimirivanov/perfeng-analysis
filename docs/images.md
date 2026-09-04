# Analysis image publication

The runtime image contains the locked `perfeng-analysis` installation and both
offline commands. It does not contain the repository, tests, development tools,
credentials, or result data.

## Local verification

```sh
docker build --platform linux/amd64 -t perfeng-analysis:local-check .
uv run --locked python scripts/image.py verify perfeng-analysis:local-check
```

Verification checks the Linux AMD64 platform, numeric non-root identity,
working directory, entry point, OCI source revision when supplied, installed
package version, and availability of both CLIs. Its runtime probes disable
networking, make the root filesystem read-only, drop every capability, and
disable privilege escalation.

The Linux AMD64 manifests for Python 3.12.11 slim-bookworm and uv 0.12.5 are
pinned in the Dockerfile. Their registry digests were resolved on 2026-09-04.
Updating either pin requires a reviewed dependency change and a new image build.
The final image has its own unrelated digest; deployments must use that final
registry digest.

## Manual publication

After merging, run **Build and optionally publish analysis image** from the
repository Actions page on `main`. Leave `publish` disabled for build-only
verification. Enabling it authorizes the workflow to log in with the
repository-scoped GitHub token and push a uniquely tagged image.

After pushing, the workflow resolves the GHCR manifest digest, pulls that exact
reference, verifies it again, and prints the reference and source revision in
the workflow summary. A local image ID or mutable tag is not a deployment
identity. A failed publication workflow must not be promoted even if it left an
image in the registry.

The workflow does not change package visibility, create Kubernetes pull
credentials, sign images, or promote them into an environment. This first image
targets Linux AMD64 only.
