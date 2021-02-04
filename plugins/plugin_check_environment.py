#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

CONFIG = {
    'name': 'env',
    'desc': 'Check zhkui running environment',
}

class Plugin(object):
    def __init__(self, zhkui):
        self.confmgr = zhkui.config.ConfigurationManger()
        self.config = self.confmgr.config

    def run(self):
        # Environment Checking
        for k in ['datadir', 'apktool']:
            if util.check_path(self.config[k]):
                print(f'[+] {k} is fine!')
            else:
                print(f'[x] {k} is not valid!')
        for k in ['jar', 'profiles', 'android-jar']:
            if util.check_path(self.config['libscout'][k]):
                print(f'[+] libscout {k} is fine!')
            else:
                print(f'[x] libscout {k} is not valid!')

