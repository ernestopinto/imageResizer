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
QUALITY_STEPS = [90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40]
DEFAULT_QUALITY = 90


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


def process_file(path: str, max_bytes: int, log) -> str:
    ext = os.path.splitext(path)[1].lower()
    original_size = os.path.getsize(path)
    if original_size <= max_bytes:
        return f"SKIP  (already {original_size // 1024} KB) {os.path.basename(path)}"

    img = Image.open(path)
    tmp_path = path + ".tmp"

    try:
        # Step 1: reduce dimensions, keep quality high (JPEGs) / lossless (PNGs)
        for scale in SCALE_STEPS:
            scaled = resize_to_scale(img, scale)
            size = encode_size(scaled, ext, DEFAULT_QUALITY, tmp_path)
            if size <= max_bytes:
                os.replace(tmp_path, path)
                return (
                    f"OK    {os.path.basename(path)}: "
                    f"{original_size // 1024}KB -> {size // 1024}KB "
                    f"(scale {scale}%, quality {DEFAULT_QUALITY if ext in JPEG_EXTS else 'n/a'})"
                )

        # Step 2: dimensions alone weren't enough.
        # JPEG: keep smallest scale, now reduce quality progressively.
        if ext in JPEG_EXTS:
            smallest = resize_to_scale(img, SCALE_STEPS[-1])
            for quality in QUALITY_STEPS:
                size = encode_size(smallest, ext, quality, tmp_path)
                if size <= max_bytes:
                    os.replace(tmp_path, path)
                    return (
                        f"OK    {os.path.basename(path)}: "
                        f"{original_size // 1024}KB -> {size // 1024}KB "
                        f"(scale {SCALE_STEPS[-1]}%, quality {quality})"
                    )
            # Couldn't hit target even at smallest scale + lowest quality;
            # keep the best (smallest) result we produced.
            os.replace(tmp_path, path)
            final_size = os.path.getsize(path)
            return (
                f"WARN  {os.path.basename(path)}: best effort "
                f"{original_size // 1024}KB -> {final_size // 1024}KB "
                f"(target not reachable without further shrinking)"
            )
        else:
            # PNG: no quality knob. Best effort is the smallest dimension step.
            os.replace(tmp_path, path)
            final_size = os.path.getsize(path)
            return (
                f"WARN  {os.path.basename(path)}: best effort "
                f"{original_size // 1024}KB -> {final_size // 1024}KB "
                f"(PNG has no quality setting; only dimensions were reduced)"
            )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Batch Image Resizer")
        self.resizable(False, False)

        self.folder_var = tk.StringVar()
        self.max_kb_var = tk.StringVar(value="1700")

        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Folder:").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.folder_var, width=45).grid(row=0, column=1, **pad)
        tk.Button(self, text="Browse...", command=self.browse_folder).grid(row=0, column=2, **pad)

        tk.Label(self, text="Max file size (KB):").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.max_kb_var, width=15).grid(row=1, column=1, sticky="w", **pad)

        self.run_btn = tk.Button(self, text="Run", command=self.run_clicked)
        self.run_btn.grid(row=2, column=0, columnspan=3, pady=10)

        self.progress = ttk.Progressbar(self, length=480, mode="determinate")
        self.progress.grid(row=3, column=0, columnspan=3, padx=10)

        self.log = tk.Text(self, width=70, height=18)
        self.log.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

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

        self.run_btn.config(state="disabled")
        self.log.delete("1.0", tk.END)
        thread = threading.Thread(target=self.run_batch, args=(folder, max_kb * 1024), daemon=True)
        thread.start()

    def run_batch(self, folder: str, max_bytes: int):
        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in (JPEG_EXTS | PNG_EXTS)
        ]
        self.progress["maximum"] = max(len(files), 1)
        self.progress["value"] = 0

        for path in files:
            try:
                result = process_file(path, max_bytes, self.append_log)
            except Exception as exc:
                result = f"ERROR {os.path.basename(path)}: {exc}"
            self.append_log(result)
            self.progress["value"] += 1

        self.append_log(f"\nDone. {len(files)} file(s) checked.")
        self.run_btn.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
