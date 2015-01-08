import numpy as np
import pylab as pl
import pickle
import shutil
import os
import pprint
import csv
from operator import xor
from music21 import *

# 2014-3-27: lyrics /rhyme added
# run -i '/Users/pvk/Documents/Eigenwerk/Projects/Rhyme/rhyme.py'

#################################################
#
# Necessary for floating point comparison
#
epsilon = 0.001

#################################################
#
# Configuration
#
krnpath = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/data/1.0/MTC-FS-1.0/krn/'
#krnpath = '/Users/pvk/Documents/data/NLB-FS-1.55/'
#krnpath = '/Users/pvk/Documents/data/Annotated_krn/'

#krnflist = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/flist/mtc-fs-krn-1.0.flist'
krnflist = '/Users/pvk/Documents/Eigenwerk/Projects/MeertensTuneCollections/flist/mtc-fs-krn-1.0-first10.flist'
#krnflist = '/Users/pvk/Documents/data/Annotated_krn/annotated.flist'

#picklekrnflist = '/Users/pvk/Documents/data/Annotated_pickle/annotated.flist'
#picklekrnflist = '/Users/pvk/Documents/data/NLB-FS-1.55-pickle/index.flist'
picklekrnflist = ''

#################################################
#
# Make corpus available
#

def pickleCorpus(fn,outputdir):
    inFile = open(fn, 'r')
    for line in inFile:
        line = line.rstrip('\n')
        print 'Parsing '+line
        s = converter.parse(line)
        bn = os.path.basename(line).rstrip('.krn')
        print 'Storing '+bn+'.pkl'
        converter.freeze(s, fmt='pickle', fp=outputdir+'/'+bn+'.pkl')

def _readCorpus(fn):
    counter = 0;
    for line in open(fn):
        line = line.rstrip('\n')
        print str(counter) + ' Reading '+line
        s = converter.thaw(line)
        yield s
        counter += 1

def readCorpus(fn):
    counter = 0;
    for line in open(fn):
        line = line.rstrip('\n')
        print str(counter) + ' Reading '+line
        s = converter.parse(line)
        yield s
        counter += 1

#################################################
#
# Construct trigrams from melodies
#

def getPhraseEnds(melody):
    """
    Returns a list of offsets of phrase _ends_ in quarterLength units
    The offsets are the ending times of the final notes/rests of phrases

    melody : music21.score object
    """
    offsets = []
    comments = melody.flat.getElementsByClass(humdrum.spineParser.GlobalComment)
    for c in comments:
        if 'verse' in c.comment:
            offsets.append(c.offset)
    #remove first, add last
    offsets.pop(0)
    offsets.append(melody.highestTime)
    return offsets

def hasBarLines(melody):
    return len(melody.flat.getElementsByClass(bar.Barline)) > 0

def getTrigrams_all(melody,noRepeats=True):
    """
    Problems:
    - rests
    - ties
    - pitch repetitions
    - note offset
    - what to do with beatstrength in case of free meter? Now: 0.0 (which does not occur elsewhere)
    - what to do with pitch repetitions across phrase boundaries?

    Alternative method: add attributes to notes
    
    n.phrase (int) : zero-based prhase number
    n.startPhrase (bool) : first note of phrase
    n.endPhrase (bool) : last note of phrase
    n.previousIsRest (bool) : True if preceeded by rest
    n.nextIsRestOrEnd (bool) : True if followed by rest, or by nothing for last note
    n.connect (bool) : True if pitch of previous is same
    n.cummulatedDuration (float) : duration of n and previous notes with same pitch
    n.connectedPhraseEnd (bool) : True if one of previous connected notes is phrase end


    Then extract the trigrams
    It is easier to remove repeating pitches
    And it is much faster
    """
    trigrams = []
    phraseBounds = getPhraseEnds(melody)
    mel = melody.flat.notes
    melR = melody.flat.notesAndRests
    timesigs = melody.flat.getTimeSignatures()
    bl = hasBarLines(melody) # melody in free meter has no barlines in kern

    #Annotate phrase number
    ix = 0
    phr = 0
    for pb in phraseBounds:
        while (ix < len(mel)) and (mel[ix].offset - pb < 0 ) :
            mel[ix].phrase = phr
            ix += 1
        phr += 1

    #Annotate cadence, and beginning of phrase
    mel[0].startPhrase = True
    mel[0].endPhrase = False
    mel[-1].startPhrase = False
    mel[-1].endPhrase = True
    for i in range(1,len(mel)-1):
        if mel[i-1].phrase != mel[i].phrase:
            mel[i].startPhrase = True
        else:
            mel[i].startPhrase = False
        if mel[i+1].phrase != mel[i].phrase:
            mel[i].endPhrase = True #could be the second of tied notes.
        else:
            mel[i].endPhrase = False

    #where are the rests?
    for ix in range(len(melR)):
        if ix>0 and melR[ix-1].isRest:
            melR[ix].previousIsRest = True
        else:
            melR[ix].previousIsRest = False
        if ix<len(melR)-1 and melR[ix+1].isRest:
            melR[ix].nextIsRestOrEnd = True
        else:
            melR[ix].nextIsRestOrEnd = False
    #final note:
    mel[-1].nextIsRestOrEnd = True

    #find out whether the note has the same pitch as previous
    #find end indices for for connected notes
    #ties always, other repeated pitches only if noRepeats
    mel[0].connect = False
    mel[0].cummulatedDuration = mel[0].quarterLength
    mel[0].connectedPhraseEnd = False
    endixs = [0]
    for ix in range(1,len(mel)):
        #if noRepeats and mel[ix].pitch == mel[ix-1].pitch and mel[ix].phrase == mel[ix-1].phrase and (not mel[ix].previousIsRest):
        mel[ix].connectedPhraseEnd = False
        if noRepeats and mel[ix].pitch == mel[ix-1].pitch and (not mel[ix].previousIsRest):
            if (mel[ix].phrase != mel[ix-1].phrase) or mel[ix-1].connectedPhraseEnd:
                mel[ix].connectedPhraseEnd = True
            mel[ix].connect = True
            mel[ix].cummulatedDuration = mel[ix-1].cummulatedDuration + mel[ix].quarterLength
            endixs[-1] = ix
        elif (not noRepeats) and mel[ix].tie:
            #tie won't go over a phrase boundary. No need to check for that.
            if mel[ix].tie.type == 'stop' or mel[ix].tie.type == 'continue':
                mel[ix].connect = True
                mel[ix].cummulatedDuration = mel[ix-1].cummulatedDuration + mel[ix].quarterLength
                endixs[-1] = ix
            else:
                mel[ix].connect = False
                mel[ix].cummulatedDuration = mel[ix].quarterLength
                endixs.append(ix)
        else:
            mel[ix].connect = False
            mel[ix].cummulatedDuration = mel[ix].quarterLength
            endixs.append(ix)

    #find start indices for connected notes
    startixs = []
    for ix,n in enumerate(mel):
        if not n.connect:
            startixs.append(ix)

    pitch_ixs = zip(startixs,endixs)

    count = max(0, len(pitch_ixs) - 3 + 1)
    for t_ixs in (tuple(pitch_ixs[i:i+3]) for i in xrange(count)):
        #print t_ixs
        tr = stream.Stream()
        strengths = []
        orig_offsets = []
        durations = []
        startixfirst = t_ixs[0][0]
        stopixlast = t_ixs[2][1]
        for startix, stopix in t_ixs:
            tr.append(mel[startix])
            if bl:
                strengths.append(mel[startix].beatStrength)
            else:
                strengths.append(0.0)
            orig_offsets.append(mel[startix].getOffsetBySite(mel))
            durations.append(mel[stopix].cummulatedDuration)
        #note offset
        #go back until other phrase or begin of melody
        off = 0
        while startixfirst-off >= 0 and mel[startixfirst-off].phrase == mel[startixfirst].phrase:
            off = off + 1
        note_offset = off
        #find current meter
        tsoffset = max([m.offset for m in timesigs if orig_offsets[0]-m.offset > -epsilon]) #offset of last time sig
        timesig = timesigs.getElementsByOffset(tsoffset-epsilon,tsoffset+epsilon)
        timesigstr = timesig[0].ratioString
        if not bl: timesigstr = 'Free'
        #label
        if mel[stopixlast].endPhrase or mel[stopixlast].connectedPhraseEnd:
            label = 1
        else:
            label = 0
        #append to trigrams
        #trigrams.append((tr,strengths,orig_offsets,note_offset,timesigstr,durations,label,mel[startixfirst].pitch,t_ixs))
        trigrams.append([(tr,strengths,orig_offsets,note_offset,timesigstr,durations),label])
    return trigrams

#split in cadence / nocadence trigrams
def splittrigrams(trigrams):
    tr_cadence = []
    tr_nocadence = []
    for t in trigrams:
        if t[1] > 0:
            tr_cadence.append(t[0])
        else:
            tr_nocadence.append(t[0])
    return tr_cadence, tr_nocadence

def trigramToScaleDegrees(tr, mel):
    degrees = []
    keys = mel.flat.getElementsByClass(key.Key)
    if len(keys) > 0:
        thiskey = keys[0]
        degrees.append( thiskey.getScaleDegreeAndAccidentalFromPitch(tr[0])[0] )
        degrees.append( thiskey.getScaleDegreeAndAccidentalFromPitch(tr[1])[0] )
        degrees.append( thiskey.getScaleDegreeAndAccidentalFromPitch(tr[2])[0] )
    return degrees

def trigramToDiatonicScaleDegrees(tr, mel):
    degrees = []
    keys = mel.flat.getElementsByClass(key.Key)
    if len(keys) > 0:
        tonicshift = keys[0].tonic.diatonicNoteNum % 7 - 1
        degrees.append( tr[0].diatonicNoteNum - tonicshift )
        degrees.append( tr[1].diatonicNoteNum - tonicshift )
        degrees.append( tr[2].diatonicNoteNum - tonicshift )
    return degrees

def toScaleDegree(diatonicScaleDegree):
    res = diatonicScaleDegree % 7
    if res == 0:
        res = 7
    return res

def beatStrengths(tr,featevals,featnames,mel):
    if len(tr) > 0:
        featevals.append(tr[1][0])
        featevals.append(tr[1][1])
        featevals.append(tr[1][2])
        featnames.append("beatstrengtfirst")
        featnames.append("beatstrengtsecond")
        featnames.append("beatstrengtthird")

def smallestMetricWeight(tr,featvals,featnames,mel):
    if len(tr) > 0:
        strength = float('inf')
        for st in tr[1]:
            strength = min(strength,st)
        featvals.append(strength)
        featnames.append("minbeatstrength") 

def rhythmicDiversity(tr,featvals,featnames,mel):
    if len(tr) > 0:
        #only compare duration of first and second, not of third
        if tr[0][0].quarterLength > tr[0][1].quarterLength:
            featvals.append(tr[0][0].quarterLength / tr[0][1].quarterLength)
        else:
            featvals.append(tr[0][1].quarterLength / tr[0][0].quarterLength)
        featnames.append("rhythmidDiversity")

def offsets(tr,featvals,featnames,mel):
    if len(tr) > 0:
        featvals.append(tr[2][0])
        featvals.append(tr[2][1])
        featvals.append(tr[2][2])
        featnames.append("offsetfirst")
        featnames.append("offsetsecond")
        featnames.append("offsetthird")

def note_offset(tr,featvals,featnames,mel):
    if len(tr) > 0:
        featvals.append(tr[3])
        featnames.append("note_offset")

def current_timesig(tr,featvals,featnames,mel):
    if len(tr) > 0:
        featvals.append(tr[4])
        featnames.append("timesig")

def durations(tr,featvals,featnames,mel):
    if len(tr) > 0:
        featvals.append(tr[5][0])
        featnames.append("durationfirst")
        featvals.append(tr[5][1])
        featnames.append("durationsecond")
        featvals.append(tr[5][2])
        featnames.append("durationthird")

def rhyme(tr,featvals,featnames,nlbid):
    #following function is in : /Users/pvk/Documents/Eigenwerk/Projects/Rhyme/rhyme.py
    offs,distoffs = collectRhymeOffsetsByNLBid(nlbid)
    rhymeFirst = False
    rhymeSecond = False
    rhymeThird = False
    for o in offs:
        if abs(tr[2][0] - o) < epsilon:
            rhymeFirst = True
        if abs(tr[2][1] - o) < epsilon:
            rhymeSecond = True
        if abs(tr[2][2] - o) < epsilon:
            rhymeThird = True
    featvals.append(rhymeFirst)
    featvals.append(rhymeSecond)
    featvals.append(rhymeThird)
    featnames.append("rhymeFirst")
    featnames.append("rhymeSecond")
    featnames.append("rhymeThird")

def dist_to_last_rhyme(tr,featvals,featnames,nlbid,mel):
    #default:
    offs,distoffs = collectRhymeOffsetsByNLBid(nlbid)
    d1 = -1
    d2 = -1
    d3 = -1
    for do in distoffs:
        if abs(tr[2][0] - do[0]) < epsilon:
            d1 = do[1]
            continue
        if abs(tr[2][1] - do[0]) < epsilon:
            d2 = do[1]
            continue
        if abs(tr[2][2] - do[0]) < epsilon:
            d3 = do[1]
            break
    featvals.append(d1)
    featvals.append(d2)
    featvals.append(d3)
    featnames.append("dist_to_last_rhyme_first")
    featnames.append("dist_to_last_rhyme_second")
    featnames.append("dist_to_last_rhyme_third")

def wordStress(tr,featvals,featnames,nlbid):
    #following function is in : /Users/pvk/Documents/Eigenwerk/Projects/Rhyme/rhyme.py
    offs = collectWordstressOffsetsByNLBid(nlbid)
    wordstressFirst = False
    wordstressSecond = False
    wordstressThird = False
    for o in offs:
        if abs(tr[2][0] - o) < epsilon:
            wordstressFirst = True
        if abs(tr[2][1] - o) < epsilon:
            wordstressSecond = True
        if abs(tr[2][2] - o) < epsilon:
            wordstressThird = True
    featvals.append(wordstressFirst)
    featvals.append(wordstressSecond)
    featvals.append(wordstressThird)
    featnames.append("wordstressFirst")
    featnames.append("wordstressSecond")
    featnames.append("wordstressThird")


#what does this mean for final cadence?
#NOT TESTED
def narmour_next_is_rest_deprecated(tr,featvals,featnames,mel):
    res = False
    fl = mel.flat.notesAndRests
    #get the element at the end! of the thrid item in the trigram
    remainder = fl.getElementsByOffset(tr[2][2]+tr[5][2]-epsilon,fl.duration.quarterLength+epsilon,includeEndBoundary=False)
    if len(remainder) > 0:
        if remainder[0].isRest:
            res = True
    #final trigram
    if len(remainder) == 0:
        res = True
    featvals.append(res)
    featnames.append("next_is_rest")

#what does this mean for final cadence?
#NOT TESTED
def narmour_next_is_rest(tr,featvals,featnames):
    featvals.append(tr[0][0].nextIsRestOrEnd)
    featvals.append(tr[0][1].nextIsRestOrEnd)
    featvals.append(tr[0][2].nextIsRestOrEnd)
    featnames.append("next_is_rest_first")
    featnames.append("next_is_rest_second")
    featnames.append("next_is_rest_third")

def narmour_shortlong(tr,featvals,featnames,mel):
    shortlong_first = False
    shortlong_second = False
    dur1 = tr[5][0]
    dur2 = tr[5][1]
    dur3 = tr[5][2]
    if dur2 > dur1:
        shortlong_first = True
    if dur3 > dur2:
        shortlong_second = True
    featvals.append(shortlong_first)
    featvals.append(shortlong_second)
    featnames.append("narmour_shortlong_first")
    featnames.append("narmour_shortlong_second")

def narmour_largesmall(tr,featvals,featnames,mel):
    first = abs(tr[0][1].diatonicNoteNum - tr[0][0].diatonicNoteNum)
    second = abs(tr[0][2].diatonicNoteNum - tr[0][1].diatonicNoteNum)
    if first >= 4 and second <= 2: #fifth is 4, third is 2
        featvals.append(True)
    else:
        featvals.append(False)
    featnames.append("narmour_largesmall")

def registralDirection(interval):
    if interval < 0  : return "down"
    if interval > 0  : return "up"
    if interval == 0 : return "lateral"
    return "undefined"

def narmour_registralchange(tr,featvals,featnames,mel):
    res = False
    first = tr[0][1].diatonicNoteNum - tr[0][0].diatonicNoteNum
    second = tr[0][2].diatonicNoteNum - tr[0][1].diatonicNoteNum
    if registralDirection(first) != registralDirection(second):
        res = True
    featvals.append(res)
    featnames.append("narmour_registralchange")

def narmour_spansmetricaccent(tr,featvals,featnames,mel):
    pass

def narmour_dissonance_consonance(tr,featvals,featnames,mel):
    pass

def extractFeatures(tr,mel):
    featvals = []
    featnames = []
    #N.B. order matters
    #indices are used in maketrigramdataset
    beatStrengths(tr,featvals,featnames,mel)
    rhythmicDiversity(tr,featvals,featnames,mel)
    smallestMetricWeight(tr,featvals,featnames,mel)
    offsets(tr,featvals,featnames,mel)
    note_offset(tr,featvals,featnames,mel)
    current_timesig(tr,featvals,featnames,mel)
    durations(tr,featvals,featnames,mel)
    rhyme(tr,featvals,featnames,os.path.splitext(os.path.basename(mel.filePath))[0])
    wordStress(tr,featvals,featnames,os.path.splitext(os.path.basename(mel.filePath))[0])
    narmour_next_is_rest(tr,featvals,featnames)
    narmour_shortlong(tr,featvals,featnames,mel)
    narmour_largesmall(tr,featvals,featnames,mel)
    narmour_registralchange(tr,featvals,featnames,mel)
    dist_to_last_rhyme(tr,featvals,featnames,os.path.splitext(os.path.basename(mel.filePath))[0],mel)
    return featvals,featnames

def getTrigramsAsScaleDegrees (fn,noRepeats=True):
    trigrams = []
    for song in readCorpus(fn):
        print "Getting trigrams"
        trs = getTrigrams_all(song,noRepeats)
        print "Converting trigrams to scale degrees"
        ts = []
        for t in trs:
            ts.append(trigramToDiatonicScaleDegrees(t[0][0],song))
            ts.append(extractFeatures(t[0],song))
            ts.append(t[1]) #label
        trigrams.append((os.path.splitext(os.path.basename(song.filePath))[0],ts))
    return trigrams

def getTrigramsAsScaleDegreesForOne(s,noRepeats=True):
    trigrams = []
    print "Getting trigrams"
    trs = getTrigrams_all(s,noRepeats)
    print "Converting trigrams to scale degrees"
    ts = []
    for t in trs:
        ts.append(trigramToDiatonicScaleDegrees(t[0][0],s))
        ts.append(extractFeatures(t[0],s))
        ts.append(t[1]) #label
    trigrams.append((os.path.splitext(os.path.basename(s.filePath))[0],ts))
    return trigrams

def pp_trigrams(trigrams):
    pp = pprint.PrettyPrinter(indent=4)
    for t in trigrams:
        print 
        print "NLBID: ", t[0]
        for ix in range(0,len(t[1]),3):
            print 
            print "Pitches : ", t[1][ix]
            pp.pprint(zip(t[1][ix+1][0],t[1][ix+1][1]))
            print "Label: ", t[1][ix+2]

def printTrigrams(id,lst):
    #id without .krn
    return next(subl for subl in lst if id+'.krn' in subl)

def toBJDict(trigrams,mclass='nocadence'):
    patterns = []
    for song in trigrams:
        for t in song[1]:
            if len(t)>0:
                pattern={}
                pattern['fam'] = 'Any'
                pattern['num'] = song[0]
                pattern['start'] = t[0][5]
                pattern['len'] = t[0][10] + t[0][11] + t[0][12]
                pattern['class'] = mclass
                pattern['desc'] = ''
                pattern['ann'] = ''
                patterns.append(pattern)
    #pickle.dump( patterns, open( "patterns.pkl", "wb" ) )
    #patterns = pickle.load( open( "patterns.pkl", "rb" ) )
    return patterns


#################################################
#
# save and trigrams from disk
#
def savetrigrams(cadence_trigrams, nocadence_trigrams):
    pickle.dump(cadence_trigrams, open( '/Users/pvk/Documents/data/NLB-FS-1.55-pickle/cadence_trigrams.pkl', 'wb') )
    pickle.dump(nocadence_trigrams, open( '/Users/pvk/Documents/data/NLB-FS-1.55-pickle/nocadence_trigrams.pkl', 'wb') )

def loadtrigrams():
    cadence_trigrams = pickle.load ( open( '/Users/pvk/Documents/data/NLB-FS-1.55-pickle/cadence_trigrams.pkl', 'rb'))
    nocadence_trigrams = pickle.load ( open( '/Users/pvk/Documents/data/NLB-FS-1.55-pickle/nocadence_trigrams.pkl', 'rb'))
    return cadence_trigrams, nocadence_trigrams

#################################################
#
# Extract features from trigrams
#
def isodd(number):
    return number % 2 == 1

def iseven(number):
    return number % 2 == 0
    
def ambitus(trigram):
    return abs(max(trigram) - min(trigram))

def containsleap(trigram):
    return max(abs(np.diff(trigram))) > 1

def hasContrastThird(trigram):
    #with respect to last note
    trigram = np.array(trigram) #Why is trigram no longer ndarray?????
    rel = trigram - trigram[2]
    return isodd(rel[0]) or isodd(rel[1])

def isAscending(trigram):
    return trigram[2] > trigram[1] and trigram[1] > trigram[0]

def isAscending_first(trigram):
    return trigram[1] > trigram[0]

def isAscending_second(trigram):
    return trigram[2] > trigram[1]

def isDescending(trigram):
    return trigram[2] < trigram[1] and trigram[1] < trigram[0]

def isDescending_first(trigram):
    return trigram[1] < trigram[0]

def isDescending_second(trigram):
    return trigram[2] < trigram[1]

def hasRepeats(trigram):
    return trigram[0] == trigram[1] or trigram[1] == trigram[2]

def narmourStructure(trigram):
    int1 = abs(trigram[1] - trigram[0])
    int2 = abs(trigram[2] - trigram[1])
    asc1 = trigram[1] > trigram[0]
    asc2 = trigram[2] > trigram[1]
    if int1 == 0 and int2 == 0: return 'D'
    if int1 <= 3 and int2 <= 3 and (asc1 == asc2): return 'P'
    if int1 <= 3 and int2 <= 3 and (int1 == int2) and (asc1 != asc2): return 'ID'
    if int1 >= 5 and int2 <= 3 and (asc1 != asc2): return 'R'
    if int1 <= 3 and int2 <= 3 and (asc1 != asc2): return 'IP'
    if int1 <= 3 and int2 >= 5 and (asc1 == asc2): return 'VP'
    if int1 >= 5 and int2 <= 3 and (asc1 == asc2): return 'IR'
    if int1 >= 5 and int2 >= 5 and (asc1 != asc2): return 'VR'
    return 'None'


#################################################
#
# Put trigrams, features and labels in numpy matrices
#
def tr_labels2tr_tr_labels(labels,ids):
    tr_tr_labels = []
    #first
    tr_tr_labels.append((0,labels[0],labels[1]))
    for ix in range(1,len(labels)-1):
        if ids[ix-1][0] != ids[ix][0]:
            tr_tr_labels.append((0,labels[ix],labels[ix+1]))
        elif ids[ix+1][0] != ids[ix][0]:
            tr_tr_labels.append((labels[ix-1],labels[ix],0))
        else:
            tr_tr_labels.append((labels[ix-1],labels[ix],labels[ix+1]))
    #final
    tr_tr_labels.append((labels[-2],labels[-1],0))
    return tr_tr_labels

def maketrigramdataset(trigrams):
    #first find out how many trigrams
    sizetr = 0
    for d in trigrams:
        sizetr = sizetr + ( len(d[1]) / 3 )
    x = np.zeros((sizetr,38),dtype=float)
    #x = [[0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,'']] * sizetr
    rawlabels = []
    timesigs = [] #storing time signatures
    narmourstructures = []
    ids = [] # for storing identity of cadences (recordnumber and offsets)
    i=0
    for d1 in trigrams:
        for tix in range(0,len(d1[1]),3):
            d2 = d1[1][tix]
            feats = d1[1][tix+1]
            if len(d2) == 3:
                x[i][0] = d2[0]
                x[i][1] = d2[1]
                x[i][2] = d2[2]
                x[i][3] = toScaleDegree(d2[0])
                x[i][4] = toScaleDegree(d2[1])
                x[i][5] = toScaleDegree(d2[2])
                x[i][6] = ambitus(d2)
                x[i][7] = containsleap(d2)
                x[i][8] = hasContrastThird(d2)
                x[i][9] = isAscending(d2)
                x[i][10] = isAscending_first(d2)
                x[i][11] = isAscending_second(d2)
                x[i][12] = isDescending(d2)
                x[i][13] = isDescending_first(d2)
                x[i][14] = isDescending_second(d2)
                x[i][15] = hasRepeats(d2)
                x[i][16] = feats[0][0] #beatstrengthfirst
                x[i][17] = feats[0][1] #beatstrengthsecond
                x[i][18] = feats[0][2] #beatstrengththird
                x[i][19] = feats[0][3] #minbeatstrength
                x[i][20] = feats[0][4] #rhythmicdiversity
                x[i][21] = feats[0][8] #note_offset
                x[i][22] = feats[0][13] #rhymes_first
                x[i][23] = feats[0][14] #rhymes_second
                x[i][24] = feats[0][15] #rhymes_third
                x[i][25] = feats[0][16] #wordstress_first
                x[i][26] = feats[0][17] #wordstress_second
                x[i][27] = feats[0][18] #wordstress_thrid
                x[i][28] = feats[0][19] #next_is_rest_first
                x[i][29] = feats[0][20] #next_is_rest_second
                x[i][30] = feats[0][21] #next_is_rest_third
                x[i][31] = feats[0][22] #narmour_short_long_first
                x[i][32] = feats[0][23] #narmour_short_long_second
                x[i][33] = feats[0][24] #narmour_large_small
                x[i][34] = feats[0][25] #narmour_registralchange
                x[i][35] = feats[0][26] #dist to last rhyme first
                x[i][36] = feats[0][27] #dist to last rhyme second
                x[i][37] = feats[0][28] #dist to last rhyme third
                narmourstructures.append(narmourStructure(d2))
                timesigs.append(feats[0][9])
                i = i + 1
                #print d2, ambitus(d2), containsleap(d2), hasContrastThird(d2), isAscending(d2), isDescending(d2), hasRepeats(d2)
                rawlabels.append(d1[1][tix+2])
                id = d1[0]
                offsets = [feats[0][5],feats[0][6],feats[0][7]]
                ids.append((id,offsets))
            else:
                print "empty: ", d1[0]
    labels=np.array(rawlabels)
    data = x[0:len(labels),:]
    tr_labels = tr_labels2tr_tr_labels(labels,ids)
    return data, labels, tr_labels, ids, timesigs, narmourstructures

def narmour_level_of_closure(tr_data):
    tr_narmour_level = np.zeros((len(tr_data),1))
    for ix, d in enumerate(tr_data):
        count = 0
        if d[18] > 1.0-epsilon: count += 1
        if d[30]: count += 1
        if d[32]: count += 1
        if d[33]: count += 1
        if d[34]: count += 1
        tr_narmour_level[ix] = count
    return tr_narmour_level

#################################################
#
# Write dataset as arff
#
def writeArffHeader(fn,timesigs):
    f = open(fn,"w")
    f.write("@RELATION cadences\n")
    f.write("@ATTRIBUTE diatonicfirst NUMERIC\n")
    f.write("@ATTRIBUTE diatonicsecond NUMERIC\n")
    f.write("@ATTRIBUTE diatonicthird NUMERIC\n")
    f.write("@ATTRIBUTE scaledegreefirst NUMERIC\n")
    f.write("@ATTRIBUTE scaledegreesecond NUMERIC\n")
    f.write("@ATTRIBUTE scaledegreethird NUMERIC\n")
    f.write("@ATTRIBUTE ambitus NUMERIC\n")
    f.write("@ATTRIBUTE containsleap NUMERIC\n")
    f.write("@ATTRIBUTE hascontrastthird NUMERIC\n")
    f.write("@ATTRIBUTE isascending NUMERIC\n")
    f.write("@ATTRIBUTE isascending_first NUMERIC\n")
    f.write("@ATTRIBUTE isascending_second NUMERIC\n")
    f.write("@ATTRIBUTE isdescending NUMERIC\n")
    f.write("@ATTRIBUTE isdescending_first NUMERIC\n")
    f.write("@ATTRIBUTE isdescending_second NUMERIC\n")
    f.write("@ATTRIBUTE hasrepeats NUMERIC\n")
    f.write("@ATTRIBUTE beatstrengthfirst NUMERIC\n")
    f.write("@ATTRIBUTE beatstrengthsecond NUMERIC\n")
    f.write("@ATTRIBUTE beatstrengththird NUMERIC\n")
    f.write("@ATTRIBUTE minbeatstrength NUMERIC\n")
    f.write("@ATTRIBUTE rhythmicdiversity NUMERIC\n")
    f.write("@ATTRIBUTE noteoffset NUMERIC\n")
    f.write("@ATTRIBUTE rhymesfirst NUMERIC\n")
    f.write("@ATTRIBUTE rhymessecond NUMERIC\n")
    f.write("@ATTRIBUTE rhymesthird NUMERIC\n")
    f.write("@ATTRIBUTE wordstressfirst NUMERIC\n")
    f.write("@ATTRIBUTE wordstresssecond NUMERIC\n")
    f.write("@ATTRIBUTE wordstressthird NUMERIC\n")
    f.write("@ATTRIBUTE narmour_next_is_rest_first NUMERIC\n")
    f.write("@ATTRIBUTE narmour_next_is_rest_second NUMERIC\n")
    f.write("@ATTRIBUTE narmour_next_is_rest_third NUMERIC\n")
    f.write("@ATTRIBUTE narmour_shortlong_first NUMERIC\n")
    f.write("@ATTRIBUTE narmour_shortlong_second NUMERIC\n")
    f.write("@ATTRIBUTE narmour_largesmall NUMERIC\n")
    f.write("@ATTRIBUTE narmour_registralchange NUMERIC\n")
    f.write("@ATTRIBUTE dist_to_last_rhyme_first NUMERIC\n")
    f.write("@ATTRIBUTE dist_to_last_rhyme_second NUMERIC\n")
    f.write("@ATTRIBUTE dist_to_last_rhyme_third NUMERIC\n")
    f.write("@ATTRIBUTE timesig {" + ",".join(list(set(timesigs))) + "}\n")
    f.write("@ATTRIBUTE narmourstructure {P,R,IP,VP,IR,VR,D,ID,None}\n")
    #f.write("@ATTRIBUTE offsetfirst NUMERIC\n")
    #f.write("@ATTRIBUTE offsetsecond NUMERIC\n")
    #f.write("@ATTRIBUTE offsetthird NUMERIC\n")
    #f.write("@ATTRIBUTE id STRING\n")
    #f.write("@ATTRIBUTE class {cadence,nocadence,cadencetonic,cadencesupertonic,cadencethird,cadencedominant}\n")
    f.write("@ATTRIBUTE class {cadence,nocadence}\n")
    f.write("@ATTRIBUTE trclass {000,001,010,011,100,101,110,111}\n")
    f.write("\n")
    f.write("@data\n")
    f.close()    

def writetrigramsarff(fn,data,labels,tr_labels,ids,timesigs,narmourstructures):
    f = open(fn,"a")
    writeArffHeader(fn,timesigs)
    selected_ids = []
    selected_labels = []
    for i in range(len(labels)):
        # KEEP ONLY FINAL CADENCES: (label is 2)
        #if labels[i] == 1:
        #    continue
        print i, "of ", len(labels)
        selected_ids.append(ids[i])
        selected_labels.append(labels[i])
        for ix in range(16):
            f.write(str(data[i][ix]))
            f.write(",")
        if data[i][16] == 0: #no metric weights
            f.write("?,?,?,?,")
            for ix in range(20,38):
                f.write(str(data[i][ix]))
                f.write(",")
            f.write(timesigs[i])
            f.write(",")
            f.write(narmourstructures[i])
            f.write(",")
        else:
            for ix in range(16,38):
                f.write(str(data[i][ix]))
                f.write(",")
            f.write(timesigs[i])
            f.write(",")
            f.write(narmourstructures[i])
            f.write(",")
        #f.write(str(ids[i][1][0]))
        #f.write(",")
        #f.write(str(ids[i][1][1]))
        #f.write(",")
        #f.write(str(ids[i][1][2]))
        #f.write(",")
        #f.write(ids[i][0])
        #f.write(",")
        if labels[i] == 0:
            f.write("nocadence")
        #if labels[i] == 1 or labels[i] == 2:
        #    if data[i][5] == 1:
        #        f.write("cadencetonic\n")
        #    elif data[i][5] == 2:
        #        f.write("cadencesupertonic\n")
        #    elif data[i][5] == 3:
        #        f.write("cadencethird\n")
        #    elif data[i][5] == 5:
        #        f.write("cadencedominant\n")
        #    else:
        #        f.write("cadence\n")
        #if labels[i] == 1 or labels[i] == 2:
        #    f.write("cadence\n")
        if labels[i] == 2 or labels[i] == 1:
            f.write("cadence")
        f.write(",")
        f.write(str(tr_labels[i][0])+str(tr_labels[i][1])+str(tr_labels[i][2]))
        f.write("\n")
    f.close()
    return selected_ids, selected_labels


def toListOfDictionaries(data,labels,ids,timesigs,narmourstructures):
    ds = []
    for i in range(len(labels)):
        fts = {}
        fts['scaledegreefirst'] = data[i][3]
        fts['scaledegreesecond'] = data[i][4]
        fts['scaledegreethird'] = data[i][5]
        fts['ambitus'] = data[i][6]
        if data[i][7] > 0: fts['containsleap'] = 1
        if data[i][9] > 0: fts['isascending'] = 1
        if data[i][10] > 0: fts['isascending_first'] = 1
        if data[i][11] > 0: fts['isascending_second'] = 1
        if data[i][12] > 0: fts['isdescending'] = 1
        if data[i][13] > 0: fts['isdescending_first'] = 1
        if data[i][14] > 0: fts['isdescending_second'] = 1
        if data[i][16] > 0: fts['beatstrengthfirst'] = data[i][16]
        if data[i][17] > 0: fts['beatstrengthsecond'] = data[i][17]
        if data[i][18] > 0: fts['beatstrengththird'] = data[i][18]
        if data[i][19] > 0: fts['minbeatstrength'] = data[i][19]
        if data[i][22] > 0: fts['rhymesfirst'] = 1
        if data[i][23] > 0: fts['rhymessecond'] = 1
        if data[i][24] > 0: fts['rhymesthird'] = 1
        if data[i][25] > 0: fts['wordstressfirst'] = 1
        if data[i][26] > 0: fts['wordstresssecond'] = 1
        if data[i][27] > 0: fts['wordstressthird'] = 1
        if data[i][28] > 0: fts['narmour_next_is_rest_first'] = 1
        if data[i][29] > 0: fts['narmour_next_is_rest_second'] = 1
        if data[i][30] > 0: fts['narmour_next_is_rest_third'] = 1
        if data[i][31] > 0: fts['narmour_shortlong_first'] = 1
        if data[i][32] > 0: fts['narmour_shortlong_second'] = 1
        if data[i][33] > 0: fts['narmour_largesmall'] = 1
        if data[i][34] > 0: fts['narmour_registralchange'] = 1
        if data[i][35] > -1: fts['dist_to_last_rhyme_first'] = data[i][33]
        if data[i][36] > -1: fts['dist_to_last_rhyme_second'] = data[i][34]
        if data[i][37] > -1: fts['dist_to_last_rhyme_third'] = data[i][35]
        fts['timesig='+timesigs[i]] = 1
        #fts['narmourstructure='+narmourstructures[i]] = 1
        ds.append(fts)
    return ds

#NBNBNB Indices kloppen niet meer. CONTROLEREN
def writeFirstLastTSV(fn,data,labels,ids):
    print "Indices kloppen niet meer. CONTROLEREN"
    f = open(fn,'w')
    f.write("id\tquarterlengthoffset\tnoteoffsetinphrase\tscaledegreefirst\tscaledegreesecond\tscaledegreethird\trange\tcontainsleap\tisascending\tarriveascending\tisdescending\tarrivedescending\tbeatstrengthfirst\tbeatstrengthsecond\tbeatstrengththird\tclass\n")
    for i in range(len(labels)):
        #keep only first and last trigrams
        if data[i][19] != 0 and labels[i] != 1 and labels[i] != 2 :
            continue
        #skip phrases with only one trigram
        if data[i][19] == 0 and ( labels[i] == 1 or labels[i] == 2 ):
            continue
        print i, "of ", len(labels)
        f.write(ids[i][0])
        f.write("\t")
        f.write(str(ids[i][1][0]))
        f.write("\t")
        f.write(str(data[i][19]))
        f.write("\t")
        for field in [3, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16]:
            f.write(str(data[i][field]))
            f.write("\t")
        if labels[i] == 2 or labels[i] == 1:
            f.write("end\n")
        else:
            f.write("begin\n")
    f.close()


#################################################
#
# Analysis of cadences
#

# returns table with counts of cadence tones (scale degrees) that are approached stepwise descending.
# Needs data and labels as returned by maketrigramdataset
def cadenceApproach(cads,labels):
    #histogram
    #bin for each scale degree
    cadhist = [0]*7
    for ix, c in enumerate(cads):
        if labels[ix] < 2:
            continue
        if round(int(c[1] - c[2])) == 1:
            cadhist[int(round(c[5]))-1] += 1
            #if int(round(c[5])) == 4: print ix 
    return cadhist

#ids as returned by maketrigramdataset
#nlblist is list of identifiers of melodies to split
def splitCadencesByNLBIDs(ids,nlblist):
    splita = []
    splitb = []
    for ix,i in enumerate(ids):
        if i[0] in nlblist:
            splita.append(ix)
        else:
            splitb.append(ix)
    return splita, splitb 

#################################################
#
# After classification
#
def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)

def readIndices(fn):
    ixs = []
    for line in open(fn):
        line = line.rstrip('\n')
        ixs.append(int(line)-1)
    return ixs

#size of rules corresponds with ixs. For each ix it gives the rule that discovered the trigram
def cadsPerSong(ixs,ids,labels,rules=None):
    cads = {}
    for i in range(len(ixs)):
        print ids[ixs[i]]
        id = ids[ixs[i]][0]
        o1 = ids[ixs[i]][1][0]
        o2 = ids[ixs[i]][1][1]
        o3 = ids[ixs[i]][1][2]
        labl = labels[ixs[i]]
        rule = None
        if rules:
            rule = rules[i] + 1 #1-based
        try:
            cads[id].append([[o1,o2,o3],labl,rule])
        except KeyError:
            cads[id] = []
            cads[id].append([[o1,o2,o3],labl,rule])
    return cads


def visualize_cadences(ixs,outputdir,ids,labels,rules=None):
    #ixs is list of indices of trigrams to visualize N.B. 0-based (output of weka is 1-based)
    ensure_dir(outputdir)
    cads = cadsPerSong(ixs,ids,labels,rules)
    for id in cads:
        print id
        #song = converter.thaw('/Users/pvk/Documents/data/Annotated_pickle/'+id+'.pkl')
        #song = converter.thaw('/Users/pvk/Documents/data/NLB-FS-1.55-pickle/'+id+'.pkl')
        song = converter.parse(krnpath+id+'.krn')
        songflat = song.flat.notesAndRests
        for c in cads[id]:
            color = "red"
            if c[1] > 0:
                color = "blue"
            for off in c[0]:
                songflat.getElementsByOffset(off-epsilon,off+epsilon)[0].color = color
            label = "X"
            if c[2]:
                label = str(c[2])
            songflat.getElementsByOffset(c[0][0]-epsilon,c[0][0]+epsilon)[0].addLyric(label)
        offsets = getPhraseEnds(song)
        ##not necessary anymore. there now are fermatas
        #for i in range(len(offsets)-1): # not last phrase end
        #    songflat.getElementsByOffset(offsets[i]-epsilon,offsets[i]+epsilon)[0].addLyric("PHR")
        out = song.write('lily.png')
        shutil.move(out,outputdir+'/'+id+'.png')

def getCadenceSequence(nlbid):
    pass

#################################################
#
# Select trigrams according to rules
#

def ruleC1(t, timesignature=None):
    return t[5] == 1 and t[12] and t[16] >= (0.5 - epsilon)

def ruleC2(t, timesignature=None):
    return t[5] == 5 and t[11] and t[16] >= (0.5 - epsilon)

def ruleC3(t, timesignature=None):
    return t[5] == 1 and t[4] == 7 and t[16] >= (1.0 - epsilon)

def ruleD1(t, timesignature=None):
    return t[19] >= 7 and t[5] == 1 and t[16] >= (0.5 - epsilon)

def ruleD2(t, timesignature=None):
    return t[19] >= 4 and t[5] == 1 and t[12] and t[16] >= (0.5 - epsilon) and timesignature == '6/8'

def ruleD3(t, timesignature=None):
    return t[19] >= 6 and t[5] == 5 and t[11] and t[16] >= (0.5 - epsilon)


def selectByRules(data,timesignatures,testrules):
    ixs = []
    rules = []
    for i in range(len(data)):
        #if i == 10
        #    print i, data[i], testrules[0](data[i])
        for j in range(len(testrules)):
            if testrules[j](data[i],timesignatures[i]):
                ixs.append(i)
                rules.append(j)
    return ixs, rules

#################################################
#
# Basic
#
def workflow():
    #cadence_trigrams, nocadence_trigrams = getTrigramsAsScaleDegrees('/Users/pvk/Documents/data/NLBpickle/index.flist')
    cadence_trigrams, nocadence_trigrams = getTrigramsAsScaleDegrees('/Users/pvk/Documents/data/NLB-FS-1.55-pickle/index.flist')
    #savetrigrams(cadence_trigrams, nocadence_trigrams)
    #cadence_trigrams, nocadence_trigrams = loadtrigrams()
    data,labels,ids,timesigs,nstructs = maketrigramdataset(cadence_trigrams,nocadence_trigrams)
    selected_ids = writetrigramsarff('/Users/pvk/Documents/Eigenwerk/Projects/Cadences/tst.arff',data,labels,ids,timesigs,nstructs)

#################################################
#
# Cadence Sequence
#
def pitchToScaleDegree(note, mel):
    keys = mel.flat.getElementsByClass(key.Key)
    degree = 0
    if len(keys) > 0:
        thiskey = keys[0]
        degree = thiskey.getScaleDegreeAndAccidentalFromPitch(note)[0]
    return degree

def getCadenceSequence(s):
    cadenceSequence = []
    ends = getPhraseEnds(s)
    p1 = 0
    p2 = 0
    p3 = 0
    for e in ends:
        p = s.flat.notes.getElementAtOrBefore(e-epsilon)
        p3 = pitchToScaleDegree(p,s)
        #find previous pitch
        ix = s.flat.notes.index(p) - 1
        while (pitchToScaleDegree(s.flat.notes[ix],s)) == p3:
            ix = ix-1
            if ix < 0: break
        if ix > 0:
            p2 = pitchToScaleDegree(s.flat.notes[ix],s)
        ix = ix -1
        while (pitchToScaleDegree(s.flat.notes[ix],s)) == p2:
            ix = ix-1
            if ix < 0: break
        if ix > 0:
            p1 = pitchToScaleDegree(s.flat.notes[ix],s)
        cadenceSequence.append(p1)
        cadenceSequence.append(p2)
        cadenceSequence.append(p3)
        #if ix_p > 1:
        #    cadenceSequence.append(pitchToScaleDegree(s.flat.notes[ix_p-2],s))
        #    cadenceSequence.append(pitchToScaleDegree(s.flat.notes[ix_p-1],s))
        #cadenceSequence.append(pitchToScaleDegree(p,s))
    return cadenceSequence

def LD(s,t):
    s = ' ' + s
    t = ' ' + t
    d = {}
    S = len(s)
    T = len(t)
    for i in range(S):
        d[i, 0] = i
    for j in range (T):
        d[0, j] = j
    for j in range(1,T):
        for i in range(1,S):
            if s[i] == t[j]:
                d[i, j] = d[i-1, j-1]
            else:
                d[i, j] = min(d[i-1, j] + 1, d[i, j-1] + 1, d[i-1, j-1] + 1)
    return d[S-1, T-1]

def NW(s,t):
    s = ' ' + s
    t = ' ' + t
    d = {}
    S = len(s)
    T = len(t)
    for i in range(S):
        d[i, 0] = -i
    for j in range (T):
        d[0, j] = -j
    for j in range(1,T):
        for i in range(1,S):
            score = -1
            if s[i] == t[j]:
                score = 1
            d[i, j] = max(d[i-1, j] - 1, d[i, j-1] - 1, d[i-1, j-1] + score)
    return d[S-1, T-1]

def createCadenceSequenceDataset(flist):
    dataset = []
    for song in readCorpus(flist):
        c = getCadenceSequence(song)
        cads = ''
        for d in c:
            cads = cads + str(d)
        dataset.append( ( song.filePath.split('/')[-1].split('.')[0], cads ) )
    return dataset 

#ids as produced by maketrigramdataset
#ixs contains indices of detected cadences in ids/data/labels/etc
#def createDetectedCadenceSequenceDataset(ixs,ids):

def ids2CadenceSequenceDataset(cadence_hat_ixs, ids, data):
    dataset = []
    tr_hat = []
    for i in cadence_hat_ixs:
        tr_hat.append( (ids[i][0], ids[i][1][2], data[i][3], data[i][4], data[i][5] ) )
    #collect nlbids
    nlbids = []
    for i in cadence_hat_ixs:
        nlbids.append(ids[i][0])
    nlbids = set(nlbids)
    for nlbid in nlbids:
        cads = []
        for tr in tr_hat:
            if tr[0] == nlbid:
                cads.append(tr)
        cads = sorted(cads, key=lambda x: x[1])
        cadseq = ''
        for c in cads:
            cadseq = cadseq + str(int(c[2])) + str(int(c[3])) + str(int(c[4]))
            #cadseq = cadseq + str(int(c[4]))
        dataset.append( (nlbid,cadseq) )
    return dataset

def writeLDDistmat(filename, dataset):
    f = open( filename, 'w' )
    f.write("rc")
    for d in dataset:
        f.write("\t"+d[0])
    f.write("\n")
    for d1 in dataset:
        f.write(d1[0])
        for d2 in dataset:
            f.write("\t")
            f.write(str(LD(d1[1],d2[1])))
            #print d1[0], d2[0], d1[1], d2[1], LD(d1[1],d2[1])
        f.write("\n")
    f.close()

def writeNWDistmat(filename, dataset):
    f = open( filename, 'w' )
    f.write("rc")
    for d in dataset:
        f.write("\t"+d[0])
    f.write("\n")
    for d1 in dataset:
        f.write(d1[0])
        for d2 in dataset:
            f.write("\t")
            dist = float(NW(d1[1],d2[1]))
            normalizeddist = dist / float(min( len(d1[1]),len(d2[1]) ) )
            f.write(str(1.0 - normalizeddist))
            #print d1[0], d2[0], d1[1], d2[1], LD(d1[1],d2[1])
        f.write("\n")
    f.close()

def getTuneFamily(NLBid):
    """
    This function takes a NLBid of the pattern to be matched (string - 'NLBxxxxxx_yy'),
    and returns the name of the tune family

    Example: getTuneFamily('NLB073862_01')
    --> 'Er_woonde_een_vrouwtje_al_over_het_bos'
    """
    file = "/Users/pvk/Documents/data/WITCHCRAFT_AnnotatedMelodies/CONTENTS_melodygroup.txt"
    tf = ""
    with open(file) as f:
        doc = csv.reader(f, delimiter="\t")
        for line in doc :
            if line[0] == NLBid :
                tf = line[2]
    return tf

def createNWDistmat(dataset):
    distmat = np.zeros((len(dataset),len(dataset)),dtype=float)
    for ix1,d1 in enumerate(dataset):
        print ix1, " of ", len(dataset)
        for ix2,d2 in enumerate(dataset):
            distmat[ix1,ix2] = 1.0 - (float(NW(d1[1],d2[1])) / float(min( len(d1[1]),len(d2[1]) ) ) )
    d_ids = []
    d_labels = {}
    for d in dataset:
        d_ids.append(d[0])
    for d in dataset:
        d_labels[d[0]] = getTuneFamily(d[0])
    return distmat, d_ids, d_labels

def createLDDistmat(dataset):
    distmat = np.zeros((len(dataset),len(dataset)),dtype=int)
    for ix1,d1 in enumerate(dataset):
        print ix1, " of ", len(dataset)
        for ix2,d2 in enumerate(dataset):
            distmat[ix1,ix2] = LD(d1[1],d2[1])
    d_ids = []
    d_labels = {}
    for d in dataset:
        d_ids.append(d[0])
    for d in dataset:
        d_labels[d[0]] = getTuneFamily(d[0])
    return distmat, d_ids, d_labels

def writeDistmat(fn,distmat,d_ids):
    f = open( fn, 'w' )
    f.write("rc")
    for d in d_ids:
        f.write("\t"+d)
    f.write("\n")
    for ix,d1 in enumerate(distmat):
        f.write(d_ids[ix])
        for d2 in d1:
            f.write("\t")
            f.write(str(d2))
        f.write("\n")
    f.close()

def evaluateDistMat1nn(distmat,d_ids,d_labels):
    hits = 0
    for ixq, q in enumerate(d_ids):
        nrRel = 0
        nrNotRel = 0
        mindist = float('inf')
        for ixdoc, doc in enumerate(d_ids):
            if ixq == ixdoc:
                continue #do not count query
            if distmat[ixq,ixdoc] < mindist:
                mindist = distmat[ixq,ixdoc]
                if d_labels[d_ids[ixq]] == d_labels[d_ids[ixdoc]]:
                    nrRel = 1
                    nrNotRel = 0
                else:
                    nrRel = 0
                    nrNotRel = 1
            elif distmat[ixq,ixdoc] == mindist:
                if d_labels[d_ids[ixq]] == d_labels[d_ids[ixdoc]]:
                    nrRel += 1
                else:
                    nrNotRel += 1
        #print ixq, mindist, nrRel, nrNotRel
        if nrRel > nrNotRel:
            hits += 1
    #print hits, len(d_ids)
    return float(hits) / float (len(d_ids))


def evaluateDistMatknn(distmat,d_ids,d_labels,k):
    hits = 0
    for ixq, q in enumerate(d_ids):
        nrRel = 0
        nrNotRel = 0
        mindist = float('inf')
        #first pass: determine distance of kth neighbour
        zerodistances = list(distmat[ixq,:]).count(0)
        if zerodistances > 1:
            mindist = sorted(set(distmat[ixq,:]))[k-1]
        else:
            mindist = sorted(set(distmat[ixq,:]))[k]
        for ixdoc, doc in enumerate(d_ids):
            if ixq == ixdoc:
                continue #do not count query
            if distmat[ixq,ixdoc] <= mindist:
                if d_labels[d_ids[ixq]] == d_labels[d_ids[ixdoc]]:
                    nrRel += 1
                else:
                    nrNotRel += 1
        #print ixq, mindist, nrRel, nrNotRel
        if nrRel > nrNotRel:
            hits += 1
    print hits, len(d_ids)
    return float(hits) / float (len(d_ids))

def showCadencePatternsForTF(cadseq_dataset, tunefamily):
    for c in cadseq_dataset:
        if getTuneFamily(c[0]) == tunefamily:
            print c

def retrieveCadencePattern(cadseq_dataset, pattern):
    for c in cadseq_dataset:
        if c[1] == pattern:
            print c
