#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import json
import os

from zhkui import util

class ConfigurationManger(object):
    def __init__(self):
        self.confdir = util.getabs(['~', '.config', 'zhkui'])
        self.confmain = util.getabs([self.confdir, 'config.json'])
        self.config = None
        if not os.path.exists(self.confmain):
            raise Exception('Please init Zhkui system!')
        with open(self.confmain, 'r') as _:
            self.config = json.load(_)
