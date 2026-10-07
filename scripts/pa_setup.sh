#!/bin/bash
set -e
cd /home/Salim653
rm -rf kana-chat-flask
if [ ! -d /home/Salim653/venv-kanachat ]; then
  python3.10 -m venv /home/Salim653/venv-kanachat
fi
source /home/Salim653/venv-kanachat/bin/activate
unzip -q -o /home/Salim653/kanachat_deploy.zip -d /home/Salim653
cd /home/Salim653/kana-chat-flask
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
cat > /home/Salim653/kana-chat-flask/.env <<'EOF'
FLASK_CONFIG=production
SECRET_KEY=98456037b2f2bce4fe4fa07dc29b7800b3bdb5caedbb505f78dc2ae955877364
EOF
export FLASK_APP=wsgi.py
export FLASK_CONFIG=production
flask db upgrade
flask seed-content
flask create-admin admin_admin kanaadmin123
echo "=== SETUP DONE ==="
