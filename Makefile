.PHONY: help setup test build verify demo app clean

PYTHON ?= python
DB_PATH ?= data/diet.db

help:
	@echo "make setup | build | test | verify | demo | app | clean"

setup:
	$(PYTHON) -m pip install -e .

build:
	$(PYTHON) -m dietdb build --db $(DB_PATH)

test:
	$(PYTHON) -m pytest -q

verify:
	$(PYTHON) -m dietdb hash --db $(DB_PATH)

demo:
	rm -f /tmp/dietdb-demo.db /tmp/dietdb-demo.json
	$(PYTHON) -m dietdb build --db /tmp/dietdb-demo.db
	$(PYTHON) -m dietdb load-rules --db /tmp/dietdb-demo.db --mode draft-review
	$(PYTHON) -m dietdb plan --db /tmp/dietdb-demo.db --patient examples/patient_t2dm.json --rules-mode draft-review --out /tmp/dietdb-demo.json || test $$? -eq 2

app:
	streamlit run app.py

clean:
	rm -f data/diet.db data/app.db
