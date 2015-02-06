import glob

from collections import defaultdict
from functools import partial
from itertools import combinations

import numpy as np
from statsmodels.stats.inter_rater import cohens_kappa
from sklearn.metrics import confusion_matrix


def pk(ref, hyp, k=None, boundary=1):
    """
    Compute the Pk metric for a pair of segmentations A segmentation
    is any sequence over a vocabulary of two items (e.g. "0", "1"),
    where the specified boundary value is used to mark the edge of a
    segmentation.

    >>> '%.2f' % pk([0, 1, 0, 0] * 100, [1] * 400, 2)
    '0.50'
    >>> '%.2f' % pk([0, 1, 0, 0] * 100, [0] * 400, 2)
    '0.50'
    >>> '%.2f' % pk([0, 1, 0, 0] * 100, [0, 1, 0, 0] * 100, 2)
    '0.00'

    """
    ref, hyp = ref.tolist(), hyp.tolist()
    if k is None:
        k = int(round(len(ref) / (ref.count(boundary) * 2.)))

    err = 0
    for i in xrange(len(ref)-k +1):
        r = ref[i:i+k].count(boundary) > 0
        h = hyp[i:i+k].count(boundary) > 0
        if r != h:
           err += 1
    return err / (len(ref)-k +1.)

def windowdiff(seg1, seg2, k, boundary=1, weighted=False):
    """
    Compute the windowdiff score for a pair of segmentations.  A
    segmentation is any sequence over a vocabulary of two items
    (e.g. "0", "1"), where the specified boundary value is used to
    mark the edge of a segmentation.

        >>> s1 = [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0]
        >>> s2 = [0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0]
        >>> s3 = [1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]
        >>> '%.2f' % windowdiff(s1, s1, 3)
        '0.00'
        >>> '%.2f' % windowdiff(s1, s2, 3)
        '0.30'
        >>> '%.2f' % windowdiff(s2, s3, 3)
        '0.80'

    """
    k = 1 if len(seg1) == 1 else k
    seg1, seg2 = seg1.tolist(), seg2.tolist()
    if len(seg1) != len(seg2):
        raise ValueError("Segmentations have unequal length")
    if k > len(seg1):
        print seg1
        print seg2
        print k
        raise ValueError("Window width k should be smaller or equal than segmentation lengths")
    wd = 0
    for i in range(len(seg1) - k + 1):
        ndiff = abs(seg1[i:i+k].count(boundary) - seg2[i:i+k].count(boundary))
        if weighted:
            wd += ndiff
        else:
            wd += min(1, ndiff)
    return wd / (len(seg1) - k + 1.)

def pairwise_evaluation(fn, *annotations):
    max_val = max(v for annotation in annotations for v in annotation)
    bin_annotations = np.zeros((len(annotations), max_val+1))
    scores = []
    for i, annotation in enumerate(annotations):
        bin_annotations[i, annotation] = 1.0
    for a, b in combinations(bin_annotations, 2):
        scores.append(fn(a, b))
    return sum(scores) / len(scores)

def pairwise_kappa(annotations):
    def _cohen(a, b):
        if a.shape[0] == 1 and b.shape[0] == 1:
            return 1
        return cohens_kappa(confusion_matrix(a, b)).kappa
    return pairwise_evaluation(_cohen, *annotations)

def pairwise_pk(annotations):
    return pairwise_evaluation(pk, *annotations)

def pairwise_windowdiff(annotations, k=3):
    return pairwise_evaluation(partial(windowdiff, k=k), *annotations)

if __name__ == '__main__':
    annotations = defaultdict(lambda: defaultdict(list))
    for a_file in glob.glob("annotations/*.txt"):
        annotator = a_file.split("/")[-1].replace(".txt", "")
        for line in open(a_file):
            idnumber, cadences = line.strip().split("\t", 1)
            annotations[idnumber][annotator] = map(int, cadences.split("\t"))

    k_scores, pk_scores, wd_scores = [], [], []
    for idnumber, cadences in annotations.items():
        k_scores.append(pairwise_kappa(cadences.values()))
        pk_scores.append(pairwise_pk(cadences.values()))
        wd_scores.append(pairwise_windowdiff(cadences.values()))
        print idnumber, "%.4f" % k_scores[-1], "%.4f" % pk_scores[-1], "%.4f" % wd_scores[-1]
        #print "    K=%.4f" % k_scores[-1]
        #print "    Pk=%.4f" % pk_scores[-1]
        #print "    WD:%.4f" % wd_scores[-1]

    print "GLOBAL PAIRWISE KAPPA:", np.array(k_scores).mean()
    print "GLOBAL PAIRWISE Pk:   ", np.array(pk_scores).mean()
    print "GLOBAL PAIRWISE WD:   ", np.array(wd_scores).mean()