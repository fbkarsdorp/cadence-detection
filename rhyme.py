from music21 import *
import shutil
import re
import time
import sys
import numpy as np
import matplotlib.pyplot as plt

# run -i '/Users/pvk/rep/rhyme/python/classifiers.py'
# mbpt = MBPT()
# mbpt.phonologize('woordje')

#CONF
krnpath = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/MTC-FS-1.0/krn/'
#krnpath = '/Users/pvk/Documents/data/NLB-FS-1.55/'
#krnpath = '/Users/pvk/Documents/data/Annotated_krn/'

krnflist = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/flist/mtc-fs-krn-1.0.flist'
#krnflist = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/flist/mtc-fs-krn-1.0-first10.flist'

#also adds n.phonemefound (False if conversion syllable->phoneme failed)
def addPhonemes(melody):
	flatmelody = melody.flat.notes
	n_notes = len(flatmelody)
	word = ''
	phons = []
	ixs = []
	for i in range(n_notes):
		if flatmelody[i].lyrics:
			if flatmelody[i].lyrics[0].syllabic != 'end' and flatmelody[i].lyrics[0].syllabic != 'single':
				word = word + flatmelody[i].lyrics[0].text
				ixs.append(i)
			elif flatmelody[i].lyrics[0].syllabic == 'single':
				tophonologize = flatmelody[i].lyrics[0].text
				tophonologize = re.sub(r"[ \.,;:]", "", tophonologize)
				#print tophonologize
				phon = ''
				try:
					phon = mbpt.phonologize(tophonologize.decode('utf-8'))
				except:
					e = sys.exc_info()[0]
					print e
					print "word: ", tophonologize
				#print phon
				accent = "0"
				if len(phon) > 0 and phon[0] == "'" :
					accent = '1'
					phon = phon[1:]	
				phons.append( [i, phon, accent] )
			elif flatmelody[i].lyrics[0].syllabic == 'end':
				word = word + flatmelody[i].lyrics[0].text
				ixs.append(i)
				word = re.sub(r"[ \.,;:]", "", word)
				#print word
				try:
					phon = mbpt.phonologize(word.decode('utf-8')).split('-')
				except:
					e = sys.exc_info()[0]
					print e
					print "word: ", word 
				#print phon 
				if len(phon) != len (ixs):
					print "len(phon) != len (ixs): ", word, phon
				else:
					for n in range(len(phon)):
						hyphvoor = ''
						hyphna = ''
						accent = '0'
						if n > 0: hyphvoor = '-'
						if n < len(phon)-1: hyphna = '-'
						if len(phon[n]) > 0:
							if phon[n][0] == "'" :
								accent = '1'
								phon[n] = phon[n][1:]
						phons.append( [ixs[n], hyphvoor+phon[n]+hyphna, accent ] )
				word = ''
				ixs = []
	#now append lyrics to melody
	for l in phons:
		#print l
		flatmelody[l[0]].addLyric(l[1])
		flatmelody[l[0]].addLyric(l[2])
	#annotate words for which text->phoneme failed
	lastphonemefound = False #for melismas: all notes 
	for n in flatmelody:
		n.phonemefound = lastphonemefound
		if n.hasLyrics():
			n.phonemefound = True
			lastphonemefound = True
			if len(n.lyrics) == 1:
				n.phonemefound = False
				lastphonemefound = False

def removeLeftConsonants(syl):
	if len(syl) == 0:
		return syl
	while syl[0] in 'pbtdkgNmnlrfvszSZjxGhwdZ':
		if len(syl) > 1:
			syl = syl[1:]
		else:
			syl = ''
			break
	return syl

#expects phonemes in lyrics[1]
def removeSingleShwa(s):
	fl = s.flat.notes
	for ix, n in enumerate(fl):
		if not n.hasLyrics():
			continue
		if len(n.lyrics) < 2:
			continue
		if n.lyrics[1].syllabic == 'single' and '@' in n.lyrics[1].text:
			n.lyrics[1].text = ''

#shift to end of melismata
#unless it is a tie
#Do apply this first
def lyricsToEndOfMelisma(s):
	fl = s.flat.notes
	for ix, n in enumerate(fl):
		if not n.lyrics and not n.tie:
			fl[ix].lyrics = fl[ix-1].lyrics
			fl[ix-1].lyric  = None

#remove non-contents words
def removeNonContentsWords(s):
	throwaway = {}
	wordfile = open('/Users/pvk/Documents/Eigenwerk/Projects/Rhyme/art-con-det-prn-adp.txt','r')
	for word in wordfile.read().split('\n'):
		throwaway[word] = None
	wordfile.close()

	fl = s.flat.notes
	startix = 0
	word = ''
	for ix, n in enumerate(fl):
		if not n.hasLyrics():
			continue
		if n.lyrics[0].syllabic == 'single':
			if n.lyrics[0].text.lower() in throwaway:
				n.lyric = None
				continue
		if n.lyrics[0].syllabic == 'begin':
			word = word + n.lyrics[0].text
			startix = ix
		if n.lyrics[0].syllabic == 'middle':
			word = word + n.lyrics[0].text
		if n.lyrics[0].syllabic == 'end':
			word = word + n.lyrics[0].text
			if word.lower() in throwaway:
				for i in range(startix,ix+1):
					if fl[i].hasLyrics():
						fl[i].lyric = None
			word = ''

class WordsCovered:
	def __init__(self):
		self.wordforms = {}
		wordfile = open('/Users/pvk/Documents/Eigenwerk/Projects/Rhyme/wordforms.txt','r')
		for word in wordfile.read().split('\n'):
			self.wordforms[word.lower()] = None
		wordfile.close()
	def __call__(self,s):
		covered = 0
		notcovered = 0

		fl = s.flat.notes
		startix = 0
		word = ''
		for ix, n in enumerate(fl):
			if not n.hasLyrics():
				continue
			if n.lyrics[0].syllabic == 'single':
				word = n.lyrics[0].text.lower()
				word = re.sub(r"[ \.,;:]", "", word)
				if word in self.wordforms:
					covered += 1
					#print "YES: ", word
				else:
					notcovered += 1
					print "NO:  ", word, " -> ", mbpt.phonologize(word.decode('utf-8'))
				word = ''
				continue
			if n.lyrics[0].syllabic == 'begin':
				word = word + n.lyrics[0].text
				startix = ix
			if n.lyrics[0].syllabic == 'middle':
				word = word + n.lyrics[0].text
			if n.lyrics[0].syllabic == 'end':
				word = word + n.lyrics[0].text
				word = re.sub(r"[ \.,;:]", "", word)
				if word.lower() in self.wordforms:
					covered += 1
					#print "YES: ", word.lower()
				else:
					notcovered += 1
					print "NO:  ", word.lower(), " -> ", mbpt.phonologize(word.lower().decode('utf-8'))
				word = ''
		return covered, notcovered
wordsCovered = WordsCovered()

def coveredInCorpus():
	covered = 0
	notcovered = 0
	with open(krnflist,'r') as f:
		for krnfile in f:
			krnfile = krnfile.split('\n')[0]
			print krnfile
			s = converter.parse(krnfile)
			c,n = wordsCovered(s)
			covered += c
			notcovered += n
	return covered, notcovered, float(covered) / float(covered+notcovered)

#returns two booleans
# rhyme,identical = wordrhymes(worda,wordb)
# if worda==wordb : rhyme = True, identical = True
# if worda rhymes with wordb : rhyme = True, identical = False
# otherwise : rhyme = False, identical = False
def wordrhymes(worda,wordb):
	#print worda,wordb
	if len(worda)==0 and len(wordb)==0:
		return False,False
	if worda == wordb:
		return True,True
	lenshortest = min(len(worda),len(wordb))
	#consonantsAndShwa = 'pbtdkgNmnlrfvszSZjxGhwdZ@+:'
	consonantsAndShwa = 'pbtdkgfvszSZxGhNmnJlrwj@+:~'
	res = False

	for ix in range(-1,-lenshortest-1,-1):
		if worda[ix] in consonantsAndShwa:
			if worda[ix] == wordb[ix]:
				continue
			else:
				break
		else: #vowel
			if worda[ix] == wordb[ix]:
				res = True
				break
			else:
				res = False
				break
	return res, False


def sylrhymes(syla,sylb):
	if '@' in syla and '@' in sylb:
		return syla == sylb
	else:
		return removeLeftConsonants(syla) == removeLeftConsonants(sylb)

# generates 'AA' 'AB' 'AC' ... 'AZ' 'BA' 'BB' ... ... 'ZZ'
def generateIdentifiers():
	id1 = 'A'
	for ix1 in range(26):
		id2 = 'A'
		for ix2 in range(26):
			yield id1+id2
			id2 = chr(ord(id2)+1)
		id1 = chr(ord(id1)+1)

def getRhyme(sylrhym,ends):
	rhyme = ['False']*len(sylrhym)
	listexpected = generateIdentifiers()
	expected = next(listexpected)
	#print sylrhym
	#get indices of syllables (exluding '')
	sylixs = [ix for ix,_s in enumerate(sylrhym) if sylrhym[ix]!='']
	#pairs = [(sylixs[i], sylixs[i+1]) for i,_s in enumerate(sylixs) if i<len(sylixs)-1]
	for ixix,ix in enumerate(sylixs):
		#print expected, sylrhym[ix]
		if sylrhym[ix]=='':
			continue
		if sylrhym[ix] != expected:
			rhyme[ix] = True
			rhyme[sylrhym.index(sylrhym[ix])] = True #also first occurrence
		else:
			expected = next(listexpected)
	#print rhyme 
	#now make sure that only last 'True' is kept if there are 'True''s in a row
	#for ix in range(1,len(rhyme)):
	#	if rhyme[ix]=='' and ix<len(rhyme) and rhyme[ix+1]==True and rhyme[ix-1]==True:
	#		print ix, rhyme[ix-1], rhyme[ix], ' -> ',
	#		rhyme[ix-1] = False
	#		print rhyme[ix-1], rhyme[ix]
	#	if rhyme[ix]==True and (rhyme[ix-1]==True or sylrhym[ix-1]==''):
	#		print ix, rhyme[ix-1], rhyme[ix], ' -> ',
	#		rhyme[ix-1] = False
	#		print rhyme[ix-1], rhyme[ix]
	#remove 'True' is not at phrase ending
	#for ix in range(len(sylrhym)):
	#	if rhyme[ix] and ends[ix] == 0:
	#		rhyme[ix-1] = False
	#print rhyme
	return rhyme


#expect a song that already has Phonemes and stress as added by addPhonemes(s)
def assignRhymeIdentifiers(s):
	fl = s.flat.notes

	def getend(note):
		if not note.lyrics:
			return -1
		else:
			if note.lyrics[1].syllabic == 'end' or note.lyrics[1].syllabic == 'single':
				return 1
			else:
				return 0

	def getsyl(note):
		if not note.lyrics:
			return ''
		else:
			return note.lyrics[1].text

	syls = list(map(getsyl,fl))
	ends = list(map(getend,fl))
	sylrhym = ['']*len(syls)

	id1 = 'A'
	id2 = 'A'
	for ix1 in range(len(syls)-1):
		if sylrhym[ix1] != '' or syls[ix1] == '':
			continue
		else:
			sylrhym[ix1] = id1+id2
		for ix2 in range(ix1+1,len(syls)):
			if sylrhymes(syls[ix1],syls[ix2]):
				sylrhym[ix2] = id1+id2
		id2 = chr(ord(id2)+1)
		if ord(id2) > 90:
			id1 = chr(ord(id1)+1)
			id2 = 'A'

	#now we have rhyme on syllable level
	#detect rhyme at word / phrase level
	rhyme = getRhyme(sylrhym,ends)

	#for ix in range(len(syls)):
		#print syls[ix], ends[ix], sylrhym[ix], rhyme[ix]

	for ix in range(len(syls)):
		if fl[ix].lyrics:
			fl[ix].addLyric(sylrhym[ix])
			fl[ix].addLyric(str(rhyme[ix]))


#expect a song that already has Phonemes and stress as added by addPhonemes(s)
def collectPhonemeWords(s):
	#collect words
	fl = s.flat.notes
	#fl.show()
	words = []
	word = ''
	for ix, n in enumerate(fl):
		if not n.lyrics: #this is problematic
			continue
		if len(n.lyrics) < 2:
			continue
		word = word + n.lyrics[1].text
		if n.lyrics[1].syllabic == 'single' or n.lyrics[1].syllabic == 'end':
			words.append((word,ix)) #store index of last syllable in word
			word = ''
	return words


def plotboolmatrix(m):
	simbool = np.zeros((len(m),len(m)))
	for i in range(len(m)):
		for j in range(len(m)):
			if m[i][j]==True: simbool[i][j] = 1.0
	plt.imshow(simbool)
	plt.draw()

def detectRhymeWords(words,plot=False):
	#create similaritymatrix
	sim   = [ [ False for i in range(len(words))] for j in range(len(words))]
	ident = [ [ False for i in range(len(words))] for j in range(len(words))]
	for x in range(len(words)):
		for y in range(len(words)):
			rm,idl = wordrhymes(words[x][0],words[y][0])
			#print x, y, words[x][0], words[y][0], rm, idl 
			sim[x][y] = rm
			ident[x][y] = idl
			#print sim,ident
	if plot==True:
		plt.ion()
		plt.show()
		plotboolmatrix(sim)
	#return sim,ident
	# back to front
	# if words rhymes : annotate
	# if words are identical : only last of series identical words rhymes
	rhymes = [False]*len(words)
	rhymedistance = [0]*len(words)
	for x in range(-1,-len(words)-1,-1):
		for y in range(x-1,-len(words)-1,-1):
			#print words[x], words[y], sim[x][y], ident[x][y]
			#time.sleep(1)
			if sim[x][y] == True:
				rhymes[x] = True
				rhymes[y] = True
				if rhymedistance[x] > 0:
					rhymedistance[x] = min( rhymedistance[x], abs(x-y) )
				else:
					rhymedistance[x] = abs(x-y)
				if rhymedistance[y] > 0:
					rhymedistance[y] = min( rhymedistance[y], abs(x-y) )
				else:
					rhymedistance[y] = abs(x-y)
				#clear trace
				x1 = x-1
				y1 = y-1
				while (x1 >= -len(words)) and (y1 >= -len(words)) and (ident[x1][y1] == True):
					sim[x1][y1] = False
					ident[x1][y1] = False
					x1 = x1 - 1
					y1 = y1 - 1
				if plot==True: plotboolmatrix(sim)
	return rhymes, rhymedistance

def addRhymeToSong(s,rhymes,words):
	fl = s.flat.notes 
	for n in fl:
		if n.lyrics:
			n.addLyric("False")
	for ix,w in enumerate(words):
		#print ix, w, rhymes[ix], w[1]
		if rhymes[ix]==True:
			fl[w[1]].lyrics[-1].text="True"

#expect rhyme ('False' or 'True') in lyrics[3].text
#return list of onsets of note at which rhyme occurs
def collectRhymeOffsets(s):
	fl = s.flat.notes
	dist = 1
	offsets = []
	dist_to_last = [] # list of (offset,dist)
	for ix, n in enumerate(fl):
		if n.lyrics:
			if len(n.lyrics) > 2 and n.lyrics[3].text == 'True':
				offsets.append(n.getOffsetBySite(fl))
				dist = 0
		dist_to_last.append( (n.getOffsetBySite(fl), dist) )
		if n.tie:
			if n.tie.type != 'start' and n.tie.type != 'continue':
				dist = dist + 1
		else:
			dist = dist + 1
	return offsets, dist_to_last

def collectWordstressOffsets(s):
	fl = s.flat.notes
	offsets = []
	for n in fl:
		if n.lyrics:
			if len(n.lyrics) > 2 and n.lyrics[2].text == '1':
				offsets.append(n.getOffsetBySite(fl))
	return offsets

def addOffsetsAsLyrics(s):
	fl = s.flat.notes
	for ix, n in enumerate(fl):
		n.addLyric(str(round(n.offset,2)))
		n.addLyric(str(ix))

def showRhyme(nlbid):
	#s = converter.parse('/Users/pvk/Documents/data/Annotated_krn/'+nlbid+'.krn')
	s = converter.parse(krnpath+nlbid+'.krn')
	addPhonemes(s)
	lyricsToEndOfMelisma(s)
	removeNonContentsWords(s)
	words = collectPhonemeWords(s)
	rh,rh_dist = detectRhymeWords(words,plot=True)
	addRhymeToSong(s,rh,words)
	s.insert(metadata.Metadata())
	s.metadata.title = nlbid
	addOffsetsAsLyrics(s)
	#out = s.write('lily.png')
	#shutil.move(out,'/Users/pvk/Documents/Eigenwerk/Projects/Rhyme/png/'+nlbid+'.png')
	s.show()

class CollectWordstressOffsetsByNLBid:
	def __init__(self):
		self.cache = {}
	def __call__(self,nlbid):
		stress = []
		if nlbid in self.cache:
			stress = self.cache[nlbid]
		else:
			#s = converter.parse('/Users/pvk/Documents/data/Annotated_krn/'+nlbid+'.krn')
			#s = converter.parse('/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/0.3/MTC-FS/krn/'+nlbid+'.krn')
			s = converter.parse(krnpath+nlbid+'.krn')
			addPhonemes(s)
			stress = collectWordstressOffsets(s)
			self.cache[nlbid] = stress
		return stress
collectWordstressOffsetsByNLBid = CollectWordstressOffsetsByNLBid()

class CollectRhymeOffsetsByNLBid:
	def __init__(self):
		self.cache = {}
	def __call__(self,nlbid):
		off = []
		distoff = []
		if nlbid in self.cache:
			off,distoff = self.cache[nlbid]
		else:
			#s = converter.parse('/Users/pvk/Documents/data/Annotated_krn/'+nlbid+'.krn')
			#s = converter.parse('/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/0.3/MTC-FS/krn/'+nlbid+'.krn')
			s = converter.parse(krnpath+nlbid+'.krn')
			addPhonemes(s)
			lyricsToEndOfMelisma(s)
			removeNonContentsWords(s)
			words = collectPhonemeWords(s)
			rh,rh_dist = detectRhymeWords(words)
			addRhymeToSong(s,rh,words)
			off,distoff = collectRhymeOffsets(s)
			self.cache[nlbid] = (off,distoff)
		return off,distoff
collectRhymeOffsetsByNLBid = CollectRhymeOffsetsByNLBid()

def showPhonology(nlbid):
	# nlbid : 'NLBxxxxxx_yy'
	# load song
	#s = converter.parse('/Users/pvk/Documents/data/Annotated_krn/'+nlbid+'.krn')
	s = converter.parse(krnpath+nlbid+'.krn')
	addPhonemes(s)
	s.insert(metadata.Metadata())
	s.metadata.title = nlbid
	out = s.write('lily.png')
	shutil.move(out,'/Users/pvk/Documents/Eigenwerk/Projects/Rhyme/png/'+nlbid+'.png')
