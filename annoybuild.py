#!/usr/bin/env python

import mmap

from annoy import AnnoyIndex


def buildAnnoyIndex(glove_dim, glove_dset_location, annoy_index_location):
    gloveDataSetFile = open(glove_dset_location, "r")
    mmGloveData = mmap.mmap(gloveDataSetFile.fileno(), 0, prot=mmap.PROT_READ)
    annoyIndex = AnnoyIndex(glove_dim)
    index = 0
    print "Building index"
    for line in iter(mmGloveData.readline, ""):
        annoyIndex.add_item(index, map(float, line.split(" ")[1:]))
        index += 1
        if index % 1000000 == 0:
            print index
    annoyIndex.build(10)
    annoyIndex.save(annoy_index_location)
    print "Index built"
