#!/usr/bin/env python3
import os
import subprocess
import venv

HOME = '/home/Salim653'
VENV_DIR = os.path.join(HOME, 'venv-kanachat')
APP_DIR = os.path.join(HOME, 'kana-chat-flask')

print('Removing old virtualenv...')
subprocess.run(['rm', '-rf', VENV_DIR], check=True)

print('Creating virtualenv with Python 3.10...')
subprocess.run(['/usr/bin/python3.10', '-m', 'venv', VENV_DIR], check=True)

pip = os.path.join(VENV_DIR, 'bin', 'pip')

print('Installing requirements...')
subprocess.run([pip, 'install', '--quiet', '-r', os.path.join(APP_DIR, 'requirements.txt')], check=True)

print('=== VENV FIXED ===')
