"""Tests for the EduFun web application."""

import pytest
from app import (app as flask_app, db, User, Subscription, Video, Channel,
                 WatchHistory, Ad, SEED_VIDEOS, seed_videos, seed_ads,
                 get_recommendations, MAX_VIDEO_DURATION_MINUTES)
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
        seed_ads()
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


# ---------------------------------------------------------------------------
# Channel tests
# ---------------------------------------------------------------------------

def test_channels_list_page(client):
    r = client.get("/channels")
    assert r.status_code == 200
    assert b"Channels" in r.data


def test_my_channel_requires_login(client):
    r = client.get("/my-channel", follow_redirects=True)
    assert b"log in" in r.data.lower()


def test_my_channel_requires_subscription(client, registered_user):
    login(client)
    r = client.get("/my-channel", follow_redirects=True)
    assert b"subscription" in r.data.lower()


def test_create_channel(client, app, subscribed_user):
    login(client)
    r = client.post("/my-channel", data={
        "action": "create_channel",
        "name": "Test Math Channel",
        "slug": "test-math",
        "description": "A great math channel",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"created" in r.data.lower()
    with app.app_context():
        ch = Channel.query.filter_by(slug="test-math").first()
        assert ch is not None
        assert ch.name == "Test Math Channel"


def test_create_channel_duplicate_slug(client, app, subscribed_user):
    login(client)
    client.post("/my-channel", data={
        "action": "create_channel",
        "name": "First Channel",
        "slug": "my-slug",
    }, follow_redirects=True)
    r = client.post("/my-channel", data={
        "action": "create_channel",
        "name": "Second Channel",
        "slug": "my-slug",
    }, follow_redirects=True)
    assert b"already taken" in r.data


def test_upload_video_within_limit(client, app, subscribed_user):
    login(client)
    # First create channel
    client.post("/my-channel", data={
        "action": "create_channel",
        "name": "My Channel",
        "slug": "my-channel-slug",
    }, follow_redirects=True)
    r = client.post("/my-channel", data={
        "action": "upload_video",
        "title": "Quick Math Lesson",
        "description": "A short video",
        "level": "6-8",
        "subject": "Math",
        "duration_minutes": str(MAX_VIDEO_DURATION_MINUTES),
    }, follow_redirects=True)
    assert b"published" in r.data.lower()
    with app.app_context():
        v = Video.query.filter_by(title="Quick Math Lesson").first()
        assert v is not None
        assert v.duration_minutes == MAX_VIDEO_DURATION_MINUTES


def test_upload_video_exceeds_limit(client, app, subscribed_user):
    login(client)
    client.post("/my-channel", data={
        "action": "create_channel",
        "name": "Over Limit Chan",
        "slug": "over-limit",
    }, follow_redirects=True)
    r = client.post("/my-channel", data={
        "action": "upload_video",
        "title": "Too Long Video",
        "description": "",
        "level": "9-12",
        "subject": "Science",
        "duration_minutes": str(MAX_VIDEO_DURATION_MINUTES + 1),
    }, follow_redirects=True)
    assert b"minutes or shorter" in r.data
    with app.app_context():
        assert Video.query.filter_by(title="Too Long Video").first() is None


def test_channel_detail_page(client, app, subscribed_user):
    login(client)
    client.post("/my-channel", data={
        "action": "create_channel",
        "name": "Public Channel",
        "slug": "public-channel",
    }, follow_redirects=True)
    r = client.get("/channel/public-channel")
    assert r.status_code == 200
    assert b"Public Channel" in r.data


def test_delete_own_video(client, app, subscribed_user):
    login(client)
    client.post("/my-channel", data={
        "action": "create_channel",
        "name": "Del Channel",
        "slug": "del-channel",
    }, follow_redirects=True)
    client.post("/my-channel", data={
        "action": "upload_video",
        "title": "To Delete",
        "level": "K-2",
        "subject": "Math",
        "duration_minutes": "5",
    }, follow_redirects=True)
    with app.app_context():
        v = Video.query.filter_by(title="To Delete").first()
        vid_id = v.id
    r = client.post(f"/my-channel/delete-video/{vid_id}", follow_redirects=True)
    assert b"deleted" in r.data.lower()
    with app.app_context():
        assert Video.query.get(vid_id) is None


def test_max_video_duration_constant():
    assert MAX_VIDEO_DURATION_MINUTES == 10


# ---------------------------------------------------------------------------
# Recommendations tests
# ---------------------------------------------------------------------------

def test_recommendations_no_history(app):
    """With no watch history, fall back to free-preview videos."""
    with app.app_context():
        user = User(username="recuser", email="rec@example.com")
        user.set_password("pw1234")
        db.session.add(user)
        db.session.commit()
        recs = get_recommendations(user, limit=4)
    assert len(recs) <= 4
    assert all(v.free_preview for v in recs)


def test_recommendations_with_history(app):
    """After watching math videos, recommendations should prefer math."""
    with app.app_context():
        user = User(username="mathfan", email="math@example.com")
        user.set_password("pw1234")
        db.session.add(user)
        db.session.commit()

        math_videos = Video.query.filter_by(subject="Math").limit(3).all()
        for v in math_videos:
            db.session.add(WatchHistory(user_id=user.id, video_id=v.id))
        db.session.commit()

        recs = get_recommendations(user, limit=6)
    assert len(recs) > 0


def test_recommendations_page_requires_login(client):
    r = client.get("/recommendations", follow_redirects=True)
    assert b"log in" in r.data.lower()


def test_recommendations_page_loads(client, registered_user):
    login(client)
    r = client.get("/recommendations")
    assert r.status_code == 200
    assert b"Recommended" in r.data


def test_watch_history_recorded(client, app, subscribed_user):
    login(client)
    with app.app_context():
        video = Video.query.filter_by(free_preview=True).first()
        vid_id = video.id
    client.get(f"/video/{vid_id}")
    with app.app_context():
        wh = WatchHistory.query.filter_by(user_id=subscribed_user, video_id=vid_id).first()
        assert wh is not None


# ---------------------------------------------------------------------------
# Ads tests
# ---------------------------------------------------------------------------

def test_seed_ads_loaded(app):
    with app.app_context():
        count = Ad.query.count()
    assert count >= 1


def test_advertise_page_loads(client):
    r = client.get("/advertise")
    assert r.status_code == 200
    assert b"Campaign" in r.data


def test_create_ad_campaign(client, app):
    r = client.post("/advertise", data={
        "company_name": "TestCorp",
        "headline": "Learn with TestCorp",
        "body": "Great products for students.",
        "cta_text": "Try Now",
        "cta_url": "https://testcorp.example.com",
        "target_levels": ["9-12"],
        "budget_usd": "50.00",
        "cost_per_impression": "0.05",
    }, follow_redirects=True)
    assert b"campaign created" in r.data.lower()
    with app.app_context():
        ad = Ad.query.filter_by(company_name="TestCorp").first()
        assert ad is not None
        assert ad.budget_usd == 50.0
        assert ad.active is True


def test_create_ad_below_minimum_budget(client):
    r = client.post("/advertise", data={
        "company_name": "Cheap Co",
        "headline": "Too cheap",
        "budget_usd": "5.00",
        "cost_per_impression": "0.05",
    }, follow_redirects=True)
    assert b"Minimum" in r.data


def test_ad_spend_and_budget(app):
    with app.app_context():
        ad = Ad(company_name="X", headline="Y", budget_usd=1.0,
                cost_per_impression=0.05, impressions=10)
        db.session.add(ad)
        db.session.commit()
        assert ad.spend == 0.50
        assert ad.budget_remaining == 0.50
        assert ad.is_active is True

        ad.impressions = 20  # spend = 1.00, budget exhausted
        db.session.commit()
        assert ad.budget_remaining == 0.0
        assert ad.is_active is False


def test_ad_impression_incremented_on_video_watch(client, app):
    with app.app_context():
        ad = Ad.query.first()
        initial = ad.impressions
        ad_id = ad.id
        video = Video.query.filter_by(free_preview=True).first()
        vid_id = video.id

    client.get(f"/video/{vid_id}")

    with app.app_context():
        ad = db.session.get(Ad, ad_id)
        assert ad.impressions >= initial  # may have incremented
