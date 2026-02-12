# WebSocket Migration Guide

## Deprecation Timeline
- Old endpoint deprecated: 2024-01-01
- Sunset date: 2024-04-01

## Endpoints
- Old: `/ws/heartbeat` and `/heartbeat`
- New: `/ws/v1/connect`

## Authentication
- Continue using token-based auth via query params.
- Include device fingerprint where applicable.

## Protocol Updates
- Use event-based subscribe/unsubscribe semantics.
- Heartbeat now requires explicit `heartbeat` event and ack handling.

## Removal Plan
- Existing clients must migrate before sunset.
- After sunset, old endpoint returns 410 GONE only.
