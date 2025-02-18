# coding:utf-8
from qfluentwidgets import (SwitchSettingCard, FolderListSettingCard,
                            OptionsSettingCard, PushSettingCard,
                            HyperlinkCard, PrimaryPushSettingCard, ScrollArea,
                            ComboBoxSettingCard, ExpandLayout, Theme, CustomColorSettingCard, TextEdit,
                            setTheme, setThemeColor, isDarkTheme, setFont, RangeSettingCard)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import SettingCardGroup as CardGroup
from qfluentwidgets import InfoBar
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QStandardPaths
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import QWidget, QLabel, QFileDialog

from ..common.config import cfg, isWin11, pedSpeed, rideSpeed, driveSpeed, pubSpeed
from ..common.setting import HELP_URL, FEEDBACK_URL, AUTHOR, VERSION, YEAR, REPO_URL
from ..common.signal_bus import signalBus
from ..common.style_sheet import StyleSheet
from ..common.icon import Icon


class SettingCardGroup(CardGroup):

   def __init__(self, title: str, parent=None):
       super().__init__(title, parent)
       setFont(self.titleLabel, 14, QFont.Weight.DemiBold)



class SettingInterface(ScrollArea):
    """ Setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        signalBus.visitSourceCodeSig.connect(self.visitSourceCode)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = QLabel(self.tr("Settings"), self)

        # personalization
        self.personalGroup = SettingCardGroup(
            self.tr('Personalization'), self.scrollWidget)
        self.micaCard = SwitchSettingCard(
            FIF.TRANSPARENT,
            self.tr('Mica effect'),
            self.tr('Apply semi transparent to windows and surfaces'),
            cfg.micaEnabled,
            self.personalGroup
        )
        self.themeCard = ComboBoxSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            self.tr('Application theme'),
            self.tr("Change the appearance of your application"),
            texts=[
                self.tr('Light'), self.tr('Dark'),
                self.tr('Use system setting')
            ],
            parent=self.personalGroup
        )
        self.zoomCard = ComboBoxSettingCard(
            cfg.dpiScale,
            FIF.ZOOM,
            self.tr("Interface zoom"),
            self.tr("Change the size of widgets and fonts"),
            texts=[
                "100%", "125%", "150%", "175%", "200%",
                self.tr("Use system setting")
            ],
            parent=self.personalGroup
        )

        # advanced settings
        self.advancedGroup = SettingCardGroup(
            self.tr('Advanced'), self.scrollWidget)
        self.pedestrainCard = RangeSettingCard(
            cfg.pedestrianSpeed,
            FIF.ROBOT,
            self.tr('Walking speed'),
            self.tr('Set the speed of pedestrian (km/h)'),
            parent=self.advancedGroup
        )
        self.ridingCard = RangeSettingCard(
            cfg.ridingSpeed,
            FIF.SPEED_MEDIUM,
            self.tr('Riding speed'),
            self.tr('Set the speed of riding (km/h)'),
            parent=self.advancedGroup
        )
        self.drivingCard = RangeSettingCard(
            cfg.drivingSpeed,
            FIF.CAR,
            self.tr('Driving speed'),
            self.tr('Set the speed of driving (km/h)'),
            parent=self.advancedGroup
        )
        self.pubTransportCard = RangeSettingCard(
            cfg.pubTransportSpeed,
            FIF.BUS,
            self.tr('Public Transport speed'),
            self.tr('Set the speed of public transport (km/h)'),
            parent=self.advancedGroup
        )

        # application
        self.aboutGroup = SettingCardGroup(self.tr('About'), self.scrollWidget)
        self.aboutCard = PrimaryPushSettingCard(
            self.tr('View Source Code'),
            Icon.APPICON,
            self.tr('About'),
            '© ' + self.tr('Copyright') + f" {YEAR}, {AUTHOR}. " +
            self.tr('Version') + " " + VERSION,
            self.aboutGroup
        )

        self.__initWidget()

    def visitSourceCode(self):
        """ visit source code """
        QDesktopServices.openUrl(QUrl(REPO_URL))

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 100, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('settingInterface')

        # initialize style sheet
        setFont(self.settingLabel, 23, QFont.Weight.DemiBold)
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)
        self.scrollWidget.setStyleSheet("QWidget{background:transparent}")

        self.micaCard.setEnabled(isWin11())

        # initialize layout
        self.__initLayout()
        self._connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 50)

        self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.zoomCard)

        self.advancedGroup.addSettingCard(self.pedestrainCard)
        self.advancedGroup.addSettingCard(self.ridingCard)
        self.advancedGroup.addSettingCard(self.drivingCard)
        self.advancedGroup.addSettingCard(self.pubTransportCard)

        self.aboutGroup.addSettingCard(self.aboutCard)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.advancedGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def _showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.success(
            self.tr('Updated successfully'),
            self.tr('Configuration takes effect after restart'),
            duration=1500,
            parent=self
        )

    def _connectSignalToSlot(self):
        """ connect signal to slot """
        cfg.appRestartSig.connect(self._showRestartTooltip)

        cfg.themeChanged.connect(setTheme)
        self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)

        self.aboutCard.clicked.connect(signalBus.visitSourceCodeSig)

        self.pedestrainCard.slider.valueChanged.connect(self.onSliderValueChanged)
        self.ridingCard.slider.valueChanged.connect(self.onSliderValueChanged)
        self.drivingCard.slider.valueChanged.connect(self.onSliderValueChanged)
        self.pubTransportCard.slider.valueChanged.connect(self.onSliderValueChanged)

    def onSliderValueChanged(self):
        global pedSpeed, rideSpeed, driveSpeed, pubSpeed
        pedSpeed = self.pedestrainCard.slider.value()
        rideSpeed = self.ridingCard.slider.value()
        driveSpeed = self.drivingCard.slider.value()
        pubSpeed = self.pubTransportCard.slider.value()
