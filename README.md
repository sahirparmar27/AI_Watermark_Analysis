# AI Watermark Analysis

An independent Python-based prototype for analyzing visible text watermarks, experimenting with custom hidden watermarks, and inspecting image metadata.

## Overview

**AI Watermark Analysis** is a Flask web application designed to explore image watermark detection and verification techniques. Users can upload images and receive an analysis report containing visible-text OCR findings, experimental hidden-marker results, image metadata, and a SHA-256 file hash.

The project is intended for educational and experimental research. It does not depend on Google SynthID.

## Features

- **Image Upload:** Upload PNG, JPG, JPEG, and WEBP images.
- **Visible Watermark Analysis:** Use Tesseract OCR and image preprocessing to identify possible repeated text watermarks.
- **Experimental Hidden Watermark:** Embed and detect a custom RGB least-significant-bit (LSB) marker.
- **Image Metadata:** Inspect image dimensions, format, color mode, and available EXIF fields.
- **SHA-256 Hashing:** Generate a hash to help identify changes to the image file.
- **Image Transformations:** Test resizing, cropping, brightness, contrast, and JPEG compression.
- **Experiment History:** Store detector results and test metadata in an SQLite database.
- **Web Interface:** View uploaded images and their analysis reports through a Flask application.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Flask | Web application and routing |
| Pillow | Image processing |
| OpenCV | Potential future image-analysis extensions |
| Tesseract OCR | Visible text recognition |
| pytesseract | Python interface to Tesseract |
| SQLite | Experiment history |
| HTML and CSS | User interface |
| Git and GitHub | Version control and project hosting |

## How It Works

1. The user uploads an image.
2. The application validates the image and calculates its SHA-256 hash.
3. The visible-text analyzer runs OCR on multiple preprocessed image variants.
4. The experimental hidden-marker detector checks for the custom marker implemented by this project.
5. Image metadata is collected.
6. Detector results are stored in the experiment database.
7. The application displays an analysis report.

## Installation

### Prerequisites

- Python 3.10 or newer
- Git
- Tesseract OCR

On Windows, install Tesseract OCR and confirm that its executable is available. The current application checks the default path:

`C:\Program Files\Tesseract-OCR\tesseract.exe`

### Clone the Repository

```bash
git clone https://github.com/sahirparmar27/AI_Watermark_Analysis.git
cd AI_Watermark_Analysis
```

### Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv _venv
.\_venv\Scripts\Activate.ps1
```

### Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Run the Application

```powershell
python app.py
```

Open the local address shown in the terminal, normally:

`http://127.0.0.1:5000`

## Project Structure

```text
AI_Watermark_Analysis/
├── app.py
├── app_backup.py
├── README.md
├── requirements.txt
├── database/
│   └── experiments.db
├── static/
│   ├── uploads/
│   └── generated/
├── templates/
└── tests/
```

The database and image folders are created by the application when needed. Local database files, uploaded images, generated images, and virtual environments should not be committed unless intentionally required for testing.

## Current Limitations

- OCR can misread faint, diagonal, stylized, or translucent watermark text.
- Repeated OCR detections are heuristic candidates and do not prove the presence of a watermark.
- The hidden-marker detector recognizes only this prototype's custom marker; it is not a universal watermark detector.
- The experimental LSB marker may be damaged by resizing, cropping, compression, or other image transformations.
- A SHA-256 hash identifies the exact file contents; it does not establish image authenticity or prove who created the image.
- The application does not currently provide a validated AI-generated-image classifier.
- No direct Google SynthID verification integration is included.

## Future Improvements

- Improve OCR accuracy for diagonal and low-contrast watermarks.
- Reduce false positives and evaluate detection performance on labelled test images.
- Add structured experiment reports and accuracy metrics.
- Evaluate robust watermarking techniques against common image transformations.
- Explore independently evaluated AI-generated-image classification models.
- Improve automated tests and user-interface feedback.

## Research and Evaluation

The project will be evaluated using watermarked and plain images, recording successful detections, false positives, missed detections, and the effects of image transformations. Results should be documented from actual experiments rather than assumed in advance.

## Disclaimer

This is an educational research prototype, not a forensic authentication system. Its results should not be treated as definitive proof that an image is authentic, AI-generated, or watermark-free.

## Author

**Sahir Parmar**

GitHub: [@sahirparmar27](https://github.com/sahirparmar27)

## License

No license has been selected yet. Usage and redistribution permissions have not been formally defined.
