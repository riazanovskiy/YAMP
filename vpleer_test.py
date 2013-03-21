import unittest
import sys

import vpleer
from for_examples import for_examples
from songslist import songslist

BYTES_TO_READ = 32768


class TestDownloadVpleer(unittest.TestCase):
    @for_examples(*songslist)
    def test_download(self, artist, title):
        exc = None
        try:
            data = vpleer.download(artist, title, BYTES_TO_READ)
        except:
            exc = sys.exc_info()
        self.assertIsNone(exc)
        self.assertGreaterEqual(len(data), BYTES_TO_READ)


if __name__ == '__main__':
    unittest.main()
