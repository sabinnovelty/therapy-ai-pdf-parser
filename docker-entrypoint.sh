#!/bin/sh
set -e
# Install/update dependencies from mounted requirements.txt (no image rebuild needed)
if [ -f /app/requirements.txt ]; then
  pip install --no-cache-dir -q -r /app/requirements.txt
fi
exec "$@"
