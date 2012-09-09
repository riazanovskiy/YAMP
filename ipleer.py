# -*- coding: utf-8 -*-
import http.client
import urllib.parse
import urllib.request
import re
import urllib


def utf2cp1251(str):
    return str.encode('utf-8').decode('cp1251')


def urldecode(str):
    return urllib.parse.unquote(str.replace('\\x', '%'))


def log_response(response):
    print ('Status ' + str(response.status) + ' ' + response.reason)


def ok_code(response, message):
    if response.status not in [200]:
        raise Exception(message + (' - error %d' % response.status))


def make_request(connection, error_message, *args, **kwargs):
    try:
        connection.request(*args, **kwargs)
    except:
        raise Exception('Error - no connection')
    response = connection.getresponse()
    ok_code(response, error_message)
    return response


_useragent = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/535.19 (KHTML, like Gecko) Ubuntu/12.04 Chromium/18.0.1025.168 Chrome/18.0.1025.168 Safari/535.19'  # 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.57 Safari/536.11'  # 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1161.0 Safari/537.1'
_cookie = None


def safe_print(text):
    try:
        print (text)
    except:
        pass


def setup_ipleer():
    global _cookie

    connection = http.client.HTTPConnection('ipleer.kz')

    # Get session cookie
    response = make_request(connection, 'Can not get cookie', 'HEAD',
                            '', headers={'User-Agent': _useragent})

    _cookie = response.getheader('Set-cookie').split(';')[0]


def download(songname):
    '''Returns mp3 data which corresponds to songname'''

    # Search for song
    query = urllib.parse.quote(songname)

    connection = http.client.HTTPConnection('ipleer.kz')
    response = make_request(connection, 'Can not make search request', 'GET',
                            '/search/' + query,
                            headers={'User-Agent': _useragent,
                                     'Cookie': _cookie,
                                     'Connection': 'Keep-Alive'})
    response_text = response.read()

    #  Get song ID, song name and artist
    songid, songartist, songname = re.search('.*?data-vkid="([^"]+)".*?data-artist="([^"]+)".*?data-name="([^"]+)"', str(response_text)).groups()

    response = make_request(connection, 'Error while downloading song', 'GET',
                            '/getsong/' + songid,
                            headers={'User-Agent': _useragent, 'Cookie': _cookie,
                                     'Connection': 'Keep-Alive'})

    return response

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        sys.argv.append('ДДТ Людмила')  # 'Deep Purple Highway star') # 'щербаков Вишневое варенье') # 'pink floyd' #
        sys.argv.append('test.mp3')

    setup_ipleer()
    with open(sys.argv[2], 'wb') as output:
        output.write(download(sys.argv[1]).read())
