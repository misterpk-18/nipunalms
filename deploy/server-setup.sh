#!/usr/bin/env bash
# First install of the LMS on a fresh Ubuntu 24.04 server (docs/DEVELOPMENT.md Part F). Run as `ubuntu` on the server, after the
# code, the SQL files and the built frontend have been copied to /srv/nipunalms (Part F section 3). Safe to run again: it never
# recreates the database or overwrites backend/.env. Usage: LMS_URL=http://<address> deploy/server-setup.sh
set -euo pipefail
ROOT=/srv/nipunalms
LMS_URL="${LMS_URL:?set LMS_URL to the address people will open, e.g. http://203.0.113.5}"
DB=nipunalms

echo "== packages, timezone, swap (a 1 GB server runs Postgres, the API and nginx, so it needs the swap)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx postgresql python3-venv python3-dev libpq-dev build-essential rsync
sudo timedatectl set-timezone Asia/Kolkata
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== database (empty: only the migrations in db/ create the reference data)"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1; then
  DBPASS=$(openssl rand -hex 24)
  sudo -u postgres psql -qc "CREATE ROLE $DB LOGIN PASSWORD '$DBPASS'"
  sudo -u postgres createdb -O $DB $DB
  FIRST_RUN=1
else
  FIRST_RUN=0
fi

echo "== python environment"
python3 -m venv $ROOT/venv
$ROOT/venv/bin/pip install -q --upgrade pip
$ROOT/venv/bin/pip install -q -r $ROOT/backend/requirements.txt gunicorn

if [ ! -e $ROOT/backend/.env ]; then
  [ "$FIRST_RUN" = 1 ] || { echo "the database exists but backend/.env does not: restore .env from a backup"; exit 1; }
  echo "== backend/.env (secrets generated here, mode 600)"
  umask 077
  cat > $ROOT/backend/.env <<EOF
APP_ENV=production
FLASK_APP=app
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://$DB:$DBPASS@127.0.0.1:5432/$DB
SECRET_KEY=$(openssl rand -hex 32)
CRM_SERVICE_KEY=$(openssl rand -hex 32)
STORAGE_BACKEND=s3
S3_BUCKET=nipunalms-uploads-prod
AWS_REGION=ap-south-1
PUBLIC_BASE_URL=$LMS_URL
# Google Workspace: configured, and every feature stays off until a Super Admin marks it Working on Setup & health
GOOGLE_WORKSPACE_DOMAIN=nipunatechnologies.com
GOOGLE_DELEGATED_ADMIN=admin@nipunatechnologies.com
GOOGLE_SA_KEY_FILE=secrets/google-sa-key.json
GOOGLE_EMAIL_SENDER=lms@nipunatechnologies.com
GOOGLE_EMAIL_SENDER_MAILBOX=admin@nipunatechnologies.com
GOOGLE_EMAIL_SENDER_NAME="Nipuna LMS"
GOOGLE_REQUEST_TIMEOUT=15
EOF
  chmod 600 $ROOT/backend/.env
fi
mkdir -p $ROOT/backend/secrets $ROOT/backups && chmod 700 $ROOT/backend/secrets

echo "== migrations (every file in order, only into a database that has no tables yet)"
set -a; . $ROOT/backend/.env; set +a
if [ -z "$(psql "${DATABASE_URL/+psycopg/}" -tAc "SELECT to_regclass('public.users')")" ]; then
  for f in $(ls $ROOT/db/*.sql | sort); do
    psql "${DATABASE_URL/+psycopg/}" -q -v ON_ERROR_STOP=1 --single-transaction -f "$f" >/dev/null
  done
  echo "applied $(ls $ROOT/db/*.sql | wc -l) files"
fi

echo "== service, web server, cron"
sudo cp $ROOT/deploy/nipunalms.service /etc/systemd/system/
sudo sed 's/server_name LMS_HOST;/server_name _;/' $ROOT/deploy/nginx-nipunalms.conf | sudo tee /etc/nginx/sites-available/nipunalms >/dev/null
sudo ln -sf /etc/nginx/sites-available/nipunalms /etc/nginx/sites-enabled/nipunalms
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now nipunalms
sudo systemctl reload nginx
chmod +x $ROOT/deploy/backup.sh
crontab $ROOT/deploy/crontab

sleep 3
echo "== health"
curl -s http://127.0.0.1:5060/api/v1/health; echo
echo "Done. Next: copy the Google key to $ROOT/backend/secrets/google-sa-key.json (mode 600), then create the first admin:"
echo "  cd $ROOT/backend && APP_ENV=production ../venv/bin/flask --app app create-admin"
