import os

from app import create_app

app = create_app(os.environ.get("FLASK_CONFIG", "development"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
