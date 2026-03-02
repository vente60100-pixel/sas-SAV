# OKTAGON SAV v4.0 — Makefile
VENV = /root/oktagon-sav/venv
PYTHON = $(VENV)/bin/python
PYTEST = $(VENV)/bin/pytest
SERVICE = oktagon-sav

.PHONY: test deploy logs restart status stop start check

## Tests
test:
	cd /root/oktagon-sav && $(PYTEST) tests/ -v --tb=short

test-fast:
	cd /root/oktagon-sav && $(PYTEST) tests/ -x -q

## Service
restart:
	systemctl restart $(SERVICE)
	@echo '✅ Service redémarré'
	@sleep 2 && systemctl status $(SERVICE) --no-pager | head -5

start:
	systemctl start $(SERVICE)

stop:
	systemctl stop $(SERVICE)

status:
	systemctl status $(SERVICE) --no-pager

logs:
	journalctl -u $(SERVICE) -f --no-pager

logs-50:
	journalctl -u $(SERVICE) -n 50 --no-pager

## Déploiement
deploy: test
	@echo '📦 Tests OK — redémarrage service...'
	systemctl restart $(SERVICE)
	@sleep 2
	@systemctl is-active $(SERVICE) > /dev/null && echo '✅ Déployé avec succès' || echo '❌ ERREUR — vérifier logs'

## Vérification code
check:
	cd /root/oktagon-sav && $(PYTHON) -m py_compile main.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile core/pipeline.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile core/models.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile core/constants.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile domain/rules.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile storage/repos.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile storage/database.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile knowledge/templates.py
	cd /root/oktagon-sav && $(PYTHON) -m py_compile knowledge/prompts.py
	@echo '✅ Compilation OK'
