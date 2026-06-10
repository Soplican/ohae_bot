import pymysql

DB_CONFIG = {
    "host": "65.109.100.181",
    "port": 3306,
    "user": "u31823_irZGCXgv1h",
    "password": "+.t.x*KPW3QPrm15QLdvqsc^P",
    "database": "s31823_MontaroBot",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def init_database():
    conn = get_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_static_ids (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username VARCHAR(255),
            server_name VARCHAR(255),
            static_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.close()


async def save_static_id(user_id, username, server_name, static_id):
    conn = get_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
        INSERT INTO user_static_ids
        (user_id, username, server_name, static_id)
        VALUES (%s, %s, %s, %s)
        """, (
            user_id,
            username,
            server_name,
            static_id
        ))

    conn.close()
