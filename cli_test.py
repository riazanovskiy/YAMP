import unittest
import unittest.mock
# from unittest.mock import patch

import cli


class TestCli(unittest.TestCase):
    def setUp(self):
        self.mock = unittest.mock.Mock()
        self.mock.get_albums.return_value = []
        self.mock.get_artists.return_value = []
        cli.db = self.mock
        self.shell = cli.YampShell()

    def test_parse_arguments(self):
        examples = [('', (None, None, '')),
                    ('213sad', (None, None, '213sad')),
                    ('#Pink', (None, 'Pink', '')),
                    ('@Pink', ('Pink', None, '')),
                    ('@Pink #Floyd', ('Pink', 'Floyd', '')),
                    ('2312 @Pink #Floyd', ('Pink', 'Floyd', '2312')),
                    ('#', (None, '', '')),
                    ('@', ('', None, '')),
                    ('   # @  ', ('', '', '')),
                    ('@    #', ('', '', '')),
                    ('1 #  @  ', ('', '', '1'))]

        for inp, out in examples:
            self.assertTupleEqual(out, self.shell.parse_arguments(inp))
            self.mock.reset_mock()

if __name__ == '__main__':
    unittest.main()
