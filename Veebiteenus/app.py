#!/usr/bin/env python
# -*- coding: utf-8 -*-

# http://flask.pocoo.org/
from flask import Flask, request, jsonify, Response
# http://flask-restplus.readthedocs.io/en/stable/
from flask_restplus import Api, Resource, fields
# https://flask-httpauth.readthedocs.io/en/latest/
from flask_httpauth import HTTPBasicAuth
import datetime
import calendar
import sys
from database import PGDatabase

# Initialize
app = Flask(__name__)
api = Api(app)
auth = HTTPBasicAuth()

# CONFIGURATION
app.config['DEBUG'] = ''

# Payload marshalling
muudetavSoogikord = api.model('Muudetav söögikord', {
    'liik' : fields.String ('Söögikorra liik (nt Hommikusöök, Lõunasöök, Lisaeine)'),
    'kuupäev' : fields.String ('Söögikorra toimumise kuupäev (nt "2018-02-02")'),
    'vaikimisi' : fields.String ('Kas söögikord on vaikimisi valik? (nt "True"/"False")'),
    'kirjeldus' : fields.String ('Söögikorra kirjeldus (nt "6. klass saab lõunatoiduna ekskursioonile kaasa võilevad ja mahla")'),
})

soogikord = api.inherit('Söögikord', muudetavSoogikord, {
    'kasutajatunnus' : fields.String('Söögikorra lisaja kasutajatunnus'),
})

avatudSoogikorrad = api.model('Registreerimiseks avatud söögikorrad', {
    'soogikorra_id' : fields.Integer,
})

opilane = api.model('Õpilane', {
    'isikukood' : fields.String,
    'eesnimi' : fields.String,
    'perekonnanimi' : fields.String,
    'klass' : fields.String
})

opilaseSoogikorrad = api.model('Õpilase söögikorrad', {
    'uid' : fields.String,
    'soogikorrad' : fields.List(fields.Nested(avatudSoogikorrad)),
})

kasutajaAndmed = api.model('Kasutaja andmed', {
    'kasutajatunnus' : fields.String,
    'parool' : fields.String,
})
## End of payload marshalling

# https://flask-httpauth.readthedocs.io/en/latest/
@auth.verify_password
def verify_password(username, password):
    db = PGDatabase()
    db.execute("""SELECT f_on_majandusalajuhataja(%s, %s) as on_majandusalajuhataja;""", (username, password))
    result = db.getRecords()
    return result[0]['on_majandusalajuhataja']

@api.route('/soogikorrad')
class Soogikorrad(Resource):

    @auth.login_required
    def get(self):

        seisund = request.args.get("seisund")

        db = PGDatabase()

        if seisund is not None:
            db.execute("""
                        SELECT sk.soogikorra_id, sk.nimetus as liik, to_char(sk.kuupaev, 'YYYY-MM-DD') as kuupäev, sk.kirjeldus, sk.vaikimisi, sk.seisund
                        FROM soogikordade_koondtabel sk
                        WHERE seisund = %s
                        ORDER BY kuupäev LIMIT 30;""", (seisund,))
        else:
            db.execute("""
                        SELECT sk.soogikorra_id, sk.nimetus as liik, to_char(sk.kuupaev, 'YYYY-MM-DD') as kuupäev, sk.kirjeldus, sk.vaikimisi, sk.seisund
                        FROM soogikordade_koondtabel sk
                        ORDER BY kuupäev LIMIT 100;""", ("",))

        soogikorrad = db.getRecords()
        db.close()

        return soogikorrad

    @auth.login_required
    @api.expect(soogikord, validate=True)
    def post(self):
        # Andmete lugemine POST sõnumist
        content = request.json

        kasutajatunnus = content['kasutajatunnus']
        soogikorra_liik_nimetus = content['liik']
        kuupaev = content['kuupäev']
        vaikimisi = content['vaikimisi']
        kirjeldus = content['kirjeldus']

        db = PGDatabase()

        db.execute("""
                    INSERT INTO Soogikord (isikukood, soogikorra_liik_kood, kuupaev, vaikimisi, kirjeldus)
                    VALUES
                    ((SELECT isikukood FROM tootaja WHERE epost=%s),
                    (SELECT soogikorra_liik_kood FROM soogikorra_liik WHERE nimetus=%s), %s, %s, %s);""",
                    (kasutajatunnus, soogikorra_liik_nimetus, kuupaev, vaikimisi, kirjeldus))
        db.commit()
        db.close()

        return {'Tulemus': 'Soogikord lisatud'}, 201

@api.route('/soogikorrad/seisundid')
class SoogikorraSeisundid(Resource):
    def get(self):
        db = PGDatabase()
        db.execute("""SELECT soogikorra_seisundi_liik_kood as kood, nimetus, COALESCE(kirjeldus, 'puudub') as kirjeldus from Soogikorra_seisundi_liik;""", "")
        seisundid = db.getRecords()
        db.close
        return seisundid

@api.route('/soogikorrad/liigid')
class SoogikorraLiigid(Resource):
    def get(self):
        db = PGDatabase()
        db.execute("""SELECT soogikorra_liik_kood as kood, nimetus, COALESCE(kirjeldus, 'puudub') as kirjeldus from Soogikorra_liik;""", "")
        liigid = db.getRecords()
        db.close
        return liigid

@api.route('/soogikorrad/<int:soogikorra_id>')
class Soogikord(Resource):

    @auth.login_required
    def get(self, soogikorra_id):

        db = PGDatabase()
        db.execute("""
                    SELECT sk.soogikorra_id, t.epost as lisas, sk.nimetus as liik, to_char(sk.kuupaev, 'DD.MM.YYYY') as kuupäev, sk.kirjeldus, sk.vaikimisi, sk.seisund
                    FROM soogikordade_koondtabel sk INNER JOIN tootaja t ON sk.isikukood = t.isikukood
                    WHERE soogikorra_id = %s;""", (soogikorra_id,))

        soogikord = db.getRecords()
        db.close()
        return soogikord[0]

    @auth.login_required
    @api.expect(muudetavSoogikord)
    def put(self, soogikorra_id):
        # Andmete lugemine PUT sõnumist
        content = request.json

        soogikorra_liik_nimetus = content['liik']
        kuupaev = content['kuupäev']
        vaikimisi = content['vaikimisi']
        kirjeldus = content['kirjeldus']

        db = PGDatabase()

        db.execute("""
                    UPDATE Soogikord SET
                    soogikorra_liik_kood = (SELECT soogikorra_liik_kood FROM soogikorra_liik WHERE nimetus=%s),
                    kuupaev = %s,
                    vaikimisi = %s,
                    kirjeldus = %s
                    WHERE soogikorra_id = %s;""",
                    (soogikorra_liik_nimetus, kuupaev, vaikimisi, kirjeldus, soogikorra_id))
        db.commit()
        db.close()

        return {'Tulemus': 'Soogikorra info muudetud'}, 201

    def delete(self, soogikorra_id):
        # Muuta selliselt, et kustutamine toimuks läbi PostgreSQL-i vaate
        db = PGDatabase()
        db.execute("""DELETE FROM Soogikord where soogikorra_id = %s;""", (soogikorra_id,))
        db.commit()
        db.close

@api.route('/soogikorrad/<int:soogikorra_id>/registreerimised')
class SoogikorraRegistreerimised(Resource):

    @auth.login_required
    def get(self, soogikorra_id):

        db = PGDatabase()
        db.execute("""
                    SELECT sk.soogikorra_id, sk.nimetus as liik, to_char(sk.kuupaev, 'DD.MM.YYYY') as kuupäev, sk.kirjeldus, sk.vaikimisi, sk.seisund
                    FROM soogikordade_koondtabel sk
                    WHERE soogikorra_id = %s;""", (soogikorra_id,))

        lunch = db.getRecords()
        lunchDict = lunch[0]

        registrations = []

        db.execute("""SELECT soojate_grupp_kood, nimetus FROM soojate_grupp""", "")
        groups = db.getRecords()


        for group in groups:
            groupDict = {}
            groupDict['sööjate_grupi_nimetus'] = group['nimetus']

            db.execute("""
                        WITH Registreerimised AS (
                          SELECT kr.klass_id, kr.opilasi_registreeritud
                          FROM Klasside_registreeringud kr
                          WHERE kr.soogikorra_id = %s
                        )

                        SELECT k.nimetus, k.opilasi_klassis, COALESCE(r.opilasi_registreeritud, 0) AS opilasi_registreeritud
                        FROM Klasside_opilaste_arv k LEFT JOIN Registreerimised r
                        ON k.klass_id = r.klass_id
                        WHERE k.soojate_grupp_kood = %s;
                        """, (lunchDict['soogikorra_id'], group['soojate_grupp_kood']))

            classes = db.getRecords()

            classList = []
            for c in classes:
                classDict = {}
                classDict['nimetus'] = c['nimetus']
                classDict['õpilasi_klassis'] = c['opilasi_klassis']
                classDict['söögikorrale_registreeritud'] = c['opilasi_registreeritud']
                classList.append(classDict)

            groupDict['klassid'] = classList
            registrations.append(groupDict)

        db.close()

        lunchDict['registreerimised'] = registrations
        return lunchDict

@api.route('/opilased')
class Opilased(Resource):

    @auth.login_required
    def get(self):
        db = PGDatabase()
        db.execute("""SELECT ok.isikukood, ok.eesnimi, ok.perekonnanimi, ok.klass FROM Opilaste_koondtabel ok
                        ORDER BY ok.klass;""", "")
        opilased = db.getRecords()
        db.close
        return opilased

class Opilane(Resource):
    def get(self, isikukood):
        db = PGDatabase()
        db.execute("""SELECT ok.isikukood, ok.eesnimi, ok.perekonnanimi, ok.klass FROM Opilaste_koondtabel ok
                    WHERE ok.isikukood=%s;""", (isikukood, ))
        opilane = db.getRecords()
        db.close
        return opilane

@api.route('/opilased/registreerimised')
class OpilasteRegistreerimised(Resource):

    @auth.login_required
    def get(self):

        try:
            alguseKuupaev = request.args.get('alguse-kuupaev')
        except:
            alguseKuupaev = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')

        try:
            lopuKuupaev = request.args.get('lopu-kuupaev')
        except:
            lopuKuupaev = datetime.date.today().replace(day=calendar.monthrange(datetime.datetime.today().year, datetime.datetime.today().month)[1]).strftime('%Y-%m-%d')

        opilased = Opilased.get(self)

        opilasteRegistreerimised = []
        db = PGDatabase()

        for opilane in opilased:
            db.execute("""SELECT rk.nimetus as liik, COUNT(*) as registreerimisi
                          FROM Registreeringute_koondtabel rk WHERE rk.isikukood = %s
                          AND kuupaev BETWEEN %s AND %s
                          GROUP BY rk.nimetus
                          ORDER BY rk.nimetus LIMIT 100 """, (opilane['isikukood'], alguseKuupaev, lopuKuupaev))
            soogikorrad = db.getRecords()
            opilane['registreerimised'] = soogikorrad
            opilasteRegistreerimised.append(opilane)

        db.close()
        return opilasteRegistreerimised

    @auth.login_required
    # Informatsiooni valideerimine
    @api.expect(opilaseSoogikorrad, validate=True)
    def post(self):
        # Andmete lugemine POST sõnumist
        content = request.json
        uid = content['uid']
        soogikorrad = content['soogikorrad']

        # Andmebaasi ühenduse avamine
        db = PGDatabase()
        db.execute("""SELECT isikukood FROM Opilaste_koondtabel WHERE UID=%s AND opilase_seisundi_liik_kood=1;""", (uid,))
        records = db.getRecords()
        try:
            isikukood = records[0]['isikukood']
        except:
            db.close()
            return Response('Tundmatu kaart!', 403)

        for soogikord in soogikorrad:
            try:
                db.execute("""INSERT INTO Registreering (soogikorra_ID, isikukood, registreerimise_kuupaev) VALUES (%s, %s, %s);""",
                (soogikord['soogikorra_id'], isikukood, datetime.date.today() ))
            except Exception as e:

                if e.pgcode == '23505':
                    soogikorraAndmed = Soogikord.get(self, soogikord['soogikorra_id'])
                    soogikord = soogikorraAndmed['liik']
                    return Response(soogikord + ' on juba registreeritud', 400)
                else:
                    return Response('Tundmatu viga', 400)

        # Andmete kinnitamine
        db.commit()
        # Ühenduse sulgemine
        db.close()

        return Response('Söögikorra registreerimine õnnestus!', 201)

@api.route('/opilased/<string:isikukood>/registreerimised')
class OpilaseRegistreerimised(Resource):

    @auth.login_required
    def get(self, isikukood):

        try:
            alguseKuupaev = request.args.get('alguse-kuupaev')
        except:
            alguseKuupaev = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')

        try:
            lopuKuupaev = request.args.get('lopu-kuupaev')
        except:
            lopuKuupaev = datetime.date.today().replace(day=calendar.monthrange(datetime.datetime.today().year, datetime.datetime.today().month)[1]).strftime('%Y-%m-%d')

        opilane = Opilane.get(self, isikukood)

        opilaseRegistreerimised = opilane[0]

        db = PGDatabase()

        db.execute("""SELECT rk.soogikorra_id, rk.nimetus as liik, to_char(rk.kuupaev, 'YYYY-MM-DD') as kuupäev
                      FROM Registreeringute_koondtabel rk WHERE rk.isikukood = %s
                      AND kuupaev BETWEEN %s AND %s
                      ORDER BY rk.kuupaev, rk.soogikorra_id LIMIT 100 """, (isikukood, alguseKuupaev, lopuKuupaev))
        soogikorrad = db.getRecords()

        db.close()

        opilaseRegistreerimised['registreerimised'] = soogikorrad

        return opilaseRegistreerimised

@api.route('/autentimine')
class Autentimine(Resource):
    @api.expect(kasutajaAndmed, validate=True)
    def post(self):
        content = request.json
        kasutajatunnus = content['kasutajatunnus']
        parool = content['parool']
        db = PGDatabase()
        db.execute("""SELECT f_on_majandusalajuhataja(%s, %s) as success;""", (kasutajatunnus, parool))
        result = db.getRecords()
        if result[0]['success']:
            return Response('Juurdepääs lubatud', 202)
        return Response('Vale parool ja/või kasutajatunnus', 401)

if __name__ == '__main__':
    app.run()
