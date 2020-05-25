#! /usr/bin/env python3

import glob
import os
import os.path
import re

from setuptools import setup
try:
    from setuptools.command.build import build as orig_build
except ModuleNotFoundError:
    from distutils.command.build import build as orig_build
from distutils.errors import DistutilsFileError


with open('README.md', 'r') as readme:
    long_description = readme.read()

source_dir = os.path.dirname(__file__)
icon_sizes = []
for icon_size_dir in glob.iglob(os.path.join(source_dir, 'icons', '*')):
    icon_size_str = re.match(
        r'([0-9]+)x[0-9]+', os.path.basename(icon_size_dir)
    )[1]
    icon_sizes.append(int(icon_size_str))
print(f'Icon sizes: {icon_sizes}')


class build(orig_build):
    def run(self):
        svg_file = os.path.join(source_dir, 'scriggle.svg')
        for size in icon_sizes:
            png_file = os.path.join(
                source_dir, 'icons', f'{size}x{size}', 'scriggle.png'
            )
            if os.stat(svg_file).st_mtime > os.stat(png_file).st_mtime:
                raise DistutilsFileError(
                    f'{svg_file} is newer than the rasterized icon file '
                    f'{png_file}.  You must run ./build_icons.py to update '
                     'the rasterized icons.'
                )
        super().run()


setup(
    name='Scriggle',
    version='0.1',
    author='Ben Bethge',
    author_email='bethge931@gmail.com',
    description='Keyboard-only graphical text editor',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/bbethge/scriggle/',
    license='GPLv3+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: MacOS X',
        'Environment :: Win32 (MS Windows)',
        'Environment :: X11 Applications',
        'Environment :: X11 Applications :: Gnome',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: Developers',
        'License :: OSI Approved'
           ' :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Text Editors'
    ],
    python_requires='>=3',
    zip_safe=False,
    packages=['scriggle'],
    entry_points={'gui_scripts': ['scriggle = scriggle.scriggle:main']},
    cmdclass={'build': build},
    data_files=[
        ('share/icons/hicolor/scalable/apps', ['scriggle.svg']),
        *[
            (
                f'share/icons/hicolor/{s}x{s}/apps',
                [f'icons/{s}x{s}/scriggle.png'],
            )
            for s in icon_sizes
        ],
        ('share/applications', ['scriggle.desktop']),
    ]
)
