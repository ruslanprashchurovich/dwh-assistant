.PHONY: setup run lint clean

VENV := .venv
PYTHON := $(VENV)\Scripts\python
PIP := $(VENV)\Scripts\pip

help:
	@echo "Usage: make <target>"
	@echo "Targets: setup run lint clean"

# Install virtual environment and dependencies
setup:
	@echo "Creating virtual environment..."
	python -m venv $(VENV)
	@echo "Virtual environment created."
	@echo "Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed."

# To activate the virtual environment, run:
# .venv\Scripts\activate
# To deactivate the virtual environment, run:
# deactivate

# Run the application
run:
	$(PYTHON) run.py

# Check code style (use flake8)
lint:
	$(PYTHON) -m flake8 ./app run.py

# Clean project directory from temporary files
clean:
	@echo "Cleaning up..."
	-forfiles /P . /S /M *.pyc /C "cmd /c del @file" 2>nul
	-forfiles /P . /S /M __pycache__ /C "cmd /c if @isdir==TRUE rmdir /s /q @file" 2>nul
	if exist $(VENV) rmdir /s /q $(VENV)
	@echo "Cleaned up."