web: python manage.py migrate --fake-initial && python manage.py collectstatic --noinput && gunicorn PPMA.wsgi:application --bind 0.0.0.0:$PORT
