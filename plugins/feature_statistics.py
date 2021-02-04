#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

'''

If you have not enough GPU memory, you can disable GPU training to use CPU training

    export CUDA_VISIBLE_DEVICES=

'''

import argparse
import gc
import json
import keras
from keras.optimizers import SGD
import math
import numpy as np
import pathlib
import pandas as pd
import pickle
from PIL import Image
from sklearn.model_selection import train_test_split, StratifiedKFold
import xgboost as xgb
import datetime

from mlmodels import run_model

KFOLD = 5
MAX_SAMPLE_COUNT = 0
IMAGE_WIDTH = 1024
IMAGE_HEIGHT = 1024
IMAGE_SIZE = (IMAGE_WIDTH, IMAGE_HEIGHT)
IMAGE_CHANNELS = 4

def epoch():
    today = datetime.datetime.today()
    return today.strftime("%Y-%m-%d.%H:%M:%S")

def api_statistics(featuredir):
    total = 0
    apifreq = {}
    for path in pathlib.Path(featuredir, 'features', 'raw').rglob('*.json'):
        with open(path, 'r') as _:
            feature = json.load(_)
            for k in feature['apifreq']:
                total += 1
                if k not in apifreq:
                    apifreq[k] = { 'black': 0, 'white': 0 }
                if feature['isblack']:
                    apifreq[k]['black'] += feature['apifreq'][k]
                else:
                    apifreq[k]['white'] += feature['apifreq'][k]
    apidiff = []
    for k in apifreq:
        diff = math.fabs(apifreq[k]['black'] - apifreq[k]['white'])
        #  diff = '{0:.3f}'.format(diff / total)
        diff = float('{0:.3f}'.format(diff / total))
        apidiff.append((k, diff))

    apicnt = 50
    sorted_api = sorted(apidiff, key=lambda k: k[1], reverse=True)
    sorted_api = sorted_api[:apicnt]

    with open(pathlib.Path(featuredir, 'api.json'), 'w') as _:
        json.dump(sorted_api, _, ensure_ascii=False, indent=2)

    PERMS = 'ACCESS_WIFI_STATE READ_LOGS CAMERA READ_PHONE_STATE CHANGE_NETWORK_STATE READ_SMS CHANGE_WIFI_STATE RECEIVE_BOOT_COMPLETED DISABLE_KEYGUARD RESTART_PACKAGES GET_TASKS SEND_SMS INSTALL_PACKAGES SET_WALLPAPER READ_CALL_LOG SYSTEM_ALERT_WINDOW READ_CONTACTS WRITE_APN_SETTINGS READ_EXTERNAL_STORAGE WRITE_CONTACTS READ_HISTORY_BOOKMARKS WRITE_SETTINGS'
    PERMS = [f'android.permission.{p}' for p in PERMS.split()]
    PERMS_MAP = { PERMS[i]: i for i in range(len(PERMS)) }
    PERMS_STR = ','.join(PERMS)

    APIS = [k[0] for k in sorted_api]
    APIS_MAP = { APIS[i]: i for i in range(len(APIS)) }
    APIS_STR = ','.join(APIS)

    csv = open(pathlib.Path(featuredir, f'feature.api-{apicnt}.csv'), 'w')
    csv.write(f'sha256,{PERMS_STR},{APIS_STR},label' + '\n')

    for path in pathlib.Path(featuredir, 'features', 'raw').rglob('*.json'):
        with open(path, 'r') as _:
            feature = json.load(_)
            permbits = [0 for i in range(len(PERMS))]
            for perm in feature['perms']:
                if perm in PERMS:
                    permbits[PERMS_MAP[perm]] = 1
            permbits = ','.join(map(str, permbits))

            apibits = [0 for i in range(len(APIS))]
            for api in feature['apifreq']:
                if api in APIS:
                    apibits[APIS_MAP[api]] = feature['apifreq'][api]
            apibits = ','.join(map(str, apibits))

            sha256 = path.stem

            label = 1 if feature['isblack'] else 0

            csv.write(f'{sha256},{permbits},{apibits},{label}' + '\n')

    csv.close()

def get_model():
    from keras.models import Sequential
    from keras.layers import Conv2D, MaxPooling2D, Dropout, Flatten, Dense, Activation, BatchNormalization

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

def train_images(images, labels, modeldir):
    from keras.callbacks import EarlyStopping, ReduceLROnPlateau

    earlystop = EarlyStopping(patience=10)
    learning_rate_reduction = ReduceLROnPlateau(monitor='val_acc',
                                                patience=2,
                                                verbose=1,
                                                factor=0.5,
                                                min_lr=0.00001)

    kfold = StratifiedKFold(n_splits=KFOLD, shuffle=True, random_state=7)
    for (i, (train, test)) in enumerate(kfold.split(images, labels.argmax(1))):
        model = get_model()
        model.fit(
            images[train],
            labels[train],
            validation_data=(images[test], labels[test]),
            epochs=20,
            batch_size=32,
            shuffle=True,
            callbacks= [earlystop, learning_rate_reduction]
        )
        modelpath = pathlib.Path(modeldir, 'model_' + str(i) + '.h5').absolute()
        print(f'Save model into {modelpath} ...')
        model.save_weights(modelpath)

def read_feature_file(featuredir):
    csvpath = pathlib.Path(featuredir, 'feature.api-40.csv')
    df = pd.read_csv(csvpath).sort_values(by='sha256').reset_index(drop=True)
    if MAX_SAMPLE_COUNT > 0:
        df = df[:min(MAX_SAMPLE_COUNT, df.shape[0])]
    return df

def get_image_feature(featuredir):
    df = read_feature_file(featuredir)
    imgpaths = df['sha256'].apply(lambda x: pathlib.Path(featuredir, 'imgs', x + '.png'))
    images = np.array([i for i in imgpaths.apply(lambda x: np.asarray(Image.open(x)))])
    imginfo = {}
    for hash, imgdata, label in zip(df['sha256'], images, df['label']):
        imginfo[hash] = {'np': imgdata, 'label': label}
    return imginfo

def get_feature(featuredir, feature_name, feature_matcher):
    df = read_feature_file(featuredir)
    feature = {}
    for _, row in df.iterrows():
        sha256 = row['sha256']
        feature[sha256] = {feature_name: [], 'label': row['label']}
        for idx in row.index:
            if idx.startswith(feature_matcher):
                feature[sha256][feature_name].append(row[idx])
    return feature

def prepare_image_data(featuredir):
    csvpath = pathlib.Path(featuredir, 'feature.api-40.csv')
    df = pd.read_csv(csvpath).sort_values(by='sha256').reset_index(drop=True)

    if MAX_SAMPLE_COUNT > 0:
        df = df[:min(MAX_SAMPLE_COUNT, df.shape[0])]

    imgpaths = df['sha256'].apply(lambda x: pathlib.Path(featuredir, 'imgs', x + '.png'))
    images = np.array([i for i in imgpaths.apply(lambda x: np.asarray(Image.open(x)))])
    labels = keras.utils.to_categorical(df['label'])

    images_train, images_test, labels_train, labels_test = train_test_split(images, labels, test_size=0.33, random_state=42)
    return images_train, images_test, labels_train, labels_test

def get_norm_imgdata(imgdata):
    imgdata = imgdata / 255
    return imgdata

def get_norm_apis(apis):
    '''
    - apis int of list:
    '''
    apis = np.array(apis)
    delta = np.max(apis) - np.min(apis)

    if delta != 0: apis = (apis - np.min(apis)) / delta
    return apis

def prepare_classifier_data(featuredir):
    perms = get_feature(featuredir, 'perms', 'android.')
    apis = get_feature(featuredir, 'apis', 'L')
    images = get_image_feature(featuredir)

    sha256s = read_feature_file(featuredir)['sha256'][:3000]

    appcnt = len(sha256s)
    permcnt = len(perms[sha256s[0]]['perms'])
    apicnt = len(apis[sha256s[0]]['apis'])
    imgsz = IMAGE_WIDTH * IMAGE_HEIGHT * IMAGE_CHANNELS
    features = np.zeros((appcnt, permcnt + apicnt + imgsz))
    labels = []

    for (i, sha256) in enumerate(sha256s):
        print(f'[+] Process {i+1}/{len(sha256s)} ...')

        start = 0
        for j in range(start, start + permcnt):
            features[i, j] = perms[sha256]['perms'][j - start]

        start += permcnt
        apilist = get_norm_apis(apis[sha256]['apis'])
        for j in range(start, start + apicnt):
            features[i, j] = apilist[j - start]
        del apilist
        gc.collect()

        imgdata = images[sha256]['np'] / 255
        del images[sha256]['np']
        gc.collect()

        imgrow = imgdata.reshape(-1)
        del imgdata
        gc.collect()

        start += apicnt
        for j in range(start, start + imgsz):
            features[i, j] = imgrow[j - start]

        del imgrow
        gc.collect()

        labels.append(perms[sha256]['label'])

    labels = np.array(labels)
    return train_test_split(features, labels, test_size=0.33, random_state=42)

def binary_xgb(train_x, train_y, test_x, iter_num):
    # Build model
    params = {
        'booster': 'gbtree',
        'objective':'binary:logistic',
        'gamma': 0.2,
        'max_depth': 6,
        'min_child_weight': 2,
        'alpha': 0,
        'lambda': 0,
        'subsample': 0.7,
        'colsample_bytree': 0.9,
        'silent': 1,
        'eta': 0.01
    }

    # Train
    dtrain = xgb.DMatrix(train_x, train_y)
    plst = params.items()
    model = xgb.train(plst, dtrain, iter_num)

    print('Save xgb model ....')
    featuredir = ['~', '.config', 'zhkui', 'model', 'features']
    featuredir = pathlib.Path(*featuredir).expanduser().absolute()
    model.save_model(pathlib.Path(featuredir, 'CNNXBG-XGB.xgb'))
    print('Save xgb model done!')

    # Predict
    preds = model.predict(test_x)
    predictions = [round(value) for value in preds]

    return preds

def prepare_xgb_data(featuredir):
    perms = get_feature(featuredir, 'perms', 'android.')
    apis = get_feature(featuredir, 'apis', 'L')

    # get sorted sha256 to keep same with CNN image
    sha256s  = read_feature_file(featuredir)['sha256']

    features = []
    labels = []
    for sha256 in sha256s:
        feature = []
        feature += perms[sha256]['perms']
        feature += get_norm_apis(apis[sha256]['apis']).tolist()
        features.append(np.array(feature))
        labels.append(perms[sha256]['label'])
    features = np.array(features)
    labels = np.array(labels)
    return train_test_split(features, labels, test_size=0.33, random_state=42)

def get_metrics(test_y, predict):
    from sklearn import metrics
    precision = metrics.precision_score(test_y, predict)
    recall = metrics.recall_score(test_y, predict)
    accuracy = metrics.accuracy_score(test_y, predict)
    auc = metrics.roc_auc_score(test_y, predict)
    f1 = metrics.f1_score(test_y, predict)
    return {'precision': precision, 'recall': recall, 'acc': accuracy, 'auc': auc, 'f1': f1}

if __name__ == '__main__':
    routines = ['statistic', 'image', 'classifier', 'xgb', 'imgpred', 'xgbcnn']
    parser = argparse.ArgumentParser()
    parser.add_argument('-x', '--execute', type=str, choices=routines, help='Function to execute')
    parser.add_argument('-p', '--params', type=str, help='Parameters seperated by comma')
    args = parser.parse_args()

    featuredir = ['~', '.config', 'zhkui', 'model', 'features']
    featuredir = pathlib.Path(*featuredir).expanduser().absolute()

    if args.execute == 'statistic':
        api_statistics(featuredir)
    elif args.execute == 'image':
        # Ensure: sorted by sha256, split is 0.33 and random_state is 42
        images_train, images_test, labels_train, labels_test = prepare_image_data(featuredir)
        train_images(images_train, labels_train, featuredir)
    elif args.execute == 'imgpred':
        images_train, images_test, labels_train, labels_test = prepare_image_data(featuredir)
        from keras.models import load_model
        imgpred_result = pathlib.Path(featuredir, f'imgpred_{epoch()}.json')
        result = {}
        for i in range(KFOLD):
            model_weights = pathlib.Path(featuredir, f'model_{i}.h5')
            print(f'[+] Using modle {model_weights} ...')
            mdl = get_model()
            mdl.load_weights(model_weights)

            predcls = mdl.predict(images_test)
            metric = get_metrics(labels_test.argmax(1), predcls.argmax(1))

            result[i] = {
                'pred': pd.DataFrame(predcls).to_json(orient='values'),
                'real': pd.DataFrame(labels_test).to_json(orient='values'),
                'metric': metric
            }

        with open(imgpred_result, 'w') as _:
            json.dump(result, _)
            print(f'Save image predication result into: {imgpred_result}')
    elif args.execute == 'classifier':
        app_train, app_test, labels_train, labels_test = prepare_classifier_data(featuredir)
        classifiers = ['DT', 'SVM', 'RF']
        result = run_model(app_train, labels_train, app_test, labels_test, classifiers)
        result_path = pathlib.Path(featuredir, f'classifier_result_{epoch()}.json').absolute()
        with open(result_path, 'w') as _:
            json.dump(result, _)
            print(f'Classifier result is saved into: {result_path}')
    elif args.execute == 'xgb':
        # sorted by sha256, split is 0.33 and random_state is 42
        app_train, app_test, labels_train, labels_test = prepare_xgb_data(featuredir)
        xgb_app_test = xgb.DMatrix(app_test)
        predprob = binary_xgb(app_train, labels_train, xgb_app_test, 1000)
        predictions = [round(value) for value in predprob]
        result_path = pathlib.Path(featuredir, f'xgb_result_{epoch()}.json')
        metric = get_metrics(labels_test, predictions)

        with open(result_path, 'w') as _:
            result = {
                'predprob': pd.Series(predprob).to_json(orient='values'),
                'predcls': pd.Series(predictions).to_json(orient='values'),
                'realcls': pd.Series(labels_test).to_json(orient='values'),
                'metric': metric,
            }
            json.dump(result, _)
            print(f'XGBoost result is saved into: {result_path}')
    elif args.execute == 'xgbcnn':
        wxgb = 0.67
        wcnn = 0.33
        xgbpath = pathlib.Path('~', 'research', 'xgb_result.json').expanduser().absolute()
        cnnpath = pathlib.Path('~', 'research', 'imgpre.json').expanduser().absolute()
        with open(xgbpath, 'r') as _:
            xgbresult = json.load(_)
            xgb_probs = pd.read_json(xgbresult['predprob'], orient='values').values[:, 0]
            test_y = pd.read_json(xgbresult['realcls'], orient='values').values[:, 0]
        with open(cnnpath, 'r') as _:
            cnnresult = json.load(_)
            cnn_probs = pd.read_json(cnnresult['0']['pred'], orient='values').values[:, 1]
        pred_labels = []
        for (xgb_prob, cnn_prob) in zip(xgb_probs, cnn_probs):
            prob = xgb_prob * wxgb + cnn_prob * wcnn
            pred_labels.append(round(prob))
        xgb_cnn_prediction = get_metrics(test_y, pred_labels)
        print(xgb_cnn_prediction)
    else:
        parser.print_help()
