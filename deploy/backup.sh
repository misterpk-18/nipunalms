#!/usr/bin/env bash
# Nightly LMS backup (docs/DEVELOPMENT.md Part F): a custom-format pg_dump of the production database and a tarball of
# the uploaded files (content, submissions, CVs live on local disk), kept for RETENTION_DAYS. Run by cron as ubuntu.
set -euo pipefail

ROOT="${LMS_ROOT:-/srv/nipunalms}"
DEST="$ROOT/backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP=$(date +%F-%H%M)

mkdir -p "$DEST"
set -a; . "$ROOT/backend/.env"; set +a
: "${DATABASE_URL:?DATABASE_URL is not set in backend/.env}"

# psql / pg_dump don't understand the SQLAlchemy driver suffix
pg_dump -Fc "${DATABASE_URL/+psycopg/}" > "$DEST/nipunalms-$STAMP.dump"
UPLOADS="${UPLOAD_DIR:-$ROOT/backend/uploads}"
if [ -d "$UPLOADS" ]; then
  tar -czf "$DEST/uploads-$STAMP.tar.gz" -C "$(dirname "$UPLOADS")" "$(basename "$UPLOADS")"
fi

find "$DEST" -maxdepth 1 \( -name 'nipunalms-*.dump' -o -name 'uploads-*.tar.gz' \) -mtime +"$RETENTION_DAYS" -delete
echo "$(date "+%F %T") backup ok: nipunalms-$STAMP.dump"
