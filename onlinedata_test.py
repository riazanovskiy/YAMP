import unittest
from unittest.mock import patch

import onlinedata as onlinedata
from misc import normalcase


class TestOnlineData(unittest.TestCase):
    def setUp(self):
        self.data = onlinedata.OnlineData()

    def test_lastfm_song(self):
        song = self.data.song(onlinedata.LASTFM, 'Алмазный британец')
        self.assertEqual(normalcase(song.name), normalcase('Алмазный британец'))
        self.assertEqual(normalcase(song.artist), normalcase('Ночные Снайперы'))

    def test_lastfm_album(self):
        album = self.data.album(onlinedata.LASTFM, 'Wish You Were Here')
        self.assertEqual(normalcase(album.name), normalcase('Wish You Were Here'))
        self.assertEqual(normalcase(album.artist), normalcase('Pink Floyd'))
        self.assertEqual(len(album.tracks()), 5)

    def test_lastfm_artist(self):
        artist = self.data.artist(onlinedata.LASTFM, "Веня Д'ркин")
        self.assertEqual(normalcase(artist.name), normalcase("Веня Д'ркин"))
        tracks = [i.name for i in artist.tracks()]
        for i in ['Маргарита', 'Кошка']:
            self.assertIn(i, tracks)

    def test_grooveshark_song(self):
        song = self.data.song(onlinedata.GROOVESHARK, 'Алмазный британец')
        self.assertEqual(normalcase(song.name), normalcase('Алмазный британец'))
        self.assertEqual(normalcase(song.artist), normalcase('Ночные Снайперы'))

    def test_grooveshark_album(self):
        album = self.data.album(onlinedata.GROOVESHARK, 'Mittelpunkt der Welt')
        self.assertEqual(normalcase(album.name), normalcase('Mittelpunkt der Welt'))
        self.assertEqual(normalcase(album.artist), normalcase('Element of Crime'))
        self.assertEqual(len(album.tracks()), 10)

    def test_grooveshark_artist(self):
        artist = self.data.artist(onlinedata.GROOVESHARK, "Веня Д'ркин")
        self.assertEqual(normalcase(artist.name), normalcase("Веня Д'ркин"))
        tracks = [i.name for i in artist.tracks()]
        for i in ['Маргарита', 'Кошка']:
            self.assertIn(i, tracks)

    def test_brainz_song(self):
        song = self.data.song(onlinedata.BRAINZ, 'Алмазный британец')
        self.assertEqual(normalcase(song.name), normalcase('Алмазный британец'))
        self.assertEqual(normalcase(song.artist), normalcase('Ночные Снайперы'))

    def test_brainz_album(self):
        album = self.data.album(onlinedata.BRAINZ, 'Mittelpunkt der Welt')
        self.assertEqual(normalcase(album.name), normalcase('Mittelpunkt der Welt'))
        self.assertEqual(normalcase(album.artist), normalcase('Element of Crime'))
        self.assertEqual(len(album.tracks()), 10)

    def test_brainz_artist(self):
        artist = self.data.artist(onlinedata.BRAINZ, "Веня Д'ркин")
        self.assertEqual(normalcase(artist.name), normalcase("Веня Д'ркин"))
        with self.assertRaises(NotImplementedError):
            artist.tracks()

    # def test_multiple_download(self):
    #     data = [('Поворот', 'Машина времени', 'Империя звезд (сборник)', 1),
    #             ('Костер', 'Машина времени', 'Империя звезд (сборник)', 2)]
    #             # ('Синяя птица', 'Машина времени', 'Империя звезд (сборник)', 3),
    #             # ('Она идет по жизни смеясь', 'Машина времени', 'Империя звезд (сборник)', 4)]

    #     files = self.data.download_by_list(data)
    #     self.assertEqual(len(files), len(data))
    #     for file in files:
    #         self.assertGreater(filesize(file), 1000)
    #         os.remove(file)


if __name__ == '__main__':
    unittest.main()
