from music21 import *

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

def annotate_melody(melody, noRepeats=False):
    """
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

    2-2-2015: add note index of third note to features
    2-2-2015: add attribute which states whether lyric word continues on next note
    n.noteindex (int) : index of the note in the melody
    n.endofword (bool) : true if a word ends here. WHAT ABOUT MELISMA?
    n.startix (int) : index of first note of connected notes n belongs to
    n.endix (int) : index of last note of connected notes n belongs to
    """

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

    #add note indices
    for ix, n in enumerate(mel):
        n.noteindex = ix

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

    #find word boundaries
    #find all ixs 1 before start of word - thus the last of note of melisma gets 'endofword'
    #use (startix,endix) pairs, resolves ties and repeated pitches
    #first pass: indicate beginnings of words:
    for n in mel:
        if n.lyrics:
            if n.lyrics[0].syllabic == 'single' or n.lyrics[0].syllabic == 'begin':
                n.startword = True
            else:
                n.startword = False
        else:
            n.startword = False
    #second pass: mark all ixs 1 before start of word by examining all 2-grams of (startix,stopix) pairs
    for n in mel:
        n.endofword = False
    count = max(0, len(pitch_ixs) - 2 + 1)
    for t_ixs in (tuple(pitch_ixs[i:i+2]) for i in xrange(count)):
        if mel[t_ixs[1][0]].startword:
            mel[t_ixs[0][0]].endofword = True
    #finally annotate very last endofword
    mel[pitch_ixs[-1][0]].endofword = True

    #add startixs and endixs as attributes to the notes
    for startix, endix in pitch_ixs:
        for n in range(startix, endix+1):
            mel[n].startix = startix
            mel[n].endix = endix

    return pitch_ixs