import urllib.request
import re
import sys
from log import logger


def download(songname):
    page = None
    try:
        page = urllib.request.urlopen('http://vpleer.ru/?' +
                                      urllib.parse.urlencode({'q': songname}))
    except urllib.error.HTTPError as exc:
        logger.debug(exc)
        raise Exception('Can not access vpleer.ru')

    data = page.read(10000)
    result = re.search("result.*?list.*?audio0.*?oncli.*?play.*?'(.*?)\\\\",
                       repr(data))
    if result:
        try:
            return urllib.request.urlopen('http://vpleer.ru/' + result.groups()[0])
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
