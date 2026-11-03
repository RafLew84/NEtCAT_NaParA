"""Build the self-contained Polish guide; run from any working directory."""
from pathlib import Path
import re

import markdown


ROOT = Path(__file__).resolve().parent
CHAPTERS = {
    "distribution.md": "paczka",
    "installation.md": "instalacja",
    "user-guide.md": "obsluga",
    "installation-models.md": "modele",
    "installation-validation.md": "sprawdzenia",
}
STYLE = """
body { color: #192b3a; background: #f4f6f8; margin: 0; font: 17px/1.65 system-ui, sans-serif; }
main { max-width: 1000px; margin: auto; padding: 32px 44px 80px; background: white; }
h1 { margin-top: 2.5em; border-top: 3px solid #21677a; padding-top: 24px; line-height: 1.3; }
h2 { margin-top: 2em; line-height: 1.35; } h3 { margin-top: 1.5em; }
a { color: #065a83; } a:hover { text-decoration-thickness: 2px; }
pre { background: #edf3f6; padding: 16px; border-left: 4px solid #21677a; overflow: auto; }
code { font-size: .92em; overflow-wrap: anywhere; } pre code { overflow-wrap: normal; }
table { width: 100%; border-collapse: collapse; font-size: .93em; }
td, th { padding: 9px 12px; border: 1px solid #cbd5dc; text-align: left; vertical-align: top; }
th { background: #edf3f6; } li { margin: 5px 0; }
.toc { padding: 12px 24px; background: #f4f7f9; } .toc ul { padding-left: 24px; }
button { border: 1px solid #21677a; padding: 10px 16px; background: white; color: #065a83; cursor: pointer; }
@media (max-width: 700px) { main { padding: 18px; } table { font-size: .85em; } }
@media print {
 body, main { background: white; } main { max-width: none; padding: 0; font-size: 10pt; }
 button { display: none; } h1 { break-before: page; } h1, h2, h3 { break-after: avoid; }
 tr, pre { break-inside: avoid; } pre { white-space: pre-wrap; }
 a { color: inherit; } @page { margin: 18mm; }
}
"""


def main() -> None:
    chapters = []
    for filename, anchor in CHAPTERS.items():
        text = (ROOT / filename).read_text(encoding="utf-8")
        text = re.sub(r"^(# .+)$", r"\1 {#" + anchor + "}", text, count=1, flags=re.M)
        for target, destination in CHAPTERS.items():
            text = text.replace("(" + target + ")", "(#" + destination + ")")
        chapters.append(text)
    body = markdown.markdown("[TOC]\n\n" + "\n\n".join(chapters),
                             extensions=["tables", "fenced_code", "toc", "attr_list"],
                             extension_configs={"toc": {"toc_depth": "1-2"}})
    page = ('<!doctype html>\n<html lang="pl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>STM Viewer — instalacja i obsługa</title><style>' + STYLE +
            '</style></head><body><main><p><strong>STM Viewer — podręcznik użytkownika</strong>'
            ' · 3 listopada 2026</p><p>Instalacja, obsługa i opcjonalne modele. '
            'Ten plik można otworzyć bezpośrednio w przeglądarce.</p>'
            '<button onclick="window.print()">Drukuj / zapisz jako PDF</button>\n' +
            body + '\n</main></body></html>\n')
    (ROOT / "guide.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
