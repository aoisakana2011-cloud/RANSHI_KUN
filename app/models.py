from .extensions import db, login_manager
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(200), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    individuals = db.relationship("Individual", backref="owner", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Individual(db.Model):
    __tablename__ = "individuals"
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(120), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle_days = db.Column(db.Float, default=28.0, nullable=False)
    toilet_avg = db.Column(db.Float, default=7.0)
    toilet_duration_avg = db.Column(db.Float, default=0.0)
    input_count = db.Column(db.Integer, default=0)
    last_high_prob_date = db.Column(db.Date, default=date.today)
    base_prob = db.Column(db.Float, default=0.0)
    base_start_date = db.Column(db.Date)
    pending_candidate_start = db.Column(db.Date)
    toilet_time_mean = db.Column(db.Float)
    last_saved = db.Column(db.DateTime, default=datetime.utcnow)

    weights = db.Column(db.JSON)
    params = db.Column(db.JSON)
    models = db.Column(db.JSON)
    
    # 内部予測データ（ホルモンバランスなど）
    internal_predictions = db.Column(db.JSON)

    history_entries = db.relationship("HistoryEntry", backref="individual", lazy="dynamic", cascade="all, delete-orphan")
    provisionals = db.relationship("ProvisionalPeriod", backref="individual", lazy="dynamic", cascade="all, delete-orphan")
    model_metas = db.relationship("ModelMeta", backref="individual", lazy="dynamic", cascade="all, delete-orphan")

class HistoryEntry(db.Model):
    __tablename__ = "history_entries"
    id = db.Column(db.Integer, primary_key=True)
    individual_id = db.Column(db.Integer, db.ForeignKey("individuals.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    gym = db.Column(db.Float, default=0.0)
    absent = db.Column(db.Float, default=0.0)
    pain = db.Column(db.Float, default=0.0)
    headache = db.Column(db.Float, default=0.0)
    tone_pressure = db.Column(db.Float, default=0.0)
    toilet = db.Column(db.Float, default=0.0)
    toilet_time_mean = db.Column(db.Float, default=0.0)
    toilet_duration_mean = db.Column(db.Float, default=0.0)
    raw_score = db.Column(db.Float, default=0.0)
    final_prob = db.Column(db.Float, default=0.0)
    cough = db.Column(db.Float, default=0.0)

    toilet_times = db.Column(db.JSON)
    meds = db.Column(db.JSON)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProvisionalPeriod(db.Model):
    __tablename__ = "provisional_periods"
    id = db.Column(db.Integer, primary_key=True)
    individual_id = db.Column(db.Integer, db.ForeignKey("individuals.id", ondelete="CASCADE"), nullable=False, index=True)
    prov_id = db.Column(db.String(80), unique=True, nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(32), default="active", nullable=False)
    score = db.Column(db.Float)
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ModelMeta(db.Model):
    __tablename__ = "model_metas"
    id = db.Column(db.Integer, primary_key=True)
    individual_id = db.Column(db.Integer, db.ForeignKey("individuals.id", ondelete="CASCADE"), nullable=False, index=True)
    model_type = db.Column(db.String(80), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    version = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)