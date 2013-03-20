# import warnings
# warnings.simplefilter('ignore')
import os
from configparser import ConfigParser

import readline

import cmd
import colorama
import glob

import database
from misc import verify_dir
from log import logger


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
                    return [i[begidx:] for i in self.artists() if i.startswith(pref[1:])]
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
            print('Nothing to import.')

    def help_import(self):
        print('import /directory/name ...')
        print('Imports selected directory to yamp. This does not actually move files.')

    def complete_import(self, text, line, begidx, endidx):
        return (glob.glob(text + '*') + [None])

############# move ########################################################################################

    def do_move(self, args):
        if get_yn_promt('Are you sure? '):
            print('Moving all music files. Be patient, this can take some time.')
            db.move_files()
            db.writeout()

    def help_move(self):
        print('Copies or moves all the files to corresponding folders.')

############# show ########################################################################################

    def do_show(self, args):
        args = args.strip()
        if not args:
            db.pretty_print()
        elif args == '@':
            print('\n'.join(sorted(self.artists())))
            return
        elif args == '#':
            print('\n'.join(sorted(self.albums())))
            return
        elif args[0] == '@':
            db.pretty_print(artist=args[1:])
            return
        elif args[0] == '#':
            db.pretty_print(album=args[1:])
            return
        elif args in self.albums():
            db.pretty_print(album=args)
            return
        elif args in self.artists():
            db.pretty_print(artist=args)
            return

    def help_show(self):
        print('show')
        print('show @artist')
        print('show #album')
        print('Shows different parts of library.')

    def complete_show(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# more ########################################################################################

    def do_more(self, args):
        args = args.strip()

        if not args:
            return
        do_artist = bool(args[0] == '@' or args in self.artists())
        do_album = bool(args[0] == '#' or args in self.albums())

        if args[0] in '@#':
            args = args[1:]

        if do_album == do_artist:
            do_album = False
            do_artist = True

        assert (do_artist != do_album)

        if do_album:
            artist = db.get_artist_of_album(args)
            print('Fetching more songs from album', args, 'by', artist)
            db.fill_album(artist, args)
        else:
            print('Fetching more songs by', args)
            db.fetch_tracks_for_artist(args)
        self._artists = []
        self._albums = []

    def help_more(self):
        print('more artist|album')
        print('more #album')
        print('more @artist')
        print('This will add more songs of to library. Use # to specify album. Use @ to specify artist.')

    def complete_more(self, text, line, begidx, endidx):
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
        args = args.strip()
        if args:
            self._artists = []
            self._albums = []
            if args[0] == '@':
                db.transliterate('artist', args[1:], artist='')
                return
            elif args[0] == '#':
                db.transliterate_album(args[1:])
                return
            elif args in self.albums():
                db.transliterate_album(args)
                return
            elif args in self.artists():
                db.transliterate('artist', args, artist='')
                return

############# fetch ########################################################################################
    def help_fetch(self):
        print('fetch [count] [#artist] [@album]')
        print("This will fetch mp3 file for songs which don't have one.")
        print('This will fetch up to count files or all of them if count is not specified')

    def do_fetch(self, args):
        artist, album, args = self.parse_arguments(args)
        if args:
            try:
                count = int(args)
            except:
                print(args, 'is not a number')
                return
        else:
            count = 100500
        db.fetch_data(count=count, artist=artist, album=album)

    def complete_fetch(self, text, line, begidx, endidx):
        return self._complete(line, begidx)

############# EOF ########################################################################################

    def do_EOF(self, args):
        db.writeout()
        print()
        print('Exiting')
        return True

    def emptyline(self):
        pass


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
    db = database.Database(path, use_grooveshark=input('Should we use grooveshark? ')[0] in ['yes', 'y'])
    logger.info('Started')
    readline.set_completer_delims(' \t\n;')
    YampShell(completekey='tab').cmdloop('This is yet another media player.\nUse help or help <command> to get help. ')
