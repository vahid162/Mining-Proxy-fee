# Changelog

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
