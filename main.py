# coding:utf-8
import os
import sys

from PyQt5.QtCore import Qt, QTranslator, QProcess, pyqtSignal, QDir
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QCompleter
from qfluentwidgets import FluentTranslator, InfoBar, InfoBarPosition

from app.common.config import *
from app.view.main_window import MainWindow
from app.common.signal_bus import signalBus

# preprocess osm data
if not os.path.exists(db_path):
    print("Preprocessing OSM data...")
    from preprocess_osm import preprocess_osm_data
    preprocess_osm_data(map_relative_path, db_path)
    print("Preprocessing OSM data completed.")

# enable dpi scale
if cfg.get(cfg.dpiScale) != "Auto":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(cfg.get(cfg.dpiScale))
else:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

class Application(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.backend_process = QProcess()
        # Specify the absolute path to backend.exe or ensure it's in the current working directory
        # backend_path = "backend/build/backend.exe"  # use this to enable serde
        backend_path = "build/backend"
        self.backend_process.setProgram(backend_path)
        
        # # Optionally, set the working directory
        # self.backend_process.setWorkingDirectory(QDir(backend_path).absolutePath())
        
        self.backend_process.setArguments([])
        self.backend_process.readyReadStandardOutput.connect(self.handle_backend_output)
        self.backend_process.readyReadStandardError.connect(self.handle_backend_error)
        self.backend_process.started.connect(self.on_backend_started)
        self.backend_process.errorOccurred.connect(self.handle_backend_error_occurred)  # Connect errorOccurred signal
        self.backend_process.start()

        # Connect the sendBackendRequest signal to the handler
        signalBus.sendBackendRequest.connect(self.handle_send_backend_request)
        
    def handle_backend_output(self):
        output = self.backend_process.readAllStandardOutput().data().decode()
        signalBus.backendOutputReceived.emit(output)
        # if "Graph loaded" in output:
        #     signalBus.backendGraphLoaded.emit(output)
        # elif "NO PATH" in output:
        #     signalBus.backendNoPathFound.emit()
        # elif "TIME" in output:
        #     signalBus.backendPathFound.emit(output)
        # elif "END" in output:
        #     signalBus.backendEndOutput.emit()

    def handle_backend_error(self):
        error = self.backend_process.readAllStandardError().data().decode()
        signalBus.backendErrorReceived.emit(error)

    def on_backend_started(self):
        # Emit the backendStarted signal via signalBus
        signalBus.backendStarted.emit()

    def handle_send_backend_request(self, request):
        self.backend_process.write(request.encode())  # Add newline character
        self.backend_process.waitForBytesWritten()  # Ensure the data is written

    def handle_backend_error_occurred(self, error):
        error_messages = {
            QProcess.FailedToStart: "Failed to start the backend process. Please check the executable path.",
            QProcess.Crashed: "The backend process crashed.",
            QProcess.Timedout: "The backend process timed out.",
            QProcess.WriteError: "An error occurred when attempting to write to the backend process.",
            QProcess.ReadError: "An error occurred when attempting to read from the backend process.",
            QProcess.UnknownError: "An unknown error occurred with the backend process."
        }
        error_message = error_messages.get(error, "An undefined error occurred.")
        InfoBar.error(
            title="Backend Error",
            content=error_message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=None  # Adjust parent if necessary
        )


# create application
app = Application(sys.argv)
app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

# internationalization
locale = cfg.get(cfg.language).value
translator = FluentTranslator(locale)
galleryTranslator = QTranslator()
galleryTranslator.load(locale, "app", ".", ":/app/i18n")

app.installTranslator(translator)
app.installTranslator(galleryTranslator)

# create main window``
w = MainWindow()
w.show()

app.exec()
