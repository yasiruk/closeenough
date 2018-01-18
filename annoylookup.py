import itertools
import jellyfish
import time
from annoy import AnnoyIndex
import numpy as np
import mmap
import re
from nltk.corpus import wordnet as wn

# borrowed this and modified a bit from here : https://www.kaggle.com/cpmpml/spell-checker-using-word2vec
class SpellCorrector:
    def __init__(self, wordvector_index):
        self.wordvector_index = wordvector_index

    def words(self, text):
        return re.findall(r'\w+', text.lower())

    def P(self, word):
        "Probability of `word`."
        # use inverse of rank as proxy
        # returns 0 if the word isn't in the dictionary
        return - self.wordvector_index.get(word, 0)

    def correction(self, word):
        "Most probable spelling correction for word."
        return max(self.candidates(word), key=self.P)

    def candidates(self, word):
        "Generate possible spelling corrections for word."
        return self.known([word]) or self.known(self.edits1(word)) or self.known(self.edits2(word)) or set([word])

    def known(self, words):
        "The subset of `words` that appear in the dictionary of WORDS."
        return set(w for w in words if w in self.wordvector_index)

    def edits1(self, word):
        "All edits that are one edit away from `word`."
        letters = 'abcdefghijklmnopqrstuvwxyz'
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        inserts = [L + c + R for L, R in splits for c in letters]
        return set(deletes + transposes + replaces + inserts)

    def edits2(self, word):
        "All edits that are two edits away from `word`."
        return (e2 for e1 in self.edits1(word) for e2 in self.edits1(e1))


class WordStore:
    def __init__(self, glove_dimension, glove_data_set_file_location, annoy_index_file_location):
        self.gloveDimension = glove_dimension
        self.gloveDataSetFile = open(glove_data_set_file_location, "r")
        self.mmGloveData = mmap.mmap(self.gloveDataSetFile.fileno(), 0, prot=mmap.PROT_READ)
        self.annoyWordLookup = []
        self.wordNetLookup = {}
        self.wordToAnnIndexLookup = {}
        self.wordtoWordNetLookup = {}
        self.phoneticLookup = {}
        self.annoyIndex = AnnoyIndex(50)
        print "Loading annoy index"
        self.annoyIndex.load(annoy_index_file_location)  # "glove.6B.50d.ann"

        for line in iter(self.mmGloveData.readline, ""):
            word = line.split(" ")[0]
            self.wordToAnnIndexLookup[word] = len(self.annoyWordLookup)
            self.annoyWordLookup.append(word)
            self.phoneticLookup.setdefault(jellyfish.metaphone(word.decode("utf-8")), []).append(word)



        print "Loading WordNet index"
        wncount = 0
        for lemmas in wn.words():
            for word in lemmas.split("_"):
                self.wordNetLookup.setdefault(word, []).append(lemmas)
                self.wordtoWordNetLookup[word] = wncount
                wncount = wncount + 1

        self.spellCorrector = SpellCorrector(self.wordtoWordNetLookup)

    def fix(self, word):
        candidateset = self.spellCorrector.candidates(word)
        # if jellyfish.metaphone(word.decode("utf-8")) in self.phoneticLookup:
        #     candidateset.update(self.phoneticLookup[jellyfish.metaphone(word.decode("utf-8"))])

        return candidateset

    def rankOfWord(self, word):
        if word in self.wordToAnnIndexLookup:
            return self.wordToAnnIndexLookup[word]
        else:
            return 6000000000

    def getSynonymsForSingleWord(self, word

                                 ):
        correctedTokens = self.fix(self.preprocess(word))
        correctedTokens.add(word)
        temp = set()
        for correctedtk in correctedTokens:
            if correctedtk in self.wordToAnnIndexLookup or correctedtk == word:
                temp.add(correctedtk)

        correctedTokens = temp
        # rank
        sortedTokens = sorted(correctedTokens, key=self.rankOfWord)
        autocorrect = sortedTokens[:5]  # top 5
        if word in autocorrect:
            autocorrect.remove(word)

        synSet, hypSet = self.getWordNetSyns(word)

        if word in self.wordToAnnIndexLookup:
            searchvector = self.annoyIndex.get_item_vector(self.wordToAnnIndexLookup[word])
            gloveHypns = map(self.getword,
                             self.annoyIndex.get_nns_by_vector(searchvector, 10, include_distances=False))
            for gh in gloveHypns:
                hypSet.add(gh)
        selectedwords = list(synSet)
        if len(selectedwords) > 10:
            selectedwords = selectedwords[:10]
        else:
            selectedwords = selectedwords + list(hypSet)

        return selectedwords, autocorrect

    def getSynonyms(self, inputPhrase):
        tokens = inputPhrase.strip().split(" ")
        correctedTokens = list(map(self.preprocess, tokens))
        correctedTokens = list(map(self.fix, correctedTokens))

        for idx, token in enumerate(correctedTokens):
            token.add(tokens[idx])

        if len(tokens) == 1:
            possibleCombinationsOfTokens = correctedTokens
        else:
            possibleCombinationsOfTokens = list(itertools.product(*correctedTokens))

        zscores = (list(map(self.calculatePhraseTogetherness, possibleCombinationsOfTokens)))

        phrases = []
        for idx, pp in enumerate(possibleCombinationsOfTokens):
            phrases.append(Phrase(" ".join(pp), zscores[idx]))

        for p in phrases:
            if p.content == inputPhrase:
                break
        sortedphrases = list(sorted(phrases, key=lambda phrase: phrase.zscore, reverse=True))

        rank = 0
        for pp in sortedphrases:
            if pp.content == inputPhrase:
                break
            rank = rank + 1

        autocorrect = []
        if rank >= 5:
            for i in range(rank):
                autocorrect.append(sortedphrases[i].content)

        return self.getSynonymsForPhrase(inputPhrase), autocorrect

    def getSynonymsForPhrase(self, phrase):

        synSet, hypSet = self.getWordNetSyns(phrase)

        if phrase in self.wordToAnnIndexLookup:
            searchvector = self.annoyIndex.get_item_vector(self.wordToAnnIndexLookup[phrase])
            gloveHypns = map(self.getword,
                             self.annoyIndex.get_nns_by_vector(searchvector, 10, include_distances=False))
            for gh in gloveHypns:
                hypSet.add(gh)
        else:
            tokens = phrase.split(" ")
            searchvector = np.zeros(self.gloveDimension)
            for token in tokens:
                if token in self.wordToAnnIndexLookup:
                    searchvector = searchvector + self.annoyIndex.get_item_vector(self.wordToAnnIndexLookup[token])

            gloveHypns = map(self.getword,
                                 self.annoyIndex.get_nns_by_vector(searchvector, 10, include_distances=False))
            for gh in gloveHypns:
                hypSet.add(gh)

        selectedwords = list(synSet)
        if len(selectedwords) > 10:
            selectedwords = selectedwords[:10]
        else:
            selectedwords = selectedwords + list(hypSet)

        return selectedwords

    def getSimilarPhrases(self, phrase):
        tokens = phrase.split(" ")
        similar_word_count = ((-2) * len(tokens)) + 9  # y = -2m + 9

        if similar_word_count < 3:
            similar_word_count = 3

        result = [self.getSimilarWords(word, similar_word_count) for word in tokens]

        for idx, val in enumerate(result):
            result[idx].append(tokens[idx])
        return result

    def calculatePhraseTogetherness(self, phrase):
        pairs = list(itertools.combinations(phrase, 2))
        distance = 0.0
        if len(pairs) < 1:
            # single word search, then use the word popularity for ranking
            if pairs[0] in self.wordToAnnIndexLookup:
                return 1.0 / (1 + self.wordToAnnIndexLookup[pairs[0]])
            else:
                return 0  # umm?
        for pair in pairs:

            if pair[0] in self.wordToAnnIndexLookup and pair[1] in self.wordToAnnIndexLookup:
                distance = distance + (1.0 / self.annoyIndex.get_distance(self.wordToAnnIndexLookup[pair[0]],
                                                                          self.wordToAnnIndexLookup[pair[1]]))
                # else: # umm, :?
        if len(pairs) > 0:
            return distance
        else:
            return 0

    def preprocess(self, word):
        word = word.replace("1", "one")
        word = word.replace("2", "two")
        word = word.replace("3", "three")
        word = word.replace("4", "four")
        word = word.replace("5", "five")
        word = word.replace("6", "six")
        word = word.replace("7", "seven")
        word = word.replace("8", "eight")
        word = word.replace("9", "nine")
        return word

    def getSimilarWords(self, word, count):

        synSet, hypSet = self.getWordNetSyns(word)

        if len(synSet) == 0:  # weird word
            print ("Correcting word " + word)
            word = self.preprocess(word)
            word = self.spellCorrector.correction(word)
            print "...to " + word
            synSet, hypSet = self.getWordNetSyns(word)

        if word in self.wordToAnnIndexLookup:
            searchvector = self.annoyIndex.get_item_vector(self.wordToAnnIndexLookup[word])
            gloveHypns = map(self.getword,
                             self.annoyIndex.get_nns_by_vector(searchvector, count, include_distances=False))
            for gh in gloveHypns:
                hypSet.add(gh)
        selectedwords = list(synSet)
        if len(selectedwords) > count:
            selectedwords = selectedwords[:count]
        else:
            selectedwords = selectedwords + list(hypSet)

        return selectedwords

    def getWordNetSyns(self, phrase):
        synSet = set()
        hypSet = set()
        word = phrase.replace(" ", "_")
        for syn in wn.synsets(word):
            for sword in syn.lemma_names():
                synSet.add(self.processWnWord(sword))
            for hword in syn.hyponyms():
                for lhw in hword.lemma_names():
                    hypSet.add(self.processWnWord(lhw))

        return synSet, hypSet.difference(synSet)

    def processWnWord(self, word):
        return word.replace("_", " ").encode("utf-8")

    def getword(self, index):
        return self.annoyWordLookup[index]


class Phrase:
    def __init__(self, content, zscore):
        self.content = content
        self.zscore = zscore

    def __repr__(self):
        return self.content + "(" + str(self.zscore) + ")"


# wordStore = WordStore(50, "../glove.6B.50d.txt", "glove.6B.50d.ann")

# while True:
#     qPhrase = raw_input("Word : ")
#     if qPhrase == "q":
#         break
#     start = time.time()
#     if len(qPhrase.strip().split(" ")) == 1:
#         result, autocorrect = wordStore.getSynonymsForSingleWord(qPhrase)
#         if len(autocorrect) > 0:
#             print "Did you mean :" + ", ".join(autocorrect)
#         print result, autocorrect
#     else:
#         result, autocorrect = wordStore.getSynonyms(qPhrase)
#         if len(autocorrect) > 0:
#             print "Did you mean :" + ", ".join(autocorrect)
#         print result, autocorrect
#     end = time.time()
#     print (end - start)
