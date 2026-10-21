PYTHON ?= python

.PHONY: gen seed test check

gen:
	$(PYTHON) -m scripts.gen_models

seed:
	$(PYTHON) -m scripts.seed

test:
	$(PYTHON) -m pytest tests

check:
	$(PYTHON) -m scripts.check_conventions
