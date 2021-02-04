#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

''' Zhkui - A malware detection framework for Android '''

import copy
import json
import os

from . import ai
from . import config
from . import network
from . import parser
from . import routers
from . import smesys
from . import util
from . import plugins

__pdoc__ = {}

def zhkui_init():
    ''' Initialize and update configration in `$HOME/.config/zhkui/config.json`

    This plugin ensures

    - The exist of configuration, logs, temporary directory
    - Update configurations if user have changed some values to the configuration

    A simple configration is showed below

        {
            "datadir": "",
            "database": {
                "host": "127.0.0.1",
                "port": 5432,
                "dbname": "db_app",
                "user": "zhkui",
                "password": "zhkui"
            },
            "logs": "",
            "proxy": {
                "http": "",
                "https": ""
            },
            "apktool": "",
            "vtkeys": [
            ],
            "tmpdir": "",
            "libscout": {
                "jar": "$HOME/.usr/libscout/LibScout.jar",
                "profiles": "$HOME/.usr/libscout/libscout-profiles",
                "android-jar": "$ANDROID_HOME/platforms/android-29/android.jar"
            }
        }

    - datadir

    '''

    confdir = util.getabs(['~', '.config', 'zhkui'])
    confmain = util.getabs([confdir, 'config.json'])
    logger = util.Log()
    CONFIG_TEMPLATE = {
        # dataset directory
        'datadir': '',
        'database' : {
            'host': '127.0.0.1',
            'port': 5432,
            'dbname': 'db_app',
            'user': 'zhkui',
            'password': '123456',
        },
        # logs directory
        'logs': util.getabs([confdir, 'logs']),
        'proxy': {
            'http': '',
            'https': '',
        },
        # path to apktool.jar
        'apktool': '',
        # virustotal keys
        'vtkeys': [],
        # temporary directory
        'tmpdir': util.getabs([confdir, 'tmp']),
        # path to libscout jar and profiles
        'libscout': {
            'jar': '',
            'profiles': '',
            'android-jar': '',
        }
    }

    os.makedirs(confdir, exist_ok=True)

    # Load main configuration into memory
    config = copy.deepcopy(CONFIG_TEMPLATE)
    os.makedirs(config['logs'], exist_ok=True)
    os.makedirs(config['tmpdir'], exist_ok=True)

    new_created = True
    if os.path.exists(confmain):
        # Update configurations if it exists
        with open(confmain, 'r') as _:
            user_config = json.load(_)

            # Update subdict
            for subdict in ['database', 'proxy', 'libscout']:
                tmp = copy.deepcopy(config[subdict])
                if subdict in user_config:
                    tmp.update(user_config[subdict])
                    user_config[subdict].update(tmp)
                else:
                    user_config[subdict] = tmp

            config.update(user_config)

        # If user does not set the default options, set them to defaults
        if not config['logs']: config['logs'] = CONFIG_TEMPLATE['logs']
        if not config['tmpdir']: config['tmpdir'] = CONFIG_TEMPLATE['tmpdir']

        # Ensure the path is absolute
        for d in ['datadir', 'apktool']:
            if config[d]: config[d] = util.getabs([config[d]])

        new_created = False

    with open(confmain, 'w') as _:
        json.dump(config, _, ensure_ascii=False, indent=4)

    if new_created:
        logger.i(f'Configuration is created at {confmain}, please config it manually!')
    else:
        logger.i(f'Configuration file is reloaded successfully!')
