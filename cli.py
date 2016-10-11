import os
from configparser import ConfigParser
import time
import sys

import readline

import cmd
import colorama
import glob

import database
from misc import verify_dir
from log import logger

try:
    import pyglet
except:
    logger.error('No pyglet library')
    pyglet = None


def get_yn_promt(promt):
    ans = input(promt)
    while ans not in ['y', 'n', '', 'yes', 'no']:
        ans = input(promt)
    return ans == 'y' or ans == 'yes'


def get_path_from_user():
    accept = False
    path = ''
    while not accept:
        path = os.path.abspath(input('Enter main path to music library: '))
        prompt = input('Path is ' + path + ' (yes/no) ')
        if prompt == 'no':
            path = os.path.abspath(input('Enter main path to music library: '))
        accept = (prompt == 'yes' or prompt == 'y')
    return path


class YampShell(cmd.Cmd):
    prompt = '$ ' if os.name == 'nt' else '> '

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._artists = []
        self._albums = []
        if not pyglet:
            logger.error('No pyglet library')
            return
        self.player = pyglet.media.Player()

    def albums(self):
        if not self._albums:
            self._albums = list(db.get_albums())
        return self._albums

    def artists(self):
        if not self._artists:
            self._artists = list(db.get_artists())
        return self._artists

    def _complete(self, line, begidx):
        command = len(line.split()[0]) + 1
        pref = line[command:]
        while pref and pref[0] in ' 1234567890':
            pref = pref[1:]
            begidx -= 1

        if pref:
            if pref[0] == '#':
                if begidx == command:
                    return ['#' + i for i in self.albums() if i.startswith(pref[1:])]
                else:
                    return [i[begidx - command - 1:] for i in self.albums() if i.startswith(pref[1:])]
            elif pref[0] == '@':
                if begidx == command:
                    return ['@' + i for i in self.artists() if i.startswith(pref[1:])]
                else:
                    return [i[begidx - command - 1:] for i in self.artists() if i.startswith(pref[1:])]
        return ([i[begidx - command:] for i in self.albums() if i.startswith(pref)] +
                [i[begidx - command:] for i in self.artists() if i.startswith(pref)])

    def parse_arguments(self, args):
        artist, album = None, None
        args = args.strip()

        if '@' in args:
            i = args.index('@')
            j = i
            saved = i
            all_artists = set(self.artists())
            while j < len(args) and args[j] != '#':
                j += 1
                if args[i + 1:j] in all_artists:
                    saved = j
            if saved == i:
                saved = j
            artist = args[i + 1:saved].strip()
            args = args[:i] + args[saved:]

        if '#' in args:
            args = args.strip()
            i = args.index('#')
            j = i
            saved = i
            all_albums = set(self.albums())
            while j < len(args) and args[j] != '@':
                j += 1
                if args[i + 1:j] in all_albums:
                    saved = j
            if saved == i:
                saved = j
            album = args[i + 1:saved].strip()
            args = args[:i] + args[saved:]
        if args in self.artists():
            artist = args
            args = ''
        elif args in self.albums():
            album = args
            args = ''
        words = args.split()
        if words and words[0].isdigit():
            new = ' '.join(words[1:])
            if new in self.artists():
                artist = new
                args = words[0]
            elif new in self.albums():
                album = new
                args = words[0]

        return (artist, album, args.strip())

############# import ########################################################################################

    def do_import(self, args):
        args = os.path.abspath(args.strip())
        if os.path.exists(args):
            if os.path.isdir(args):
                db.import_folder(args)
            elif os.path.isfile(args):
                db.import_file(args)
                db.sql.commit()
            db.remove_extensions_from_tracks()
            db.track_numbers()
            db.generic_correction('artist')
            db.generic_correction('album')
            db.generic_correction('track')
            self._albums = []
            self._artists = []
        else:
            print('Nothing to import.', file=sys.stderr)

    def help_import(self):
        print('import /directory/name ...')
        print('Imports selected directory to yamp. This does not actually move files.')

    def complete_import(self, text, line, begidx, endidx):
        return (glob.glob(text + '*') + [None])

############# move ########################################################################################

    def do_move(self, args):
        if get_yn_promt('Are you sure? '):
            print('Moving all music files. Be patient, this can take some time.', file=sys.stderr)
            db.move_files()
            db.writeout()

    def help_move(self):
        print('Copies or moves all the files to corresponding folders.')

############# show ########################################################################################

    def do_show(self, args):
        artist, album, args = self.parse_arguments(args)
        if album is not None:
            if album:
                db.pretty_print(album=album)
            else:
                print('\n'.join(sorted(self.albums())))
        elif artist is not None:
            if artist:
                db.pretty_print(artist=artist)
            else:
                print('\n'.join(sorted(self.artists())))
        else:
            db.pretty_print()

    def help_show(self):
        print('show')
        print('show @artist')
        print('show #album')
        print('Shows different parts of library.')

    def complete_show(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# more ########################################################################################

    def do_more(self, args):
        artist, album, args = self.parse_arguments(args)

        if album:
            if not artist:
                artist = db.get_artist_of_album(album)
            print('Fetching more songs from album', album, 'by', artist, file=sys.stderr)
            db.fill_album(artist, album)
        elif artist:
            print('Fetching more songs by', artist, file=sys.stderr)
            db.fetch_tracks_for_artist(artist)
        elif args:
            print('Fetching more songs by', args, file=sys.stderr)
            db.fetch_tracks_for_artist(args)
        else:
            return
        self._artists = []
        self._albums = []

    def help_more(self):
        print('more artist|album')
        print('more #album')
        print('more @artist')
        print('This will add more songs of to library. Use # to specify album. Use @ to specify artist.')

    def complete_more(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# correct ########################################################################################

    def do_correct(self, args):
        artist, album, args = self.parse_arguments(args)
        if album:
            album = db.correct_album(album)
            if not artist:
                artist = db.get_artist_of_album(album)
            db.fill_album(artist, album, only_correct=True)
        if artist:
            db.correct_artist(artist, force=True)
        self._albums = []
        self._artists = []

    def help_correct(self):
        print('correct artist|album')
        print('correct #album')
        print('correct @artist')
        print('This will try to improve tags. Use # to specify album. Use @ to specify artist.')

    def complete_correct(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# translit ########################################################################################
    def help_translit(self):
        print('translit artist|album')
        print('translit #album')
        print('translit @artist')
        print('Заменит транслит в названиях')

    def complete_translit(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

    def do_translit(self, args):
        artist, album, args = self.parse_arguments(args)
        if album or artist:
            self._albums = []
            self._artists = []
            if album:
                db.transliterate_album(album)
                return
            elif artist:
                db.transliterate('artist', artist, artist='')
                return

############# fetch ########################################################################################
    def help_fetch(self):
        print('fetch [count] [@artist] [#album]')
        print("This will fetch mp3 file for songs which don't have one.")
        print('This will fetch up to count files or all of them if count is not specified')

    def do_fetch(self, args):
        artist, album, args = self.parse_arguments(args)
        if args:
            try:
                count = int(args)
            except:
                print(args, 'is not a number', file=sys.stderr)
                return
        else:
            count = 100500
        db.fetch_data(count=count, artist=artist, album=album)

    def complete_fetch(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# rescan ########################################################################################
    def help_rescan(self):
        print('rescan')
        print("This will check whether all files in database exist")

    def do_rescan(self, args):
        db.rescan()

############# play ########################################################################################
    def help_play(self):
        print('play')
        print('This will resume playback')
        print('play @artist')
        print('This will start playing songs of specified artist in random order')
        print('play #album')
        print('This will play specified album')

    def do_play(self, args):
        if not pyglet:
            logger.error('No pyglet library')
            return

        artist, album, args = self.parse_arguments(args)
        if album:
            self.player.pause()
            self.player = pyglet.media.Player()
            if artist:
                cursor = db.sql.execute('select track, filename from songs where album=? and artist=? and has_file=1',
                                        (album, artist))
            else:
                cursor = db.sql.execute('select track, filename from songs where album=? and has_file=1', (album,))
            for track, filename in sorted(cursor):
                self.player.queue(pyglet.media.load(filename))
        elif artist:
            self.player.pause()
            self.player = pyglet.media.Player()
            filenames = [i for i, in db.sql.execute('select filename from songs where artist=? and has_file=1 order by random()', (artist,))]
            for filename in filenames:
                self.player.queue(pyglet.media.load(filename))
        self.player.play()

    def complete_play(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# next ########################################################################################
    def help_next(self):
        print('next')
        print("This will switch to next song")

    def do_next(self, args):
        if not pyglet:
            logger.error('No pyglet library')
            return

        self.player.next_source()
        self.player.play()

############# shuffle ########################################################################################
    def help_shuffle(self):
        print('shuffle [count]')
        print("This will play 100 or count songs in random order")

    def do_shuffle(self, args):
        if not pyglet:
            logger.error('No pyglet library')
            return

        logger.debug('shuffle: started')

        args = args.strip()
        if args:
            try:
                count = int(args)
            except:
                count = 100
        else:
            count = 100
        self.player.pause()
        logger.debug('shuffle: paused')
        self.player = pyglet.media.Player()
        logger.debug('shuffle: new player')
        filenames = [i for i, in db.sql.execute('select filename from songs '
                                                'where has_file=1 '
                                                'order by random() limit ?;', (count,))]
        logger.debug('shuffle: starting to add')
        for filename in filenames:
            try:
                src = pyglet.media.load(filename)
                logger.debug('shuffle: source created')
                self.player.queue(src)
                logger.debug('shuffle: added to queue')
            except:
                logger.warning('{} failed to add'.format(filename))
        logger.debug('shuffle: all added')
        self.player.play()

############# pause ########################################################################################
    def help_pause(self):
        print('pause')
        print("This will pause playback")

    def do_pause(self, args):
        self.player.pause()

############# EOF ########################################################################################

    def do_EOF(self, args):
        print(file=sys.stderr)
        print('Saving your changes...', file=sys.stderr)
        db.writeout()
        print('Exiting', file=sys.stderr)
        return True

    def emptyline(self):
        pass

    def precmd(self, line):
        self.time_before = time.time()
        return line

    def postcmd(self, stop, line):
        logger.info('Execution time was {}'.format(round(time.time() - self.time_before, 2)))
        return stop

if __name__ == '__main__':
    colorama.init()
    config = ConfigParser()
    if os.path.exists('yampconfig'):
        config.read('yampconfig')
        path = config['DefaultDirectory']['path']
    else:
        path = get_path_from_user()
        config['DefaultDirectory'] = {'path': path}
        with open('yampconfig', 'w') as file:
            config.write(file)
    verify_dir(path)
    db = database.Database(path)
    logger.info('Started')
    readline.set_completer_delims(' \t\n;')
    YampShell(completekey='tab').cmdloop('This is yet another media player.\nUse help or help <command> to get help. ')
