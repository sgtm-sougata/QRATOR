#!/bin/bash
set -euo pipefail

# Run migrations
python manage.py migrate --noinput

# Create superuser from .env only if all vars are present and user does not exist
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" && -n "${DJANGO_SUPERUSER_EMAIL:-}" ]]; then
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser created: {username}")
else:
    print(f"Superuser exists: {username} (leaving as-is)")
EOF
else
  echo "DJANGO_SUPERUSER_* not fully set; skipping superuser creation."
fi

# Collect static files automatically (with clear to ensure fresh files)
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear
echo "Static files collected successfully!"

exec "$@"
