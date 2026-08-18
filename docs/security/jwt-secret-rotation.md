# JWT secret rotation

Demo `JWT_SECRET` is a learning default. Rotate it like any signing key.

## Procedure (sketch)

1. Deploy code that accepts **two** secrets: current + previous (`JWT_SECRET`, `JWT_SECRET_PREVIOUS`)
2. Issue new tokens only with the current secret
3. After `JWT_EXPIRE_MINUTES` has passed for all clients, drop the previous secret
4. Never log tokens or `Authorization` headers (structlog redacts `Bearer`)

A rotation that invalidates all sessions at once looks like an auth outage. Dual-key verify avoids that.

Demo users (`analyst` / `analystpass`) are not an IdP. Replace with OIDC in a real deployment.
