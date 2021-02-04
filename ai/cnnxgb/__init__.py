#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import json
import numpy as np
import os
from pathlib import Path

from PIL import Image, ImageDraw
import simhash

import zhkui
from zhkui.util import Result

def predict(apkpath):
    '''
    - return Result(status, bool): True if the application is malware
    '''

    cnnxgb = _CNNXGB(apkpath)
    return cnnxgb.predict()

class _CNNXGB(object):

    VERSION = '1.0.0'

    def __init__(self, apkpath):
        '''
        - app str: The full path to the Android application
        '''

        self.check_environment()

        self.parser = zhkui.parser.android.Android(apkpath)
        self.params = None
        with open(Path(Path(__file__).parent, 'params.json').absolute(), 'r') as _:
            self.params = json.load(_)[self.VERSION]
        self.confmgr = zhkui.config.ConfigurationManger()
        self.logger = zhkui.util.Log()

    def check_environment(self):
        cpu_cuda_env = 'CUDA_VISIBLE_DEVICES'
        if os.getenv(cpu_cuda_env) is None:
            self.logger.w(f'The image size is large, please do `export {cpu_cuda_env}=` to enable CPU')

    def predict(self):
        ''' Predict category of the application

        The model should save into `<confdir>/model/cnnxgb/<version>/`.
        '''

        from keras.models import load_model
        import xgboost as xgb

        modeldir = Path(self.confmgr.confdir, 'model', 'cnnxgb', self.VERSION)

        r = self.get_cnnxgb_features()
        if not r.status: return r
        features = r.value

        cnn_model_file = Path(modeldir, 'CNNXGB-CNN.model')
        cnn_model = load_model(cnn_model_file)
        # CNN output example: [[1.7378864e-11 1.0000000e+00]]
        cnn_pred = cnn_model.predict(np.array([features['img'], ]))
        cnn_pred = cnn_pred[0][1]

        xgb_model_file = Path(modeldir, 'CNNXGB-XGB.model')
        xgb_model = xgb.Booster({'nthread': 4})
        xgb_model.load_model(xgb_model_file)
        feature = features['perms'] + features['apis']
        # XGBoost output example:: [0.9816855]
        xgb_pred = xgb_model.predict(xgb.DMatrix(np.array([feature])))
        xgb_pred = xgb_pred[0]

        wxgb, wcnn = 0.67, 0.33
        pred = xgb_pred * wxgb + cnn_pred * wcnn
        return Result(True, bool(round(pred)))

    def get_cnn_model(self):
        from keras.models import Sequential
        from keras.layers import Conv2D, MaxPooling2D, Dropout, Flatten, Dense, Activation, BatchNormalization
        from keras.optimizers import SGD

        IMAGE_WIDTH = 1024
        IMAGE_HEIGHT = 1024
        IMAGE_SIZE = (IMAGE_WIDTH, IMAGE_HEIGHT)
        IMAGE_CHANNELS = 4

        model = Sequential()

        model.add(Conv2D(32, (3, 3), activation='relu', input_shape=(IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_CHANNELS)))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))

        model.add(Conv2D(64, (3, 3), activation='relu'))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))

        model.add(Conv2D(128, (3, 3), activation='relu'))
        model.add(BatchNormalization())
        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(Dropout(0.25))

        model.add(Flatten())
        model.add(Dense(512, activation='relu'))
        model.add(BatchNormalization())
        model.add(Dropout(0.5))
        model.add(Dense(2, activation='softmax'))

        sgd = SGD(lr=0.001, decay=1e-8, momentum=0.9, nesterov=True)

        model.compile(optimizer=sgd, loss='binary_crossentropy', metrics=['accuracy'])

        model.summary()
        return model

    def get_cnnxgb_features(self):
        ''' Get normalized features

        return Result(status, features: dict):

        features structure:

            {
                'perms': list of 0 or 1,
                'apis': list of float which values are in [0, 1],
                'img': numpy 2d-array which values are in [0, 1],
            }
        '''
        r = self.get_cnnxgb_features_data()
        if not r.status: return r

        perms = r.value['perms']
        permission_feature = []
        for p in self.params['perms']:
            if p in perms:
                permission_feature.append(1)
            else:
                permission_feature.append(0)

        apis = r.value['apis']
        apis_feature_raw = []
        for api in self.params['apis']:
            if api in apis.keys():
                apis_feature_raw.append(apis[api])
            else:
                apis_feature_raw.append(0)
        apis_feature = np.array(apis_feature_raw)
        apis_feature_delta = np.max(apis_feature) - np.min(apis_feature)
        if apis_feature_delta != 0:
            apis_feature = (apis_feature - np.min(apis_feature)) / apis_feature_delta

        img_feature = np.asarray(r.value['img']) / 255

        return Result(
            status=True,
            value={
                'perms': permission_feature,
                'apis': apis_feature.tolist(),
                'img': img_feature
            }
        )

    def get_cnnxgb_features_data(self):
        ''' Generate features for CNNXGB model from Android appliation

        - return Result(status: bool, features: dict):

            features structure:

                {
                    'perms': [ '<name>', '<name>' ],
                    'apis': [
                        { '<name>': int },
                        { '<name>': int },
                    ],
                    'img': Instance of PIL.image
                }
        '''

        SYSPKGS = (
            "Landroid/", "Lcom/android/internal/util", "Ldalvik/", "Ljava/",
            "Ljavax/", "Lorg/apache/", "Lorg/json/", "Lorg/w3c/dom/",
            "Lorg/xml/sax", "Lorg/xmlpull/v1/", "Ljunit/"
        )

        features_data = {}

        # Get permissions
        features_data['perms'] = self.parser.get_permissions()

        r = self.parser.get_extpkgs()
        if not r.status: return r
        extpkgs = tuple(f'L{pkg.replace(".", "/")}/' for pkg in r.value.keys())

        '''
        1) Do statistics on API frequences to get API feature
        2) Encode every basic block using simhash algorithm
        '''
        xyrgb, apifreq = [], {}
        methods = self.parser.get_methods()
        for item in methods:
            mid = list(item.keys())[0]
            method = item[mid]
            # skip third-party packages
            if mid.startswith(extpkgs):
                continue
            # external method, no codes at all, skipped
            if method['ext']:
                continue

            mnemonic = ''
            for bb in method['bb']:
                for instruct in bb['i']:
                    mnemonic += instruct['m']
                    if instruct['m'].startswith('invoke-'):
                        if '->' in instruct['o']:
                            #  v0, Ljava/lang/Object;-><init>()V
                            mid = instruct['o'].find('->')
                            end = instruct['o'].find('(', mid)
                            api = instruct['o'][:end].split(',')[0].strip()
                            if api.startswith(SYSPKGS):
                                if api not in apifreq:
                                    apifreq[api] = 1
                                else:
                                    apifreq[api] += 1
            if len(mnemonic) > 0:
                xyrgb.append(self.get_xyrgb(mnemonic))

        features_data['apis'] = apifreq

        # Get image feature using the data generated by simhash
        r = self.get_image(xyrgb)
        if not r.status: return r
        features_data['img'] = r.value

        return Result(status=True, value=features_data)

    def get_xyrgb(self, s):
        ''' Do Simhash on string s to get its color representation

        - s str: A string
        - return five-element tuple: (x, y, r, g, b)
        '''
        bitsz = 48
        bits = bin(simhash.Simhash(s, f=bitsz).value)[2:]
        if len(bits) != bitsz:
            padsz = bitsz - len(bits)
            bits = '0' * padsz + bits
        bits = bits[:44]
        x, y = int(bits[:10], 2), int(bits[10:20], 2)
        r, g, b = tuple(int(bits[20 + i * 8: 20 + (i + 1) * 8], 2) for i in range(3))
        return (x, y, r, g, b)

    def get_image(self, pxseq):
        ''' Get a 1024*1024 image from pixel sequences

        - pxseq list of five-element tuple: Each element has the style (x, y, r, g, b)
        - return util.Result:

            If success, the Result.value will be the generated PIL.Image instance
        '''

        w, h = 1024, 1024

        if len(pxseq) > w * h:
            return Result(status=False, value='Sequence is too long!')

        stats = {}
        img = Image.new(mode='RGBA', size=(w, h), color=(0, 0, 0, 255))
        for px in pxseq:
            x, y, r, g, b = px

            # Skip default pixel value
            if r == 0 and g == 0 and b == 0: continue

            rr, gg, bb, _ = img.getpixel((x, y))


            # Current location is empty, fill it
            if rr == 0 and gg == 0 and bb == 0:
                img.putpixel((x, y), (r, g, b, 255))
                continue

            # Same location same color
            if rr == r and gg == g and bb == b:
                k = f'{x}:{y}:{r}:{g}:{b}'
                if k not in stats:
                    stats[k] = 1
                else:
                    stats[k] += 1
            # Same location but different color, color conflict! We should find
            # the next empty location
            else:
                has_next_pos = False
                deltas = range(1, max(w, h) - min(x, y) + 1)
                for delta in deltas:
                    neighbours = self.get_neighbours(w, h, x, y, delta)
                    for neighbour in neighbours:
                        newr, newg, newb, _ = img.getpixel(neighbour)
                        if newr == 0 and newg == 0 and newb == 0:
                            x, y = neighbour
                            has_next_pos = True
                            break
                    if has_next_pos:
                        break
                if not has_next_pos:
                    return Result(status=False, value='Exhausted searching, but no empty cell!')
                else:
                    img.putpixel((x, y), (r, g, b, 255))

        # Adjust alpha value for the pixel of same color same location
        # the number of conflict and its corresponding alpha value
        #   < 10          => 0
        #   [10, 20)      => 1
        #   [20, 30)      => 2
        #   [30, 40)      => 3
        #   ...
        #   [2530, 2540)  => 253
        #   >= 2540       => 254

        freqseg = [i * 10 for i in range(1, 254)]
        for stat in stats:
            x, y, r, g, b = [int(i) for i in stat.split(':')]
            freq = stats[stat]
            if freq < 10:
                alpha = 0
            elif freq >= 2540:
                alpha = 254
            else:
                if freq in freqseg:
                    alpha = freq // 10
                else:
                    alpha = (freq - freq % 10) // 10
            img.putpixel((x, y), (r, g, b, alpha))


        return Result(status=True, value=img)

    def get_neighbours(self, w, h, x, y, r):
        ''' Get neighbours around (x, y) with distance r in flat (0, 0, w-1, h-1)

        The walk illustration

                            1
                (x-1, y-1) --> (x+1, y-1)

                    | 3  (x, y)    | 4
                    v              v
                            2
                (x-1, y+1) --> (x+1, y+1)

        '''
        pos = []

        for i in range(x - r, x + r + 1):
            safex = 0 <= i and i < w
            if safex and y - r >= 0: pos.append((i, y - r))
            if safex and y + r < h: pos.append((i, y + r))

        for j in range(y - r + 1, y + r):
            safey = 0 <= j and j < h
            if safey and x - r >= 0: pos.append((x - r, j))
            if safey and x + r < w: pos.append((x + r, j))

        return pos
