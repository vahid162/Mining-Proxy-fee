# Changelog

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
