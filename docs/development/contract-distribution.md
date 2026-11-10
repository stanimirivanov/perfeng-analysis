# Updating Analysis contract resources

Use the signed historical distribution to prepare contract snapshots. Retain the
previous wheel, its reviewed SHA-256, and its dependency inputs before changing
the checkout. The current rehearsal uses identical schema bytes in both wheels.

Stage the assets and verifier as described in the [shadow setup](../../README.md#contracts-and-provenance).
The update gate previews the pinned selection. To produce a wheel-ready tree,
choose a new destination under an operator-owned directory.

```sh
make contracts-update-check CONTRACTS_SHADOW_ASSETS="$assets" \
  CONTRACTS_BOOTSTRAP="$bootstrap" CONTRACTS_VERIFIER="$verifier"
uv run --locked --offline python -m scripts.contracts_update --assets "$assets" \
  --bootstrap "$bootstrap" --verifier "$verifier" --target "$staging/contracts"
```

Review the staged tree before using it as `src/perfeng_analysis/contracts` in a
disposable build checkout. Build offline from that checkout. Signature,
source-revision, lock, and byte mismatches stop preparation. Changes to the
selected schema revision require their own reviewed lock and compatibility work.

```sh
make contracts-package-check CONTRACTS_CURRENT_WHEEL="$current_wheel" \
  CONTRACTS_ROLLBACK_WHEEL="$retained_wheel" CONTRACTS_ROLLBACK_SHA256="$retained_sha256"
```

The package gate installs the candidate and then reinstalls the retained wheel
in the same isolated environment. It validates both with locked, preprovisioned
dependencies and checks that Python loads the packaged resources. This rehearses
a distribution rollback at the current schema revision. Keep the earlier wheel
and signed source inputs available for recovery.
