import email.message
import os
import smtplib
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, ContactForm

'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
app.instance_path = os.environ.get('INSTANCE_PATH', '/instance')
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI', 'sqlite:///blog.db')
db = SQLAlchemy()
db.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    author = relationship('User', back_populates='comments')
    post = relationship('BlogPost', back_populates='comments')


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship('User', back_populates='posts')
    comments = relationship('Comment', back_populates='post')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String(250))
    name = db.Column(db.String(250))
    email = db.Column(db.String(250), unique=True)
    posts = relationship('BlogPost', back_populates='author')
    comments = relationship('Comment', back_populates='author')


with app.app_context():
    db.create_all()


def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.id in [1, 2, 3, 4, 5]:
            return function(*args, **kwargs)
        return abort(403)
    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            comment = Comment(text=form.comment.data,
                              author=current_user,
                              post=requested_post)
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id))
        flash(message='You need to login to post comments, please login.', category='error')
        return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, form=form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(title=form.title.data,
                            subtitle=form.subtitle.data,
                            body=form.body.data,
                            img_url=form.img_url.data,
                            author=current_user,
                            date=date.today().strftime("%B %d, %Y"))
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(title=post.title,
                               subtitle=post.subtitle,
                               img_url=post.img_url,
                               author=post.author,
                               body=post.body)
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        body_message = f'Name: {form.name.data}\n\nEmail: {form.email.data}\n\n\n\n{form.message.data}'
        with smtplib.SMTP('smtp.gmail.com', port=587) as connection:
            connection.starttls()
            connection.login(user=ADMIN_EMAIL, password=os.environ.get('APP_PASSWORD'))
            em = email.message.EmailMessage()
            em['From'] = ADMIN_EMAIL
            em['To'] = ADMIN_EMAIL
            em['Subject'] = form.subject.data
            em.set_content(body_message, subtype="html")
            connection.send_message(em)
        flash(message='Yay! Message have been sent.')
        return redirect(url_for('contact'))
    return render_template("contact.html", form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        user = db.session.query(User).filter_by(email=email).first()
        if not user:
            password = generate_password_hash(password=form.password.data,
                                              method='pbkdf2:sha256',
                                              salt_length=8)
            new_user = User(name=form.name.data,
                            email=email,
                            password=password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
        flash(message='You have already signed up with that email, sign in instead!', category='error')
        return redirect(url_for('login'))
    return render_template("register.html", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter_by(email=form.email.data).first()
        if user:
            if check_password_hash(pwhash=user.password, password=form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash(message='Incorrect password, please try again.', category='error')
                return redirect(url_for('login'))
        flash(message='That email does not exist, please try again.', category='error')
        return redirect(url_for('login'))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
