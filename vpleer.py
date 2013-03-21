import urllib.request
import re
import sys
from pprint import pprint
import http
import http.client


from errors import NotFoundOnline
from misc import diff, make_request
from log import logger

useragent = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'  # 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1161.0 Safari/537.1'
cookie = None


def download(artist, title, limit=0):
    global cookie
    if cookie is None:
        connection = http.client.HTTPConnection('vpleer.ru')
        response = make_request(connection, 'Can not get a cookie', 'HEAD', '', headers={'User-Agent': useragent})
        cookie = response.getheader('set-cookie').split(';')[0]
    page = None
    url = 'http://vpleer.ru/music/' + urllib.parse.quote_plus(artist + ' ' + title) + '/'
    request = urllib.request.Request(url, headers={'User-Agent': useragent, 'Cookie': cookie})
    try:
        page = urllib.request.urlopen(request)
    except urllib.error.HTTPError as exc:
        logger.debug(exc)
        raise Exception('Can not access vpleer.ru')
    data = page.read()
    try:
        data = data.decode('utf-8')
    except:
        data = repr(data)
    for i in range(20):
        result = re.search("audio{}.*?oncli.*?play.*?'([^\\']*?)'.*?<span class=\"ausong\">\\s*<b>\\s*([^<]+)\\s*</b>\\s*</span>.*?<span class=\"auname\">([^<]+)</span>".format(i), data, re.DOTALL)
        if result:
            url, vartist, vtitle = result.groups()
            if (diff(artist, vartist) < 0.3 and diff(title, vtitle) < 0.3):
                url = 'http://vpleer.ru' + url.replace('&amp;', '&')
                while url[-1] == '\\':
                    url = url[:-1]
                try:
                    response = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': useragent,
                                                                                           'Cookie': cookie}))
                except urllib.error.HTTPError as exc:
                    continue
                if limit > 0:
                    mp3 = response.read(limit)
                else:
                    mp3 = response.read()
                if mp3:
                    return mp3
            # else:
                # print(vartist, vtitle)
    raise NotFoundOnline()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('paolo conte')
        sys.argv.append('test__.mp3')
    elif len(sys.argv) != 3:
        print('Enter your search query and output filename')
        exit(1)
    output = open(sys.argv[2], 'wb')
    output.write(download(sys.argv[1]).read())
    output.close()
