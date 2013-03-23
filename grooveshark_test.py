import unittest
import sys

import grooveshark
from for_examples import for_examples
from songslist import songslist

BYTES_TO_READ = 32768


class TestDownloadGrooveshark(unittest.TestCase):
    def setUp(self):
        grooveshark.setup_connection()

    @for_examples(*songslist)
    def test_download(self, artist, title):
        exc = None
        try:
            data = grooveshark.download(artist, title, BYTES_TO_READ)
        except:
            exc = sys.exc_info()[1]

        self.assertIsNone(exc)
        self.assertGreaterEqual(len(data), BYTES_TO_READ)

if __name__ == '__main__':
    unittest.main()
