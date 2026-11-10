FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=octopus_core.settings.production

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect Django admin static files at build time. Settings need these env
# vars to import; dummy values are fine because nothing connects anywhere.
RUN SECRET_KEY=build DB_NAME=x DB_USER=x DB_PASSWORD=x \
    SHOPIFY_API_KEY=x SHOPIFY_API_SECRET=x SHOPIFY_APP_URL=http://x \
    RAZORPAY_KEY_ID=x RAZORPAY_KEY_SECRET=x RESEND_API_KEY=x \
    python manage.py collectstatic --noinput

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# Apply migrations, then serve. The Celery worker reuses this image with its own command.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn octopus_core.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60"]
