#!/bin/sh
exec uvicorn app.main:app --host "${BIND_HOST:-127.0.0.1}" --port "${PORT:-8000}"
