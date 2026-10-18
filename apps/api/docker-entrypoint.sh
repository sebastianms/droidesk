#!/bin/sh
set -eu

alembic upgrade head
python -m droidesk_api.seed

exec uvicorn --factory droidesk_api.main:create_app --host 0.0.0.0 --port 8000
