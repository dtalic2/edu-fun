"""
EduFun - Educational Video Streaming Platform
A subscription-based app ($0.99/month) with videos for K-12 and University students.
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    featured = Video.query.filter_by(free_preview=True).limit(4).all()
    return render_template("index.html", levels=levels, featured=featured)


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
    related = Video.query.filter_by(level=video.level).filter(Video.id != video.id).limit(4).all()
    return render_template("video.html", video=video, can_watch=can_watch, related=related)


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
# App factory / init
# ---------------------------------------------------------------------------

def create_app():
    with app.app_context():
        db.create_all()
        seed_videos()
    return app


if __name__ == "__main__":
    create_app()
    app.run(debug=True)
