# -*- coding: utf-8 -*-
import http
import http.client
import urllib.parse
import urllib.request
import sys
import json
import string
import random
import io
import hashlib
import uuid
import time

from log import logger
from errors import NotFoundOnline

from misc import make_request, ungzip


class Grooveshark():
    salt_htmlshark = 'greenPlants'
    salt_jsqueue = 'tastyTacos'
    useragent = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'
    referer = 'http://grooveshark.com/JSQueue.swf?20121002.01'
    referer2 = 'http://grooveshark.com/'
    clientRevision = '20120830'
    clientRevision2 = '20120830.12'

    def __init__(self):
        self.timeout = 1200
        self.cookie = None
        self.header = {'country': {'CC1': '0',
                                   'CC2': '0',
                                   'CC3': '0',
                                   'CC4': '0',
                                   'ID': '1'},
                       'privacy': 0,
                       'session': None,
                       'uuid': str(uuid.uuid4()).upper()}

    def make_grooveshark_token(self, method, secret):
        rnd = (''.join(random.choice(string.hexdigits) for x in range(6))).lower()
        return rnd + hashlib.sha1((method + ':' + self.token + ':' + secret + ':' + rnd).encode('utf-8')).hexdigest()

    def make_grooveshark_query(self, method, **kwargs):
        if not self.cookie:
            raise Exception('You should get a cookie first.')

        self.header['session'] = self.cookie[10:]

        query = {}
        query['parameters'] = {}
        query['header'] = self.header
        query['method'] = method
        query['header']['clientRevision'] = self.clientRevision
        if method == 'getCommunicationToken':
            query['header']['client'] = 'htmlshark'
            key = hashlib.md5(self.header['session'].encode('utf-8')).hexdigest()
            query['parameters']['secretKey'] = key
        elif method == 'getResultsFromSearch':
            query['header']['client'] = 'htmlshark'
            query['parameters']['type'] = kwargs['search_type']
            query['parameters']['query'] = kwargs['songname']
            query['header']['token'] = self.make_grooveshark_token(method, self.salt_htmlshark)
        elif method == 'getStreamKeysFromSongIDs':
            query['header']['clientRevision'] = self.clientRevision2
            query['header']['client'] = 'jsqueue'
            query['parameters']['mobile'] = 'false'
            query['parameters']['prefetch'] = 'false'
            query['parameters']['songIDs'] = kwargs['songid']
            query['parameters']['country'] = self.header['country']
            query['header']['token'] = self.make_grooveshark_token(method, self.salt_jsqueue)
        elif method == 'getArtistByID':
            query['header']['token'] = self.make_grooveshark_token(method, self.salt_htmlshark)
            query['parameters']['artistID'] = kwargs['artistID']
        elif method == 'artistGetAllSongsEx':
            query['header']['token'] = self.make_grooveshark_token(method, self.salt_htmlshark)
            query['parameters']['artistID'] = kwargs['artistID']
        elif method == 'albumGetAllSongs':
            query['header']['token'] = self.make_grooveshark_token(method, self.salt_htmlshark)
            query['parameters']['albumID'] = kwargs['albumID']
        else:
            raise NotImplementedError(method)

        if (method != 'getCommunicationToken'
            and self.last_time - time.time() > self.timeout):
            self.getCommunicationToken()

        return json.JSONEncoder().encode(query)

    def getCommunicationToken(self):
        query = self.make_grooveshark_query('getCommunicationToken')

        connection = http.client.HTTPSConnection('grooveshark.com')

        response = make_request(connection,
                                'Can not get communication token.',
                                'POST',
                                '/more.php', query,
                                {'User-Agent': self.useragent,
                                 'Referer': self.referer,
                                 'Content-Type': '',
                                 'Accept-Encoding': 'gzip',
                                 'Cookie': self.cookie})

        data = response.read()
        data = io.BytesIO(data)

        decoded = json.JSONDecoder().decode(ungzip(data).decode('utf-8'))
        self.token = decoded['result']
        self.last_time = time.time()

    def getResultsFromSearch(self, songname, search_type):
        connection = http.client.HTTPConnection('grooveshark.com')

        query = self.make_grooveshark_query('getResultsFromSearch',
                                            songname=songname,
                                            search_type=search_type)
        response = make_request(connection,
                                'Can not make search request',
                                'POST',
                                '/more.php?getResultsFromSearch',
                                query,
                                {'User-Agent': self.useragent,
                                 'Referer': 'http://grooveshark.com/',
                                 'Content-Type': 'application/json',
                                 'Accept-Encoding': 'gzip',
                                 'Cookie': self.cookie})

        ungzipped = ungzip(io.BytesIO(response.read()))
        return json.JSONDecoder().decode(ungzipped.decode('utf-8'))['result']

    def getStreamKeysFromSongIDs(self, songid):
        query = self.make_grooveshark_query('getStreamKeysFromSongIDs',
                                            songid=songid)

        connection = http.client.HTTPConnection('grooveshark.com')

        response = make_request(connection,
                                'Can not get stream key',
                                'POST',
                                '/more.php?getStreamKeysFromSongIDs',
                                query,
                                {'User-Agent': self.useragent,
                                 'Referer': self.referer,
                                 'Content-Type': 'application/json',
                                 'Accept-Encoding': 'gzip',
                                 'Cookie': self.cookie})

        ungzipped = ungzip(io.BytesIO(response.read()))
        return json.JSONDecoder().decode(ungzipped.decode('utf-8'))['result']

    def getArtistByID(self, artist_id):
        query = self.make_grooveshark_query('getArtistByID', artistID=artist_id)

        connection = http.client.HTTPConnection('grooveshark.com')

        response = make_request(connection,
                                'Can not get artist data',
                                'POST',
                                '/more.php?getArtistByID',
                                query,
                                {'User-Agent': self.useragent,
                                 'Referer': self.referer2,
                                 'Content-Type': 'application/json',
                                 'Accept-Encoding': 'gzip',
                                 'Cookie': self.cookie})

        ungzipped = ungzip(io.BytesIO(response.read()))
        return json.JSONDecoder().decode(ungzipped.decode('utf-8'))['result']

    def artistGetAllSongsEx(self, artist_id):
        query = self.make_grooveshark_query('artistGetAllSongsEx', artistID=artist_id)

        connection = http.client.HTTPConnection('grooveshark.com')

        response = make_request(connection,
                                'Can not get artist data',
                                'POST',
                                '/more.php?artistGetAllSongsEx',
                                query,
                                {'User-Agent': self.useragent,
                                 'Referer': self.referer2,
                                 'Content-Type': 'application/json',
                                 'Accept-Encoding': 'gzip',
                                 'Cookie': self.cookie})

        ungzipped = ungzip(io.BytesIO(response.read()))
        return json.JSONDecoder().decode(ungzipped.decode('utf-8'))['result']

    def albumGetAllSongs(self, album_id):
        query = self.make_grooveshark_query('albumGetAllSongs', albumID=album_id)

        connection = http.client.HTTPConnection('grooveshark.com')

        response = make_request(connection,
                                'Can not get track list',
                                'POST',
                                '/more.php?albumGetAllSongs',
                                query,
                                {'User-Agent': self.useragent,
                                 'Referer': self.referer2,
                                 'Content-Type': 'application/json',
                                 'Accept-Encoding': 'gzip',
                                 'Cookie': self.cookie})

        ungzipped = ungzip(io.BytesIO(response.read()))
        return json.JSONDecoder().decode(ungzipped.decode('utf-8'))['result']

    def download_from_stream_key(self, stream_key, ip):
        query = urllib.parse.urlencode({'streamKey': stream_key})
        connection = http.client.HTTPConnection(ip)

        return make_request(connection,
                            'Can not get stream data',
                            'POST', '/stream.php',
                            query,
                            {'User-Agent': self.useragent,
                             'Referer': self.referer,
                             'Cookie': self.cookie,
                             'Content-Type': 'application/x-www-form-urlencoded',
                             'Connection': 'Keep-Alive'})

    def get_cookie(self):
        connection = http.client.HTTPConnection('grooveshark.com')
        response = make_request(connection,
                                'First connection failed',
                                'HEAD',
                                '',
                                headers={'User-Agent': self.useragent})

        self.cookie = response.getheader('set-cookie').split(';')[0]


singleton = Grooveshark()


def setup_connection():
    singleton.get_cookie()
    singleton.getCommunicationToken()


def download(songname):
    decoded = singleton.getResultsFromSearch(songname, 'Songs')

    try:
        song = decoded['result']['Songs'][0]
    except Exception:
        try:
            song = decoded['result'][0]
        except:
            raise NotFoundOnline()
    try:
        songid = song['SongID']
    except:
        raise NotFoundOnline()

    decoded = singleton.getStreamKeysFromSongIDs(songid)

    result = decoded[songid]
    stream_key = result['streamKey']
    ip = result['ip']
    return singleton.download_from_stream_key(stream_key, ip)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('paolo conte')
        sys.argv.append('test__.mp3')
    output = open(sys.argv[2], 'wb')
    setup_connection()
    output.write(download(sys.argv[1]).read())
    output.close()
