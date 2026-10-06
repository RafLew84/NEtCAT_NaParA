"""Exercise real file decoding, arguments, stdout, stderr and process status."""

import json
from pathlib import Path
import sys


message = "Zażółć gęślą jaźń — Łódź, źródło, przesunięcie"
print(json.dumps({
    "message": message,
    "arguments": sys.argv[2:],
    "utf8_mode": sys.flags.utf8_mode,
    "stdin_encoding": sys.stdin.encoding,
    "stdout_encoding": sys.stdout.encoding,
    "stderr_encoding": sys.stderr.encoding,
    "source": Path(__file__).read_text(),
}, ensure_ascii=False))
print("Błąd próbny: " + message, file=sys.stderr)
raise SystemExit(int(sys.argv[1]))
