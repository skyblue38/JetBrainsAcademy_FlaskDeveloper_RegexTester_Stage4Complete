from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import Column, Integer, String, Boolean, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sys
import os
import re

Base = declarative_base()


class Record(Base):
    __tablename__ = "record"
    id = Column(Integer, primary_key=True)
    regex = Column(String(50))
    text = Column(String(1024))
    result = Column(Boolean)

    def __repr__(self):
        return f"Record(regex={self.regex!r}, text={self.text!r}, result={self.result!r})"


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config.update(SECRET_KEY=os.urandom(42))
engine = create_engine("sqlite:///db.sqlite3?check_same_thread=False", echo=True, future=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


@app.route('/result/<int:row_id>/', methods=["GET", "POST"])
def outcome(row_id):
    try:
        with Session(bind=engine) as session:
            result_list = session.get(Record, row_id)
    except Exception as e:
        flash("Failed to get /result/{}: {}".format(id, e), 'error')
        return redirect(url_for('main_page'))
    return render_template('result.html', rdict=result_list)


@app.route('/history/', methods=["GET"])
def history():
    try:
        with Session(bind=engine) as session:
            stmt = text("SELECT * FROM record ORDER BY id DESC;")
            result_tuples = session.execute(stmt).fetchall()
    except Exception as e:
        flash('Failed to get /history: {}'.format(e), 'error')
        return redirect(url_for('main_page'))
    result_list = [(str(t[0]), t[1], t[2], str(bool(t[3]))) for t in result_tuples]
    return render_template('history.html', rlist=result_list)


@app.route('/', methods=["GET", "POST"])
def main_page():
    if request.method == 'GET':
        return render_template('index.html')
    if request.method == 'POST':
        form_regex = request.form['regex']
        form_text = request.form['text']
        result = False
        try:
            m = re.match(form_regex, form_text)
        except re.error as e:
            flash("Regex error: {}".format(e), 'error')
            return redirect(url_for('main_page'))
        if m is not None:
            result = True
        r = Record(regex=form_regex, text=form_text, result=result)
        try:
            with Session(bind=engine) as session:
                session.add(r)
                session.commit()
                new_id = r.id
        except Exception as e:
            flash("Failed to record history: {}".format(e), 'error')
            return redirect(url_for('main_page'))
        return redirect(url_for('outcome', row_id=new_id))


# don't change the following way to run flask:
if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg_host, arg_port = sys.argv[1].split(':')
        app.run(host=arg_host, port=arg_port)
    else:
        app.run()
