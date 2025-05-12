@echo off
setlocal enabledelayedexpansion

echo Starting Move37 setup...

:: Check if Python 3.12 is installed
python --version 2>NUL | findstr /R /C:"Python 3.12" >NUL
if errorlevel 1 (
    echo Python 3.12 is not installed. Please install it first.
    echo Visit https://www.python.org/downloads/ to download Python 3.12
    exit /b 1
)

:: Check if pip is installed
pip --version >NUL 2>&1
if errorlevel 1 (
    echo pip is not installed. Please install pip first.
    exit /b 1
)

:: Create virtual environment
echo Creating virtual environment...
python -m venv venv

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install requirements
echo Installing dependencies...
pip install -r requirements.txt

:: Check if installation was successful
if errorlevel 1 (
    echo Error installing dependencies. Please check the error messages above.
    exit /b 1
) else (
    echo Dependencies installed successfully!
)

:: Download spacy model
echo Downloading spacy model...
python -m spacy download en_core_web_sm

:: Verify installation
echo Verifying installation...
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('Spacy loaded successfully!')"
python -c "import fastmcp; print('Fastmcp loaded successfully!')"

echo Setup completed successfully!
echo To activate the virtual environment, run:
echo venv\Scripts\activate.bat

endlocal 