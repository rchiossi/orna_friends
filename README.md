# Orna Friends Extractor

This application extracts player information (Username, Level, Class) from screenshots of the Orna RPG Allies list using OCR.

## Features

*   **Image Processing Tab:**
    *   Select individual screenshot images via GUI.
    *   Run OCR processing on demand for the selected image.
    *   Displays extracted data in an editable table.
    *   Save manually corrected/verified data to the database.
*   **Bulk Processing Tab:**
    *   Select a folder containing multiple screenshots.
    *   Lists all valid image files in the folder.
    *   Process selected image or all images in the folder.
    *   Displays results for the selected image in an editable table.
    *   Save data for the selected image or save all processed results from the folder to the database.
*   **Manage Data Tab:**
    *   Lists all images currently stored in the database.
    *   Select an image to view it and its saved data in an editable table.
    *   Edit and save changes to the stored data for an image.
    *   Delete an image and its associated data from the database.
*   **All Data Tab:**
    *   Displays all extracted data entries from the database in a table.
    *   Filter the table to show only the most recent entry per username.
    *   Sort the table by clicking on column headers (Username, Level, Class, Extraction Date).
*   **Database Storage:**
    *   Stores original images and extracted/edited data in an SQLite database (`orna_data.db`).
*   **GUI:**
    *   Tabbed interface for different functions.
    *   Uses `tksheet` for editable data tables.
    *   Press `Escape` key to exit the application.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd orna_friends
    ```

2.  **Install Tesseract OCR Engine:**
    *   This application requires Google's Tesseract OCR engine to be installed **manually** on your system (it is *not* a Python package installed by pip).
    *   **macOS (using Homebrew):** `brew install tesseract`
    *   **Debian/Ubuntu:** `sudo apt update && sudo apt install tesseract-ocr`
    *   **Fedora:** `sudo dnf install tesseract`
    *   **Windows:** Download the installer from the [official Tesseract GitHub repository](https://github.com/tesseract-ocr/tesseract). Follow their installation instructions.
    *   **Important:** After installing Tesseract, you might need to configure the path to its executable within the `ocr_processor.py` file if the script cannot find it automatically (especially on Windows or non-standard installs). See comments in that file.

3.  **Create and activate a Python virtual environment:**
    *   It is recommended to use Python 3.12 or newer (problems were encountered with tkinter on macOS using pyenv and Python 3.11).
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

4.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the application:**
    ```bash
    python main.py
    ```

## Dependencies

*   Python 3.12+ (recommended)
*   Tesseract OCR Engine (see Setup section)
*   Python packages listed in `requirements.txt`:
    *   Pillow
    *   pytesseract
    *   opencv-python
    *   pandas
    *   tksheet 