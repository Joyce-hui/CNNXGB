#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import requests
import copy

class Requestsx(object):
    def __init__(self, **presets):
        self.presets = {}
        if presets: self.presets.update(**presets)

    def get(self, url, **kwargs):
        options = copy.deepcopy(self.presets)
        options.update(**kwargs)
        return requests.get(url, **options)

    def post(self, url, **kwargs):
        options = copy.deepcopy(self.presets)
        options.update(**kwargs)
        return requests.post(url, **options)
