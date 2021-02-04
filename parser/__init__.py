#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

''' Various application parser '''

from . import android
import hashlib
import os

from zhkui import util

def is_platform_supported(platform):
    if platform in ['android']:
        return True
    else:
        return False
