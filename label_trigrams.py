from collections import Counter, defaultdict

def ngrams(iterable, n):
    count = max(0, len(iterable) - n + 1)
    return (tuple(iterable[i:i+n]) for i in xrange(count))

def trigrams(iterable):
    return ngrams(iterable, 3)

def predict(*predictions):
    return Counter(predictions).most_common(n=1)[0][0]

def predict_proba(*predictions):
    preds = defaultdict(float)
    for (pred, probability) in predictions:
        preds[pred] += probability
    return max(preds, key=preds.__getitem__)

def expand(sequence):
    first, last = sequence[0], sequence[-1]
    new_first = (0,) + first[:2]
    new_last = last[1:] + (0, )
    return [new_first] + sequence + [new_last]

def expand_proba(sequence):
    (first, _), (last, _) = sequence[0], sequence[-1]
    new_first = (0,) + first[:2], 1.0
    new_last = last[1:] + (0,), 1.0
    return [new_first] + sequence + [new_last]

def iter_predictions(predictions):
    for (_, _, right), (_, middle, _), (left, _, _), in trigrams(expand(predictions)):
        yield right, middle, left

def iter_prob_predictions(predictions):
    for ((_, _, r), rp), ((_, m, _), mp), ((l, _, _), lp), in trigrams(
            expand_proba(predictions)):
        yield (r, rp), (m, mp), (l, lp)

def test():
    # 1) when all three votes are unanimous, their
    #    common vote is returned:
    assert predict(1, 1, 1) == 1
    # 2) when two out of three votes are for the same
    #    class label, this class label is returned:
    assert predict(1, 0, 1) == 1
    assert predict(0, 0, 1) == 0

    predictions = [(0, 0, 1), (0, 0, 1), (0, 1, 0), (1, 0, 0), (1, 0, 0)]
    for tr in trigrams(expand(predictions)):
        print tr
    #predictions = expand(predictions)
    #print predictions
    for right, middle, left in iter_predictions(predictions):
        print predict(right, middle, left)

    predictions = [((0, 0, 1), 0.5), ((0, 0, 1), 0.2), ((0, 1, 0), 0.7),
                   ((1, 0, 0), 0.1), ((1, 0, 0), 0.3)]

    for tr in trigrams(expand_proba(predictions)):
        print tr

    for right, middle, left in iter_prob_predictions(predictions):
        print predict_proba(right, middle, left)

    assert predict_proba((0, 0.1), (1, 0.7), (0, 0.3)) == 1
    assert predict_proba((0, 0.3), (1, 0.7), (0, 0.6)) == 0
    assert predict_proba((1, 0.1), (1, 0.1), (0, 0.7)) == 0
    print 'all tests passed'

if __name__ == '__main__':
    test()
