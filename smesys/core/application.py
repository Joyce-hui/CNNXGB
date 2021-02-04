#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import hashlib
import os

from zhkui import util

class Application(object):
    def __init__(self, path, typ=0):
        """ A class that represents an application to be processed.

        - path str: The full path of the application
        - typ int: (Deprecated) The type of the application: virus(-1), unknown(0): benign(1)
        """

        self.path = util.getabs([path])
        self.type = typ
        self.name = self._getname()
        self.md5, self.sha256 = self._gethash()
        self.sz = self._getsz()

    def _getname(self):
        return os.path.basename(self.path)

    def _gethash(self):
        """Get file md5 and sha256"""
        with open(self.path, mode = 'rb') as _:
            content = _.read()
            md5= hashlib.md5(content).hexdigest()
            sha256= hashlib.sha256(content).hexdigest()
        return md5, sha256

    def _getsz(self):
        """Get file size in bytes"""
        return os.path.getsize(self.path)
