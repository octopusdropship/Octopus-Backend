# Makefile — Common developer commands
# Usage: make <command>

.PHONY: install dev migrate test shell celery

install:
	pip install -r requirements-dev.txt

dev:
	python manage.py runserver 0.0.0.0:8000

migrate:
	python manage.py makemigrations
	python manage.py migrate

test:
	pytest

shell:
	python manage.py shell

celery:
	celery -A octopus_core worker --loglevel=info

celery-beat:
	celery -A octopus_core beat --loglevel=info

superuser:
	python manage.py createsuperuser

collectstatic:
	python manage.py collectstatic --noinput
