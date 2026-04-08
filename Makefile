.PHONY: sync run migrate makemigrations bolt db

sync:
	uv sync

run: sync
	uv run python manage.py runserver

bolt: sync
	uv run python manage.py runbolt --dev

migrate: sync
	uv run python manage.py migrate

makemigrations: sync
	uv run python manage.py makemigrations

db:
	fly proxy 5432 -a exiftree-db
