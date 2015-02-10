import pandas as pd

from sklearn.cross_validation import KFold
from sklearn.metrics import precision_recall_fscore_support, f1_score, fbeta_score

import numpy as np

from cadencer import CadenceClassifier, load_data, FEATURES
from cadencer import unzip, flatten, decode

from sklearn.ensemble import RandomForestClassifier

#%cd '/Users/pvk/rep/cadence-detection'

data, IDs = load_data('data/trigram_dataset_note_20150202.pkl', features='all_20140503b')

#find ixs of 90 songs
#read IDs
with open('ids_annotated.txt','r') as f:
    nlbids90 = [s.split('\t')[2].strip('\n') for s in f.readlines()]

#get annid-nlbid mapping
annids2nlbids = {} #keys are strings
with open('ids_annotated.txt','r') as f:
    for s in f.readlines():
        s = s.strip('\n')
        annids2nlbids[s.split('\t')[1]] = s.split('\t')[2]

#also get nlbid-annid mapping
nlbids2annids = {}
for k,v in annids2nlbids.items():
    nlbids2annids[v] = k

ixs90 = [IDs.index(id) for id in nlbids90]

test = data[ixs90]
mask = np.ones(len(data), np.bool)
mask[ixs90] = 0
train = data[mask]

estimator = RandomForestClassifier(n_estimators=50, min_samples_leaf=1, n_jobs=6)
clf = CadenceClassifier(estimator)

scores = pd.DataFrame(columns=['fold', 'class', 'precision', 'recall', 'F'])
scoresPerSong = pd.DataFrame(columns=['ID', 'F1', 'F2'])
predictionsPerSong = {}
n_experiments = 0
n_songs = 0

#train, test = data[train_ixs], data[test_ixs]
X_train, y_train, indices_train = unzip(flatten(train))
y_train = np.array(y_train)
clf.fit(X_train, y_train)
all_preds = []
all_y_test = []

for k, i_test in enumerate(test): #for each melody
    X_test, y_test, indices_test = unzip(i_test)
    _, y_test, _ = unzip(map(decode, y_test))
    preds = clf.predict(X_test)
    all_y_test.extend(y_test)
    all_preds.extend(preds)
    scoresPerSong.loc[n_songs] = [IDs[ixs90[k]], f1_score(y_test, preds, pos_label=1, average='weighted'), fbeta_score(y_test, preds, beta=2.0, pos_label=1, average='weighted')]
    n_songs += 1
    #predictionsPerSong[IDs[ixs90[k]]] = [0] #keep list of note indices of phrase _beginnings_
    #for tr_ix, pred in enumerate(preds[:-1]):
    #    if pred == 1:
    #        predictionsPerSong[IDs[ixs90[k]]].append(indices_test[tr_ix][5]+1)
    predictionsPerSong[nlbids2annids[IDs[ixs90[k]]]] = [] #keep list of note indices of phrase _endings_
    for tr_ix, pred in enumerate(preds):
        if pred == 1:
            predictionsPerSong[nlbids2annids[IDs[ixs90[k]]]].append(indices_test[tr_ix][2])
p, r, f, _ = precision_recall_fscore_support(all_y_test, all_preds)

predictionsPerSong

