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
