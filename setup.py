from setuptools import setup

with open('README.md', 'r') as readme:
    long_description = readme.read()

setup(name='Scriggle',
      version='0.1',
      author='Ben Bethge',
      author_email='bethge931@gmail.com',
      description='Keyboard-only graphical text editor',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/bbethge/scriggle/',
      license='GPLv3+',
      classifiers=['Development Status :: 3 - Alpha',
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
                   'Programming Language :: Python :: 3.7',
                   'Topic :: Text Editors'],
      zip_safe=False,
      packages=['scriggle'],
      entry_points={'gui_scripts': ['scriggle = scriggle.scriggle:main']},
      data_files=[('share/icons/hicolor/scalable/apps', ['scriggle.svg']),
                  *[(f'share/icons/hicolor/{s}x{s}/apps',
                     [f'icons/{s}x{s}/scriggle.png'])
                    for s in [16, 22, 24, 48]],
                  ('share/applications', ['scriggle.desktop'])])
