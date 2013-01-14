import unittest
from for_examples import for_examples
import grooveshark
from songslist import songslist
import sys
BYTES_TO_READ = 32768


class TestDownloadGrooveshark(unittest.TestCase):
    def setUp(self):
        grooveshark.setup_connection()

    @for_examples(*songslist[:5])
    def test_download(self, songname):
        exc = None
        try:
            data = grooveshark.download(songname).read(BYTES_TO_READ)
        except:
            exc = sys.exc_info()[1]

        self.assertIsNone(exc)
        self.assertGreaterEqual(len(data), BYTES_TO_READ)

if __name__ == '__main__':
    unittest.main()
