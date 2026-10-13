from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from pathlib import Path
from datetime import datetime
import sqlite3, hashlib, os, random, re, collections

try:
    import pytesseract
    from pytesseract import Output
    OCR_IMPORT_ERROR = None
except Exception as exc:
    pytesseract, Output = None, None
    OCR_IMPORT_ERROR = str(exc)

# Common Windows installer location; users can also configure PATH normally.
if pytesseract is not None:
    tesseract_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_exe.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / 'static' / 'uploads'
GENERATED = BASE / 'static' / 'generated'
DB_PATH = BASE / 'database' / 'experiments.db'
for folder in (UPLOADS, GENERATED, DB_PATH.parent):
    folder.mkdir(parents=True, exist_ok=True)

ALLOWED = {'png', 'jpg', 'jpeg', 'webp'}
MAX_PIXELS = 40_000_000
MAGIC = b'AWM3'
MARKER_SECRET = b'AI-Watermark-Lab-independent-demo-marker-v3'
MARKER_REPEATS = 3
app = Flask(__name__)
app.secret_key = os.environ.get('WATERMARK_APP_SECRET', 'local-research-prototype-change-me')
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS experiments(
          id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL,
          detector TEXT NOT NULL, result TEXT NOT NULL, source_type TEXT NOT NULL,
          modification TEXT NOT NULL, sha256 TEXT NOT NULL, notes TEXT NOT NULL,
          created_at TEXT NOT NULL)''')


def allowed(name):
    return '.' in name and name.rsplit('.', 1)[1].lower() in ALLOWED


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def marker_payload():
    # Fixed digest means this detector only validates markers created by this demo.
    return MAGIC + hashlib.sha256(MARKER_SECRET).digest()[:8]


def payload_bits(payload):
    return [((byte >> shift) & 1) for byte in payload for shift in range(7, -1, -1)]


def marker_positions(width, height, count):
    capacity = width * height * 3
    if capacity < count:
        raise ValueError('Image is too small for the experimental watermark. Use an image at least 10×10 pixels.')
    return random.Random(0xA17E).sample(range(capacity), count)


def embed_watermark(src, dst):
    """Embed a low-capacity RGB-LSB demo marker; this is not SynthID or a universal watermark."""
    with Image.open(src) as opened:
        if opened.width * opened.height > MAX_PIXELS:
            raise ValueError('Image has too many pixels for this prototype.')
        im = opened.convert('RGB')
    width, height = im.size
    bits = payload_bits(marker_payload())
    repeated = [bit for bit in bits for _ in range(MARKER_REPEATS)]
    positions = marker_positions(width, height, len(repeated))
    pixels = im.load()
    for position, bit in zip(positions, repeated):
        pixel_index, channel = divmod(position, 3)
        x, y = pixel_index % width, pixel_index // width
        rgb = list(pixels[x, y])
        rgb[channel] = (rgb[channel] & 0xFE) | bit
        pixels[x, y] = tuple(rgb)
    im.save(dst, 'PNG')
    return len(repeated)


def detect_watermark(path):
    """Detect only this prototype's own marker, using majority voting over repeated bits."""
    try:
        with Image.open(path) as opened:
            if opened.width * opened.height > MAX_PIXELS:
                return 'Image too large to scan'
            im = opened.convert('RGB')
        width, height = im.size
        bits = payload_bits(marker_payload())
        repeated_count = len(bits) * MARKER_REPEATS
        positions = marker_positions(width, height, repeated_count)
        pixels = im.load()
        votes = [[] for _ in bits]
        for bit_index, position in enumerate(positions):
            pixel_index, channel = divmod(position, 3)
            x, y = pixel_index % width, pixel_index // width
            votes[bit_index // MARKER_REPEATS].append(pixels[x, y][channel] & 1)
        recovered = []
        for group in votes:
            recovered.append(1 if sum(group) > len(group) / 2 else 0)
        data = bytearray()
        for i in range(0, len(recovered), 8):
            value = 0
            for bit in recovered[i:i + 8]:
                value = (value << 1) | bit
            data.append(value)
        if bytes(data) == marker_payload():
            return 'Prototype Watermark Detected'
        return 'No Prototype Watermark Detected'
    except Exception as exc:
        return f'Watermark scan error: {exc}'


def detect_visible_watermark(path):
    """Look for repeated visible text using OCR at several rotations.

    This is a heuristic: it can find repeated text, but cannot prove that the
    text is a watermark or reliably detect every faint/stylized watermark.
    """
    if pytesseract is None or Output is None:
        return {
            'status': 'OCR unavailable', 'text': '',
            'message': 'Python OCR package is unavailable. Install requirements.txt and confirm Tesseract is installed.'
        }

    try:
        with Image.open(path) as opened:
            if opened.width * opened.height > MAX_PIXELS:
                return {
                    'status': 'Image too large to scan', 'text': '',
                    'message': 'The image exceeds this prototype’s pixel limit.'
                }
            image = ImageOps.exif_transpose(opened).convert('RGB')

        original_width, original_height = image.size
        scale = 2 if max(image.size) < 1600 else 1
        if scale > 1:
            image = image.resize(
                (image.width * scale, image.height * scale),
                Image.Resampling.LANCZOS
            )

        gray = image.convert('L')
        # A small set of rotations helps OCR read diagonal repeating watermarks.
        # Keep coordinates separate per angle so detections are compared only
        # within the same orientation and duplicate OCR passes aren't counted
        # as separate locations.
        angles = (0, -25, 25)
        all_words = collections.defaultdict(list)
        recognized = collections.defaultdict(float)

        for angle in angles:
            rotated = gray if angle == 0 else gray.rotate(
                angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=128
            )
            auto = ImageOps.autocontrast(rotated)
            variants = (
                (rotated, 'gray'),
                (ImageEnhance.Contrast(auto).enhance(1.6), 'contrast'),
            )

            for variant, variant_name in variants:
                # Sparse-text mode is better suited to scattered watermarks.
                data = pytesseract.image_to_data(
                    variant, output_type=Output.DICT,
                    config='--oem 3 --psm 11'
                )
                for i, raw in enumerate(data.get('text', [])):
                    word = re.sub(r'[^A-Za-z0-9©®™]', '', str(raw)).lower()
                    try:
                        conf = float(data.get('conf', ['-1'])[i])
                        x = int(data['left'][i])
                        y = int(data['top'][i])
                        w = int(data['width'][i])
                        h = int(data['height'][i])
                    except (ValueError, TypeError, IndexError, KeyError):
                        continue

                    # Very low-confidence short fragments were the main source
                    # of false positives in the previous implementation.
                    if len(word) < 4 or conf < 25 or w <= 0 or h <= 0:
                        continue
                    cx = (x + w / 2) / scale
                    cy = (y + h / 2) / scale
                    all_words[(angle, word)].append((cx, cy, conf, variant_name))
                    recognized[word] = max(recognized[word], conf)

        if not recognized:
            return {
                'status': 'No visible text confidently recognized', 'text': '',
                'message': 'OCR did not confidently read text. Faint, diagonal, stylized or graphic watermarks may still be present.'
            }

        # De-duplicate detections from preprocessing variants at the same spot.
        min_distance = max(24, min(original_width, original_height) * 0.035)
        candidates = []
        for (angle, word), detections in all_words.items():
            points = []
            for x, y, confidence, variant_name in sorted(
                detections, key=lambda item: item[2], reverse=True
            ):
                matched = None
                for point in points:
                    distance = ((x - point['x']) ** 2 + (y - point['y']) ** 2) ** 0.5
                    if distance <= min_distance:
                        matched = point
                        break
                if matched is None:
                    points.append({
                        'x': x, 'y': y, 'confidence': confidence,
                        'passes': {variant_name}
                    })
                else:
                    matched['confidence'] = max(matched['confidence'], confidence)
                    matched['passes'].add(variant_name)

            # Only report repeated words if they occur in at least two distinct
            # places. Each location must have either cross-variant support or
            # one strong OCR confidence to reduce single-pass hallucinations.
            supported_points = [
                point for point in points
                if len(point['passes']) >= 2 or point['confidence'] >= 45
            ]
            if len(supported_points) >= 2 and len(word) >= 4:
                candidates.append((word, len(supported_points), max(
                    point['confidence'] for point in supported_points
                )))

        candidates.sort(key=lambda item: (-item[1], -item[2], -len(item[0]), item[0]))
        extracted = ' '.join(
            word for word, confidence in sorted(
                recognized.items(), key=lambda item: (-item[1], item[0])
            )
        )[:1200]

        if candidates:
            summary = ', '.join(
                f'{word} ({count} locations)' for word, count, _confidence in candidates[:8]
            )
            return {
                'status': 'Possible visible text watermark', 'text': extracted,
                'message': f'Repeated text candidates: {summary}. OCR confidence and repetition are clues only; inspect the image to confirm.'
            }

        return {
            'status': 'Text recognized; watermark not confirmed', 'text': extracted,
            'message': 'Text was recognized, but no repeated-text pattern passed the stricter checks. A watermark may still be present.'
        }
    except Exception as exc:
        return {
            'status': 'OCR error', 'text': '',
            'message': f'Tesseract could not run: {exc}. Check its executable path and English language data.'
        }


def image_metadata(path):
    with Image.open(path) as im:
        exif = im.getexif()
        fields = []
        for key, label in ((306, 'Date/time'), (305, 'Software'), (271, 'Camera make'), (272, 'Camera model')):
            try:
                value = exif.get(key)
                if value:
                    fields.append({'label': label, 'value': str(value)[:180]})
            except Exception:
                pass
        return {'width': im.width, 'height': im.height, 'format': im.format or 'Unknown',
                'mode': im.mode, 'bytes': os.path.getsize(path), 'exif': fields,
                'has_exif': bool(exif)}


def log_result(filename, detector, result, source, modification, path, notes):
    with conn() as c:
        c.execute('''INSERT INTO experiments(filename,detector,result,source_type,modification,sha256,notes,created_at)
                     VALUES(?,?,?,?,?,?,?,?)''',
                  (filename, detector, result, source, modification, sha256(path), notes,
                   datetime.now().strftime('%Y-%m-%d %H:%M:%S')))


def log_scan(filename, path, source='Unknown', modification='Original'):
    marker_result = detect_watermark(path)
    visible_result = detect_visible_watermark(path)
    log_result(filename, 'Experimental hidden marker', marker_result, source, modification, path,
               'Checks only this application’s custom marker; not a universal or proprietary watermark detector.')
    log_result(filename, 'Visible text OCR heuristic', visible_result['status'], source, modification, path,
               visible_result['message'])
    return marker_result, visible_result


init_db()


@app.errorhandler(413)
def too_large(_error):
    flash('File is larger than 25 MB. Please upload a smaller image.')
    return redirect(url_for('home'))


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('image')
    if not f or not f.filename:
        flash('Choose an image first.')
        return redirect(url_for('home'))
    if not allowed(f.filename):
        flash('Use PNG, JPG, JPEG or WEBP.')
        return redirect(url_for('home'))
    safe_name = secure_filename(f.filename)
    name = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + safe_name
    path = UPLOADS / name
    try:
        f.save(path)
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if im.width * im.height > MAX_PIXELS:
                path.unlink(missing_ok=True)
                flash('Image exceeds the 40-megapixel prototype limit.')
                return redirect(url_for('home'))
    except Exception:
        path.unlink(missing_ok=True)
        flash('That file could not be opened as a valid image.')
        return redirect(url_for('home'))
    marker_result, visible_scan = log_scan(name, path)
    return render_template('result.html', filename=name, result=marker_result,
                           digest=sha256(path), visible_scan=visible_scan, metadata=image_metadata(path))


@app.route('/result/<path:filename>')
def result(filename):
    path = UPLOADS / filename
    if not path.exists() or path.resolve().parent != UPLOADS.resolve():
        flash('Image not found.')
        return redirect(url_for('home'))
    marker_result = detect_watermark(path)
    visible_scan = detect_visible_watermark(path)
    metadata = image_metadata(path)
    return render_template('result.html', filename=filename, result=marker_result,
                           digest=sha256(path), visible_scan=visible_scan, metadata=metadata)


@app.route('/embed/<path:filename>', methods=['POST'])
def embed(filename):
    src = UPLOADS / filename
    if not src.exists() or src.resolve().parent != UPLOADS.resolve():
        flash('Image not found.')
        return redirect(url_for('home'))
    out_name = 'watermarked_' + Path(filename).stem + '.png'
    dst = GENERATED / out_name
    try:
        embed_watermark(src, dst)
    except Exception as exc:
        flash(str(exc))
        return redirect(url_for('result', filename=filename))
    marker_result, visible_scan = log_scan(out_name, dst, 'Prototype Watermarked', 'Marker embedded')
    return render_template('result.html', filename=filename, result=marker_result,
                           digest=sha256(dst), generated=out_name,
                           visible_scan=visible_scan, metadata=image_metadata(dst))


@app.route('/transform/<path:filename>', methods=['POST'])
def transform(filename):
    src = UPLOADS / filename
    if not src.exists():
        src = GENERATED / filename
    if not src.exists() or src.resolve().parent not in (UPLOADS.resolve(), GENERATED.resolve()):
        flash('Image not found.')
        return redirect(url_for('home'))
    mode = request.form.get('mode', 'brightness')
    with Image.open(src) as opened:
        im = opened.convert('RGB')
    if mode == 'resize':
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.Resampling.LANCZOS)
    elif mode == 'crop':
        im = im.crop((int(im.width * .1), int(im.height * .1), int(im.width * .9), int(im.height * .9)))
    elif mode == 'brightness':
        im = ImageEnhance.Brightness(im).enhance(1.3)
    elif mode == 'contrast':
        im = ImageEnhance.Contrast(im).enhance(1.3)
    elif mode != 'jpeg':
        flash('Unknown transformation.')
        return redirect(url_for('result', filename=filename))
    if mode == 'jpeg':
        out_name = Path(filename).stem + '_jpeg.jpg'
        out = UPLOADS / out_name
        im.save(out, 'JPEG', quality=35)
    else:
        out_name = Path(filename).stem + '_' + mode + '.png'
        out = UPLOADS / out_name
        im.save(out, 'PNG')
    marker_result, visible_scan = log_scan(out_name, out, 'Transformed copy', mode)
    return render_template('result.html', filename=out_name, result=marker_result,
                           digest=sha256(out), visible_scan=visible_scan, metadata=image_metadata(out))


@app.route('/dashboard')
def dashboard():
    with conn() as c:
        rows = c.execute('SELECT * FROM experiments ORDER BY id DESC').fetchall()
    detected = sum(r['result'] == 'Prototype Watermark Detected' for r in rows)
    not_detected = sum(r['result'] == 'No Prototype Watermark Detected' for r in rows)
    return render_template('dashboard.html', rows=rows, total=len(rows), detected=detected,
                           not_detected=not_detected)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete(item_id):
    with conn() as c:
        c.execute('DELETE FROM experiments WHERE id=?', (item_id,))
    return redirect(url_for('dashboard'))


@app.route('/uploads/<path:name>')
def uploaded(name):
    return send_from_directory(UPLOADS, name)


@app.route('/generated/<path:name>')
def generated(name):
    return send_from_directory(GENERATED, name)


if __name__ == '__main__':
    app.run(debug=False)
