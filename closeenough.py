#!/usr/bin/env python
import sys
import os
import urllib
from flask import Flask, request, jsonify

from annoybuild import buildAnnoyIndex
from annoylookup import WordStore

app = Flask(__name__)
args = sys.argv
# default locations
gloveDataSetFileLocation = "data" + os.sep + "glove.6B.50d.txt"
gloveDimension = 50
annoyFileLocation = "data" + os.sep + "glove.6B.50d.ann"
flaskport = 9000
gloveUrl = "https://yasiru.me/glove.6B.50d.txt"

def printUsage():
    print "Invalid args. Usage:"
    print args[0] + " [glove dimension] [glove data set txt file] [annoy index location]"
    print "eg: " + args[0] + " 50 glove.6B.txt glove.6B.ann"
    print "Alternatively run with '--init' argument to download glove data set, build indexes and proceed"


def findGloveDim(glovefile):
    f = open(glovefile)
    return len(f.readline().split(" ")) - 1


def init():
    global gloveDimension
    gloveOpenner = urllib.URLopener()
    print "Downloading glove file from " + gloveUrl
    gloveOpenner.retrieve(gloveUrl, gloveDataSetFileLocation)
    print "File downloaded to " + gloveDataSetFileLocation
    gloveDimension = findGloveDim(gloveDataSetFileLocation)
    print "Glove dimension " + gloveDimension
    buildAnnoyIndex(gloveDimension, gloveDataSetFileLocation, annoyFileLocation)


if len(args) == 5:
    gloveDataSetFileLocation = str(args[2])
    annoyFileLocation = str(args[3])
    if not os.path.exists(gloveDataSetFileLocation):
        print "glove data file not found"
        printUsage()
        sys.exit(2)
    if not os.path.exists(annoyFileLocation):
        print "Annoy index file not found"
        printUsage()
        sys.exit(3)
    try:
        flaskport = int(args[4])
        if flaskport < 1:
            raise ValueError
    except ValueError:
        print "Server port should be a positive integer"
        printUsage()
        sys.exit(4)
else:
    if len(args) == 2 and args[1] == "--init":
        init()
    else:
        printUsage()
        sys.exit(1)

ws = WordStore(gloveDimension, gloveDataSetFileLocation, annoyFileLocation)


@app.route("/search", methods=["GET"])
def hello():
    phrase = request.args.get('phrase')
    phrase = phrase.strip()
    result = []
    autocorrect = []
    try:
        if len(phrase.split(" ")) > 1:
            result, autocorrect = ws.getSynonyms(phrase)
        else:
            result, autocorrect = ws.getSynonymsForSingleWord(phrase)

        return jsonify({"status": "Success", "results": result, "autocorrect": autocorrect})
    except:
        print "Unexpected error:"
        return jsonify({"status": "Error"})
    return "done"


app.run(host="0.0.0.0", port=flaskport)
