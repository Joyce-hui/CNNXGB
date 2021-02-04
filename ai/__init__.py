#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

''' Deep learning module '''

import logging
import os

# Disable tensorflow verbose output, this line must be put before the import of cnnxgb
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

from . import cnnxgb

def predict_by_cnnxgb(apkpath):
    return cnnxgb.predict(apkpath)
