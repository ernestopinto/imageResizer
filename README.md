# ImageResizer

Small desktop GUI tool to batch-resize/compress `.jpg`, `.jpeg` and `.png` files
in a folder down to a maximum file size, while preserving aspect ratio.

## How it works

For each image over the size limit:
1. Dimensions are reduced first (in steps), keeping quality high.
2. If still too large (JPEG only), quality is reduced progressively.
3. PNG files are dimension-only, since PNG has no quality setting.

Files already under the limit are skipped. **Originals are overwritten in place** —
back up your folder before running on important files.

## Running from source

```bash
python -m pip install -r requirements.txt
python resize_images.py
```

## Building the .exe

```bash
build_exe.bat
```

Produces `dist/ImageResizer.exe` — a standalone executable, no Python required to run it.
