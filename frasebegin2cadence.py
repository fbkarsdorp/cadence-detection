from music21 import *

from annotate_melody import annotate_melody

krnpath = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/MTC-FS-1.0/krn/'

#get ann_id-nlbid mapping
nlbids = {} #keys are strings
with open('ids_annotated.txt','r') as f:
	for s in f.readlines():
		s = s.strip('\n')
		nlbids[s.split('\t')[1]] = s.split('\t')[2]	

#ixs of phrase beginnings -> ixs of cadence notes
#annotations: dictionary. Key: annbid. Value: array of ints (indices of phrase beginnings)
#N.B. adds the final cadence of each song!!!!
def phrasebegin2cadence(annotations):
	cadences = {}
	for annid in annotations.keys():
		nlbid = nlbids[annid]
		s = converter.parse(krnpath+nlbid+'.krn')
		annotate_melody(s)
		mel = s.flat.notes
		length = len(mel)
		cadences[annid] = []
		for ix in annotations[annid]:
			if ix > 0:
				cadences[annid].append(mel[ix-1].startix)
		cadences[annid].append(mel[-1].startix) #final cadence
	return cadences

def writecadenceannotationstodisk(cadences, filename):
	with open(filename,'w') as f:
		for annid, cads in cadences.items():
			f.write(annid+'\t')
			strcads = [str(int(c)) for c in cads]
			f.write('\t'.join(strcads))
			f.write('\n')

