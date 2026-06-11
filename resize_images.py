"""
Batch image resizer.

Picks a folder, a max file size (KB), and shrinks every .jpg/.jpeg/.png
above that size — preserving aspect ratio. Dimensions are reduced first;
if quality reduction is still needed (JPEG only), it's applied last.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

from PIL import Image

JPEG_EXTS = {".jpg", ".jpeg"}
PNG_EXTS = {".png"}
SCALE_STEPS = [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40]
DEFAULT_QUALITY = 100
DEFAULT_MINIMUM_QUALITY = 80


def resize_to_scale(img: Image.Image, scale: int) -> Image.Image:
    if scale == 100:
        return img
    w, h = img.size
    new_w = max(1, round(w * scale / 100))
    new_h = max(1, round(h * scale / 100))
    return img.resize((new_w, new_h), Image.LANCZOS)


def encode_size(img: Image.Image, ext: str, quality: int, tmp_path: str) -> int:
    if ext in JPEG_EXTS:
        img.convert("RGB").save(tmp_path, "JPEG", quality=quality, optimize=True)
    else:
        img.save(tmp_path, "PNG", optimize=True)
    return os.path.getsize(tmp_path)


def format_result(status: str, path: str, original_size: int, final_size: int, detail: str) -> str:
    return (
        f"{status:<5} {os.path.basename(path)}: "
        f"{original_size // 1024}KB -> {final_size // 1024}KB "
        f"({detail})"
    )


def find_best_jpeg_quality(
    img: Image.Image,
    max_bytes: int,
    minimum_quality: int,
    tmp_path: str,
) -> tuple[int | None, int]:
    best_quality = None
    best_size = 0
    low = minimum_quality
    high = DEFAULT_QUALITY - 1

    while low <= high:
        quality = (low + high) // 2
        size = encode_size(img, ".jpg", quality, tmp_path)
        if size <= max_bytes:
            best_quality = quality
            best_size = size
            low = quality + 1
        else:
            high = quality - 1

    return best_quality, best_size


def process_file(path: str, max_bytes: int, minimum_quality: int, log) -> str:
    ext = os.path.splitext(path)[1].lower()
    original_size = os.path.getsize(path)
    if original_size <= max_bytes:
        return f"SKIP  (already {original_size // 1024} KB) {os.path.basename(path)}"

    img = Image.open(path)
    tmp_path = path + ".tmp"
    smallest_tmp_path = path + ".smallest.tmp"

    try:
        if ext in JPEG_EXTS:
            smallest_size = 0
            smallest_scale = SCALE_STEPS[-1]
            smallest_quality = minimum_quality

            for scale in SCALE_STEPS:
                scaled = resize_to_scale(img, scale)
                size = encode_size(scaled, ext, DEFAULT_QUALITY, tmp_path)
                if size <= max_bytes:
                    os.replace(tmp_path, path)
                    return format_result(
                        "OK",
                        path,
                        original_size,
                        size,
                        f"scale {scale}%, quality {DEFAULT_QUALITY}",
                    )

                minimum_size = encode_size(scaled, ext, minimum_quality, tmp_path)
                if minimum_size <= max_bytes:
                    quality, quality_size = find_best_jpeg_quality(
                        scaled,
                        max_bytes,
                        minimum_quality,
                        tmp_path,
                    )
                    if quality is None:
                        quality = minimum_quality
                        quality_size = minimum_size
                    encode_size(scaled, ext, quality, tmp_path)
                    os.replace(tmp_path, path)
                    return format_result(
                        "OK",
                        path,
                        original_size,
                        quality_size,
                        f"scale {scale}%, quality {quality}",
                    )

                if smallest_size == 0 or minimum_size < smallest_size:
                    os.replace(tmp_path, smallest_tmp_path)
                    smallest_size = minimum_size
                    smallest_scale = scale

            os.replace(smallest_tmp_path, path)
            return format_result(
                "WARN",
                path,
                original_size,
                smallest_size,
                (
                    f"scale {smallest_scale}%, quality {smallest_quality}; "
                    "target not reachable at configured minimum quality"
                ),
            )
        else:
            # PNG: no quality knob. Reduce dimensions until the target is reached.
            smallest_size = 0
            smallest_scale = SCALE_STEPS[-1]

            for scale in SCALE_STEPS:
                scaled = resize_to_scale(img, scale)
                size = encode_size(scaled, ext, DEFAULT_QUALITY, tmp_path)
                if size <= max_bytes:
                    os.replace(tmp_path, path)
                    return format_result(
                        "OK",
                        path,
                        original_size,
                        size,
                        f"scale {scale}%, quality n/a",
                    )
                if smallest_size == 0 or size < smallest_size:
                    os.replace(tmp_path, smallest_tmp_path)
                    smallest_size = size
                    smallest_scale = scale

            os.replace(smallest_tmp_path, path)
            return format_result(
                "WARN",
                path,
                original_size,
                smallest_size,
                (
                    f"scale {smallest_scale}%, quality n/a; "
                    "PNG has no quality setting and target was not reachable"
                ),
            )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(smallest_tmp_path):
            os.remove(smallest_tmp_path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Batch Image Resizer")
        self.resizable(False, False)

        self.folder_var = tk.StringVar()
        self.max_kb_var = tk.StringVar(value="1700")
        self.minimum_quality_var = tk.StringVar(value=str(DEFAULT_MINIMUM_QUALITY))

        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Folder:").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.folder_var, width=45).grid(row=0, column=1, **pad)
        tk.Button(self, text="Browse...", command=self.browse_folder).grid(row=0, column=2, **pad)

        tk.Label(self, text="Max file size (KB):").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.max_kb_var, width=15).grid(row=1, column=1, sticky="w", **pad)

        tk.Label(self, text="Minimum quality (%):").grid(row=2, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.minimum_quality_var, width=15).grid(row=2, column=1, sticky="w", **pad)

        self.run_btn = tk.Button(self, text="Run", command=self.run_clicked)
        self.run_btn.grid(row=3, column=0, columnspan=3, pady=10)

        self.progress = ttk.Progressbar(self, length=480, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=3, padx=10)

        self.log = tk.Text(self, width=70, height=18)
        self.log.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def append_log(self, text: str):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def run_clicked(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please pick a valid folder.")
            return
        try:
            max_kb = int(self.max_kb_var.get().strip())
            if max_kb <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Max file size must be a positive integer (KB).")
            return
        try:
            minimum_quality = int(self.minimum_quality_var.get().strip())
            if minimum_quality <= 0 or minimum_quality > DEFAULT_QUALITY:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", f"Minimum quality must be between 1 and {DEFAULT_QUALITY}.")
            return

        self.run_btn.config(state="disabled")
        self.log.delete("1.0", tk.END)
        thread = threading.Thread(
            target=self.run_batch,
            args=(folder, max_kb * 1024, minimum_quality),
            daemon=True,
        )
        thread.start()

    def run_batch(self, folder: str, max_bytes: int, minimum_quality: int):
        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in (JPEG_EXTS | PNG_EXTS)
        ]
        self.progress["maximum"] = max(len(files), 1)
        self.progress["value"] = 0

        for path in files:
            try:
                result = process_file(path, max_bytes, minimum_quality, self.append_log)
            except Exception as exc:
                result = f"ERROR {os.path.basename(path)}: {exc}"
            self.append_log(result)
            self.progress["value"] += 1

        self.append_log(f"\nDone. {len(files)} file(s) checked.")
        self.run_btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
