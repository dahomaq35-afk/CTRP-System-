import sqlite3

DB_FILE = "ctrp_system.db"


def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            log_channel INTEGER,
            broadcast_channel INTEGER,
            suggestion_channel INTEGER,
            auto_member_role INTEGER,
            auto_bot_role INTEGER
        )
    """)

    con.commit()
    con.close()
