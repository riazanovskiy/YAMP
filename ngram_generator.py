from collections import Counter, defaultdict
import json
from urllib.request import urlopen


def make_ngrams(sources):
    digrams = defaultdict(int)
    trigrams = defaultdict(int)
    for source in sources:
        with urlopen(source) as file:
            for line in file:
                word = '\0' + line.decode('utf-8')[:-1] + '\0'
                for i in range(len(word) - 1):
                    digrams[word[i:i + 2]] += 1
                # for i in range(len(word) - 2):
                #     trigrams[word[i:i + 3]] += 1

    digrams['total'] = sum(digrams.values())
    trigrams['total'] = sum(trigrams.values())
    with open('digrams.json', 'w') as file:
        file.write(json.dumps(dict(digrams)))
    # with open('trigrams.json', 'w') as file:
    #     file.write(json.dumps(dict(trigrams)))


make_ngrams(['https://raw.githubusercontent.com/dwyl/english-words/master/words.txt',
             'https://gist.githubusercontent.com/riazanovskiy/86d3204cd55d1f8f621452dc3028d80b/raw/62b31f43c8f68d4c4edd4dfab207cf31522bfd4e/russian_words.txt'])
