# pratikbassi.github.io

Personal photography portfolio for [Pratik Bassi](https://github.com/pratikbassi), published as a static site on [GitHub Pages](https://pratikbassi.github.io).

## Overview

The site is a scrollable photo gallery with a lightbox ("loupe") viewer. Thumbnails are arranged in a responsive, justified grid; clicking a photo opens the full-size image with prev/next navigation, keyboard shortcuts, and shareable deep links.

Photos are shown **newest first**: `main.js` reverses the `LR.images` array at load time, so the last entry in `index.html` appears at the top of the gallery.

The gallery was exported from **Adobe Lightroom** using its web gallery template. The exported HTML, CSS, and JavaScript drive the layout and interactions; `live_update.js` supports Lightroom's live preview when editing the gallery inside the app.

## Tech stack

- **Static HTML** — single-page gallery (`index.html`)
- **jQuery 1.10** — DOM manipulation and animations
- **jQuery Velocity** — transitions
- **Modernizr** — feature detection (e.g. fullscreen API)
- **Jekyll** — GitHub Pages build (`jekyll-theme-minimal` via `_config.yml`)
- **Python + Pillow** — optional scripts to add photos (`upload/`) or archive them (`archive/`)

## Project structure

```
.
├── index.html              # Gallery page and image metadata (LR.images)
├── _config.yml             # Jekyll / GitHub Pages config
├── private/
│   ├── index.html          # Password-gated gallery (cookie auth)
│   └── to_private.txt      # Names to move from public → private
├── upload/                 # Drop photos here (gitignored); processed by add script
├── archive/                # Tracked storage for archived photos (not on the site)
│   ├── names.txt           # Paste exportFilename values to archive
│   ├── large/
│   └── thumbnails/
├── scripts/
│   ├── add_photos.py       # Resize images and update index.html
│   ├── archive_photos.py   # Move listed photos out of the gallery
│   ├── move_to_private.py  # Move public photos into encrypted private gallery
│   ├── gen_private_token.py # Generate password hash for private-gate.js
│   └── requirements.txt    # Pillow dependency (add script only)
├── assets/
│   ├── css/
│   │   ├── normalize.css   # CSS reset
│   │   ├── main.css        # Gallery layout and loupe styles
│   │   └── custom.css      # Theme overrides (colors, spacing)
│   └── js/
│       ├── main.js         # Gallery logic (grid, lazy load, lightbox)
│       ├── private-gate.js # Cookie + SHA-256 gate for /private/
│       ├── live_update.js  # Lightroom live-preview hooks
│       └── libs/           # jQuery, Velocity, Modernizr
└── images/
    ├── large/              # Public full-size photos
    ├── thumbnails/
    └── private/
        └── encrypted/
            ├── large/      # AES-GCM encrypted blobs (.enc)
            └── thumbnails/
```

## Features

- Newest-first display order (reversed at runtime in `main.js`)
- Justified thumbnail grid with configurable row height
- Lazy loading as you scroll (`data-pagination-style="scroll"`)
- Lightbox viewer with prev/next controls and arrow-key navigation
- URL hash deep linking (`#/view/ID{id}`)
- Fullscreen mode (when supported by the browser)
- Compact header on scroll
- Private gallery at `/private/` with cookie-based password gate (low security; see below)

## Private gallery

The public site header includes a **Private** link to [`/private/`](private/). Visitors enter a password once; cookies store:

- `pb_private_auth` — SHA-256 login token (30 days)
- `pb_private_key` — derived AES decryption key (30 days)

The gallery does not load until both are set. Private images are stored as **encrypted `.enc` files** (AES-256-GCM). Browsers cannot display them as pictures without the key from your password. Direct URLs return opaque ciphertext, not JPEGs.

**Set up the password** (must match everywhere):

1. Create `private/.gallery-password` (gitignored) with your password on a single line, **or** set `PRIVATE_GALLERY_PASSWORD` in the environment.
2. Run `python scripts/gen_private_token.py your-password` and paste the hash into `AUTH_TOKEN` in `assets/js/private-gate.js`.

**Default password:** `changeme` (change before deploying).

**Add private photos:** drop files in `upload/private/` (gitignored), then:

```bash
pip install -r scripts/requirements.txt
python scripts/add_photos.py --private
```

This writes encrypted files under `images/private/encrypted/` and updates `private/index.html`.

**Move public photos to private:** paste `exportFilename` values into `private/to_private.txt`, then:

```bash
python scripts/move_to_private.py
```

This encrypts the public JPEGs, removes them from `index.html`, and appends the same metadata to `private/index.html`.

**Limitations:** Anyone with the auth cookies can decrypt in the browser (same as before, but better than public JPEG URLs). Ciphertext can still be downloaded. This is casual privacy, not enterprise security.

## Local development

Because this is a static site, any local HTTP server works. From the repository root:

```bash
# Python
python -m http.server 8000

# Node (npx)
npx serve .

# Jekyll (matches GitHub Pages build)
bundle exec jekyll serve
```

Then open `http://localhost:8000` (or the port shown by your server).

## Deployment

The site deploys automatically to GitHub Pages from the `main` branch of this repository. Push changes to `origin/main` and GitHub Pages will rebuild and publish to [https://pratikbassi.github.io](https://pratikbassi.github.io).

## Adding or updating photos

### Quick add (script)

1. Install dependencies once: `pip install -r scripts/requirements.txt`
2. Copy photos into `upload/` (gitignored). The file basename becomes `exportFilename` (e.g. `sunset-beach.jpg` → `sunset-beach`).
3. Run: `python scripts/add_photos.py`

The script creates `images/large/` and `images/thumbnails/` JPEGs, appends an entry to `LR.images` in `index.html`, and moves sources to `upload/processed/`. Because the gallery reverses order on load, **new photos appear at the top** without editing `index.html` by hand.

Commit `images/` and `index.html` when ready.

The script skips a file if that `exportFilename` is already in the gallery or if the output JPEGs already exist.

Use `python scripts/add_photos.py --private` for the private gallery (`upload/private/` → `images/private/`, updates `private/index.html`).

### Manual add

The gallery currently includes 30 images. To add new ones by hand:

1. Export or resize photos into `images/large/` and `images/thumbnails/` (matching filenames).
2. Append an entry to the `LR.images` array in `index.html` (newest-first display means **append at the end** to show the photo first):

   ```javascript
   {"id": "unique-id", "largeWidth": "1200", "largeHeight": "800", "exportFilename": "IMG_1234", "title": "", "caption": ""}
   ```

   - `exportFilename` must match the image basename (without `.jpg`).
   - `largeWidth` and `largeHeight` are the pixel dimensions of the large image.
   - `id` must be unique among all entries.

Alternatively, re-export the gallery from Adobe Lightroom and replace the generated files to keep metadata in sync.

### Archive photos (script)

Use this to take photos off the live gallery while keeping the files in the repo under `archive/` (tracked by git, not gitignored).

1. Paste `exportFilename` values into `archive/names.txt`, one per line (with or without `.jpg`). Lines starting with `#` are ignored.
2. Run: `python scripts/archive_photos.py`

For each name, the script:

- Moves `images/large/{name}.jpg` → `archive/large/`
- Moves `images/thumbnails/{name}.jpg` → `archive/thumbnails/`
- Removes the matching entry from `LR.images` in `index.html`
- Appends a line to `archive/archive.log`

Successful names are cleared from `archive/names.txt`. Failed names are left in the file for retry. Commit `index.html`, `images/`, and `archive/` when ready.

To put a photo back on the site later, move the JPEGs from `archive/` back into `images/`, add an `LR.images` entry (or use `add_photos.py` with a new source file).

## Customization

| What | Where |
|------|-------|
| Gallery title | `#galleryTitle` in `index.html` |
| Display order (newest vs. oldest first) | `LR.images.reverse()` in `assets/js/main.js` — remove or comment out to restore original order |
| Colors (background, text, icons) | `assets/css/custom.css` |
| Row height | `data-target-row-height` on `<body>` (default: `300`) |
| Row spacing | `row-spacing-lg` class on `<body>` (`none`, `sm`, `md`, `lg`) |
| Header visibility | `has-header` class on `<body>` |
| Private password token | `AUTH_TOKEN` in `assets/js/private-gate.js` (generate with `scripts/gen_private_token.py`) |
| Private link label | `Private` anchor in `index.html` header |

## License

Photos and site content © Pratik Bassi. Third-party libraries (jQuery, Velocity, Modernizr) retain their respective licenses.
