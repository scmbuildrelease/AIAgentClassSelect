"""Optional OCR for poster images (sources with "parser": "poster").

Uses the system `tesseract` command, so there is no Python dependency. Chinese needs the
chi_sim / chi_tra language data:
  macOS:  brew install tesseract tesseract-lang
  Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra
OCR text is treated like page text: fields not found stay empty, nothing is guessed.
"""
import shutil
import subprocess

WANTED_LANGS = ("chi_sim", "chi_tra", "eng")


class OCRUnavailable(RuntimeError):
    pass


def available_languages() -> set[str]:
    exe = shutil.which("tesseract")
    if not exe:
        return set()
    out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=30)
    return {line.strip() for line in (out.stdout + out.stderr).splitlines()[1:] if line.strip()}


def ocr_image(data: bytes, timeout: int = 120) -> str:
    exe = shutil.which("tesseract")
    if not exe:
        raise OCRUnavailable("OCR engine not installed (tesseract); poster could not be read")
    langs = [lang for lang in WANTED_LANGS if lang in available_languages()]
    if not {"chi_sim", "chi_tra"} & set(langs):
        raise OCRUnavailable("tesseract has no Chinese language data (chi_sim/chi_tra); poster could not be read")
    # --psm 6: treat the poster as a block of text. stdin/stdout keep everything in memory.
    out = subprocess.run([exe, "stdin", "stdout", "-l", "+".join(langs), "--psm", "6"],
                         input=data, capture_output=True, timeout=timeout)
    if out.returncode != 0:
        raise OCRUnavailable(f"tesseract failed: {out.stderr.decode('utf-8', 'replace')[:200]}")
    return out.stdout.decode("utf-8")
