# End-to-end card flows

The real dispatcher, middlewares, handlers, PushService, Postgres and Redis —
only Telegram is faked (`harness.FakeTelegram`). Each scenario lets the worker
tick send a card and taps the buttons that card actually carries. Every tap must
visibly do something; no handler may crash; the coverage test fails when a push
button action has no scenario.

Needs a disposable Postgres holding a restored copy (the *template*, never
written to) and a disposable Redis. On the server:

    docker run -d --name eng-e2e-pg -e POSTGRES_USER=englsh -e POSTGRES_PASSWORD=e2e \
      -e POSTGRES_DB=postgres -p 127.0.0.1:55481:5432 postgres:16-alpine
    docker run -d --name eng-e2e-redis -p 127.0.0.1:55482:6379 redis:7-alpine
    docker exec eng-e2e-pg createdb -U englsh pristine
    docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U englsh englsh \
      | docker exec -i eng-e2e-pg psql -q -U englsh -d pristine

    E2E_DATABASE_URL=postgresql+asyncpg://englsh:e2e@127.0.0.1:55481/pristine \
    E2E_REDIS_URL=redis://127.0.0.1:55482/0 .venv/bin/pytest -q tests/e2e

    docker rm -f eng-e2e-pg eng-e2e-redis   # when done

Without the two variables the suite is skipped, so the regular run is unchanged.
