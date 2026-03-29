.PHONY: setup run lint clean

VENV := .venv
PYTHON := $(VENV)/Scripts/python.exe
PIP := $(VENV)/Scripts/pip.exe

# Install virtual environment and dependencies
setup:
	@echo "Creating virtual environment..."
	python -m venv $(VENV)
	@echo "Virtual environment created."
	@echo "Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed."

# Run the application
run:
	$(PYTHON) run.py

# Check code style (use flake8)
lint:
	$(PYTHON) -m flake8 ./app run.py

# Clean project directory from temporary files
clean:
	@echo "Cleaning up..."
	del /s /q *.pyc
	rmdir /s /q __pycache__
	rmdir /s /q $(VENV)
	@echo "Cleaned up."