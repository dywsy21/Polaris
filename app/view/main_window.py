# coding: utf-8
from PyQt5.QtCore import QUrl, QSize, Qt, QProcess  # Ensure Qt is imported
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtWidgets import QApplication

from qfluentwidgets import * # type: ignore
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, InfoBarPosition  # Ensure InfoBar imports are present

from .setting_interface import SettingInterface
from .map_interface import MapInterface, QPixmap
from .info_interface import InfoInterface
from ..common.config import cfg
from ..common.icon import Icon
from ..common.signal_bus import signalBus
from ..common import resource


class MainWindow(FluentWindow):

    def __init__(self):
        super().__init__()
        self.initWindow()

        # 创建子界面
        self.mapInterface = MapInterface(self)
        self.infoInterface = InfoInterface(self)
        self.settingInterface = SettingInterface(self)
        self.connectSignalToSlot()

        # 添加导航项
        self.initNavigation()

    def connectSignalToSlot(self):
        signalBus.micaEnableChanged.connect(self.setMicaEffectEnabled)
        signalBus.graphLoaded.connect(self.on_graph_loaded)  # Add this line

    def on_backend_started(self):
        InfoBar.success(
            title="Backend Started",
            content="Backend is running in the background.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def on_graph_loaded(self):
        InfoBar.success(
            title="Graph Loaded",
            content="Backend: Graph loaded successfully.",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
            parent=self
        )

    def initNavigation(self):
        self.navigationInterface.setAcrylicEnabled(True)
        # 添加导航项
        self.addSubInterface(self.mapInterface, Icon.MAP, self.tr('Map'))  # 添加地图界面到导航栏
        self.addSubInterface(
            self.settingInterface, FIF.SETTING, self.tr('Settings'), NavigationItemPosition.BOTTOM)
        self.addSubInterface(
            self.infoInterface, FIF.INFO, self.tr('Info'))

        self.splashScreen.finish()

    def initWindow(self):
        self.resize(960, 780)
        self.setMinimumWidth(760)
        self.setWindowIcon(QIcon(Icon.APPICON.path()))
        self.setWindowTitle('Polaris')

        self.setCustomBackgroundColor(QColor(240, 244, 249), QColor(32, 32, 32))
        self.setMicaEffectEnabled(cfg.get(cfg.micaEnabled))

        # 创建启动画面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(106, 106))
        self.splashScreen.raise_()

        desktop = QApplication.primaryScreen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
        self.show()
        QApplication.processEvents()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'splashScreen'):
            self.splashScreen.resize(self.size())

