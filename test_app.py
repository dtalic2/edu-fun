"""Tests for the EduFun web application."""

import pytest
from app import app as flask_app, db, User, Subscription, Video, SEED_VIDEOS, seed_videos
from datetime import datetime, timedelta


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.app_context():
        db.create_all()
        seed_videos()
    yield flask_app
    with flask_app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(app):
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def subscribed_user(app, registered_user):
    with app.app_context():
        sub = Subscription(
            user_id=registered_user,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.session.add(sub)
        db.session.commit()
    return registered_user


def login(client, email="test@example.com", password="password123"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

def test_index_loads(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"EduFun" in r.data


def test_browse_loads(client):
    r = client.get("/browse")
    assert r.status_code == 200
    assert b"Browse" in r.data


def test_browse_by_level(client, app):
    r = client.get("/browse/math")   # invalid level → shows all
    assert r.status_code == 200
    r2 = client.get("/browse/9-12")
    assert r2.status_code == 200


def test_video_detail_free_preview(client, app):
    with app.app_context():
        video = Video.query.filter_by(free_preview=True).first()
        r = client.get(f"/video/{video.id}")
    assert r.status_code == 200
    assert b"Video player" in r.data


def test_video_detail_locked_without_subscription(client, app, registered_user):
    login(client)
    with app.app_context():
        video = Video.query.filter_by(free_preview=False).first()
        r = client.get(f"/video/{video.id}")
    assert r.status_code == 200
    assert b"Subscribe to Watch" in r.data


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_register_and_login(client, app):
    r = client.post("/register", data={
        "username": "newuser",
        "email": "new@example.com",
        "password": "secure123",
        "confirm_password": "secure123",
    }, follow_redirects=True)
    assert r.status_code == 200
    # After registration, should be redirected to subscribe page
    assert b"Subscribe" in r.data or b"subscription" in r.data.lower()


def test_register_duplicate_email(client, app, registered_user):
    r = client.post("/register", data={
        "username": "other",
        "email": "test@example.com",
        "password": "secure123",
        "confirm_password": "secure123",
    }, follow_redirects=True)
    assert b"already exists" in r.data


def test_register_password_mismatch(client):
    r = client.post("/register", data={
        "username": "u",
        "email": "u@example.com",
        "password": "abc123",
        "confirm_password": "xyz789",
    }, follow_redirects=True)
    assert b"do not match" in r.data


def test_login_invalid(client):
    r = client.post("/login", data={"email": "bad@example.com", "password": "wrong"}, follow_redirects=True)
    assert b"Invalid email or password" in r.data


def test_logout(client, registered_user):
    login(client)
    r = client.get("/logout", follow_redirects=True)
    assert b"logged out" in r.data


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

def test_subscribe_page_requires_login(client):
    r = client.get("/subscribe", follow_redirects=True)
    assert b"log in" in r.data.lower()


def test_subscribe_flow(client, registered_user):
    login(client)
    r = client.post("/subscribe", data={
        "card_number": "4242424242424242",
        "expiry": "12/27",
        "cvc": "123",
    }, follow_redirects=True)
    assert b"Subscription activated" in r.data


def test_subscribe_invalid_card(client, registered_user):
    login(client)
    r = client.post("/subscribe", data={
        "card_number": "123",
        "expiry": "12/27",
        "cvc": "123",
    }, follow_redirects=True)
    assert b"valid card" in r.data


def test_cancel_subscription(client, app, subscribed_user):
    login(client)
    r = client.post("/cancel-subscription", follow_redirects=True)
    assert b"cancelled" in r.data
    with app.app_context():
        sub = Subscription.query.filter_by(user_id=subscribed_user).first()
        assert sub.cancelled is True


def test_subscribed_user_can_watch_locked_video(client, app, subscribed_user):
    login(client)
    with app.app_context():
        video = Video.query.filter_by(free_preview=False).first()
        r = client.get(f"/video/{video.id}")
    assert r.status_code == 200
    assert b"Video player" in r.data


# ---------------------------------------------------------------------------
# Seed data integrity
# ---------------------------------------------------------------------------

def test_seed_videos_loaded(app):
    with app.app_context():
        count = Video.query.count()
    assert count == len(SEED_VIDEOS)


def test_all_levels_have_videos(app):
    levels = ["K-2", "3-5", "6-8", "9-12", "university"]
    with app.app_context():
        for level in levels:
            count = Video.query.filter_by(level=level).count()
            assert count >= 1, f"No videos for level {level}"


def test_free_previews_exist(app):
    with app.app_context():
        count = Video.query.filter_by(free_preview=True).count()
    assert count >= 1


def test_account_page(client, registered_user):
    login(client)
    r = client.get("/account")
    assert r.status_code == 200
    assert b"testuser" in r.data
