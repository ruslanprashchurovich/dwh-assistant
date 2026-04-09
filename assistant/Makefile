.PHONY: setup run lint clean

VENV := .venv
PYTHON := $(VENV)\Scripts\python.exe
PIP := $(VENV)\Scripts\pip.exe

# Install virtual environment and dependencies
setup:
	@echo "Creating virtual environment..."
	python -m venv $(VENV)
	@echo "Virtual environment created."
	@echo "Installing dependencies..."
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed."

# Run the application (uvicorn)
run:
	$(PYTHON) run.py

# Check code style (use flake8)
lint:
	$(PYTHON) -m flake8 ./app run.py

# Clean project directory from temporary files
clean:
	@echo "Cleaning up..."
	del /s /q *.pyc
	for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	rmdir /s /q $(VENV)
	@echo "Cleaned up."
