#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

from inspect import getframeinfo,stack
import logging
import json
import os

class Log(object):

    # Logging modes
    ERROR   = 0x01
    WARN    = 0x02
    INFO    = 0x04
    DEBUG   = 0x08
    VERBOSE = 0x10
    PLAIN   = 0x12 # simply print the message and exit

    # Decode log mode
    MODED = {
        0x01: 'ERROR',
        0x02: 'WARN',
        0x04: 'INFO',
        0x08: 'DEBUG',
        0x10: 'VERBOSE',
        0x12: 'PLAIN',
    }

    # Encode log mode
    MODEE = {
            'ERROR': 0x01,
            'WARN':  0x02,
            'INFO':  0x04,
            'DEBUG': 0x08,
            'VERBOSE': 0x010,
            'PLAIN': 0x12,
    }

    # Logging tags
    TAGS = {
        ERROR: '[E] ',
        WARN: '[W] ',
        INFO: '[I] ',
        DEBUG: '[D] ',
        VERBOSE: '[V] ',
    }

    CONFIG = os.path.expanduser('~/.log.json')

    def __init__(self, level=INFO):
        ''' Log util

        - level limited int(optional, depracated): Choose one from Log.ERROR, Log.INFO,
              Log.WARN, Log.DEBUG, Log.VERBOSE, Log.VERBOSE. Default to be Log.INFO.

        The message to be printed depends on the log level.

        - Log.PLAIN: It always prints.
        - Log.ERROR: Print `Log.e` message
        - Log.INFO: Print `Log.e, Log.i` message
        - Log.WARN: Print `Log.e, Log.i, Log.w` message
        - Log.DEBUG: Print `Log.e, Log.i, Log.w, Log.d` message
        - Log.VERBOSE: Print `Log.e, Log.i, Log.w, Log.d, Log.v` message
        '''

        self.level = 'PLAIN'

        if not os.path.exists(self.CONFIG):
            with open(self.CONFIG, 'w') as _:
                json.dump({'level': 'PLAIN'}, _, ensure_ascii=False, indent=2)

        # Log level is controled by configurations
        with open(self.CONFIG, 'r') as _:
            self.level = self.MODEE[json.load(_)['level']]

    def _log(self, level, msg, tag):
        # Plain mode will simple print the message and exit
        if self.level == Log.PLAIN:
            print(f'{msg}')
            return

        # suppress logging message which below the specify level
        if level <= self.level:
            # If the level is 'INFO' we will not print callerstack
            if level != self.MODEE['INFO']:
                caller = getframeinfo(stack()[2][0])
                info = f'[{caller.filename}->{caller.function}->{caller.lineno}]'
                print(info)
            # Prefix message with tag and print
            tagval = self.TAGS.get(level, '')
            if tag: tagval =  tag
            print(f'{tagval}{msg}')

    def e(self, msg, tag=None):
        self._log(Log.ERROR, msg, tag)

    def i(self, msg, tag=None):
        self._log(Log.INFO, msg, tag)

    def w(self, msg, tag=None):
        self._log(Log.WARN, msg, tag)

    def d(self, msg, tag=None):
        self._log(Log.DEBUG, msg, tag)

    def v(self, msg, tag=None):
        self._log(Log.VERBOSE, msg, tag)
