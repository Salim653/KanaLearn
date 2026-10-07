#!/usr/bin/env python3
import os
import sys
import subprocess
import venv

HOME = '/home/Salim653'
VENV_DIR = os.path.join(HOME, 'venv-kanachat')
APP_DIR = os.path.join(HOME, 'kana-chat-flask')

print('Creating virtualenv...')
venv.create(VENV_DIR, with_pip=True, clear=True)

pip = os.path.join(VENV_DIR, 'bin', 'pip')
python = os.path.join(VENV_DIR, 'bin', 'python')
flask = os.path.join(VENV_DIR, 'bin', 'flask')

print('Upgrading pip...')
subprocess.run([pip, 'install', '--quiet', '--upgrade', 'pip'], check=True)

print('Installing requirements...')
subprocess.run([pip, 'install', '--quiet', '-r', os.path.join(APP_DIR, 'requirements.txt')], check=True)

print('Writing .env...')
with open(os.path.join(APP_DIR, '.env'), 'w') as f:
    f.write('FLASK_CONFIG=production\n')
    f.write('SECRET_KEY=98456037b2f2bce4fe4fa07dc29b7800b3bdb5caedbb505f78dc2ae955877364\n')

env = os.environ.copy()
env['FLASK_APP'] = 'wsgi.py'
env['FLASK_CONFIG'] = 'production'

print('Running flask db upgrade...')
subprocess.run([flask, 'db', 'upgrade'], cwd=APP_DIR, env=env, check=True)

print('Running flask seed-content...')
subprocess.run([flask, 'seed-content'], cwd=APP_DIR, env=env, check=True)

print('Creating admin user...')
subprocess.run([flask, 'create-admin', 'admin_admin', 'kanaadmin123'], cwd=APP_DIR, env=env, check=True)

print('=== SETUP DONE ===')
