# coding: utf-8
from pathlib import Path

# change DEBUG to False if you want to compile the code to exe
# DEBUG = "__compiled__" not in globals()
DEBUG = False 


YEAR = 2024
AUTHOR = "Wangsy"
VERSION = "v1.0.0"
APP_NAME = "Polaris"
HELP_URL = "https://github.com/dywsy21/Data-Structure-Project/blob/main/README.md"
REPO_URL = "https://github.com/dywsy21/Data-Structure-Project"
FEEDBACK_URL = "https://github.com/dywsy21/Data-Structure-Project/issues"
DOC_URL = "https://github.com/dywsy21/Data-Structure-Project/blob/main/README.md"

CONFIG_FOLDER = Path('AppData').absolute()
CONFIG_FILE = CONFIG_FOLDER / "config.json"
