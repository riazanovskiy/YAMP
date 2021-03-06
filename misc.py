import json
import os
import gzip
import urllib
import urllib.parse
import re
from functools import lru_cache
import unicodedata
from log import logger

import enchant
import pytils

languages = ['en_US', 'de_DE', 'fr_FR', 'ru_RU']  # FIXME: add Spanish
dictionaries = [enchant.Dict(lang) for lang in languages]
digrams, trigrams = None, None


@lru_cache()
def strip_unprintable(data):
    return ''.join([i for i in data if ord(i) > 31]) if data else ''


def strip_brackets(data):
    return re.sub('\[.+\]', '', re.sub('\(.+\)', '', data))


def measure_spelling(words):
    words = re.split('\W+', words)
    if words:
        spelling = 0.0
        for word in words:
            if not word.isdigit() and len(word) > 1:
                if any(d.check(word) for d in dictionaries):
                    spelling += 1
        return spelling / len(words)
    else:
        return 1.0


def get_translit(words):
    return ' '.join(pytils.translit.detranslify(i) for i in re.sub('[._/-]', ' ', words).split())


def get_recoded(request):
    yield request
    for dst, src in [('cp1252', 'cp1251'), ('cp1251', 'cp1252')]:
        try:
            yield request.encode(dst).decode(src)
        except:
            continue


def load_ngrams_dictionary():
    if not (os.path.isfile('digrams.json') and os.path.isfile('digrams.json')):
        logger.info('Generating ngrams dictionary')
        import ngram_generator
        logger.info('Dictionary created')
    global digrams, trigrams
    with open('digrams.json') as file:
        digrams = json.load(file)
        # with open('trigrams.json') as file:
        #     trigrams = json.load(file)


def measure_spelling_ngrams(word):
    if not digrams:
        load_ngrams_dictionary()
    word = '\0' + word + '\0'
    return sum(digrams.get(word[i:i + 2], 0) for i in range(len(word) - 1)) / digrams['total'] / len(word)


@lru_cache()
def improve_encoding(request):
    if not is_all_ascii(request):
        return max(get_recoded(request), key=lambda word: max(measure_spelling(word),
                                                              measure_spelling_ngrams(word)))
    return request

def levenshtein(s1, s2):
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            current_row.append(min(previous_row[j + 1] + 1, current_row[j] + 1,
                                   previous_row[j] + (c1 != c2)))
        previous_row = current_row
    return previous_row[-1]


def longest_common_substring(data):
    substr = ''
    if len(data) > 1 and len(data[0]) > 0:
        for i in range(len(data[0])):
            for j in range(len(data[0]) - i + 1):
                if j > len(substr) and all(data[0][i:i + j] in x for x in data):
                    substr = data[0][i:i + j]
    return substr


@lru_cache()
def diff(a, b):
    a = normalcase(a)
    b = normalcase(b)
    if min(len(a), len(b)) > 0:
        return levenshtein(a, b) / min(len(a), len(b))
    else:
        return 1.0


def filesize(file):
    return os.stat(file).st_size


def valid_filename(filename):
    invalid = frozenset('*”"/\[]:;|=,')
    return ''.join('-' if i in invalid else i for i in filename)


def verify_dir(name):
    if not os.path.isdir(name):
        os.makedirs(name)


def is_all_ascii(data):
    try:
        data.encode('ascii')
    except UnicodeEncodeError:
        return False
    else:
        return True


def urldecode(string):
    return urllib.parse.unquote(string.replace('\\x', '%'))


def log_response(response):
    return 'Status ' + str(response.status) + ' ' + response.reason


def ok_code(response, message):
    if response.status not in [200]:
        raise Exception(message + (' - error {}'.format(response.status)))


def make_request(connection, error_message, *args, **kwargs):
    connection.request(*args, **kwargs)
    response = connection.getresponse()
    ok_code(response, error_message)
    return response


def ungzip(data):
    return gzip.GzipFile(fileobj=data).read()


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


@lru_cache()
def normalcase(data):
    return re.sub(' +', ' ',
                  strip_accents(data.upper().translate(str.maketrans('[][._/(:;\)-]"\'', '               '))))
