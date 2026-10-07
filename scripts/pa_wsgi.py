import os
import sys

path = '/home/Salim653/kana-chat-flask'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['FLASK_CONFIG'] = 'production'

from app import create_app
application = create_app('production')
