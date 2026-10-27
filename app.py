import os
import sqlite3

from flask import Flask, g

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE = os.path.join(app.root_path, "booker.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql") as f:
            db.executescript(f.read().decode("utf-8"))
        count = db.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        if count == 0:
            for name in ["Study Room", "Laundry Machine 1", "Gym"]:
                db.execute("INSERT INTO resources (name) VALUES (?)", (name,))
            db.commit()


init_db()


@app.route("/")
def home():
    return "Hostel Slot Booker is running"


if __name__ == "__main__":
    app.run(debug=True)