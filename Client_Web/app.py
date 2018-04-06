import requests
import datetime
import calendar
import sys
from flask import Flask, render_template, request, flash, redirect, session
from flask_wtf import FlaskForm
from wtforms import Form, StringField, BooleanField, SubmitField, DateField, TextAreaField, SelectField, validators
from functools import wraps

# Initialize
app = Flask(__name__) # root path
app.config['SECRET_KEY'] = 'olen-v2ga-salajane'

#App to debug mode - website changes with refresh
app.debug = True

def on_sisselogitud(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'on_sisselogitud' in session:
             return f(*args, **kwargs)
        else:
            #flash('Juurdepääs keelatud. Palun logi sisse', 'danger')
            return redirect('/sisselogimine')
    return wrap

class SoogikorraMuutmiseVorm(FlaskForm):
    seisundid = requests.get('http://127.0.0.1:5000/soogikorrad/seisundid')
    seisundid_dict = seisundid.json()
    liigid = requests.get('http://127.0.0.1:5000/soogikorrad/liigid')
    liigid_dict = liigid.json()

    # https://wtforms.readthedocs.io/en/stable/crash_course.html#download-installation
    seisund = SelectField('Seisund', coerce=int, choices=[(seisund['kood'], seisund['nimetus']) for seisund in seisundid_dict])
    liik = SelectField('Liik', coerce=int, choices=[(liik['kood'], liik['nimetus']) for liik in liigid_dict])
    kuupaev = DateField('Kuupäev')
    kirjeldus = TextAreaField('Kirjeldus')

class SoogikorraSisestamiseVorm(SoogikorraMuutmiseVorm):
    isikukood = StringField('Isikukood')

class KuupaevaVahemikuVorm(FlaskForm):
    algusekuupaev = DateField('Alguse kuupäev')
    lopukuupaev = DateField('Lõpu kuupäev')

class SisselogimiseVorm(FlaskForm):
    kasutajatunnus = StringField('E-mail')
    parool = StringField('Salasõna')

@app.route('/')
@app.route('/soogikorrad')
@on_sisselogitud
def soogikorrad():
    andmed = requests.get('http://127.0.0.1:5000/soogikorrad', auth=(session['kasutaja'], session['parool']))
    return render_template('soogikorrad.html', soogikorrad=andmed.json())

@app.route('/soogikorrad/lisa', methods = ('GET', 'POST'))
@on_sisselogitud
def lisaSoogikord():

    vorm = SoogikorraSisestamiseVorm()

    if vorm.validate_on_submit():

        payload = {}
        payload['isikukood'] = vorm.isikukood.data
        payload['seisund'] = vorm.seisund.data
        payload['liik'] = vorm.liik.data
        payload['kuupäev'] = '{:%Y-%m-%d}'.format(vorm.kuupaev.data)
        payload['vaikimisi'] = 'True' if vorm.liik.data == 2 else 'False'
        payload['kirjeldus'] = vorm.kirjeldus.data
        # print(payload)
        request = requests.post('http://127.0.0.1:5000/soogikorrad', auth=(session['kasutaja'], session['parool']), json = payload)

        return redirect('/')

    print(vorm.errors)
    return render_template('soogikorra-lisamine.html', vorm=vorm)

@app.route('/soogikorrad/<string:id>/registreerimised')
@on_sisselogitud
def soogikorraRegistreerimised(id="1"):
    andmed = requests.get('http://127.0.0.1:5000/soogikorrad/' + id + '/registreerimised', auth=(session['kasutaja'], session['parool']))
    return render_template('soogikorra-registreerimised.html', soogikorraAndmed=andmed.json())

@app.route('/soogikorrad/muuda/<string:id>', methods = ['POST'])
@on_sisselogitud
def muudaSoogikord(id):

    vorm = SoogikorraMuutmiseVorm()
    if vorm.validate_on_submit():

        payload = {}
        payload['seisund'] = vorm.seisund.data
        payload['liik'] = vorm.liik.data
        payload['kuupäev'] = '{:%Y-%m-%d}'.format(vorm.kuupaev.data)
        payload['vaikimisi'] = 'True' if vorm.liik.data == 2 else 'False'
        payload['kirjeldus'] = vorm.kirjeldus.data
        request = requests.put('http://127.0.0.1:5000/soogikorrad/' + id, auth=(session['kasutaja'], session['parool']), json = payload)

        return redirect('/')

    print(vorm.errors)
    return render_template('soogikorra-muutmine.html', vorm=vorm, id=id)

@app.route('/soogikorrad/kustuta/<string:id>', methods = ['POST'])
@on_sisselogitud
def kustutaSoogikord(id):
    request = requests.delete('http://127.0.0.1:5000/soogikorrad/' + id, auth=(session['kasutaja'], session['parool']))
    return redirect('/')

@app.route('/opilased/registreerimised')
@on_sisselogitud
def opilasteRegistreerimised():

    vorm = KuupaevaVahemikuVorm()

    alguseKuupaev = request.args.get('algusekuupaev')
    if alguseKuupaev is None:
        alguseKuupaev = datetime.date.today().replace(day=1).strftime('%d.%m.%Y')
    lopuKuupaev = request.args.get('lopukuupaev')
    if lopuKuupaev is None:
        lopuKuupaev = datetime.date.today().replace(day=calendar.monthrange(datetime.datetime.today().year, datetime.datetime.today().month)[1]).strftime('%d.%m.%Y')

    opilasteAndmed = requests.get('http://127.0.0.1:5000/opilased/registreerimised?alguse-kuupaev='
    + datetime.datetime.strptime(alguseKuupaev, '%d.%m.%Y').strftime('%Y-%m-%d')
    + '&lopu-kuupaev=' + datetime.datetime.strptime(lopuKuupaev, '%d.%m.%Y').strftime('%Y-%m-%d'),
    auth=(session['kasutaja'], session['parool']))

    soogikorraAndmed = requests.get('http://127.0.0.1:5000/soogikorrad/liigid', auth=(session['kasutaja'], session['parool']))

    return render_template('opilaste-registreerimised.html', opilased=opilasteAndmed.json(), soogikorraLiigid=soogikorraAndmed.json(), vorm=vorm,
    alguseKuupaev=alguseKuupaev, lopuKuupaev = lopuKuupaev)


@app.route('/opilased/<string:id>/registreerimised')
@on_sisselogitud
def opilaseRegistreerimised(id):

    vorm = KuupaevaVahemikuVorm()

    alguseKuupaev = request.args.get('algusekuupaev')
    if alguseKuupaev is None:
        alguseKuupaev = datetime.date.today().replace(day=1).strftime('%d.%m.%Y')
    lopuKuupaev = request.args.get('lopukuupaev')
    if lopuKuupaev is None:
        lopuKuupaev = datetime.date.today().replace(day=calendar.monthrange(datetime.datetime.today().year, datetime.datetime.today().month)[1]).strftime('%d.%m.%Y')

    andmed = requests.get('http://127.0.0.1:5000/opilased/' + id + '/registreerimised?alguse-kuupaev=' + alguseKuupaev + '&lopu-kuupaev=' + lopuKuupaev, auth=(session['kasutaja'], session['parool']))

    return render_template('opilase-registreerimised.html', opilaseAndmed=andmed.json(), vorm=vorm,
    alguseKuupaev=alguseKuupaev, lopuKuupaev = lopuKuupaev)

@app.route('/sisselogimine', methods = ['GET', 'POST'])
def sisselogimine():
    vorm = SisselogimiseVorm()
    if vorm.validate_on_submit():
        payload = {}
        payload['kasutajatunnus'] = vorm.kasutajatunnus.data
        payload['parool'] = vorm.parool.data
        authentication = requests.post('http://127.0.0.1:5000/autentimine', json = payload)
        if authentication.status_code == 202:
            session['on_sisselogitud'] = True
            session['kasutaja'] = payload['kasutajatunnus']
            session['parool'] = payload['parool']
            return redirect('/')
    return render_template('sisselogimine.html', vorm=vorm)

@app.route('/valjalogimine')
def valjalogimine():
    session.clear()
    return redirect('/')

# Only run if it is a main file
if __name__ == '__main__':
    app.run(port=5001)
