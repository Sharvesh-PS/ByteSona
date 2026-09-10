from email.utils import parsedate_to_datetime
import os

import psycopg2
import psycopg2.extras
import requests
from news import fetch_news
from chatai import analyze_news, news_assistant_response, vector as openrouter_vector
from werkzeug.security import check_password_hash, generate_password_hash

# Previous Hugging Face embedding configuration (kept for reference):
# HFAPI = os.getenv("HFAPI")
# API_URL = "https://router.huggingface.co/hf-inference/models/BAAI/bge-base-en-v1.5"


def vector(prompt):
    """Use the shared OpenRouter embedding implementation for news retrieval."""
    return openrouter_vector(prompt)

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

print(cursor)
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
            sentiment TEXT,
            importance TEXT,
            analysis_reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    # Safe migrations for databases created by earlier versions of the app.
    cursor.execute("ALTER TABLE live_news ADD COLUMN IF NOT EXISTS sentiment TEXT")
    cursor.execute("ALTER TABLE live_news ADD COLUMN IF NOT EXISTS importance TEXT")
    cursor.execute("ALTER TABLE live_news ADD COLUMN IF NOT EXISTS analysis_reason TEXT")
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
        CREATE TABLE IF NOT EXISTS live_news_comments (
            id SERIAL PRIMARY KEY,
            article_id INTEGER NOT NULL REFERENCES live_news(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS chat_messages_user_created_idx ON chat_messages (user_id, created_at DESC)")
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
        analysis = analyze_news(row["title"], row["description"])

        cursor.execute(
            """
            INSERT INTO live_news (
                title,
                link,
                description,
                published_at,
                published_at_ts,
                content_vector,
                sentiment,
                importance,
                analysis_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (link) DO NOTHING
            """,
            (
                row["title"],
                row["link"],
                row["description"],
                row["published_at"],
                row["published_at_ts"],
                psycopg2.extras.Json(row["content_vector"]),
                analysis["sentiment"],
                analysis["importance"],
                analysis["reason"],
            ),
        )
        inserted_count += cursor.rowcount

    conn.commit()
    return inserted_count


def get_articles(limit=24):
    initialize_database()
    cursor.execute(
        """
        SELECT id, title, link, description, published_at, sentiment, importance, analysis_reason
        FROM live_news
        ORDER BY
            published_at_ts DESC NULLS LAST,
            created_at DESC,
            id DESC
        LIMIT %s
        """,
        (limit,),
    )
    articles = []
    for article_id, title, link, description, published_at, sentiment, importance, reason in cursor.fetchall():
        # Backfill saved articles lazily, so every article displayed receives AI analysis.
        if (
            not sentiment
            or not importance
            or reason in {"Analysis is temporarily unavailable.", "AI classification unavailable."}
        ):
            analysis = analyze_news(title, description or "")
            sentiment, importance, reason = analysis["sentiment"], analysis["importance"], analysis["reason"]
            cursor.execute(
                "UPDATE live_news SET sentiment = %s, importance = %s, analysis_reason = %s WHERE id = %s",
                (sentiment, importance, reason, article_id),
            )
        articles.append({
            "id": article_id,
            "title": title,
            "link": link,
            "description": description,
            "published_at": published_at,
            "sentiment": sentiment or "neutral",
            "importance": importance or "mid",
            "analysis_reason": reason or "Analysis is temporarily unavailable.",
            "comments": [],
        })

    if articles:
        article_ids = [article["id"] for article in articles]
        cursor.execute(
            """
            SELECT c.article_id, c.body, c.created_at, u.name, u.username
            FROM live_news_comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.article_id = ANY(%s)
            ORDER BY c.created_at ASC, c.id ASC
            """,
            (article_ids,),
        )
        comments_by_article = {article_id: [] for article_id in article_ids}
        for article_id, body, created_at, name, username in cursor.fetchall():
            comments_by_article[article_id].append({"body": body, "created_at": created_at, "name": name, "username": username})
        for article in articles:
            article["comments"] = comments_by_article[article["id"]]

    conn.commit()
    return articles


def get_article(article_id):
    """Return one saved live-news item for sharing or an AI discussion prompt."""
    initialize_database()
    cursor.execute(
        """
        SELECT id, title, link, description, published_at, sentiment, importance, analysis_reason
        FROM live_news
        WHERE id = %s
        """,
        (article_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    article_id, title, link, description, published_at, sentiment, importance, reason = row
    return {
        "id": article_id,
        "title": title,
        "link": link,
        "description": description or "",
        "published_at": published_at,
        "sentiment": sentiment or "neutral",
        "importance": importance or "mid",
        "analysis_reason": reason or "",
    }


def refresh_and_get_articles(limit=24):
    live_articles = fetch_news(limit=limit)
    store_articles(live_articles)
    return get_articles(limit=limit)


def add_live_news_comment(article_id, user_id, body):
    initialize_database()
    cursor.execute(
        """
        INSERT INTO live_news_comments (article_id, user_id, body)
        SELECT id, %s, %s FROM live_news WHERE id = %s
        """,
        (user_id, body.strip(), article_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_chat_history(user_id, limit=30):
    initialize_database()
    cursor.execute(
        """
        SELECT role, content, created_at
        FROM chat_messages
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """,
        (user_id, limit),
    )
    return [
        {"role": role, "content": content, "created_at": created_at}
        for role, content, created_at in reversed(cursor.fetchall())
    ]


def _flat_vector(value):
    """Normalize provider embedding shapes to a list of numeric values."""
    while isinstance(value, list) and len(value) == 1 and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, list) or not value or not all(isinstance(item, (int, float)) for item in value):
        return None
    return value


def _cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0
    numerator = sum(a * b for a, b in zip(left, right))
    left_size = sum(a * a for a in left) ** 0.5
    right_size = sum(b * b for b in right) ** 0.5
    return numerator / (left_size * right_size) if left_size and right_size else 0


def get_news_context(query, limit=6):
    """Retrieve topical live news; important recent stories remain available as fallback."""
    initialize_database()
    cursor.execute(
        """
        SELECT id, title, description, importance, content_vector
        FROM live_news
        ORDER BY published_at_ts DESC NULLS LAST, created_at DESC, id DESC
        LIMIT 40
        """
    )
    candidates = cursor.fetchall()
    try:
        query_vector = _flat_vector(_build_content_vector(query))
    except Exception:
        query_vector = None

    ranked = []
    for article_id, title, description, importance, content_vector in candidates:
        score = _cosine_similarity(query_vector, _flat_vector(content_vector)) if query_vector else 0
        importance_bonus = {"hot": 0.16, "mid": 0.08, "chill": 0}.get(importance, 0)
        ranked.append((score + importance_bonus, article_id, title, description, importance or "mid"))
    ranked.sort(reverse=True)
    return [
        {"id": article_id, "title": title, "description": description or "", "importance": importance}
        for _, article_id, title, description, importance in ranked[:limit]
    ]


def chat_with_news_assistant(user, message):
    """Persist a user-specific exchange after retrieving current live-news context."""
    message = message.strip()[:3000]
    history = get_chat_history(user["id"], limit=24)
    articles = get_news_context(message)
    reply = news_assistant_response(user["name"], message, history, articles)
    top_events_terms = ("top event", "top headline", "headlines today", "today's headline", "today news", "what is happening", "what's happening", "current summary")
    if any(term in message.lower() for term in top_events_terms) and "/news#article-" not in reply:
        links = "\n".join(f"- [{article['title']}](/news#article-{article['id']})" for article in articles)
        if links:
            reply = f"{reply.rstrip()}\n\n**Open the stories:**\n{links}"
    initialize_database()
    cursor.executemany(
        "INSERT INTO chat_messages (user_id, role, content) VALUES (%s, %s, %s)",
        [(user["id"], "user", message), (user["id"], "assistant", reply)],
    )
    conn.commit()
    return reply


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
