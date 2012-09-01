print('Started ' + __name__)
import unittest
from testing_examples import for_examples
import ipleer
from songslist import songslist
import sys
BYTES_TO_READ = 32768


class TestDownloadIpleer(unittest.TestCase):
    def setUp(self):
        ipleer.setup_ipleer()

    @for_examples(*songslist[:5])
    def test_download(self, songname):
        exc = None
        try:
            data = ipleer.download(songname).read(BYTES_TO_READ)
        except:
            exc = sys.exc_info()[1]

        self.assertIsNone(exc)
        self.assertGreaterEqual(len(data), BYTES_TO_READ)

if __name__ == '__main__':
    unittest.main()
