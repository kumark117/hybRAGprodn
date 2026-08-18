# CORS star in production (INC-5120)

`CORS_ALLOWED_ORIGINS=*` with cookies or `Authorization` headers is a gift to any website that wants to call your RAG API as the user.

This app **rejects** `*` when `APP_ENV` is production (`cors_origins` property).

Development default is `http://localhost:3000`.

## Checklist

- Explicit origin list
- Do not reflect arbitrary `Origin`
- Expose `X-Request-ID` if the browser must read it (`expose_headers`)
- SSE still needs CORS on POST `/api/v1/query/stream`
