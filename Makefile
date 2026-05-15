.PHONY: setup run install clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[32m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv + install deps + copy .env
	bash setup.sh

run: ## Start the bot + web server
	bash run.sh

install: ## Install/update Python dependencies inside venv
	. venv/bin/activate && pip install -r requirements.txt

clean: ## Remove venv and .pyc files
	rm -rf venv __pycache__ bot/__pycache__ db/__pycache__ web/__pycache__ \
	       bot/handlers/__pycache__ *.pyc

freeze: ## Save current installed packages to requirements.txt
	. venv/bin/activate && pip freeze > requirements.txt
