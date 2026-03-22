"""
EduFun - Educational Video Streaming Platform
A subscription-based app ($0.99/month) with videos for K-12 and University students.
Supports creator channels: any subscriber can start a channel and upload videos (max 10 min).
"""

from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///edufun.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

SUBSCRIPTION_PRICE = 0.99  # USD per month
MAX_VIDEO_DURATION_MINUTES = 10  # Creator-uploaded video limit


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscription = db.relationship("Subscription", backref="user", uselist=False)
    channel = db.relationship("Channel", backref="owner", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_subscribed(self):
        if self.subscription is None:
            return False
        return self.subscription.is_active


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    plan = db.Column(db.String(50), default="monthly")
    price = db.Column(db.Float, default=SUBSCRIPTION_PRICE)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    cancelled = db.Column(db.Boolean, default=False)

    @property
    def is_active(self):
        if self.cancelled:
            return False
        if self.expires_at is None:
            return False
        return datetime.utcnow() < self.expires_at


class Channel(db.Model):
    """A creator channel owned by one user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    slug = db.Column(db.String(80), unique=True, nullable=False)  # URL-friendly name
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    videos = db.relationship("Video", backref="channel", lazy="dynamic",
                             foreign_keys="Video.channel_id")

    @property
    def video_count(self):
        return self.videos.count()


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(500))
    video_url = db.Column(db.String(500))
    duration_minutes = db.Column(db.Integer)
    level = db.Column(db.String(50))        # e.g. "K-2", "3-5", "6-8", "9-12", "university"
    subject = db.Column(db.String(100))     # Math, Science, History, etc.
    grade_label = db.Column(db.String(50))  # Display label
    free_preview = db.Column(db.Boolean, default=False)
    # Creator channel videos
    channel_id = db.Column(db.Integer, db.ForeignKey("channel.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_creator_video(self):
        return self.channel_id is not None


class WatchHistory(db.Model):
    """Records each time a user watches a video — powers recommendations."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=False)
    watched_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="watch_history")
    video = db.relationship("Video", backref="watch_events")


class Ad(db.Model):
    """Sponsored ad paid for by a company to appear on EduFun."""
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(120), nullable=False)
    headline = db.Column(db.String(200), nullable=False)
    body = db.Column(db.String(400))
    cta_text = db.Column(db.String(60), default="Learn More")    # call-to-action
    cta_url = db.Column(db.String(500))
    target_levels = db.Column(db.String(200))  # comma-separated levels, empty = all
    budget_usd = db.Column(db.Float, default=0.0)                # total spend budget
    cost_per_impression = db.Column(db.Float, default=0.05)      # $ per view
    impressions = db.Column(db.Integer, default=0)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def spend(self):
        return round(self.impressions * self.cost_per_impression, 2)

    @property
    def budget_remaining(self):
        return max(0.0, round(self.budget_usd - self.spend, 2))

    @property
    def is_active(self):
        return self.active and self.budget_remaining > 0


SEED_ADS = [
    {
        "company_name": "Brilliant.org",
        "headline": "Master Math and Science Interactively",
        "body": "Thousands of guided problems in math, science, and computer science. Learn by doing.",
        "cta_text": "Try Free",
        "cta_url": "#",
        "target_levels": "",
        "budget_usd": 500.0,
        "cost_per_impression": 0.05,
    },
    {
        "company_name": "Khan Academy",
        "headline": "Free World-Class Education for Everyone",
        "body": "Practice exercises, videos, and a personalized learning dashboard — 100% free.",
        "cta_text": "Start Learning",
        "cta_url": "#",
        "target_levels": "K-2,3-5,6-8",
        "budget_usd": 300.0,
        "cost_per_impression": 0.04,
    },
    {
        "company_name": "Coursera",
        "headline": "Earn University Certificates Online",
        "body": "Take courses from top universities. Add credentials to your resume today.",
        "cta_text": "Explore Courses",
        "cta_url": "#",
        "target_levels": "university",
        "budget_usd": 400.0,
        "cost_per_impression": 0.06,
    },
]


def seed_ads():
    if Ad.query.count() == 0:
        for a in SEED_ADS:
            db.session.add(Ad(**a))
        db.session.commit()


# ---------------------------------------------------------------------------
# Recommendation helpers
# ---------------------------------------------------------------------------

def get_recommendations(user, limit=6):
    """
    Return recommended videos for a user based on their watch history.
    Strategy:
      1. Find the subjects and levels the user watches most.
      2. Return unseen videos from those subjects/levels, newest first.
      3. Fall back to free-preview videos if history is empty.
    """
    if user is None:
        return Video.query.filter_by(free_preview=True).order_by(Video.created_at.desc()).limit(limit).all()

    watched_ids = {wh.video_id for wh in user.watch_history}

    if not watched_ids:
        return Video.query.filter_by(free_preview=True).order_by(Video.created_at.desc()).limit(limit).all()

    # Count subject and level frequency
    from collections import Counter
    subject_counts = Counter()
    level_counts = Counter()
    for wh in user.watch_history:
        if wh.video:
            subject_counts[wh.video.subject] += 1
            level_counts[wh.video.level] += 1

    top_subjects = [s for s, _ in subject_counts.most_common(3)]
    top_levels = [l for l, _ in level_counts.most_common(2)]

    # Preferred: same subject + same level
    recs = (
        Video.query
        .filter(Video.id.notin_(watched_ids))
        .filter(Video.subject.in_(top_subjects))
        .filter(Video.level.in_(top_levels))
        .order_by(Video.created_at.desc())
        .limit(limit)
        .all()
    )

    # Top up with same-subject videos if needed
    if len(recs) < limit:
        existing_ids = {v.id for v in recs} | watched_ids
        more = (
            Video.query
            .filter(Video.id.notin_(existing_ids))
            .filter(Video.subject.in_(top_subjects))
            .order_by(Video.created_at.desc())
            .limit(limit - len(recs))
            .all()
        )
        recs += more

    # Final fallback: newest unwatched videos
    if len(recs) < limit:
        existing_ids = {v.id for v in recs} | watched_ids
        more = (
            Video.query
            .filter(Video.id.notin_(existing_ids))
            .order_by(Video.created_at.desc())
            .limit(limit - len(recs))
            .all()
        )
        recs += more

    return recs


def get_ad_for_level(level=None):
    """Return a random active ad targeting the given level (or any level)."""
    import random
    query = Ad.query.filter_by(active=True)
    candidates = [
        a for a in query.all()
        if a.is_active and (
            not a.target_levels or
            not level or
            level in (a.target_levels or "").split(",")
        )
    ]
    return random.choice(candidates) if candidates else None


def record_watch(user_id, video_id):
    """Record a watch event and increment ad impression if applicable."""
    if user_id:
        db.session.add(WatchHistory(user_id=user_id, video_id=video_id))
        db.session.commit()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def subscription_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        user = db.session.get(User, session["user_id"])
        if not user or not user.is_subscribed:
            flash("A subscription is required to watch this video.", "info")
            return redirect(url_for("subscribe"))
        return f(*args, **kwargs)
    return decorated


def current_user():
    if "user_id" in session:
        return db.session.get(User, session["user_id"])
    return None


# Make current_user available in all templates
@app.context_processor
def inject_user():
    return {"current_user": current_user()}


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_VIDEOS = [
    # K-2
    {"title": "Counting to 100 with Songs", "description": "Fun number songs to help early learners count confidently.", "duration_minutes": 8, "level": "K-2", "subject": "Math", "grade_label": "Kindergarten – Grade 2", "free_preview": True},
    {"title": "Letters and Sounds", "description": "Phonics basics: learn the alphabet and letter sounds.", "duration_minutes": 10, "level": "K-2", "subject": "Language Arts", "grade_label": "Kindergarten – Grade 2", "free_preview": False},
    {"title": "Colors and Shapes Around Us", "description": "Discover colors and geometric shapes in everyday objects.", "duration_minutes": 7, "level": "K-2", "subject": "Science", "grade_label": "Kindergarten – Grade 2", "free_preview": False},
    # 3-5
    {"title": "Introduction to Fractions", "description": "Visual explanations of fractions using pizza and pie charts.", "duration_minutes": 15, "level": "3-5", "subject": "Math", "grade_label": "Grades 3–5", "free_preview": True},
    {"title": "The Water Cycle Explained", "description": "Evaporation, condensation, and precipitation made simple.", "duration_minutes": 12, "level": "3-5", "subject": "Science", "grade_label": "Grades 3–5", "free_preview": False},
    {"title": "Writing Paragraphs", "description": "Topic sentences, supporting details, and conclusions.", "duration_minutes": 14, "level": "3-5", "subject": "Language Arts", "grade_label": "Grades 3–5", "free_preview": False},
    {"title": "Ancient Egypt", "description": "Pyramids, pharaohs, and life along the Nile River.", "duration_minutes": 18, "level": "3-5", "subject": "History", "grade_label": "Grades 3–5", "free_preview": False},
    # 6-8
    {"title": "Pre-Algebra: Variables and Expressions", "description": "Introduction to algebraic thinking with real-world examples.", "duration_minutes": 20, "level": "6-8", "subject": "Math", "grade_label": "Grades 6–8", "free_preview": True},
    {"title": "Cell Biology Basics", "description": "Cell structure, organelles, and the difference between plant and animal cells.", "duration_minutes": 22, "level": "6-8", "subject": "Science", "grade_label": "Grades 6–8", "free_preview": False},
    {"title": "The American Revolution", "description": "Causes, key battles, and the founding of the United States.", "duration_minutes": 25, "level": "6-8", "subject": "History", "grade_label": "Grades 6–8", "free_preview": False},
    {"title": "Reading Comprehension Strategies", "description": "Inference, main idea, and context clue techniques.", "duration_minutes": 16, "level": "6-8", "subject": "Language Arts", "grade_label": "Grades 6–8", "free_preview": False},
    # 9-12
    {"title": "Quadratic Equations", "description": "Factoring, completing the square, and the quadratic formula.", "duration_minutes": 30, "level": "9-12", "subject": "Math", "grade_label": "Grades 9–12", "free_preview": True},
    {"title": "DNA and Genetics", "description": "Mendel's laws, Punnett squares, and gene expression.", "duration_minutes": 28, "level": "9-12", "subject": "Science", "grade_label": "Grades 9–12", "free_preview": False},
    {"title": "World War II: Causes and Consequences", "description": "Global tensions, major events, and the post-war world order.", "duration_minutes": 35, "level": "9-12", "subject": "History", "grade_label": "Grades 9–12", "free_preview": False},
    {"title": "Essay Writing: Thesis and Argument", "description": "Crafting a strong thesis and building a persuasive essay.", "duration_minutes": 24, "level": "9-12", "subject": "Language Arts", "grade_label": "Grades 9–12", "free_preview": False},
    {"title": "Introduction to Chemistry: Atoms & Bonds", "description": "Atomic structure, periodic table trends, and chemical bonding.", "duration_minutes": 32, "level": "9-12", "subject": "Science", "grade_label": "Grades 9–12", "free_preview": False},
    # University
    {"title": "Calculus I: Limits and Derivatives", "description": "Rigorous introduction to differential calculus with proofs.", "duration_minutes": 50, "level": "university", "subject": "Math", "grade_label": "University", "free_preview": True},
    {"title": "Introduction to Microeconomics", "description": "Supply, demand, elasticity, and market structures.", "duration_minutes": 45, "level": "university", "subject": "Economics", "grade_label": "University", "free_preview": False},
    {"title": "Organic Chemistry: Functional Groups", "description": "Nomenclature and reactions of major organic functional groups.", "duration_minutes": 55, "level": "university", "subject": "Science", "grade_label": "University", "free_preview": False},
    {"title": "Data Structures and Algorithms", "description": "Arrays, linked lists, trees, graphs, sorting, and Big-O analysis.", "duration_minutes": 60, "level": "university", "subject": "Computer Science", "grade_label": "University", "free_preview": False},
    {"title": "Modern World History", "description": "Colonialism, industrialization, and the 20th-century global order.", "duration_minutes": 48, "level": "university", "subject": "History", "grade_label": "University", "free_preview": False},
    {"title": "Psychology 101: Human Behavior", "description": "Foundations of behavioral, cognitive, and social psychology.", "duration_minutes": 52, "level": "university", "subject": "Psychology", "grade_label": "University", "free_preview": False},
]


def seed_videos():
    if Video.query.count() == 0:
        for v in SEED_VIDEOS:
            db.session.add(Video(**v))
        db.session.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    levels = [
        {"key": "K-2",        "label": "Kindergarten – Grade 2", "icon": "🌱"},
        {"key": "3-5",        "label": "Grades 3–5",             "icon": "📚"},
        {"key": "6-8",        "label": "Grades 6–8",             "icon": "🔬"},
        {"key": "9-12",       "label": "Grades 9–12",            "icon": "🎓"},
        {"key": "university", "label": "University",             "icon": "🏛️"},
    ]
    user = current_user()
    featured = Video.query.filter_by(free_preview=True).limit(4).all()
    recommendations = get_recommendations(user, limit=6)
    ad = get_ad_for_level()
    return render_template("index.html", levels=levels, featured=featured,
                           recommendations=recommendations, ad=ad)


@app.route("/browse")
@app.route("/browse/<level>")
def browse(level=None):
    all_levels = ["K-2", "3-5", "6-8", "9-12", "university"]
    query = Video.query
    if level and level in all_levels:
        query = query.filter_by(level=level)
    videos = query.order_by(Video.level, Video.subject, Video.title).all()
    subjects = sorted(set(v.subject for v in Video.query.all()))
    return render_template("browse.html", videos=videos, current_level=level, all_levels=all_levels, subjects=subjects)


@app.route("/video/<int:video_id>")
def video_detail(video_id):
    video = db.get_or_404(Video, video_id)
    user = current_user()
    can_watch = video.free_preview or (user and user.is_subscribed)
    if can_watch and user:
        record_watch(user.id, video.id)
    related = Video.query.filter_by(level=video.level).filter(Video.id != video.id).limit(4).all()
    ad = get_ad_for_level(video.level)
    if ad and ad.is_active:
        ad.impressions += 1
        db.session.commit()
    return render_template("video.html", video=video, can_watch=can_watch, related=related, ad=ad)


@app.route("/subscribe", methods=["GET", "POST"])
@login_required
def subscribe():
    user = current_user()
    if user.is_subscribed:
        flash("You already have an active subscription!", "info")
        return redirect(url_for("index"))

    if request.method == "POST":
        # In production: integrate Stripe or another payment processor here.
        # For demo purposes we simulate a successful payment.
        card_number = request.form.get("card_number", "").replace(" ", "")
        if len(card_number) < 13:
            flash("Please enter a valid card number.", "danger")
            return redirect(url_for("subscribe"))

        sub = user.subscription
        if sub is None:
            sub = Subscription(user_id=user.id)
            db.session.add(sub)

        sub.cancelled = False
        sub.started_at = datetime.utcnow()
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        sub.price = SUBSCRIPTION_PRICE
        db.session.commit()

        flash(f"Subscription activated! Enjoy unlimited learning for $0.99/month. 🎉", "success")
        return redirect(url_for("index"))

    return render_template("subscribe.html", price=SUBSCRIPTION_PRICE)


@app.route("/cancel-subscription", methods=["POST"])
@login_required
def cancel_subscription():
    user = current_user()
    if user.subscription:
        user.subscription.cancelled = True
        db.session.commit()
        flash("Your subscription has been cancelled. You can re-subscribe any time.", "info")
    return redirect(url_for("account"))


@app.route("/account")
@login_required
def account():
    user = current_user()
    return render_template("account.html", user=user, price=SUBSCRIPTION_PRICE)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        elif User.query.filter_by(username=username).first():
            flash("That username is already taken.", "danger")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash(f"Welcome to EduFun, {username}! Start watching for just $0.99/month.", "success")
            return redirect(url_for("subscribe"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            flash(f"Welcome back, {user.username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Channel routes
# ---------------------------------------------------------------------------

@app.route("/channels")
def channels_list():
    channels = Channel.query.order_by(Channel.created_at.desc()).all()
    return render_template("channels.html", channels=channels)


@app.route("/channel/<slug>")
def channel_detail(slug):
    channel = Channel.query.filter_by(slug=slug).first_or_404()
    user = current_user()
    can_watch = user and user.is_subscribed
    videos = channel.videos.order_by(Video.created_at.desc()).all()
    return render_template("channel.html", channel=channel, videos=videos, can_watch=can_watch)


@app.route("/my-channel", methods=["GET", "POST"])
@login_required
def my_channel():
    user = current_user()
    if not user.is_subscribed:
        flash("You need an active subscription to create a channel.", "info")
        return redirect(url_for("subscribe"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_channel":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            slug_raw = request.form.get("slug", "").strip().lower()
            slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug_raw).strip("-")

            if not name or not slug:
                flash("Channel name and URL slug are required.", "danger")
            elif len(slug) < 3:
                flash("Slug must be at least 3 characters.", "danger")
            elif Channel.query.filter_by(slug=slug).first():
                flash("That channel URL is already taken.", "danger")
            else:
                channel = Channel(user_id=user.id, name=name, description=description, slug=slug)
                db.session.add(channel)
                db.session.commit()
                flash(f'Channel "{name}" created!', "success")
                return redirect(url_for("my_channel"))

        elif action == "upload_video":
            channel = user.channel
            if not channel:
                flash("Create a channel first.", "danger")
                return redirect(url_for("my_channel"))

            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            level = request.form.get("level", "").strip()
            subject = request.form.get("subject", "").strip()
            duration_str = request.form.get("duration_minutes", "").strip()
            free_preview = request.form.get("free_preview") == "on"

            grade_labels = {
                "K-2": "Kindergarten – Grade 2", "3-5": "Grades 3–5",
                "6-8": "Grades 6–8", "9-12": "Grades 9–12", "university": "University",
            }
            valid_levels = list(grade_labels.keys())

            if not title or not level or not subject or not duration_str:
                flash("Title, level, subject, and duration are required.", "danger")
            elif level not in valid_levels:
                flash("Please select a valid education level.", "danger")
            else:
                try:
                    duration = int(duration_str)
                except ValueError:
                    flash("Duration must be a whole number of minutes.", "danger")
                    return redirect(url_for("my_channel"))

                if duration < 1:
                    flash("Duration must be at least 1 minute.", "danger")
                elif duration > MAX_VIDEO_DURATION_MINUTES:
                    flash(f"Videos must be {MAX_VIDEO_DURATION_MINUTES} minutes or shorter.", "danger")
                else:
                    video = Video(
                        title=title,
                        description=description,
                        level=level,
                        subject=subject,
                        grade_label=grade_labels[level],
                        duration_minutes=duration,
                        free_preview=free_preview,
                        channel_id=channel.id,
                    )
                    db.session.add(video)
                    db.session.commit()
                    flash(f'Video "{title}" published!', "success")
                    return redirect(url_for("my_channel"))

    return render_template("my_channel.html", user=user,
                           max_duration=MAX_VIDEO_DURATION_MINUTES)


@app.route("/my-channel/delete-video/<int:video_id>", methods=["POST"])
@login_required
def delete_channel_video(video_id):
    user = current_user()
    video = db.get_or_404(Video, video_id)
    if not user.channel or video.channel_id != user.channel.id:
        flash("You can only delete your own videos.", "danger")
        return redirect(url_for("my_channel"))
    db.session.delete(video)
    db.session.commit()
    flash("Video deleted.", "info")
    return redirect(url_for("my_channel"))


# ---------------------------------------------------------------------------
# Advertiser routes
# ---------------------------------------------------------------------------

@app.route("/advertise", methods=["GET", "POST"])
def advertise():
    """Self-serve ad purchase page for companies."""
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        headline = request.form.get("headline", "").strip()
        body = request.form.get("body", "").strip()
        cta_text = request.form.get("cta_text", "Learn More").strip()
        cta_url = request.form.get("cta_url", "").strip()
        target_levels = ",".join(request.form.getlist("target_levels"))
        budget_str = request.form.get("budget_usd", "").strip()
        cpi_str = request.form.get("cost_per_impression", "0.05").strip()

        if not company_name or not headline or not budget_str:
            flash("Company name, headline, and budget are required.", "danger")
        else:
            try:
                budget = float(budget_str)
                cpi = float(cpi_str)
            except ValueError:
                flash("Budget and cost-per-impression must be numbers.", "danger")
                return redirect(url_for("advertise"))

            if budget < 10:
                flash("Minimum ad budget is $10.00.", "danger")
            else:
                ad = Ad(
                    company_name=company_name,
                    headline=headline,
                    body=body,
                    cta_text=cta_text or "Learn More",
                    cta_url=cta_url,
                    target_levels=target_levels,
                    budget_usd=budget,
                    cost_per_impression=cpi,
                    active=True,
                )
                db.session.add(ad)
                db.session.commit()
                flash(f"Ad campaign created! Your ad will begin showing immediately.", "success")
                return redirect(url_for("advertise"))

    active_ads = Ad.query.filter_by(active=True).all()
    total_impressions = sum(a.impressions for a in Ad.query.all())
    return render_template("advertise.html", active_ads=active_ads, total_impressions=total_impressions)


@app.route("/recommendations")
@login_required
def recommendations_page():
    user = current_user()
    recs = get_recommendations(user, limit=12)
    ad = get_ad_for_level()
    watched_count = len(user.watch_history)
    return render_template("recommendations.html", recommendations=recs, ad=ad, watched_count=watched_count)


# ---------------------------------------------------------------------------
# App factory / init
# ---------------------------------------------------------------------------

def create_app():
    with app.app_context():
        db.create_all()
        seed_videos()
        seed_ads()
    return app


if __name__ == "__main__":
    create_app()
    app.run(debug=True)
