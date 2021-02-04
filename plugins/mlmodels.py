#! /usr/bin/env python3
#! -*- coding:utf-8 -*-

import sys
import os
import time
from sklearn import metrics
import numpy as np

# Multinomial Naive Bayes Classifier
def naive_bayes_classifier(train_x, train_y):
    from sklearn.naive_bayes import MultinomialNB
    model = MultinomialNB(alpha=0.01)
    model.fit(train_x, train_y)
    return model


# KNN Classifier
def knn_classifier(train_x, train_y):
    from sklearn.neighbors import KNeighborsClassifier
    model = KNeighborsClassifier()
    model.fit(train_x, train_y)
    return model


# Logistic Regression Classifier
def logistic_regression_classifier(train_x, train_y):
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression(penalty='l2')
    model.fit(train_x, train_y)
    return model


# Random Forest Classifier
def random_forest_classifier(train_x, train_y):
    from sklearn.ensemble import RandomForestClassifier
    model = RandomForestClassifier(n_estimators=8)
    model.fit(train_x, train_y)
    return model


# Decision Tree Classifier
def decision_tree_classifier(train_x, train_y):
    from sklearn import tree
    model = tree.DecisionTreeClassifier()
    model.fit(train_x, train_y)
    return model


# GBDT(Gradient Boosting Decision Tree) Classifier
def gradient_boosting_classifier(train_x, train_y):
    from sklearn.ensemble import GradientBoostingClassifier
    model = GradientBoostingClassifier(n_estimators=200)
    model.fit(train_x, train_y)
    return model

# SVM Classifier
def svm_classifier(train_x, train_y):
    from sklearn.svm import SVC
    model = SVC(kernel='rbf', probability=True)
    model.fit(train_x, train_y)
    return model

# SVM Classifier using cross validation
def svm_cross_validation(train_x, train_y):
    from sklearn.grid_search import GridSearchCV
    from sklearn.svm import SVC
    model = SVC(kernel='rbf', probability=True)
    param_grid = {'C': [1e-3, 1e-2, 1e-1, 1, 10, 100, 1000], 'gamma': [0.001, 0.0001]}
    grid_search = GridSearchCV(model, param_grid, n_jobs = 1, verbose=1)
    grid_search.fit(train_x, train_y)
    best_parameters = grid_search.best_estimator_.get_params()
    for para, val in best_parameters.items():
        print(para, val)
    model = SVC(kernel='rbf', C=best_parameters['C'], gamma=best_parameters['gamma'], probability=True)
    model.fit(train_x, train_y)
    return model


def run_model(train_x, train_y, test_x, test_y, classifiers):
    allowed_classifiers = ['NB', 'KNN', 'LR', 'RF', 'DT', 'SVM', 'GBDT']
    test_classifiers = list(set(allowed_classifiers) & set(classifiers))
    if not test_classifiers:
        print(f'Allowed classifiers: {allowed_classifiers}')
        return

    classifiers = {
        'NB': naive_bayes_classifier,
        'KNN': knn_classifier,
        'LR': logistic_regression_classifier,
        'RF': random_forest_classifier,
        'DT': decision_tree_classifier,
        'SVM': svm_classifier,
        'SVMCV': svm_cross_validation,
        'GBDT': gradient_boosting_classifier
    }

    num_train, num_feat = train_x.shape
    num_test, num_feat = test_x.shape

    info = {}
    info['train'] = num_train
    info['test'] = num_test
    print(f'#training data: {num_train}, #testing_data: {num_test}, dimension: {num_feat}')
    for classifier in test_classifiers:
        info[classifier] = {}
        print(f'[+] Running classifier {classifier} ....')
        start_time = time.time()
        model = classifiers[classifier](train_x, train_y)
        print(f'[+] Training took {time.time() - start_time}')
        predict = model.predict(test_x)

        precision = metrics.precision_score(test_y, predict)
        recall = metrics.recall_score(test_y, predict)
        accuracy = metrics.accuracy_score(test_y, predict)
        auc = metrics.roc_auc_score(test_y, predict)
        f1 = metrics.f1_score(test_y, predict)

        info[classifier]['precision'] = precision
        info[classifier]['recall'] = recall
        info[classifier]['accuracy'] = accuracy
        info[classifier]['auc'] = auc
        info[classifier]['f1'] = f1
    return info
