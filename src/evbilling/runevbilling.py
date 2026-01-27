'''
Run evbilling from Windows File Explorer Open with ... menu
'''

__author__ = 'Keith Gorlen'

import subprocess
import sys
import os


def main():
    """Run evbilling from Windows File Explorer Open with ... menu."""
    if len(sys.argv) > 1:
        file_path = sys.argv[1]  # PG&E PDF bill file path
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
    else:
        print("Usage: python runevbilling.py <filename>")
        sys.exit(1)

    command = f'pushd "{file_dir}" && cmd.exe /c evbilling "{file_name}" & popd & pause'
    print('Running evbilling ...')
    subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    main()
