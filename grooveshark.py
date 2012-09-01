# -*- coding: utf-8 -*-
print('Started ' + __name__)
import http
import http.client
import urllib.parse
import urllib.request
import gzip
import sys
import json
import string
import random
import io
import hashlib
import uuid
from log import logger

SALT_HTMLSHARK = 'reallyHotSauce'
SALT_JSQUEUE = 'circlesAndSquares'
_useragent = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'  # 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1161.0 Safari/537.1'
_referer = 'http://grooveshark.com/JSQueue.swf?20120521.01'
_clientRevision = '20120312'
_token = ''
_cookie = ''


def utf2cp1251(str):
    try:
        return str.encode('utf-8').decode('cp1251')
    except Exception:
        return str


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


def _make_grooveshark_token(method, secret):
    rnd = (''.join(random.choice(string.hexdigits) for x in range(6))).lower()
    return rnd + hashlib.sha1((method + ':' + _token + ':' + secret + ':' + rnd).encode('utf-8')).hexdigest()

_header = {}
_header['country'] = {}
_header['country']['CC1'] = '0'
_header['country']['CC2'] = '0'
_header['country']['CC3'] = '0'
_header['country']['CC4'] = '0'
_header['country']['ID'] = '1'
_header['privacy'] = 0
_header['session'] = None
_header['uuid'] = str(uuid.uuid4()).upper()


def _make_grooveshark_query(method, **kwargs):
    global _header
    if not _cookie:
        raise Exception('You should get cookie first.')

    _header['session'] = _cookie[10:]

    query = {}
    query['parameters'] = {}
    query['header'] = _header
    query['method'] = method
    query['header']['clientRevision'] = _clientRevision
    if method == 'getCommunicationToken':
        query['header']['client'] = 'htmlshark'
        key = hashlib.md5(_header['session'].encode('utf-8')).hexdigest()
        query['parameters']['secretKey'] = key
    elif method == 'getResultsFromSearch':
        query['header']['client'] = 'htmlshark'
        query['parameters']['type'] = 'Songs'
        query['parameters']['query'] = kwargs['songname']
        query['header']['token'] = _make_grooveshark_token(method, SALT_HTMLSHARK)
    elif method == 'getStreamKeysFromSongIDs':
        query['header']['clientRevision'] = _clientRevision + '.02'
        query['header']['client'] = 'jsqueue'

        query['parameters']['mobile'] = 'false'
        query['parameters']['prefetch'] = 'false'
        query['parameters']['songIDs'] = kwargs['songid']
        query['parameters']['country'] = _header['country']
        query['header']['token'] = _make_grooveshark_token(method, SALT_JSQUEUE)
    else:
        raise NotImplementedError(method)

    return json.JSONEncoder().encode(query)


def setup_connection():
    global header, _token, _cookie
    connection = http.client.HTTPConnection('grooveshark.com')

    response = make_request(connection,
                            'First connection failed.',  # error message
                            'HEAD',  # Request type
                            '',  # Url
                            headers={'User-Agent': _useragent})

    _cookie = response.getheader('set-cookie').split(';')[0]
    query = _make_grooveshark_query('getCommunicationToken')

    connection = http.client.HTTPSConnection('grooveshark.com')

    response = make_request(connection,
                            'Can not get communication token.',
                            'POST',
                            '/more.php', query,
                            {'User-Agent': _useragent,
                             'Referer': _referer,
                             'Content-Type': '',
                             'Accept-Encoding': 'gzip',
                             'Cookie': _cookie})

    data = response.read()
    data = io.BytesIO(data)
    # response.seek(0)

    ungzipped = ungzip(data)
    decoded = json.JSONDecoder().decode(ungzipped.decode('utf-8'))
    logger.debug(decoded)

    _token = decoded['result']
    logger.debug(_token)


def download(songname):
    connection = http.client.HTTPConnection('grooveshark.com')

    query = _make_grooveshark_query('getResultsFromSearch', songname=songname)
    response = make_request(connection,
                            'Can not make search request',
                            'POST',
                            '/more.php?getResultsFromSearch',
                            query,
                            {'User-Agent': _useragent,
                             'Referer': 'http://grooveshark.com/',
                             'Content-Type': 'application/json',
                             'Accept-Encoding': 'gzip',
                             'Cookie': _cookie})

    ungzipped = ungzip(io.BytesIO(response.read()))
    decoded = json.JSONDecoder().decode(ungzipped.decode('utf-8'))

    song = None

    # Get first result from search
    try:
        song = decoded['result']['result']['Songs'][0]
    except Exception:
        try:
            song = decoded['result']['result'][0]
        except:
            raise Exception('Song not found.')

    songid = song['SongID']

    query = _make_grooveshark_query('getStreamKeysFromSongIDs', songid=songid)

    connection = http.client.HTTPConnection('grooveshark.com')

    response = make_request(connection,
                            'Can not get stream key',
                            'POST',
                            '/more.php?getStreamKeysFromSongIDs',
                            query,
                            {'User-Agent': _useragent,
                             'Referer': _referer,
                             'Content-Type': 'application/json',
                             'Accept-Encoding': 'gzip',
                             'Cookie': _cookie})

    ungzipped = ungzip(io.BytesIO(response.read()))
    decoded = json.JSONDecoder().decode(ungzipped.decode('utf-8'))

    result = decoded['result'][song['SongID']]

    query = urllib.parse.urlencode({'streamKey': result['streamKey']})
    connection = http.client.HTTPConnection(result['ip'])

    response = make_request(connection,
                            'Can not get stream data',
                            'POST', '/stream.php',
                            query,
                            {'User-Agent': _useragent,
                             'Referer': _referer,
                             'Cookie': _cookie,
                             'Content-Type': 'application/x-www-form-urlencoded',
                             'Connection': 'Keep-Alive'})
    return response


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('paolo conte')
        sys.argv.append('tmp/test__.mp3')
    output = open(sys.argv[2], 'wb')
    setup_connection()
    output.write(download(sys.argv[1]).read())
    output.close()
