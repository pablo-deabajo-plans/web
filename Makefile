.PHONY: audit test

audit:
	pip-audit -r backend/requirements.txt

test:
	python -m pytest backend/tests/ -m "not integration"
