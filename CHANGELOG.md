# Changelog

## 0.7.28
- Make `simple-forwarder` use env-driven SOCKS settings via `FORWARDER_SOCKS5_HOST` / `FORWARDER_SOCKS5_PORT`, with fallback to shared `SOCKS5_HOST` / `SOCKS5_PORT`.
- Clarify in README that the optional v2rayA bridge overlay only fixes `simple-forwarder` when its SOCKS chain also points to `v2raya:22070` (or the equivalent env-driven override).
- Replace the v2rayA Compose healthcheck with a `wget`-based probe on the local UI endpoint instead of a Bash-only `/dev/tcp` check.

## 0.7.27
- Add explicit fee-route armed/readiness gating so fee dispatch stays on main until authorize/resync boundaries are settled and a fresh post-boundary `mining.notify` arrives.
- Disarm fee readiness on session start, re-authorize, reconnect, `mining.set_difficulty`, and `mining.set_extranonce`, with greppable logs/metric for skipped fee slices while preserving local stale protections.
- Add proxy/integration tests covering fee readiness arming/disarming, downstream suppression before arming, and continued main-path mining during fee grace windows.

## 0.7.26
- Defer job-generation invalidation for `mining.set_difficulty` and `mining.set_extranonce` until the next `mining.notify`, with explicit pending/committed epoch logs.
- Keep immediate invalidation on `clean_jobs=true` and reconnect/failover boundaries, while preserving local stale/unknown submit rejection.
- Add tests for deferred difficulty/extranonce invalidation behavior and reconnect invalidation safety helper coverage.

## 0.7.25
- Strengthen downstream job-generation invalidation on upstream mining-state transitions: clean_jobs, set_difficulty epochs, set_extranonce resets, reconnect, and miner re-authorize boundaries.
- Keep local stale/unknown submit rejection behavior and enrich generation-mismatch reject logs with explicit invalidation causes (e.g. `stale_due_to_clean_jobs`, `stale_due_to_reconnect`).
- Add integration tests covering stale local rejection after clean_jobs, re-authorize, and extranonce reset boundaries while preserving normal current-generation submit behavior.

## 0.7.24
- Pin downstream `mining.submit` route to the job route chosen at `mining.notify` dispatch time, with per-job generation metadata for stale-safety.
- Remove unsafe unknown-job fallback routing and reject unknown/stale/generation-mismatched submits locally with explicit `event=local_submit_rejected` logging.
- Add integration tests for unknown-job local rejection, pinned known-job routing, and old-generation local rejection while keeping normal known-job flow intact.

## 0.7.23
- Enforce single-upstream subscribe semantics per miner session by caching the first `mining.subscribe` response and serving it locally for duplicate subscribe requests (no second upstream subscribe RPC).
- Add integration coverage that verifies duplicate miner subscribe calls still result in a single upstream subscribe while preserving client response shape.

## 0.7.22
- Refactor proxy session flow from dual-upstream to single-upstream dual-authorize so `mining.subscribe` + main/fee `mining.authorize` run on one shared upstream connection.
- Keep fee selection behavior based on `SelectionTracker` / routed-work ratio and `MAX_CONSECUTIVE_FEE_JOBS`, while rewriting submit username per route (`main_user` or `fee_user`) on the same socket.
- Update integration tests for single-connection dual-authorize behavior, shared notify stream, route-specific submit username rewriting, and preserved reject logging with upstream error payload.

## 0.7.21
- Add regression integration test ensuring `submitted_main` still grows when fee submits are repeatedly rejected.
- Add regression integration test for `mining.submit` without `job_id` to verify fallback routing does not get stuck on fee.
- Add regression integration test asserting reject `submit_result` logs include upstream `error` payload.

## 0.7.20
- Prevent fee-route lock-in by separating accepted-work reporting (`RatioTracker`) from route-selection accounting (`SelectionTracker`) and selecting routes from routed work plus `MAX_CONSECUTIVE_FEE_JOBS` guard.
- Add `MAX_CONSECUTIVE_FEE_JOBS` config parsing/validation (`>= 1`) and include reject error payload in submit logs when available.
- Update proxy and tests so repeated fee rejects and fallback routing no longer keep the selector permanently on `fee` while accepted metrics remain accepted-only.

## 0.7.19
- Fix `deploy/check-socks-reachability.sh` to pass `SOCKS5_HOST`/`SOCKS5_PORT` into `docker exec` explicitly, so operator-provided overrides are reliably honored.
- Clarify README preflight helper wording for host/port override usage.

## 0.7.18
- Clarify in README that `compose.v2raya-bridge.yaml` remains strictly opt-in and is not merged into canonical `compose.yaml` by default.
- Explicitly document that the bridge overlay uses `depends_on: condition: service_healthy` (not `service_started`) to stay aligned with existing v2raya health-gated startup behavior.

## 0.7.17
- Add optional `compose.v2raya-bridge.yaml` overlay with `v2raya-socks-bridge` (GOST sidecar in `service:v2raya` network namespace) to bridge loopback-only v2rayA listeners on ports 22070/22071/22072.
- Keep canonical default path unchanged (`SOCKS5_HOST=v2raya`, `SOCKS5_PORT=20170`) and document fallback activation/verification and troubleshooting in README.
- Add lightweight operator preflight helper `deploy/check-socks-reachability.sh` for DNS + TCP checks from `fee-proxy` to configured SOCKS endpoint.

## 0.7.16
- Trigger CI workflow on `merge_group` in addition to `pull_request`/`push` so required check `ci / pytest` is reported in merge-queue flows and does not remain pending.

## 0.7.15
- Switch v2rayA core selector to full binary paths by mapping `V2RAYA_V2RAY_BIN` from `${V2RAYA_CORE_BIN:-/usr/local/bin/v2ray}` in Compose.
- Update `.env.example` and README to document full-path override usage, including Xray with `/usr/local/bin/xray`.

## 0.7.14
- Make v2rayA core selection explicit in `compose.yaml` via `V2RAYA_V2RAY_BIN` env and default it to `v2ray` (v2ray-core) instead of implicit image default behavior.
- Add `V2RAYA_V2RAY_BIN` to `.env.example` and README environment docs so operators can override core choice (e.g. `xray`) explicitly.

## 0.7.13
- Add a release pre-flight checklist in README (VERSION check, CHANGELOG section check, pytest, and compose validations) to reduce tagged-release failures before pushing `vX.Y.Z`.
- Clarify that release starts only after pushing the tag because GitHub Actions trigger is configured on `push.tags`, and Git does not push tags by default.

## 0.7.12
- Clarify canonical Compose naming in README (`compose.yaml` + `compose.dev.yaml`) and explicitly state that `docker-compose.yml` is not the official path.
- Make operator commands in README explicitly target `compose.yaml` and add guidance to tag exactly the same version as `VERSION`.
- Add a release pre-flight checklist in README (VERSION check, matching `CHANGELOG.md` section, pytest, and compose validations) before creating `vX.Y.Z` tags.
- Clarify that release starts only after pushing the tag to GitHub because workflow trigger is configured on `push.tags`.

## 0.7.11
- Enforce canonical Compose naming by validating `compose.yaml` and `compose.dev.yaml` existence in CI and release workflows.
- Keep release readiness aligned with README by adding explicit pre-checks that prevent automation drift if compose files are renamed or removed.

## 0.7.10
- Unify test dependency installation across CI and release workflows by using a shared `requirements-test.txt` file.
- Keep release workflow resilient for future test dependency growth by installing from the shared requirements file before running pytest.

## 0.7.9
- Strengthen release workflow parity checks by validating that `.env.example` contains a concrete GHCR image reference (no `REPLACE_WITH_OWNER` placeholder).
- Run `docker compose config` validation (`compose.yaml` and `compose.dev.yaml`) during tagged releases, matching the CI-level configuration checks.

## 0.7.8
- Set `.env.example` default `FEE_PROXY_IMAGE` to the real GHCR path `ghcr.io/vahid162/mining-proxy-fee` for operator-ready out-of-the-box usage.

## 0.7.7
- Stabilize CI/release pytest execution by disabling third-party auto-loaded pytest plugins (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`).
- Pin pytest version in GitHub workflows (`pytest==8.3.3`) to reduce pull-request runner variance.
- Keep the same test suite (`python -m pytest -q`) while making CI behavior deterministic.

## 0.7.6
- Align README with `.env.example` by adding a complete environment-variable reference grouped by runtime, routing, fee control, reliability, and image/logging settings.
- Finalize operator quick-start wording around release-bundle consumption and `docker compose pull` + `docker compose up -d` flow.
- Harden Docker image runtime by switching container execution to a non-root user (`appuser`).

## 0.7.5
- Update README Quick Start to the final operator flow: download release bundle, configure `.env`, then run `docker compose pull` + `docker compose up -d`.
- Remove build-from-source commands from the main operator path and mark local build as developer-only guidance.
- Keep operator docs aligned with artifact-based deployment expectations.

## 0.7.4
- Add a standard `LICENSE` file (MIT) for clear public-repo usage terms.
- Add `.dockerignore` to reduce Docker build context size and avoid shipping non-runtime files.
- Document license section in README while keeping operator-first docs structure.

## 0.7.3
- Complete release pipeline by generating GitHub Release notes directly from the matching `CHANGELOG.md` section for the tagged version.
- Keep GHCR image publish flow for both tags (`vX.Y.Z` and `latest`) and fail the release if changelog section extraction is missing.
- Preserve and attach operator release assets (`compose.yaml`, `.env.example`, `CHANGELOG.md`, `checksums.txt`, `release-bundle.tar.gz`) with checksums.

## 0.7.2
- Refactor README into operator-first sections: `What it is`, `Quick Start`, `Minimal config`, and `Upgrade path`.
- Move operational detail to docs and formalize runbooks for operations/upgrade/rollback.
- Add explicit operations guidance for health checks, logs, metrics, and `deploy/v2raya` backup.

## 0.7.1
- Simplify operator Quick Start to a 3-command flow (`cp .env.example .env`, edit required vars, `docker compose pull && docker compose up -d`).
- Reduce Quick Start configuration focus to essential variables only (`FEE_USER`, `FEE_RATIO`, `UPSTREAM_*`, `FEE_UPSTREAM_*`, optional `FORWARDER_UPSTREAM_*` and ports).
- Align `docs/OPERATIONS.md` with the same operator-first 3-command onboarding.

## 0.7.0
- Extend release workflow to attach operator assets (`compose.yaml`, `.env.example`, `CHANGELOG.md`, `checksums.txt`, `release-bundle.tar.gz`) on every tagged release.
- Generate `checksums.txt` and build `release-bundle.tar.gz` automatically in CI before publishing GitHub Release.
- Add operator runbooks (`docs/UPGRADE.md`, `docs/ROLLBACK.md`, `docs/OPERATIONS.md`) and include them in release bundle.

## 0.6.0
- Add GHCR publish pipeline in release workflow to build/push `ghcr.io/<owner>/mining-proxy-fee` on every SemVer tag with both `:vX.Y.Z` and `:latest` tags.
- Keep GitHub Release creation in the same release workflow and include published image references in release notes.
- Update `.env.example` and README so operator workflow points to GHCR-hosted `fee-proxy` images.

## 0.5.0
- Split deployment Compose into operator-first `compose.yaml` (pull/up) and development override `compose.dev.yaml` (build from source).
- Switch default `APP_VERSION` in `.env.example` to `latest` so image tags default to latest as requested.
- Update README and v2rayA volume docs to reflect Quick Start vs Development workflow and new compose filenames.

## 0.4.10
- Add versioned `fee-proxy` image naming in Compose via `FEE_PROXY_IMAGE` + `APP_VERSION` and sync `.env.example`/README with runtime env variables.
- Ensure global fee ratio mode uses shared controller + shared tracker path selection in proxy.
- Expand CI to explicitly install test dependency (`pytest`) before running tests.
- Add tests for `FEE_RATIO` and `MAX_PENDING_RPCS` validation plus integration checks for `job_mismatch_count` and `auth_failures_fee` metrics.

## 0.4.9
- Add configurable fee ratio scope (`FEE_RATIO_SCOPE`) and switch default control to global scope so fee ratio targeting matches service-wide metrics.
- Add configurable fee path startup policy (`FEE_PATH_STARTUP_POLICY`) with strict fail-fast default when fee subscribe/authorize fails.
- Extend config and proxy tests for new scope/policy behavior and validation.

## 0.4.8
- Fix outdated release command example in README to use current SemVer tag format aligned with latest documented version flow.

## 0.4.7
- Add a public CI workflow (`.github/workflows/ci.yml`) for `pytest` on push/pull_request.
- Add a CI check for `docker compose config` (with `.env.example` copied to `.env`) to validate Compose syntax in PRs.

## 0.4.6
- Make `simple-forwarder` upstream host configurable via new `FORWARDER_UPSTREAM_HOST` env in Compose and `.env.example` (host is no longer hardcoded).
- Keep fee-proxy ports and healthcheck fully env-driven (`LISTEN_PORT`, `METRICS_PORT`) and align docs with runtime behavior.

## 0.4.5
- Make image references configurable via env (`V2RAYA_IMAGE`, `GOST_IMAGE`) to support controlled version pinning.
- Reduce default exposure by binding v2rayA UI and metrics ports to localhost (`V2RAYA_UI_BIND_HOST`, `METRICS_BIND_HOST`).
- Document a practical hardening checklist (pinning, env-driven ports, exposure limits, canary/rollback responsibility).

## 0.4.4
- Add Docker log rotation settings (`json-file` with `DOCKER_LOG_MAX_SIZE` / `DOCKER_LOG_MAX_FILE`) for all Compose services.
- Document production monitoring/log-handling guidance (structured logs + metrics collection) in README.

## 0.4.3
- Add GitHub Actions release workflow triggered by SemVer tags (`vX.Y.Z`) with version consistency check against `VERSION` and automatic GitHub Release publication.
- Document step-by-step release process in README to move project from source-deploy toward packaged release maturity.

## 0.4.2
- Add tracked `deploy/v2raya` directory (with usage notes) so Compose volume mount target exists in the repository by default.
- Document v2rayA volume-path prerequisite and persistence behavior in README.

## 0.4.1
- Fix fee-proxy Compose healthcheck to respect `METRICS_PORT` env value instead of hardcoded `9100`.
- Clarify README metrics endpoint examples to use `${METRICS_PORT:-9100}`.

## 0.4.0
- Add dedicated fee upstream configuration (`FEE_UPSTREAM_HOST`, `FEE_UPSTREAM_PRIMARY_PORT`, `FEE_UPSTREAM_SECONDARY_PORT`) so fee traffic can target a different pool/domain than main.
- Make fee-proxy published ports configurable in Compose via `LISTEN_PORT` and `METRICS_PORT` env values.
- Update docs/examples/tests to cover the new fee-upstream and configurable fee-port behavior.

## 0.3.5
- Make `simple-forwarder` active by default in Compose so port `60046` is always a pure forwarding path and never enters fee logic.
- Update README to explicitly state that `60046` stays outside fee-aware proxy logic.

## 0.3.4
- Harden Compose healthcheck format for `fee-proxy` by switching to `CMD` array form (avoids shell-quote parsing issues across environments).

## 0.3.3
- Fix invalid Compose healthcheck quoting for `fee-proxy` and sync docs with runtime behavior (`MAIN_USER` not required, integration tests included in `pytest -q`).

## 0.3.2
- Add an explicit canary rollout and rollback runbook in README with step-by-step operational commands and gating metrics.

## 0.3.1
- Separate fee port and simple forwarding port at Compose level (optional `simple-forwarder` profile) and document product boundary: orchestration in Compose, correctness logic inside proxy.

## 0.3.0
- Add real async integration tests for subscribe/authorize flow, dual-upstream notify/submit, difficulty-aware accounting, and runtime failover/reconnect.
- Harden runtime proxy/config path used by integration scenarios (timeouts, reconnect policy, session-centric metrics/logging fields).

## 0.2.0
- Implement protocol-correcter core flow: session-bound miner main account, explicit per-path session state, stricter job routing, and difficulty-weighted accepted-work fee accounting.

## 0.1.1
- Fix core behavior gaps: preserve miner main account, avoid mixed upstream notify/difficulty streams, await fee subscribe/authorize responses, close upstream sessions cleanly, and clarify operational limits.

## 0.1.0
- Initial practical MVP: Python stratum-aware fee proxy with Docker Compose deployment (v2rayA + fee-proxy), metrics endpoint, and starter tests.
