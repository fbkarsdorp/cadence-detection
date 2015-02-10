#visualize cadens annotations

from music21 import *
import os
import shutil

krnpath = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/MTC-FS-1.0/krn/'

#cd '~/rep/cadence-detection'

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

#get representations of annotated songs (M: melody, T: text, TM: text and melody)
representations = {}
with open('ids_annotated.txt','r') as f:
	for s in f.readlines():
		s = s.strip('\n')
		representations[s.split('\t')[1]] = s.split('\t')[0]

def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)

def getAnnotationsFromFile(filename):
	annotations = {} #keep annotations of different annotators separate
	with open(filename, 'r') as infile:
		for s in infile.readlines():
			s = s.strip('\n')
			fields = s.split('\t')
			annid = fields[0]
			annotations[annid] = []
			if len(fields) > 1 and len(fields[1]) > 0:
				for f in fields[1:]:
					annotations[annid].append(int(f))
	return annotations

#filenames: array with filenames containing annotations
def visualize_annotations(filenames, outputdir='./viz_ann/', annotators=None):
	if not annotators:
		annotators = [str(ix) for ix in range(len(filenames))]
	if len(annotators) != len(filenames):
		print "len(annotators) != len(filenames)"
		annotators = [str(ix) for ix in range(len(filenames))]

	#assemble annotations per song
	annotations = {} #annotations[ix][annid]
	annids = set() #keep track which songs have been annotated across the input files
	for ix, fn in enumerate(filenames):
		annotations[ix] = getAnnotationsFromFile(fn)
		for annid in annotations[ix].keys():
			annids.add(annid)
	
	#read songs
	songs = {}
	for annid in annids:
		nlbid = annids2nlbids[annid]
		songs[annid] = converter.parse(krnpath+nlbid+'.krn')
		songs[annid].insert(metadata.Metadata())
		songs[annid].metadata.title = annid+' - '+nlbid+' - '+representations[annid]
	#add annotations
	for ix in annotations.keys():
		for annid in annotations[ix].keys():
			for ann in annotations[ix][annid]:
				songs[annid].flat.notes[ann].addLyric(annotators[ix])
	#visualize songs and put in outputdir
	ensure_dir(outputdir)
	for annid in annids:
		song = songs[annid]
		nlbid = annids2nlbids[annid]
		out = song.write('lily.pdf')
		shutil.move(out,outputdir+nlbid+'.pdf')

if __name__ == '__main__':
	pass
	#filenames = [ 'annotations/jorn.txt', 'annotations/sanneke.txt', 'annotations/ellen.txt', 'annotations/ismir2014classifier.txt']
	#names = ['J', 'S', 'E', 'M']
	#visualize_annotations(filenames, annotators=names)

