from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from config import Config
from extensions import db, login_manager
from models import User, Auction
from datetime import datetime, timedelta
from models import User, Auction, Bid
from datetime import datetime, timedelta
import secrets



app = Flask(__name__)
app.config.from_object(Config)
app.config["SECRET_KEY"] = secrets.token_hex(16)


db.init_app(app)
login_manager.init_app(app)


@app.route("/")
def home():

    # AUTO CLOSE EXPIRED AUCTIONS
    active_auctions = Auction.query.filter_by(is_active=True).all()

    for auction in active_auctions:

        if datetime.utcnow() >= auction.end_time:

            highest = auction.highest_bid

            if highest:
                auction.winner_id = highest.bidder_id
                auction.current_price = highest.amount
                auction.is_active = False

            else:
                auction.end_time = datetime.utcnow() + timedelta(minutes=5)
                auction.restart_count += 1

    db.session.commit()

    # SEARCH / FILTER
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    sort = request.args.get("sort", "")

    query = Auction.query

    if search:
        query = query.filter(Auction.title.ilike(f"%{search}%"))

    if status == "live":
        query = query.filter_by(is_active=True)

    elif status == "closed":
        query = query.filter_by(is_active=False)

    if category:
        query = query.filter_by(category=category)

    if sort == "price":
        query = query.order_by(Auction.current_price.desc())
    else:
        query = query.order_by(Auction.created_at.desc())

    auctions = query.all()

    return render_template("index.html", auctions=auctions)


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        blocked_names = ["admin", "administrator", "root", "system", "owner"]

        if username.lower() in blocked_names:
            flash("Username not allowed.")
            return redirect(url_for("register"))

        # validations
        if len(username) < 3:
            flash("Username must be at least 3 characters.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("register"))

        existing = User.query.filter_by(username=username).first()

        if existing:
            flash("Username already exists.")
            return redirect(url_for("register"))

        user = User(username=username)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully.")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user is None:
            flash("Account not found.")
            return redirect(url_for("login"))

        if not user.check_password(password):
            flash("Incorrect password.")
            return redirect(url_for("login"))

        login_user(user)
        flash("Logged in successfully.")
        return redirect(url_for("home"))

    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():

    my_auctions = Auction.query.filter_by(
        seller_id=current_user.id
    ).order_by(Auction.created_at.desc()).all()

    won_auctions = Auction.query.filter_by(
        winner_id=current_user.id
    ).order_by(Auction.created_at.desc()).all()

    total_created = len(my_auctions)
    total_won = len(won_auctions)
    total_active = len([a for a in my_auctions if a.is_active])
    total_closed = len([a for a in my_auctions if not a.is_active])

    notifications = []

    for auction in won_auctions:
        notifications.append(
            f"🏆 You won {auction.title} for ${auction.current_price:.2f}"
        )

    for auction in my_auctions:
        if auction.winner:
            notifications.append(
                f"💰 Your item {auction.title} was sold to {auction.winner.username}"
            )

    return render_template(
        "dashboard.html",
        my_auctions=my_auctions,
        won_auctions=won_auctions,
        total_created=total_created,
        total_won=total_won,
        total_active=total_active,
        total_closed=total_closed,
        notifications=notifications
    )


@app.route("/admin")
@login_required
def admin():

    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("home"))

    total_users = User.query.count()
    total_auctions = Auction.query.count()
    total_bids = Bid.query.count()

    active_auctions = Auction.query.filter_by(is_active=True).count()
    closed_auctions = Auction.query.filter_by(is_active=False).count()

    users = User.query.order_by(User.id.desc()).all()

    auctions = Auction.query.order_by(Auction.id.desc()).all()

    bids = Bid.query.order_by(Bid.id.desc()).limit(20).all()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_auctions=total_auctions,
        total_bids=total_bids,
        active_auctions=active_auctions,
        closed_auctions=closed_auctions,
        users=users,
        auctions=auctions,
        bids=bids
    )


@app.route("/admin/delete-user/<int:user_id>")
@login_required
def admin_delete_user(user_id):

    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("home"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Admin cannot delete own account.")
        return redirect(url_for("admin"))

    db.session.delete(user)
    db.session.commit()

    flash("User deleted successfully.")
    return redirect(url_for("admin"))



@app.route("/admin/delete-bid/<int:bid_id>")
@login_required
def admin_delete_bid(bid_id):

    if not current_user.is_admin:
        flash("Access denied.")
        return redirect(url_for("home"))

    bid = Bid.query.get_or_404(bid_id)

    auction = bid.auction

    if not auction.is_active:
        flash("Cannot delete bids from closed auctions.")
        return redirect(url_for("admin"))

    db.session.delete(bid)
    db.session.commit()

    highest = Bid.query.filter_by(
        auction_id=auction.id
    ).order_by(Bid.amount.desc()).first()

    if highest:
        auction.current_price = highest.amount
    else:
        auction.current_price = auction.starting_price

    db.session.commit()

    flash("Bid deleted successfully.")
    return redirect(url_for("admin"))


# ---------------- CREATE AUCTION ----------------
@app.route("/create-auction", methods=["GET", "POST"])
@login_required
def create_auction():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        starting_price = float(request.form["starting_price"])

        auction = Auction(
            title=title,
            description=description,
            category=category,
            starting_price=starting_price,
            current_price=starting_price,
            seller_id=current_user.id,
            end_time=datetime.utcnow() + timedelta(minutes=5)
        )

        db.session.add(auction)
        db.session.commit()

        flash("Auction created successfully.")
        return redirect(url_for("home"))

    return render_template("create_auction.html")

@app.route("/auction/<int:auction_id>", methods=["GET", "POST"])
def auction_page(auction_id):

    auction = Auction.query.get_or_404(auction_id)

    # AUTO CLOSE WHEN TIMER ENDS
    if auction.is_active and datetime.utcnow() >= auction.end_time:

        highest = auction.highest_bid

        if highest:
            auction.winner_id = highest.bidder_id
            auction.current_price = highest.amount
            auction.is_active = False

        else:
            # restart if no bids
            auction.end_time = datetime.utcnow() + timedelta(minutes=5)
            auction.restart_count += 1

        db.session.commit()

    # PLACE BID
    if request.method == "POST":

        if not current_user.is_authenticated:
            flash("Please login first.")
            return redirect(url_for("login"))

        if not auction.is_active:
            flash("Auction already closed.")
            return redirect(url_for("auction_page", auction_id=auction.id))

        amount = float(request.form["amount"])

        # cannot bid on own auction
        if current_user.id == auction.seller_id:
            flash("You cannot bid on your own auction.")
            return redirect(url_for("auction_page", auction_id=auction.id))

        # invalid amount
        if amount <= 0:
            flash("Invalid bid amount.")
            return redirect(url_for("auction_page", auction_id=auction.id))

        # must exceed current price
        if amount <= auction.current_price:
            flash("Bid must be higher than current price.")
            return redirect(url_for("auction_page", auction_id=auction.id))

        # create bid
        bid = Bid(
            amount=amount,
            bidder_id=current_user.id,
            auction_id=auction.id
        )

        auction.current_price = amount

        # ANTI-SNIPING EXTENSION
        remaining = (auction.end_time - datetime.utcnow()).total_seconds()

        if remaining <= 30:
            auction.end_time = auction.end_time + timedelta(seconds=30)
            flash("Late bid detected. Auction extended by 30 seconds!")

        db.session.add(bid)
        db.session.commit()

        flash("Bid placed successfully.")

        return redirect(url_for("auction_page", auction_id=auction.id))

    # LOAD BID HISTORY
    bids = Bid.query.filter_by(
        auction_id=auction.id
    ).order_by(
        Bid.amount.desc(),
        Bid.created_at.asc()
    ).all()

    return render_template(
        "auction.html",
        auction=auction,
        bids=bids
    )

@app.route("/delete-account")
@login_required
def delete_account():

    # Rule 1: active seller
    active_selling = Auction.query.filter_by(
        seller_id=current_user.id,
        is_active=True
    ).first()

    if active_selling:
        flash("Cannot delete account while selling an active auction.")
        return redirect(url_for("dashboard"))

    # Rule 2: currently highest bidder on active auction
    active_auctions = Auction.query.filter_by(is_active=True).all()

    for auction in active_auctions:
        highest = auction.highest_bid

        if highest and highest.bidder_id == current_user.id:
            flash("Cannot delete account while leading an active bid.")
            return redirect(url_for("dashboard"))

    # Delete user
    user = User.query.get(current_user.id)

    logout_user()

    db.session.delete(user)
    db.session.commit()

    flash("Account deleted successfully.")
    return redirect(url_for("home"))


@app.route("/create-secret-admin")
def create_secret_admin():

    existing = User.query.filter_by(username="muktaadmin").first()

    if existing:
        return "Admin already exists."

    admin = User(
        username="muktaadmin",
        is_admin=True
    )

    admin.set_password("VerifyAcc1206")

    db.session.add(admin)
    db.session.commit()

    return "Private admin account created successfully."


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)