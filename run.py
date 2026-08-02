"""Entry point for the thesis platform."""
from app import create_app
from app.models import db

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
