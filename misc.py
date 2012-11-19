import os
import gzip
import urllib
import re
from functools import lru_cache

import enchant
import pytils

languages = ['en_US', 'de_DE', 'fr_FR', 'ru_RU']  # FIXME: add spanish
dictionaries = [enchant.Dict(lang) for lang in languages]


@lru_cache()
def strip_unprintable(data):
    return ''.join([i for i in data if ord(i) > 31])


def measure_spelling(words):
    _words = re.sub('[][._/(:;\)-]', ' ', words).split()
    if _words:
        spelling = 0.0
        for word in _words:
            if not word.isdigit() and len(word) > 1:
                if any(d.check(word) for d in dictionaries):
                    spelling += 1
        return spelling / len(_words)
    else:
        return 1.0


def get_translit(words):
    return ' '.join(pytils.translit.detranslify(i) for i in re.sub('[._/-]', ' ', words).split())


def improve_encoding(request):
    result = request
    spelling = measure_spelling(request)

    if not is_all_ascii(request):
        attepmts = [('cp1252', 'cp1251'), ('cp1251', 'cp1252')]
        for dst, src in attepmts:
            try:
                suggest = request.encode(dst).decode(src)
                quality = measure_spelling(suggest)
                if quality > spelling:
                    result = suggest
            except:
                continue
    return result


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
                if (j > len(substr) and
                    all(data[0][i:i + j] in x for x in data)):
                    substr = data[0][i:i + j]
    return substr


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


def urldecode(str):
    return urllib.parse.unquote(str.replace('\\x', '%'))


def log_response(response):
    return 'Status ' + str(response.status) + ' ' + response.reason


def ok_code(response, message):
    if response.status not in [200]:
        raise Exception(message + (' - error %d' % response.status))


def make_request(connection, error_message, *args, **kwargs):
    connection.request(*args, **kwargs)
    response = connection.getresponse()
    ok_code(response, error_message)
    return response


def ungzip(data):
    return gzip.GzipFile(fileobj=data).read()


@lru_cache()
def normalcase(data):
    return re.sub(' +', ' ', re.sub('[][._/(:;\)-]', ' ', data.upper()))
