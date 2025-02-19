# coding: utf-8
from multiprocessing import process
from PyQt5.QtCore import * # type: ignore
from PyQt5.QtGui import * # type: ignore
from PyQt5.QtWidgets import * # type: ignore
from inquirer import Checkbox
from numpy import signbit
from qfluentwidgets import * # type: ignore
from PyQt5.QtWebEngineWidgets import * # type: ignore
from PyQt5.QtWebChannel import * # type: ignore
from ..common.config import *
from ..common.style_sheet import StyleSheet
from ..common.icon import Icon
import os, shutil
import subprocess
from ..common.signal_bus import signalBus
import math
from utils.map_utils import *
from ..common.config import *
import concurrent.futures
import json  # Add this import

class InfoInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("infoInterface")
        signalBus.sendCommonInfo.connect(self.handleCommonInfo)
        signalBus.sendRendererInfo.connect(self.handleRendererInfo)
        signalBus.sendBackendInfo.connect(self.handleBackendInfo)

        self.initUI()

    def initUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.topLayout = QHBoxLayout(self)
        self.mainLayout.addLayout(self.topLayout)
        # Create top layout for two QTextEdits

        self.backendLayout = QVBoxLayout(self)
        self.topLayout.addLayout(self.backendLayout)
        self.backendMessageLabel = QLabel("Backend message", self)
        self.backendMessageLabel.setFont(QFont("Helvetica", 6))
        self.backendLayout.addWidget(self.backendMessageLabel)
        
        self.backendMessageEdit = TextEdit(self)
        self.backendLayout.addWidget(self.backendMessageEdit)
        
        self.rendererLayout = QVBoxLayout(self)
        self.topLayout.addLayout(self.rendererLayout)
        self.rendererMessageLabel = QLabel("Renderer message", self)
        self.rendererMessageLabel.setFont(QFont("Helvetica", 6))
        self.rendererLayout.addWidget(self.rendererMessageLabel)
        
        self.rendererMessageEdit = TextEdit(self)
        self.rendererLayout.addWidget(self.rendererMessageEdit)
        
        # Create bottom QTextEdit
        self.commonMessageLabel = QLabel("Common message", self)
        self.commonMessageLabel.setFont(QFont("Helvetica", 6))
        self.mainLayout.addWidget(self.commonMessageLabel)
        
        self.commonMessageEdit = TextEdit(self)
        self.mainLayout.addWidget(self.commonMessageEdit)

    def handleCommonInfo(self, info):
        self.commonMessageEdit.append(info)
    
    def handleRendererInfo(self, info):
        self.rendererMessageEdit.append(info)

    def handleBackendInfo(self, info):
        self.backendMessageEdit.append(info)
