.PHONY: sync run migrate makemigrations bolt

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
