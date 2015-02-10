import numpy as np
import pickle

from collections import defaultdict
from itertools import izip

from sklearn.base import BaseEstimator
from sklearn.feature_extraction import DictVectorizer

from label_trigrams import iter_predictions, predict
from label_trigrams import iter_prob_predictions, predict_proba


def flatten(iterable):
    return [x for xs in iterable for x in xs]

def unzip(iterable):
    return zip(*iterable)

def encode(label_trigram):
    return ' '.join(str(label) for label in label_trigram)

def decode(label_trigram):
    return tuple(int(label) for label in label_trigram.split())


FEATURES20140503b = {'pitch': [3, 4, 5, 6, 8],
            'contour': [7, 9, 10, 11, 12, 13, 14, 33, 34],
            'rhythmfeatures': [16, 17, 18, 19, 28, 29, 30, 31, 32] + range(38,65),
            'textual': [22, 23, 24, 25, 26, 27, 35, 36, 37],
            'narmour': [16, 17, 18, 28, 29, 30, 31, 32, 33, 34],
            'context': [30, 35, 36, 37],
            'rest': [28, 29, 30],
            'indices' : [],
            'all': range(65),
            'alwaysexclude' : [0,1,2,15,20,21]}

FEATURES20150202 = {'pitch': [3, 4, 5, 6, 8],
            'contour': [7, 9, 10, 11, 12, 13, 14, 33, 34],
            'rhythmfeatures': [16, 17, 18, 19, 28, 29, 30, 31, 32] + range(47,74),
            'textual': [22, 23, 24, 25, 26, 27, 35, 36, 37, 38, 39, 40],
            'narmour': [16, 17, 18, 28, 29, 30, 31, 32, 33, 34],
            'context': [30, 35, 36, 37],
            'rest': [28, 29, 30],
            'indices' : [41, 42, 43, 44, 45, 46],
            'all': range(74),
            'all_20140503b' : range(38) + range(47,74),
            'alwaysexclude' : [0,1,2,15,20,21,41,42,43,44,45,46]}

FEATURES = FEATURES20150202

def load_data(filename='data/trigram_dataset_note_20140503b.pkl', features='all'):
    with open(filename, 'r') as f:
        tr_data, tr_labels, tr_tr_labels, tr_ids, tr_timesigs, tr_nstructs = pickle.load(f)
    vectorizer = DictVectorizer(sparse=False)
    time_feats = []
    for timesig in tr_timesigs:
        time_feats.append({timesig: 1.0})
    tr_timesigs_ = vectorizer.fit_transform(time_feats)
    tr_data = np.hstack((tr_data, tr_timesigs_))
    feature_ixs = list(set(FEATURES[features]) - set(FEATURES['alwaysexclude']))
    tr_data_sel = tr_data[:,feature_ixs]
    tr_data_ixs = tr_data[:,FEATURES['indices']]

    features_per_id = defaultdict(list)
    for features, label, (id, _), ixs in izip(tr_data_sel, tr_tr_labels, tr_ids, tr_data_ixs):
        features_per_id[id].append( (features, encode(label), ixs))

    return np.array(features_per_id.values()), features_per_id.keys()


class CadenceClassifier(BaseEstimator):

    def __init__(self, classifier, prediction_mode='majority'):
        self.classifier = classifier
        if prediction_mode not in ('majority', 'weighted'):
            raise ValueError("Prediction mode must be one of `majority` or `weighted`.")
        self.prediction_mode = prediction_mode

    def fit(self, X, y):
        self.classifier.fit(X, y)
        return self

    def predict(self, X):
        preds = [decode(trigram) for trigram in self.classifier.predict(X)]
        if self.prediction_mode == 'majority':
            preds = [predict(r, m, l) for r, m, l in iter_predictions(preds)]
        else:
            probs = np.max(self.classifier.predict_proba(X), axis=1).tolist()
            preds = [predict_proba(r, m, l)
                     for r, m, l in iter_prob_predictions(zip(preds, probs))]
        return preds
