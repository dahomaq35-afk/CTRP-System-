import sqlite3

DB_FILE = "ctrp_system.db"


def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()

    # =====================================================
    # إعدادات السيرفر
    # =====================================================

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

    # =====================================================
    # لوقات السيرفر - كل قسم له روم مستقل
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS log_settings (
            guild_id INTEGER PRIMARY KEY,

            member_log INTEGER,
            role_log INTEGER,
            message_log INTEGER,
            channel_log INTEGER,
            warning_log INTEGER,

            ticket_log INTEGER,
            application_log INTEGER,
            moderation_log INTEGER,
            suggestion_log INTEGER,
            notification_log INTEGER,

            voice_log INTEGER,
            level_log INTEGER,
            points_log INTEGER
        )
    """)

    # =====================================================
    # الردود التلقائية
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS replies (
            guild_id INTEGER,
            trigger TEXT,
            response TEXT,
            PRIMARY KEY (guild_id, trigger)
        )
    """)

    # =====================================================
    # الرتب الذاتية
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS self_roles (
            guild_id INTEGER,
            role_id INTEGER,
            PRIMARY KEY (guild_id, role_id)
        )
    """)

    # =====================================================
    # التحذيرات
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            created_at TEXT
        )
    """)

    # =====================================================
    # النقاط
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS points (
            guild_id INTEGER,
            user_id INTEGER,
            points INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    # =====================================================
    # القوانين
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS laws (
            guild_id INTEGER,
            number INTEGER,
            name TEXT,
            text TEXT,
            PRIMARY KEY (guild_id, number)
        )
    """)

    # =====================================================
    # التقديمات
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            application_type TEXT,
            content TEXT,
            status TEXT,
            created_at TEXT
        )
    """)

    # =====================================================
    # إشعارات المنصات
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS streamers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            platform TEXT,
            username TEXT,
            channel_id INTEGER,
            message TEXT,
            last_live INTEGER DEFAULT 0,
            last_content_id TEXT,
            UNIQUE (guild_id, platform, username)
        )
    """)

    # =====================================================
    # نظام اللفلات
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER,
            user_id INTEGER,
            text_xp INTEGER DEFAULT 0,
            voice_xp INTEGER DEFAULT 0,
            total_xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    # =====================================================
    # إعدادات اللفلات
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS level_settings (
            guild_id INTEGER PRIMARY KEY,
            text_xp INTEGER DEFAULT 10,
            voice_xp INTEGER DEFAULT 5,
            base_xp INTEGER DEFAULT 100,
            levelup_message TEXT DEFAULT 'مبروك {user} 🎉 وصلت للمستوى {level}!'
        )
    """)

    # =====================================================
    # اختصارات الأوامر
    # =====================================================

    con.execute("""
        CREATE TABLE IF NOT EXISTS command_shortcuts (
            guild_id INTEGER,
            command_name TEXT,
            shortcut1 TEXT NOT NULL,
            shortcut2 TEXT,
            shortcut3 TEXT,
            PRIMARY KEY (guild_id, command_name)
        )
    """)

    con.commit()
    con.close()
