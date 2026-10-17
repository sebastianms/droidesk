#!/bin/sh
set -eu

if [ -f migrations/env.py ]; then
    alembic upgrade head
fi

exec uvicorn --factory droidesk_api.main:create_app --host 0.0.0.0 --port 8000
