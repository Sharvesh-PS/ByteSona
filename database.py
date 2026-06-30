from email.utils import parsedate_to_datetime
import os

import psycopg2
import psycopg2.extras
import requests
from news import fetch_news
from werkzeug.security import check_password_hash, generate_password_hash

HFAPI = os.getenv("HFAPI")
API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-base-en-v1.5"

def vector(prompt):
    if not HFAPI:
        return None

    headers = {
    "Authorization": f"Bearer {HFAPI}"
    }

    data = {
        "inputs":prompt
    }

    response = requests.post(API_URL, headers=headers, json=data, timeout=20)
    response.raise_for_status()
    return(response.json())

DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": os.getenv("passdb"),
    "host": "localhost",
    "port": "5433"
}

TOP_K = 5
SIMILARITY_THRESHOLD = 0.5


conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()


def _parse_published_at(value):
    if not value:
        return None

    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _build_content_vector(text):
    try:
        return vector(text)
    except requests.RequestException:
        return None


def initialize_database():
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS live_news (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            link TEXT NOT NULL UNIQUE,
            description TEXT,
            published_at TEXT,
            published_at_ts TIMESTAMPTZ,
            content_vector JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_news_posts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            link TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS post_comments (
            id SERIAL PRIMARY KEY,
            post_id INTEGER NOT NULL REFERENCES user_news_posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS post_upvotes (
            post_id INTEGER NOT NULL REFERENCES user_news_posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (post_id, user_id)
        )
        """
    )
    conn.commit()


def _article_to_row(article, include_vector=True):
    title = (article.get("title") or "").strip()
    description = (article.get("description") or "").strip()
    combined_text = f"{title}\n\n{description}".strip()

    return {
        "title": title,
        "link": (article.get("link") or "").strip(),
        "description": description,
        "published_at": (article.get("published_at") or "").strip(),
        "published_at_ts": _parse_published_at(article.get("published_at")),
        "content_vector": _build_content_vector(combined_text) if include_vector and combined_text else None,
    }


def store_articles(articles):
    initialize_database()

    inserted_count = 0
    for article in articles:
        row = _article_to_row(article, include_vector=False)
        if not row["title"] or not row["link"]:
            continue

        cursor.execute("SELECT 1 FROM live_news WHERE link = %s", (row["link"],))
        if cursor.fetchone():
            continue

        row["content_vector"] = _build_content_vector(
            f"{row['title']}\n\n{row['description']}".strip()
        )

        cursor.execute(
            """
            INSERT INTO live_news (
                title,
                link,
                description,
                published_at,
                published_at_ts,
                content_vector
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (link) DO NOTHING
            """,
            (
                row["title"],
                row["link"],
                row["description"],
                row["published_at"],
                row["published_at_ts"],
                psycopg2.extras.Json(row["content_vector"]),
            ),
        )
        inserted_count += cursor.rowcount

    conn.commit()
    return inserted_count


def get_articles(limit=24):
    initialize_database()
    cursor.execute(
        """
        SELECT title, link, description, published_at
        FROM live_news
        ORDER BY
            published_at_ts DESC NULLS LAST,
            created_at DESC,
            id DESC
        LIMIT %s
        """,
        (limit,),
    )

    return [
        {
            "title": title,
            "link": link,
            "description": description,
            "published_at": published_at,
        }
        for title, link, description, published_at in cursor.fetchall()
    ]


def refresh_and_get_articles(limit=24):
    live_articles = fetch_news(limit=limit)
    store_articles(live_articles)
    return get_articles(limit=limit)


def create_user(username, name, role, password):
    initialize_database()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, name, role, password_hash)
            VALUES (%s, %s, %s, %s)
            RETURNING id, username, name, role
            """,
            (
                username.strip().lower(),
                name.strip(),
                role.strip(),
                generate_password_hash(password),
            ),
        )
        user = cursor.fetchone()
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        return None

    return _user_from_row(user)


def authenticate_user(username, password):
    initialize_database()
    cursor.execute(
        """
        SELECT id, username, name, role, password_hash
        FROM users
        WHERE username = %s
        """,
        (username.strip().lower(),),
    )
    row = cursor.fetchone()
    if not row or not check_password_hash(row[4], password):
        return None

    return _user_from_row(row[:4])


def get_user_by_id(user_id):
    if not user_id:
        return None

    initialize_database()
    cursor.execute(
        """
        SELECT id, username, name, role
        FROM users
        WHERE id = %s
        """,
        (user_id,),
    )
    return _user_from_row(cursor.fetchone())


def create_user_post(user_id, title, description, link=None):
    initialize_database()
    cursor.execute(
        """
        INSERT INTO user_news_posts (user_id, title, description, link)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (
            user_id,
            title.strip(),
            description.strip(),
            (link or "").strip() or None,
        ),
    )
    post_id = cursor.fetchone()[0]
    conn.commit()
    return post_id


def add_post_comment(post_id, user_id, body):
    initialize_database()
    cursor.execute(
        """
        INSERT INTO post_comments (post_id, user_id, body)
        VALUES (%s, %s, %s)
        """,
        (post_id, user_id, body.strip()),
    )
    conn.commit()


def add_post_upvote(post_id, user_id):
    initialize_database()
    cursor.execute(
        """
        INSERT INTO post_upvotes (post_id, user_id)
        VALUES (%s, %s)
        ON CONFLICT (post_id, user_id) DO NOTHING
        """,
        (post_id, user_id),
    )
    conn.commit()


def get_user_posts(limit=20, user_id=None):
    initialize_database()

    params = []
    where_clause = ""
    if user_id is not None:
        where_clause = "WHERE p.user_id = %s"
        params.append(user_id)

    params.append(limit)
    cursor.execute(
        f"""
        SELECT
            p.id,
            p.title,
            p.description,
            p.link,
            p.created_at,
            u.id,
            u.username,
            u.name,
            u.role,
            COUNT(DISTINCT v.user_id) AS upvotes
        FROM user_news_posts p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN post_upvotes v ON v.post_id = p.id
        {where_clause}
        GROUP BY p.id, u.id
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = cursor.fetchall()
    posts = [_post_from_row(row) for row in rows]

    if not posts:
        return []

    post_ids = [post["id"] for post in posts]
    cursor.execute(
        """
        SELECT
            c.id,
            c.post_id,
            c.body,
            c.created_at,
            u.username,
            u.name
        FROM post_comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ANY(%s)
        ORDER BY c.created_at ASC, c.id ASC
        """,
        (post_ids,),
    )

    comments_by_post = {post_id: [] for post_id in post_ids}
    for comment in cursor.fetchall():
        comments_by_post[comment[1]].append(
            {
                "id": comment[0],
                "body": comment[2],
                "created_at": comment[3],
                "username": comment[4],
                "name": comment[5],
            }
        )

    for post in posts:
        post["comments"] = comments_by_post.get(post["id"], [])

    return posts


def _user_from_row(row):
    if not row:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "name": row[2],
        "role": row[3],
    }


def _post_from_row(row):
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "link": row[3],
        "created_at": row[4],
        "author": {
            "id": row[5],
            "username": row[6],
            "name": row[7],
            "role": row[8],
        },
        "upvotes": row[9],
        "comments": [],
    }
