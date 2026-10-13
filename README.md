# AI Watermark Lab — Independent Prototype

A local Flask research prototype for studying visible text watermarks and a custom experimental hidden marker. It does not call Google SynthID, Gemini, or another online detector.

## What it does

- Upload PNG, JPG/JPEG, or WEBP images (up to 25 MB).
- Automatically checks whether the image contains this app's own custom hidden marker.
- Uses Tesseract OCR with several image-preprocessing passes to look for repeated visible text that may be a watermark.
- Reports image dimensions, format, color mode, available EXIF fields, and SHA-256 file hash.
- Stores scan events in a local SQLite database.
- Embeds the prototype's custom marker into a PNG and tests it after crop, resize, brightness, contrast, and JPEG transformations.

## What it does not claim

- It does not detect Google's proprietary SynthID or every other invisible watermark.
- Its custom marker is a research demonstration, not a production-grade robust watermark. It is stored in RGB least-significant bits and is expected to fail under some transformations, especially JPEG compression, cropping, and resizing.
- OCR candidates are heuristic. A repeated word may be a watermark, but OCR alone cannot prove that.
- It does not yet classify an image as AI-generated or human-created. Do not interpret “No Prototype Watermark Detected” as proof that an image is human-made.
- EXIF metadata can be missing or edited; SHA-256 identifies exact file bytes but does not establish authorship.

## Windows setup

1. Open this folder in VS Code.
2. Create and activate a virtual environment in the VS Code terminal:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install Python packages:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Install Tesseract OCR for Windows. The app checks the common path `C:\Program Files\Tesseract-OCR\tesseract.exe`; otherwise make sure `tesseract.exe` is on PATH. English language data (`eng`) should be installed.
5. Start the website:

   ```powershell
   python app.py
   ```

6. Open `http://127.0.0.1:5000` in a browser.

## Project structure

```text
AI_Watermark_Prototype_v5/
├── app.py
├── requirements.txt
├── README.md
├── database/                 # created automatically; local SQLite DB
├── dataset/
│   ├── ai_original/
│   ├── human/
│   └── modified/
├── static/
│   ├── css/style.css
│   ├── uploads/              # uploaded and transformed images
│   └── generated/            # marked PNG outputs
└── templates/
    ├── base.html
    ├── index.html
    ├── result.html
    └── dashboard.html
```

## Suggested experiment protocol

For each test image, record its known source and whether the custom marker was embedded. Compare the original, marked PNG, and transformed copies. Report true positives, false positives, false negatives, and true negatives for the custom marker detector. For visible OCR, manually verify each candidate against the image. Use a separate labelled dataset and train/evaluate a separate model before making AI-origin classification claims.
