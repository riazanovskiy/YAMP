print('Started ' + __name__)
import unittest
from testing_examples import for_examples
import vpleer
from songslist import songslist
import sys
BYTES_TO_READ = 32768


class TestDownloadVpleer(unittest.TestCase):
    @for_examples(*songslist[:5])
    def test_download(self, songname):
        exc = None
        try:
            data = vpleer.download(songname).read(BYTES_TO_READ)
        except:
            exc = sys.exc_info()[1]
        self.assertIsNone(exc)
        self.assertGreaterEqual(len(data), BYTES_TO_READ)


if __name__ == '__main__':
    unittest.main()
