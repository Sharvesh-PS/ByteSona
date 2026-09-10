import os
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from database import (
    add_post_comment,
    add_post_upvote,
    add_live_news_comment,
    authenticate_user,
    create_user,
    create_user_post,
    chat_with_news_assistant,
    get_chat_history,
    get_articles,
    get_article,
    get_user_by_id,
    get_user_posts,
    refresh_and_get_articles,
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-news-app-secret")


def current_user():
    return get_user_by_id(session.get("user_id"))


@app.context_processor
def inject_current_user():
    return {"current_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.full_path))
        if not current_user():
            session.clear()
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/")
def home():
    return render_template("loading.html")


@app.route("/news")
def news_page():
    error = None
    try:
        articles = refresh_and_get_articles(limit=24)
        
    except Exception as exc:
        error = f"Unable to refresh live news right now: {exc}"
        try:
            articles = get_articles(limit=24)
        except Exception:
            error = f"Unable to refresh live news or load saved articles right now: {exc}"
            articles = []

    featured = articles[0] if articles else None
    latest = articles[1:7] if len(articles) > 1 else []
    more_news = articles[7:] if len(articles) > 7 else []

    
    print(error)
    print("artic",articles)
    print(featured,latest,more_news)
    return render_template(
        "index.html",
        error=error,
        featured=featured,
        latest=latest,
        more_news=more_news,
        total_articles=len(articles),
    )


@app.route("/news/<int:article_id>/comment", methods=["POST"])
@login_required
def comment_live_news(article_id):
    body = request.form.get("body", "").strip()[:1000]
    if body:
        add_live_news_comment(article_id, session["user_id"], body)
    return redirect(request.referrer or url_for("news_page"))

@app.route("/chatai", methods=["GET", "POST"])
@login_required
def chatai():
    user = current_user()
    community_posts = get_user_posts(limit=4)
    starter_prompt = request.args.get("prompt", "").strip()[:3000]
    if starter_prompt:
        chat_with_news_assistant(user, starter_prompt)
        session["chat_first_question_asked"] = True
        return redirect(url_for("chatai"))
    if request.method == "POST":
        user_message = request.form.get("message", "").strip()
        if user_message:
            chat_with_news_assistant(user, user_message)
            session["chat_first_question_asked"] = True
        return redirect(url_for("chatai"))
    return render_template(
        "chatai.html",
        chat_history=get_chat_history(user["id"]),
        show_quick_questions=not session.get("chat_first_question_asked", False),
        community_posts=community_posts,
        starter_prompt="",
    )


@app.route("/api/chatai", methods=["POST"])
@login_required
def chatai_api():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get("message", "")).strip()
   
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    
    reply = chat_with_news_assistant(current_user(), user_message)
    session["chat_first_question_asked"] = True
    return jsonify({"reply": reply})


@app.route("/profile")
@login_required
def profile():
    user = current_user()
    posts = get_user_posts(limit=12, user_id=user["id"])
    return render_template("profile.html", user=user, posts=posts)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")

        if not username or not name or not role or not password:
            error = "All fields are required."
        else:
            user = create_user(username, name, role, password)
        if user:
            session["user_id"] = user["id"]
            session["chat_first_question_asked"] = False
            return redirect(url_for("profile"))
            error = "That username is already taken."

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(username, password)

        if user:
            session["user_id"] = user["id"]
            session["chat_first_question_asked"] = False
            return redirect(request.args.get("next") or url_for("profile"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/community")
def community():
    tagged_article = None
    article_id = request.args.get("article", type=int)
    if article_id:
        tagged_article = get_article(article_id)
    return render_template(
        "community.html",
        posts=get_user_posts(limit=40),
        tagged_article=tagged_article,
    )


@app.route("/community/post", methods=["POST"])
@login_required
def create_post():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    link = request.form.get("link", "").strip()

    if title and description:
        create_user_post(session["user_id"], title, description, link)

    # A tagged repost should return to a clean composer after it is published.
    return redirect(url_for("community"))


@app.route("/community/<int:post_id>/comment", methods=["POST"])
@login_required
def comment_post(post_id):
    body = request.form.get("body", "").strip()
    if body:
        add_post_comment(post_id, session["user_id"], body)

    return redirect(request.referrer or url_for("community"))


@app.route("/community/<int:post_id>/upvote", methods=["POST"])
@login_required
def upvote_post(post_id):
    add_post_upvote(post_id, session["user_id"])
    return redirect(request.referrer or url_for("community"))


if __name__ == "__main__":
    app.run(debug=True)
