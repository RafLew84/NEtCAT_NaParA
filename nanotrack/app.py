import sys

from PyQt6.QtWidgets import QApplication, QMainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setOrganizationName("NaParA")
    app.setApplicationName("NanoTrack")

    window = QMainWindow()
    window.setWindowTitle("NanoTrack")
    window.resize(1100, 800)
    window.show()

    sys.exit(app.exec())
