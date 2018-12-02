from setuptools import setup

with open('README.md', 'r') as readme:
    long_description = readme.read()

setup(name='Eddy',
      version='0.1',
      author='Ben Bethge',
      author_email='bethge931@gmail.com',
      description='Keyboard-only graphical text editor',
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/bbethge/eddy/',
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
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.6',
                   'Topic :: Text Editors'],
      zip_safe=False,
      packages=['eddy'],
      entry_points={'gui_scripts': ['eddy = eddy.eddy:main']},
      data_files=[('share/icons/hicolor/scalable/apps', ['eddy.svg']),
                  ('share/applications', ['eddy.desktop'])])
