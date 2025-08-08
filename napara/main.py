# napara/main.py
from PyQt6.QtWidgets import QApplication
from napara.gui.main_window import MainWindow
import sys
import pyqtgraph as pg

def main():
    pg.setConfigOptions(imageAxisOrder='row-major')

    app = QApplication(sys.argv)
    app.setOrganizationName("NaParA")
    app.setApplicationName("NaParA - Nanoparticle Analyzer")

    win = MainWindow()
    win.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
