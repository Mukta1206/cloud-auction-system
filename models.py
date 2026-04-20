from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    auctions = db.relationship(
        "Auction",
        foreign_keys="Auction.seller_id",
        backref="seller",
        lazy=True
    )

    won_auctions = db.relationship(
        "Auction",
        foreign_keys="Auction.winner_id",
        backref="winner",
        lazy=True
    )

    bids = db.relationship("Bid", backref="bidder", lazy=True)

    # ADD THESE
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Auction(db.Model):
    __tablename__ = "auctions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default="Other")
    starting_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    restart_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False)

    seller_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    bids = db.relationship("Bid", backref="auction", lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.end_time:
            self.end_time = datetime.utcnow() + timedelta(minutes=5)

    @property
    def highest_bid(self):
        return (
            Bid.query.filter_by(auction_id=self.id)
            .order_by(Bid.amount.desc(), Bid.created_at.asc())
            .first()
        )





class Bid(db.Model):
    __tablename__ = "bids"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bidder_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))