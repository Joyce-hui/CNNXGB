#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import zhkui
from zhkui import util

CONFIG = {
    'name': 'demo',
    'desc': 'A plugin demo',
}

class Plugin(object):
    def __init__(self):
        self.confmgr = zhkui.config.ConfigurationManger()
        self.logger = util.Log()

    def run(self):
        self.logger.i("It works!")
