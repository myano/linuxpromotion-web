# LaSG - Lame Site Generator
# Copyright (C) 2012  Nikita Churaev
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import errno
import json
import shutil
import copy
import subprocess
import argparse
from datetime import datetime
import xml.etree.ElementTree as etree

script_start_time = datetime.now()

# ============================================================================
#  Page parser
# ============================================================================

PAGE_BLOCK_TEXT = 0
PAGE_BLOCK_CODE = 1

class PageBlock:
    def __init__(self, content, type):
        self.type = type
        self.content = content

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        if self.type == PAGE_BLOCK_TEXT:
            return repr(('text', self.content))
        else:
            return repr(('code', self.content))

# Separates page into blocks of code and text.
def parse_page_blocks(s):
    blocks = []
    block_first = 0
    block_type = PAGE_BLOCK_TEXT
    cur = 0
    
    def end_block(old_last, new_first, new_type):
        nonlocal block_first
        nonlocal block_type

        blocks.append(PageBlock(s[block_first:old_last+1], block_type))
        block_first = new_first
        block_type = new_type

    while True:
        last = (cur == len(s) - 1)

        if block_type == PAGE_BLOCK_TEXT:
            if not last and s[cur] == '<' and s[cur + 1] == '?':
                end_block(cur-1, cur+2, PAGE_BLOCK_CODE)
                in_leading_space = True
                cur += 2
            elif not last:
                cur += 1
            else:
                end_block(cur, None, None)
                break
        else:
            if not last and s[cur] == '?' and s[cur + 1] == '>':
                end_block(cur-1, cur+2, PAGE_BLOCK_TEXT)
                cur += 2
            elif not last:
                cur += 1
            else:
                end_block(cur, None, None)
                break

    return blocks

# ============================================================================
#  Page generator
# ============================================================================

def cvar_substitute(s, d):
    for key, value in d.items():
        s = s.replace('@' + key + '@', str(value))
    return s

def fix_code_spaces(s):
    def is_spaces_only(s):
        for c in s:
            if not c.isspace():
                return False
        return True

    base_indent = ''
    lines = s.splitlines(False)
    
    # Find first line that contains something and get its indent
    for line in lines:
        if not is_spaces_only(line):
            for c in line:
                if c.isspace():
                    base_indent += c
                else:
                    break
            break

    # Remove base indent from all other lines
    for i in range(0, len(lines)):
        if lines[i].startswith(base_indent):
            lines[i] = lines[i][len(base_indent):]

    return '\n'.join(lines)

def generate_page(template_blocks, content_blocks, cvars):
    template_result = [''] * len(template_blocks)
    content_result = [''] * len(content_blocks)

    print_buffer = ''
    def my_print(s):
        nonlocal print_buffer
        print_buffer += s

    class CvarObject:
        def __getattr__(self, k):
            if k in cvars:
                return cvars[k]
            return None

        def __setattr__(self, k, v):
            nonlocal cvars
            cvars[k] = v

    my_globals = { '__builtins__': __builtins__, 'print': my_print, 'cvars': CvarObject() }

    def run_code_blocks(blocks, result):
        nonlocal print_buffer
        for i in range(0, len(blocks)):
            if blocks[i].type == PAGE_BLOCK_CODE:
                print_buffer = ''
                exec(fix_code_spaces(blocks[i].content), my_globals)
                result[i] = print_buffer

    def run_text_blocks(blocks, result):
        for i in range(0, len(blocks)):
            if blocks[i].type == PAGE_BLOCK_TEXT:
                result[i] = cvar_substitute(blocks[i].content, cvars)

    run_code_blocks(content_blocks, content_result)
    run_code_blocks(template_blocks, template_result)
    run_text_blocks(content_blocks, content_result)
    run_text_blocks(template_blocks, template_result)

    template_text = ''.join(template_result)
    content_text = ''.join(content_result)
    
    return template_text.replace('#content#', content_text)

# ============================================================================
#  Utility functions
# ============================================================================

def split_path(path):
    path_list = []

    while True:
        (tail, head) = os.path.split(path)

        if head:
            path_list.insert(0, head)
            if tail:
                path = tail
            else:
                return path_list
        elif tail:
            path_list.insert(0, tail) 
            return path_list
        else:
            return []
        
# ============================================================================
#  Script body
# ============================================================================

parser = argparse.ArgumentParser(description='LaSG is a lame site generator')
parser.add_argument('-f, --force', dest='force', action='store_true', help='Regenerate every single file, even if source hasn\'t changed')
parser.add_argument('mode', metavar='MODE', type=str, help='Genration mode (release or test)')
args = parser.parse_args()

# -----------------------------------------------------------------------------

generation_mode = 'release'

if args.mode:
    generation_mode = args.mode

# -----------------------------------------------------------------------------

if generation_mode == 'release':
    print('Generating release version...')
elif generation_mode == 'test':
    print('Generating test version...')
else:
    print('Unknown generation mode "' + generation_mode + '". Available generation modes: release, test')
    sys.exit(1)

# -----------------------------------------------------------------------------

config = json.load(open('config.json', 'r'))

# -----------------------------------------------------------------------------

# Load template source
template_source = open('template.html', 'r').read()

# Separate template source
template_blocks = parse_page_blocks(template_source)

# Template modify time
template_mtime = os.path.getmtime('template.html')

# Directory that contains site sources
site_dir = os.path.join(os.getcwd(), 'site')

# Directory that the site will be generated into
out_dir = os.path.join(os.getcwd(), generation_mode)

# -----------------------------------------------------------------------------

for dir_name, dir_names, file_names in os.walk(site_dir):
    for file_name in file_names:
        file_path     = os.path.join(dir_name, file_name)
        file_rel_path = os.path.relpath(file_path, site_dir)
        out_path      = os.path.join(out_dir, file_rel_path)
        out_rel_path  = os.path.relpath(out_path, out_dir)
        file_mtime    = os.path.getmtime(file_path)
        
        # Check if we need to optimize stuff (only optimize in release version)
        optimize = (generation_mode == 'release')

        # Check if we really need to regenrate this file
        needs_update = True

        if not args.force:
            if os.path.exists(out_path):
                out_mtime = os.path.getmtime(out_path)
                
                max_source_mtime = max(file_mtime, template_mtime)

                if max_source_mtime < out_mtime:
                    needs_update = False
            
            if not needs_update:
                print('File "' + out_rel_path + '" is up to date')
                continue

        # Make sure that the directory where we'll create the output file exists
        try:
            os.makedirs(os.path.dirname(out_path))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise e

        if file_name.endswith('~'):
            pass

        elif file_name.endswith('.html') or file_name.endswith('.htm'):
            # Load content source
            content_source = open(file_path, 'r').read()

            # Separate content source
            content_blocks = parse_page_blocks(content_source)

            # Create page config
            page_cvars = copy.deepcopy(config['cvars'])

            # When the content was last modified
            page_cvars['content_mtime'] = file_mtime

            # Find relative page root and data root
            if generation_mode == 'release':
                page_cvars['page_root'] = '/'
                page_cvars['data_root'] = '/data/'
            else:
                num_levels = len(split_path(file_rel_path)) - 1

                page_cvars['page_root'] = '../' * num_levels
                page_cvars['data_root'] = '../' * num_levels + 'data/'

            # Generate the page
            print('Generating page "' + out_rel_path + '"...')
            page = generate_page(template_blocks, content_blocks, page_cvars)

            # Write page
            out_file = open(out_path, 'w')
            out_file.write(page)

        elif optimize and file_name.endswith('.svg'):
            print('Optimizing SVG "' + out_rel_path + '"...')
            subprocess.call(['inkscape', '--vacuum-defs', '-f', file_path, '-l', out_path, ])

        elif optimize and file_name.endswith('.png'):
            print('Optimizing PNG "' + out_rel_path + '"...')
            subprocess.call(['optipng', '-quiet', '-o7', '-zm9', '-out', out_path, file_path ])

        else:
            print('Copying "' + out_rel_path + '"...')
            shutil.copy(file_path, out_path)

# -----------------------------------------------------------------------------

print('Generation completed in: ' + str(datetime.now() - script_start_time))
