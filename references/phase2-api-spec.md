# Phase 2 API Specification (Planned)

When static JSON files become limiting, upgrade to a simple CRUD API.

## Endpoints

```
GET    /api/memory/{agent}/topics                    → list topics
GET    /api/memory/{agent}/topics/{topic}             → read topic entries
POST   /api/memory/{agent}/topics/{topic}/entries     → create entry
PUT    /api/memory/{agent}/topics/{topic}/entries/{id} → update entry
DELETE /api/memory/{agent}/topics/{topic}/entries/{id} → soft-delete (archive)

GET    /api/memory/shared/{file}                      → read shared file
POST   /api/memory/shared/{file}/entries              → create (requires published_by)
POST   /api/memory/shared/conflicts                   → create conflict record

GET    /api/memory/meta/agents                        → agent registry
POST   /api/memory/meta/agents                        → register new agent

GET    /api/memory/search?q={query}&agent={agent}     → full-text search across entries
```

## Authentication

- Bearer token per agent (agent-specific write access)
- Read access: configurable (public or token-required)
- Admin token for shared/ deletions (human principal only)

## Migration Path

1. Deploy Flask/FastAPI alongside nginx static files
2. Proxy /api/memory/* to the API server
3. Keep /memory/* static files as read-only cache
4. Gradually switch agents to use API endpoints
5. Static files become backup/cache layer

## Key Principle

The JSON schema stays identical — only the transport layer changes.
An agent that reads static JSON files today should work unchanged
when the API is deployed, just with faster access and real-time updates.
