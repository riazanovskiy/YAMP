import urllib.request
import re
import sys

from log import logger

useragent = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11'  # 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1161.0 Safari/537.1'


def download(songname):
    page = None
    url = 'http://vpleer.ru/music/' + urllib.parse.quote_plus(songname)
    request = urllib.request.Request(url, headers={'User-Agent': useragent})
    try:
        page = urllib.request.urlopen(request)
    except urllib.error.HTTPError as exc:
        logger.debug(exc)
        raise Exception('Can not access vpleer.ru')
    data = page.read()
    result = re.search("audio0.*?oncli.*?play.*?'([^']*?)'", data.decode('utf-8'), re.DOTALL)
    url = 'http://vpleer.ru' + result.groups()[0][:-1].replace('&amp;', '&')
    if result:
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': useragent}))
        except urllib.error.HTTPError as exc:
            logger.debug(exc)
            raise Exception('Can not download from vpleer.ru')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('paolo conte')
        sys.argv.append('tmp/test__.mp3')
    elif len(sys.argv) != 3:
        print('Enter your search query and output filename')
        exit(1)
    output = open(sys.argv[2], 'wb')
    output.write(download(sys.argv[1]).read())
    output.close()
