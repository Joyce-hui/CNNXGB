#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

''' # Plugin System

Plugins are searched in two places: `zhkui.plugins` and `$HOME/.config/zhkui/plugins`.
Plugin file name must begin with `plugin_`, a plugin structure is showed as below

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

`CONFIG['name']` is required, each plugin may use the root namespace `zhkui` to
implement their own logic in the `run` method which afterwards will be called.
'''

from . import runner
