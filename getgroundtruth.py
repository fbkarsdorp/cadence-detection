from music21 import *

with(open('data/trigram_dataset_note_20150202.pkl','r')) as f:
    tr_data, tr_labels, tr_tr_labels, tr_ids, tr_timesigs, tr_nstructs = pickle.load(f)

ids, offs = zip(*tr_ids)
uniqids = list(set(ids))

lengths = {}

for id in uniqids:
	s = converter.parse('/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/MTC-FS-1.0/krn/'+id+'.krn')
	lengths[id] = len(s.flat.notes)

predictionsPerSong = {}
for id in uniqids:
	predictionsPerSong[id] = [0]

for i in range(len(tr_data)):
	if tr_labels[i] == 1:
		if tr_data[i][46]+1.0 < lengths[ids[i]]:
			predictionsPerSong[ids[i]].append(tr_data[i][46]+1.0)

for k,v in predictionsPerSong.items():
    print k, v
