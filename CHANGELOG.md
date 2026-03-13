# Changelog

## 0.2.0
- Implement protocol-correcter core flow: session-bound miner main account, explicit per-path session state, stricter job routing, and difficulty-weighted accepted-work fee accounting.

## 0.1.1
- Fix core behavior gaps: preserve miner main account, avoid mixed upstream notify/difficulty streams, await fee subscribe/authorize responses, close upstream sessions cleanly, and clarify operational limits.

## 0.1.0
- Initial practical MVP: Python stratum-aware fee proxy with Docker Compose deployment (v2rayA + fee-proxy), metrics endpoint, and starter tests.
