# ==============================
# CONFIG
# ==============================

DC = docker compose
APP = dotabluez

# ==============================
# MAIN COMMANDS
# ==============================

up:
	@echo "🚀 Starting full project (db + migrations + bot)..."
	$(DC) up --build

down:
	@echo "🛑 Stopping project..."
	$(DC) down

restart:
	@echo "🔄 Restarting project..."
	$(DC) down
	$(DC) up --build -d

logs:
	@echo "📜 Showing logs..."
	$(DC) logs -f

# ==============================
# DATABASE
# ==============================

db:
	@echo "🐘 Starting only database..."
	$(DC) up -d db

db-down:
	@echo "🛑 Stopping database..."
	$(DC) stop db

# ==============================
# MIGRATIONS
# ==============================

migrate:
	@echo "⬆️ Applying migrations..."
	$(DC) run --rm migrations alembic upgrade head

downgrade:
	@echo "⬇️ Rolling back last migration..."
	$(DC) run --rm migrations alembic downgrade -1

revision:
	@echo "🧬 Creating new migration..."
	@read -p "Enter migration name: " name; \
	$(DC) run --rm migrations alembic revision --autogenerate -m "$$name"

# ==============================
# DEV UTILS
# ==============================

bash:
	@echo "🐚 Entering bot container..."
	$(DC) exec bot bash

ps:
	@echo "📦 Containers:"
	$(DC) ps

# ==============================
# HELP MENU
# ==============================

help:
	@echo ""
	@echo "================  DotaBluez Makefile ================="
	@echo ""
	@echo " MAIN:"
	@echo "  make up           - start full project (db + bot)"
	@echo "  make down         - stop everything"
	@echo "  make restart      - restart project"
	@echo "  make logs         - view logs"
	@echo ""
	@echo " DATABASE:"
	@echo "  make db           - start only database"
	@echo "  make db-down      - stop database"
	@echo ""
	@echo " MIGRATIONS:"
	@echo "  make migrate      - apply migrations"
	@echo "  make downgrade    - rollback last migration"
	@echo "  make revision     - create new migration"
	@echo ""
	@echo " DEV:"
	@echo "  make bash         - open bot container shell"
	@echo "  make ps           - show containers"
	@echo ""
	@echo "======================================================="
	@echo ""