import cmd
import os
import yamp
import sys
import glob
import readline


class YampShell(cmd.Cmd):
    prompt = '$ ' if os.name == 'nt' else '> '
    file = None
    doc_header = 'This is yet another music player.'

    def do_import(self, args):
        folders = [os.path.abspath(i) for i in args.split()]
        if not folders:
            print('Nothing to import.')
        for i in folders:
            database.import_folder(i)

    def help_import(self):
        print('import /directory/name ...')
        print('Imports selected directory to yamp. This does not actually move files.')

    def complete_import(self, text, line, begidx, endidx):
        return (glob.glob(text + '*') + [None])

    def do_move(self, args):
        database.move_files()

    def help_move(self):
        print('Moves all the files to correct folders.')

    def do_EOF(self):
        print()
        print('Exiting')
        return True

if __name__ == '__main__':
    accept = False
    try:
        # while (not accept):
            # path = os.path.abspath(input('Enter main path to music library: '))
            # accept = (input('Path is ' + path + ' (yes/no) ') == 'yes')
        path = '/home/dani/yamp'
        yamp.verify_dir(path)
        database = yamp.Database(path)
        readline.set_completer_delims(' \t\n;')
        YampShell().cmdloop()
    except:
        print()
        print('Exiting')
