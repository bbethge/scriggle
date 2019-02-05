#! /usr/bin/env python3

import os
import os.path
import subprocess


source_dir = os.path.dirname(__file__)
icon_prefix = os.path.join(source_dir, 'icons')
svg_file = os.path.join(source_dir, 'scriggle.svg')
for size in [16, 22, 24, 48]:
    icon_dir = os.path.join(icon_prefix, f'{size}x{size}')
    os.makedirs(icon_dir, exist_ok=True)
    icon_file = os.path.join(icon_dir, 'scriggle.png')
    subprocess.run(['inkscape', svg_file, f'--export-png={icon_file}',
                    f'--export-width={size}', f'--export-height={size}'])
