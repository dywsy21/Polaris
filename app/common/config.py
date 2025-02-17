# coding:utf-8
import sys
from enum import Enum

from PyQt5.QtCore import QLocale
from qfluentwidgets import (qconfig, QConfig, ConfigItem, OptionsConfigItem, BoolValidator,
                            OptionsValidator, Theme, FolderValidator, ConfigSerializer, RangeConfigItem, RangeValidator)

from .setting import CONFIG_FILE
import os
# map_relative_path = os.path.join("backend", "data", "map.osm")
# db_path = os.path.join("backend", "data", "map.db")
# map_html_path = os.path.join("AppData", "map.html")

map_relative_path = os.path.join("map_data", "map.osm")
db_path = os.path.join("map_data", "map.db")
map_html_path = os.path.join("AppData", "map.html")

pedSpeed = 1
rideSpeed = 15
driveSpeed = 60
pubSpeed = 60

class Language(Enum):
    """ Language enumeration """

    CHINESE_SIMPLIFIED = QLocale(QLocale.Chinese, QLocale.China)
    CHINESE_TRADITIONAL = QLocale(QLocale.Chinese, QLocale.HongKong)
    ENGLISH = QLocale(QLocale.English)
    AUTO = QLocale()


class LanguageSerializer(ConfigSerializer):
    """ Language serializer """

    def serialize(self, language):
        return language.value.name() if language != Language.AUTO else "Auto"

    def deserialize(self, value: str):
        return Language(QLocale(value)) if value != "Auto" else Language.AUTO


def isWin11():
    return sys.platform == 'win32' and sys.getwindowsversion().build >= 22000


class Config(QConfig):
    """ Config of application """

    # TODO: ADD YOUR CONFIG GROUP HERE


    # main window
    micaEnabled = ConfigItem("MainWindow", "MicaEnabled", isWin11(), BoolValidator())
    dpiScale = OptionsConfigItem(
        "MainWindow", "DpiScale", "Auto", OptionsValidator([1, 1.25, 1.5, 1.75, 2, "Auto"]), restart=True)
    language = OptionsConfigItem(
        "MainWindow", "Language", Language.AUTO, OptionsValidator(Language), LanguageSerializer(), restart=True)

    # software update
    checkUpdateAtStartUp = ConfigItem("Update", "CheckUpdateAtStartUp", True, BoolValidator())

    # speed settings
    pedestrianSpeed = RangeConfigItem("Speed", "PedestrianSpeed", 1, RangeValidator(1, 10))
    ridingSpeed = RangeConfigItem("Speed", "RidingSpeed", 15, RangeValidator(5, 30))
    drivingSpeed = RangeConfigItem("Speed", "DrivingSpeed", 60, RangeValidator(20, 120))
    pubTransportSpeed = RangeConfigItem("Speed", "PubTransportSpeed", 60, RangeValidator(20, 150))


cfg = Config()
cfg.themeMode.value = Theme.AUTO
qconfig.load(str(CONFIG_FILE.absolute()), cfg)
