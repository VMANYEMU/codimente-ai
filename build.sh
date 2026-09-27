#!/usr/bin/env bash
# Render build script for Codimente Private AI.
# Render executes this with bash; fail fast on errors.

set -euo pipefail

pip install --upgrade pip

pip install -r requirements.txt

# Collect static files for whitenoise.
python manage.py collectstatic --noinput

# Apply database migrations (the pgvector extension is
# created by migration knowledge 0001 via pgvector's
# VectorField / CreateExtension operation).
python manage.py migrate --noinput

# Seed the default organisation, assistants, knowledge
# bases and an organisation admin. Idempotent: existing
# data is never overwritten or duplicated. If no password
# is configured, a random one is generated and printed to
# the build log once. --django-admin also grants the user
# Django /admin/ access (idempotent on existing users).
python manage.py seed_organisation \
    --django-admin \
    --admin-password "${SEED_ADMIN_PASSWORD:-}"
