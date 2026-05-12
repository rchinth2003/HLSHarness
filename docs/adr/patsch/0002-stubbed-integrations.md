# ADR 0002: Fully Stubbed Data Integrations

**Status:** Accepted — Implemented (Slice 0)  
**Date:** 2026-05-12

## Decision
All data integrations (Epic FHIR, 270/271 clearinghouse, CRM, Identity/SSO, SMS/voice/email) are stubbed via harness `StubToolMiddleware` using YAML fixtures. No real EHR or payer connections are provisioned.

## Context
This is a customer demo solution. Real Epic FHIR and payer sandbox credentials are not available and would take 1–3 weeks to provision. The entire solution must run offline against scripted fixtures.

## Alternatives Considered
- **Epic public FHIR sandbox** — accessible without org credentials, but still requires auth setup and adds real network dependency to the demo.
- **Hybrid (stub payer, real Epic sandbox)** — adds complexity without meaningful demo benefit; stub fixtures are more controllable for demo scenarios.

## Consequences
- Demo is fully self-contained — no network dependencies at demo time.
- Stub fixtures in `stubs/` must be realistic enough to reflect actual patient journeys.
- Real connector implementation is explicitly out of scope for all four slices.
- Eval results reflect agent decision quality against scripted data, not end-to-end system behavior.
