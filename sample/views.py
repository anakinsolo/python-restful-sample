# coding: utf-8
from pyramid.response import Response as pyResponse
from pyramid.httpexceptions import HTTPNotFound, HTTPFound, HTTPOk
from pyramid.view import view_config,notfound_view_config
from passlib.hash import pbkdf2_sha256
from math import *
from pyramid_mailer.message import Message as Mailer_Message

from sqlalchemy.exc import DBAPIError,IntegrityError

import os,uuid,datetime,re,dateutil.parser,base64,atexit,thread,sys,json, stripe, time, sendgrid
from facebook import GraphAPI,GraphAPIError

from azure.storage.blob import BlobService
from firebase import firebase

from .models import (
     DBSession,
     User,
     Token,
     Session,
     Review,
     Message,
     Job,
     JobApplication,
     JobImage,
     Response,
     FavouriteUser,
     SkillCategory,
     SavedJob,
     Notifications,
     PaymentInfo,
     ReportedJob,
     ComapnyInformation,
     TempJobApplication,
     PaymentRestriction
    )

from . import v1
from constants import ek,aak,aan,default_profile_pic,default_job_pic,firebase_key, skill_keywords, filtering_out_keywords, test_secret_key, tos,sendgrid_key,pc
from utils import get_user_info


##########################################################################################################
## Globals
##########################################################################################################

blob_service = BlobService(account_name=aan, account_key=aak)

fb_auth = firebase.FirebaseAuthentication(firebase_key, 'development@wetaskit.com' ,admin=True)
fb = firebase.FirebaseApplication('https://wtirt.firebaseio.com', fb_auth)

#urllib3.contrib.pyopenssl.inject_into_urllib3()

#Stripe key
stripe.api_key = test_secret_key
client = sendgrid.SendGridClient(sendgrid_key)

##########################################################################################################
## Utilities
##########################################################################################################

def send_welcome_mail(email,name):
    message = sendgrid.Mail()
    message.add_to(email)
    message.set_from('')
    message.set_subject('Welcome to Skillfied!')
    message.set_html(u'<p> Hei <i>'+unicode(name)+u'</i> <br><br>\
                    Olen Tuomas, yksi Skillfiedin perustajista. Halusin laittaa sinulle sähköpostia henkilökohtaisesti ja toivottaa sinut lämpimästi tervetulleeksi Skillfied-yhteisöön.<br><br> \
                    Me muodostamme yhdessä Skillfiedin ja täällä jokaiselle taidolle löytyy töitä. Lisäksi saat apua taitajilta, kun et itse ehdi tehdä kaikkea.<br><br>\
                    Kyseessä on Beta-versio, millä saamme arvokasta palautetta. Juuri sinun mielipiteesi kiinnostaa meitä. Beta-versiossa ei ole kaikkia ominaisuuksia, mutta pääset tutustumaan tärkeimpiin ominaisuuksiin kuten työn antamiseen ja vastaanottamiseen.<br><br> \
                    Auta meitä tekemään palvelusta juuri sinulle sopiva ja anna palautetta helposti sähköpostilla tai Facebookissa-sivullamme. <br><br> \
                    Lämpimästi tervetuloa muuttamaan Suomea, yksi työ kerrallaan. <br><br> \
                    Tuomas Tiilikainen<br>weTask!t Oy - Skillfied\
                    <br><br><br><br>\
                    Hey <i>'+unicode(name)+u'</i> <br><br> \
                    I\'m Tuomas, Co-Founder of Skillfied. I wanted to e-mail you personally and welcome you into Skillfied -community. <br><br> \
                    Together we form Skillfied and for every skill there\'s a job. Also you can receive help if you don\'t have the time to do everything.<br><br> \
                    This is a Beta-version, which we are using to gather your precious feedback. We value your feedback greatly. The beta-version doesn\'t include all the features but with this you can get familiar with our core functionalities as being an employer or employee. <br><br> \
                    Help us perfecting our service by giving us feedbag via e-mail or on our Facebook page. <br><br> \
                    So welcome to to change Finland one job at a time. <br><br> \
                    Tuomas Tiilikainen<br>weTask!t Oy - Skillfied</p>')
    client.send(message)

def send_password_mail(email,password):
    message = sendgrid.Mail()
    message.add_to(email)
    message.set_from('')
    message.set_subject('WeTaskIt: Your Skillfied Password!')   
    message.set_html('Your new password is : <i>'+password+'</i>')
    client.send(message)

def send_verification_mail(email,token):
    message = sendgrid.Mail()
    message.add_to(email)
    message.set_from('')
    message.set_subject('Please verify your email address for Skillfied')
    message.set_html('<p>Tervetuloa Skillfiediin <br><br>\
                    Paina alla olevaa linkkiä vahvistaaksesi sähköpostiosoitteesi <a href="https://api-wetaskit.rhcloud.com/verify_email/'+token+'">Vahvista sähköposti</a> <br><br><br><br> \
                    Welcome to Skillfied <br><br> \
                    Please use this link to verify your email <a href="https://api-wetaskit.rhcloud.com/verify_email/'+token+'">Verify Email</a></p>')
    client.send(message)

def send_reset_mail(mailer,email,token):
    message = sendgrid.Mail()
    message.add_to(email)
    message.set_from('')
    message.set_subject('WeTaskIt: Reset your password')
    message.set_html('<a href="https://api-wetaskit.rhcloud.com/web/reset_password.html?'+token+'">Reset Password</a>')
    client.send(message)

def send_feedback_mail(email,feedback,name):
    message = sendgrid.Mail()
    message.add_to('')
    message.set_from(email)
    message.set_subject(u'Skillfied: Feedbacks from '+unicode(name))
    message.set_html(u'<p>'+unicode(feedback)+u'</p>')
    client.send(message)

def upload_base64_image(base64_string):
    try:
        imgdata = base64.b64decode(base64_string)
        name = str(uuid.uuid4())+'.jpg'

        blob_service.put_block_blob_from_bytes (
        'images',
        name,
        imgdata,
        x_ms_blob_content_type='image/jpeg'
        )

        return 'https://wetaskit.blob.core.windows.net/images/'+name
    except:
        return None

def delete_image(path):
    blob_service.delete_blob('images', path.split('/')[-1])

def get_session(req):
    token = req.json_body.get('wti_token')
    if not token:
        return None  
    s = Session.by_token(token)
    if not s:
        return None
    return s

def get_authenticated_user(req):
    token = req.json_body.get('wti_token')
    
    if not token:
        return None  

    session = DBSession.query(Session).filter(Session.auth_token == token).first()

    if not session:
        return None
    return session.user

responses = {}
for r in DBSession.query(Response).all():
    responses[r.secondary_code] = r.serialize()

def response(code, data=None, wti_token=None, extra='',extra_finn=''):
    res = {}
    if code in responses:
        res['message'] = responses[code].get('message')
        res['code'] = responses[code].get('primary_code')
        res['type'] = responses[code].get('type')
        res['secondary_code'] = code

    res['extra'] = extra
    if wti_token is not None:
        res['wti_token'] = wti_token
    if data is not None:
        res['data'] = data
    if extra_finn is not None:
        res['extra_finn'] = extra_finn
    return res


def get_applicants_info(id, first_name, last_name, profile_pic, thumbs_up, thumbs_down, has_bank_account, is_company):
    u = {}
    u['user_id'] = id
    u['name'] = (first_name if first_name else '')+' '+(last_name if last_name else '')
    u['thumbs_up'] = thumbs_up
    u['thumbs_down'] = thumbs_down
    u['has_bank_account'] = True if has_bank_account else False
    u['is_company'] = True if is_company else False
    if profile_pic:
        u['profile_pic'] = profile_pic
    else:
        u['profile_pic'] = default_profile_pic
    u['review'] = []
    sql = '''
    SELECT a.review, a.thumbs_up, a.thumbs_down, a.created_at
    FROM review as a
    WHERE a.review_for = '''+str(id)+'''
    ORDER BY a.created_at DESC
    LIMIT 2
    '''
    for review,thumbs_up,thumbs_down,created_at in DBSession.execute(sql):
        re = {}
        re['review'] = review
        re['thumbs_up'] = True if thumbs_up else False
        re['thumbs_down'] = True if thumbs_down else False
        u['review'].append(re)
    return u

def distance(device_lat,device_long,job_lat,job_long):

    radius = 6371
    device_lat_angle = radians(float(device_lat))
    job_lat_angle = radians(float(job_lat))

    lat_distance = radians(float(job_lat) - float(device_lat))
    long_distance = radians(float(job_long) - float(device_long))

    a = pow(sin(lat_distance/2),2) + cos(device_lat_angle)*cos(job_lat_angle)*pow(sin(long_distance/2),2)
    c = 2 * atan2(sqrt(a),sqrt(1-a))
    d = radius * c

    return d

def bubbleSort(alist):
    for passnum in range(len(alist)-1,0,-1):
        for i in range(passnum):
            if alist[i].get('distance_to_job')>alist[i+1].get('distance_to_job'):
                temp = alist[i]
                alist[i] = alist[i+1]
                alist[i+1] = temp

##########################################################################################################
## User API
##########################################################################################################
@view_config(route_name='pingping', renderer='json',request_method='GET')
def pingping(request):
    '''
    Ping the server to stop it from idling
    ''' 
    try:
        DBSession.query(Response).all()
    except:
        print 'sonething wrong with db'
    return response(code='S002')

@view_config(route_name=v1+'_user', renderer='json',request_method='POST')
def v1_user_post(request):
    '''
    Create a user , takes email,password as parameters, returns a authentication token
    ''' 

    email = request.json_body.get('email')
    password = request.json_body.get('password')
    first_name = request.json_body.get('first_name')
    last_name = request.json_body.get('last_name')
    last_use = request.json_body.get('last_use')

    if not (email and password and first_name and last_name):
        return response(code='E005',extra='Needs Email, Password, Full Name', extra_finn='Vaatii sähköpostin, salasanan ja koko nimen')
    
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return response(code='E006',extra = 'Invalid Email',extra_finn='Sähköposti ei kelpaa') #Invalid Email

    try:
        user = User(email,password,first_name,last_name)
        user.last_use = last_use

        DBSession.add(user)
        DBSession.flush() #To generate the primary key        

    except IntegrityError:
        return response(code='E007', extra='User already exists',extra_finn='Käyttäjä on jo olemassa') # User already exists


    t = Token.generate(uid = user.id)
    s = Session.generate(user.id)

    send_verification_mail(email,t.token)

    customer = stripe.Customer.create(
        description='stripe customer',
        email=email
    )    
    user.stripe_customer_id = customer.id

    #send_welcome_mail(email,first_name)

    return response(code='S001', wti_token=s.auth_token, extra='Successfully registered',extra_finn='Rekisteröityminen onnistui', data=user.serialize()) #Verification Email Sent

@view_config(route_name=v1+'_user', renderer='json',request_method='PUT')
def v1_user_put(request):
    '''
    Updates the user who is authenticated, takes email,password as parameters, returns a authentication token
    '''
    user = get_authenticated_user(request)

    if not user:
        return response(code='E003', extra='Invalid Token',extra_finn='Virheellinen tunnistus')

    user.first_name = request.json_body.get('first_name') if request.json_body.get('first_name') else user.first_name
    user.last_name = request.json_body.get('last_name') if request.json_body.get('last_name') else user.last_name

    if request.json_body.get('profile_pic'):
        result = upload_base64_image(request.json_body.get('profile_pic'))
        if result:
            user.profile_pic = result

    user.latitude = request.json_body.get('latitude') if request.json_body.get('latitude') else user.latitude
    user.longitude = request.json_body.get('longitude') if request.json_body.get('longitude') else user.longitude

    if 'skills' in request.json_body:
        DBSession.query(SkillCategory).filter(SkillCategory.user_id == user.id).delete()
        DBSession.flush()

        for x in request.json_body.get('skills'):
            try: 
                sc = SkillCategory()
                sc.user_id = user.id
                sc.category_id = x
                DBSession.add(sc)
            except IntegrityError:
                return response(code='E007', extra='Skill exists') # Job application already exists

        DBSession.flush()

    return response(code='S002',wti_token=request.json_body.get('wti_token'), data=user.serialize())

@view_config(route_name=v1+'_user_resend_mail', renderer='json', request_method='POST')
def v1_user_resend_mail(request):

    email = request.json_body.get('email')

    user = User.by_email(email)
    if not user:
        return response(code='E003',extra='User not found',extra_finn='Käyttäjää ei löytynyt')
    t = Token.generate(uid = user.id)

    send_verification_mail(email,t.token)

    return response(code='S002',extra='Success',extra_finn='Valmis')

@view_config(route_name=v1+'_user_get', renderer='json', request_method='POST')
def v1_user_get(request):
    '''
    Gets User data. takes wti_token as input 
    '''

    user = get_authenticated_user(request)
    
    if not user:
        return response(code='E003',extra='Invalid Token',extra_finn='Virheellinen tunnistus')

    id = request.matchdict.get('id')

    if id == 'me':
        id = user.id

    try:
        id = int(id)
    except:
        return response(code='E009',extra='Wrong parameters,userid is integer',extra_finn='Väärät parametrit') #Wrong Parameters, it is supposed to be integer

    u = User.by_id(id)
    if not u:
        return response(code='E014',extra = 'User not found',extra_finn='Käyttäjää ei löydy') # User not found

    data={}
    cards=[]
    banks=[]
    data['cards'] = cards
    data['banks'] = banks
    data['user_profiles'] = u.serialize()

    if u.has_stripe_customer():
        customer = stripe.Customer.retrieve(u.stripe_customer_id)
        for i in customer.sources.all().get('data'):
            c = {}
            c['id']=i.get('id')
            c['type']=i.get('object')
            c['last4']=i.get('last4')
            c['exp_month']=i.get('exp_month')
            c['exp_year']=i.get('exp_year')
            cards.append(c)

    if u.has_stripe_account():
        account = stripe.Account.retrieve(u.stripe_account_id)
        for i in account.external_accounts.all().get('data'):
            b = {}
            b['id']=i.get('id')
            b['type']=i.get('object')
            b['last4']=i.get('last4')
            b['default_for_currency'] = i.get('default_for_currency')
            banks.append(b)
   
    return response(code='S002',wti_token=request.json_body.get('wti_token'), data=data)

@view_config(route_name=v1+'_user_login', renderer='json', request_method='POST')
def v1_user_login(request):
    '''
    Logs in a user, email and password as parameter, returns a wti_token if logged in 
    else returns error with message
    ''' 

    email = request.json_body.get('email')
    password = request.json_body.get('password')
    
    if not (email and password):
        return response('E009',extra = 'Email, Password required',extra_finn='Sähköposti ja salasana vaaditaan')

    user = User.by_email(email)

    if not user:
        return response(code='E015', extra = 'Email not registered', extra_finn='Sähköpostia ei ole rekisteröity') #Not Found

    try:
        a = pbkdf2_sha256.verify(password, user.password)
    except:
        return response(code='E009', extra = 'Wrong Password', extra_finn='Virheellinen salasana')

    if not a:
       return response(code='E016', extra = 'Wrong Password', extra_finn='Virheellinen salasana') #Not Found

    user.latitude = request.json_body.get('latitude') if request.json_body.get('latitude') else user.latitude
    user.longitude = request.json_body.get('longitude') if request.json_body.get('longitude') else user.longitude        
    user.last_use = request.json_body.get('last_use') if request.json_body.get('last_use') else user.last_use

    s = Session.generate(user.id)
    DBSession.add(s)

    return response(code='S002',extra='success',extra_finn='Valmis',wti_token=s.auth_token,data = user.serialize(own_info=True))
    
@view_config(route_name=v1+'_user_logout', renderer='json', request_method='POST')
def v1_user_logout(request):
    '''
    Logs out a user, wti_token as parameter, returns if success or not
    ''' 

    s = get_session(request)
    
    if not s:
        return response(code='E019',extra='Invalid Token',extra_finn='Virheellinen tunnistus')

    #Delete the token from database so that noone can use that token again to get data
    DBSession.delete(s)
    return response(code='S002',extra='Successfully logged out',extra_finn='Valmis')

@view_config(route_name=v1+'_user_verify', renderer='json', request_method='GET')
def v1_user_verify(request):
    '''
    Verify a Email , takes the token as parameter, returns a normal response
    TODO : Return HTML/Normal Response rather than JSON
    ''' 

    token = request.matchdict.get('token')
    if not token:
        return response(code='E019',extra = 'Token not found',extra_finn='Osoitetta ei löydy') #Not Found

    t = Token.by_token(token)
    if not t:
        return response(code='E019', extra = 'Not Found',extra_finn='Osoitetta ei löydy') #Not Found

    if t.expiry < datetime.datetime.utcnow():
        return response(code='E019', extra = 'Expired Link',extra_finn='Osoitetta ei löydy') #Not Found, Expired Link

    if t.type != 1:
        return response(code='E019', extra = 'Not Found 3',extra_finn='Osoitetta ei löydy') #Not Found

    u = t.user
    if not u:
        return response(code='E019',extra='User not found',extra_finn='Käyttäjää ei löydy') #Not Found, Linked user not found
    u.is_verified = True
    #Delete the token to save database space
    DBSession.delete(t)

    #Delete all existing tokens which are expired
    DBSession.query(Token).filter(Token.expiry < datetime.datetime.utcnow()).delete()

    temp_applications = TempJobApplication.by_employee_id(u.id)

    if temp_applications:
        for temp_application in temp_applications:
            job = Job.by_id(temp_application.job_id)
            if not job:
                DBSession.delete(temp_application)
                continue

            if job.expires_on < datetime.datetime.utcnow():
                DBSession.delete(temp_application)
                continue

            try:
                application = JobApplication(temp_application.employee_id,job.id,temp_application.employer_id,job.pay,job.hours,temp_application.comment)
                DBSession.add(application)
                DBSession.flush()
            except IntegrityError:
                DBSession.delete(temp_application)
                continue

            application.wti_fees = application.modified_pay*10
            application.seeker_wti_fees = application.wti_fees
            
            if application.wti_fees < 200:
                application.wti_fees = 200
                application.seeker_wti_fees = application.wti_fees
            else:
                application.wti_fees = application.wti_fees
                application.seeker_wti_fees = application.wti_fees
            #insurrance_fees = #TODO: add insurrance fees
            application.new_modified_pay = application.modified_pay - application.wti_fees/100
            application.total_amount = application.modified_pay*100 + application.wti_fees

            #TyEl fees for the company
            application.employer_tyel = application.wti_fees*1/100
            application.seeker_tyel = round(float(application.wti_fees)*115/10000)

            #Added notification when seeker applied for a job
            text = u.first_name + ' ' + u.last_name + ' ' + u'applied' + ' for ' + job.title
            finn_text = u.first_name + ' ' + u.last_name + ' ' + u'haki työtehtävää'+ ' ' + job.title
            type = u'application'
            notification = Notifications(job.posted_by,text,finn_text,type,job.title,job.posted_by,application.id)
            DBSession.add(notification)

            #Post JobApplication on FireBase
            data = {}
            employer = User.by_id(job.posted_by)
            data['id'] = application.id
            data['employer'] = employer.first_name + " " + employer.last_name
            data['employee'] = u.first_name + " " + u.last_name
            data['status'] = str(application.status) + ',' + str(u.id) + ',' + str(application.id) + ',s' + ',' + (text) + ',' + (finn_text) + ',' + str(application.job_id)
            data['modified'] = datetime.datetime.utcnow().isoformat()

            fb.put('/applications/',application.application_key, data)
            fb.post('/users/'+employer.user_key+'/applications', application.application_key)
            fb.post('/users/'+u.user_key+'/applications', application.application_key)

            DBSession.delete(temp_application)
    return HTTPFound(location='/web/verified.html')

@view_config(route_name=v1+'_user_reset', renderer='json', request_method='POST')
def v1_user_reset(request):
    '''
    Reset Password
    ''' 

    token = request.json_body.get('token')
    new_password = request.json_body.get('new_password')
    
    if not (token and new_password):
        return response(code='E009',extra = 'Wrong Parameters') #Not Found

    t = Token.by_token(token)
    if not t:
        return response(code='E019',extra = 'Not Found',extra_finn='Osoitetta ei löydy') #Not Found

    if t.expiry < datetime.datetime.utcnow():
        return pyResponse('Expired Link') #Not Found, Expired Link

    if t.type != 2:
        return response(code='E019',extra = 'Not Found',extra_finn='Osoitetta ei löydy') #Not Found

    u = t.user
    
    if not u:
        return response(code='E019',extra='Linked user not found',extra_finn='Käyttäjää ei löydy') #Not Found, Linked user not found
    u.reset_password(new_password)

    #Delete ass other Sessions
    DBSession.query(Session).filter(Session.user_id == u.id)

    #Delete the token to save database space
    DBSession.delete(t)

    #Delete all existing tokens which are expired
    DBSession.query(Token).filter(Token.expiry < datetime.datetime.utcnow()).delete()

    #Return Normal response as he will be looking at it in his browser
    return response(code='S002',extra='Successfully Reset Password',extra_finn='Salasanan vaihto onnistui')

@view_config(route_name=v1+'_user_forgot', renderer='json', request_method='POST')
def v1_user_forgot(request):
    '''
    Send Email for forgot password
    ''' 
    email = request.json_body.get('email')
    if not email:
        return response(code='E006', extra = 'No email provided',extra_finn='Sähköpostia ei löydy')
    
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return response(code='E006',extra = 'Invalid Email',extra_finn='Sähköposti ei kelpaa') #Invalid Email

    user = User.by_email(email)

    if not user:
        return response(code='E015', extra = 'Email not registered',extra_finn='Sähköposti ei kelpaa') #Not Found

    t = Token.generate(uid=user.id,type=2)

    send_reset_mail(request.registry['mailer'],email,t.token)
    return response(code='S002', extra='Reset Email Sent', extra_finn='Salasanan vaihdon sähköposti on lähetetty')


@view_config(route_name=v1+'_user_change_password', renderer='json', request_method='POST')
def v1_user_change_password(request):
    '''
    Change Password
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_fin='Et ole vahvistanut tiliäsi')

    new_password = request.json_body.get('password')
    if not new_password:
        return response(code='E009',extra="Password not present")

    user.reset_password(new_password)
    
    #Delete all other Sessions
    DBSession.query(Session).filter(Session.user_id == user.id)

    #Return Normal response as he will be looking at it in his browser
    return response(code='S002',extra='Successfully Reset Password',extra_finn='Salasanan vaihto onnistui')

@view_config(route_name=v1+'_user_feedback', renderer='json', request_method='POST')
def v1_user_send_feedback(request):

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    feedback = request.json_body.get('feedback')
    if not feedback:
        return response(code='E009',extra="Please give feedback",extra_finn='Anna palautetta')

    send_feedback_mail(user.mail,feedback,user.first_name+user.last_name)

    return response(code='S002',extra='Successfully send feedback',extra_finn='Valmis')

##########################################################################################################
## Job API
##########################################################################################################
@view_config(route_name=v1+'_job', renderer='json', request_method='POST')
def v1_job_post(request):
    '''
    Create a Job , takes details required, returns the job id
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    title = request.json_body.get('title')
    desc = request.json_body.get('description')
    pay = request.json_body.get('pay')
    hours = request.json_body.get('hours')
    expires_on = request.json_body.get('expires_on')
    category = request.json_body.get('category')
    latitude = request.json_body.get('latitude')
    longitude = request.json_body.get('longitude')
    location = request.json_body.get('location')

    if expires_on:
        try:
            if dateutil.parser.parse(expires_on) < datetime.datetime.utcnow()+datetime.timedelta(days=0):
                return response(code='E009',extra="Expiry date must be at least one day",extra_finn='Vanhenemispäivän tulee olla vähintään päivän päässä')
        except:
            return response(code='E009',extra="Wrong format expires_on (dd.mm.yyy)",extra_finn='Väärä formaatti (pv.kk.vvvv)')

    ##Validate if enough parameters are there or not
    if not(title and pay and hours and latitude is not None and longitude is not None and category):
        return response(code='E009',extra="All parameters are not present",extra_finn='Täytä kaikki vaadittavat kentät')

    #Now create a job
    j = Job(user.id,title,desc,pay,category,hours,expires_on,latitude,longitude,location)
    DBSession.add(j)
    DBSession.flush()

    if request.json_body.get('images'):
        for i in request.json_body.get('images')[:3]:
            url = upload_base64_image(i)
            if url:
                DBSession.add(JobImage(j.id, url))

    DBSession.flush()

    #TODO SEND NOTIFICATION TO COMPNAY IF PAY > 500

    data = j.serialize()

    return response(code='S002',extra='Successfully Created',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_job', renderer='json',request_method='PUT')
def v1_job_put(request):
    '''
    Update a Job , takes details required, returns the job id
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    id = request.json_body.get('id')

    if not id:
        return response(code='E009',extra='Job ID required',extra_finn='Tehtävän nimike puuttuu')

    j = Job.by_id(id)
    
    if not j:
        return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')

    if j.posted_by != user.id:
        return response(code='E013',extra='Not possible to change job posted by someone else', extra_finn='Sinun ei ole mahdollista muuttaa jonkun muun ilmoittamaa työtehtävää')

    if DBSession.query(JobApplication).filter(JobApplication.job_id == j.id).filter(JobApplication.status >= 4).count() != 0:
        return response(code='E013',extra='Not possible to edit job as it has already started', extra_finn='Sinun ei ole mahdollista muokata aloitettua työtehtävää')

    j.title = request.json_body.get('title') if request.json_body.get('title') else j.title
    j.desc = request.json_body.get('description') if request.json_body.get('description') else j.desc
    j.pay = request.json_body.get('pay') if request.json_body.get('pay') else j.pay
    j.category = request.json_body.get('category') if request.json_body.get('category') else j.category
    j.hours = request.json_body.get('hours') if request.json_body.get('hours') else j.hours
    if request.json_body.get('expires_on'):
        if dateutil.parser.parse(request.json_body.get('expires_on')) < datetime.datetime.utcnow()+datetime.timedelta(days=0):
            return response(code='E009',extra="Expiry date must be at least one day")
        else:
            j.expires_on = dateutil.parser.parse(request.json_body.get('expires_on'))
    j.latitude = request.json_body.get('latitude') if request.json_body.get('latitude') else j.latitude
    j.longitude = request.json_body.get('longitude') if request.json_body.get('longitude') else j.longitude
    j.location_name = request.json_body.get('location') if request.json_body.get('location') else j.location_name

    if request.json_body.get('images'):
        #Delete Images
        for ji in JobImage.by_jobid(id):
            try:
                delete_image(ji.url)
            except:
                pass
            DBSession.delete(ji)

        for i in request.json_body.get('images')[:3]:
            url = upload_base64_image(i)
            if url:
                DBSession.add(JobImage(j.id, url))

    DBSession.flush()

    data = j.serialize()
    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successfully Updated',data=data,extra_finn='Päivittäminen onnistui')


@view_config(route_name=v1+'_job_delete', renderer='json',request_method='POST')
def v1_job_delete(request):
    '''
    Delete a Job , takes id
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    id = request.json_body.get('id')
    if not id:
        return response(code='E009',extra='Job ID required',extra_finn='Tehtävän nimike puuttuu')

    j = Job.by_id(id)
    
    if not j:
        return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')

    if j.posted_by != user.id:
        return response(code='E013',extra='Not possible to delete job posted by someone else',extra_finn='Sinun ei ole mahdollista muuttaa jonkun muun ilmoittamaa työtehtävää')

    #Check if there are any applications that have started
    if DBSession.query(JobApplication).filter(JobApplication.job_id == j.id).filter(JobApplication.status >= 4).count() != 0:
        return response(code='E013',extra='Not possible to delete job as it has already started', extra_finn='Työtä ei voi poistaa, koska tämä on jo aloitettu')

    #Delete Applications Related
    DBSession.query(JobApplication).filter(JobApplication.job_id == j.id).delete()

    #Delete Images
    for ji in JobImage.by_jobid(id):
        try:
            delete_image(ji.url)
        except:
            pass
        DBSession.delete(ji)

    #Delete the job in SavedJob
    for saved_jobs in DBSession.query(SavedJob).filter(SavedJob.job_id == id).all():
        DBSession.delete(saved_jobs)

    #TODO: DO not delete but change the status 
    DBSession.delete(j)

    return response(code='S002',extra='Successfully Deleted', extra_finn='Poistettu')


@view_config(route_name=v1+'_job_report', renderer='json',request_method='POST')
def v1_job_report(request):
    '''
    Report a Job , takes id
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    job_id = request.json_body.get('job_id')
    if not job_id:
        return response(code='E009',extra='Job ID required',extra_finn='Tehtävän nimike puuttuu')

    j = Job.by_id(job_id)
    
    if not j:
        return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')
    
    r = ReportedJob()
    r.job_id = job_id
    r.by_user_id = user.id 
    DBSession.add(r)

    return response(code='S002',extra='Successfully Reported',extra_finn='Ilmiantaminen onnistui')

@view_config(route_name=v1+'_job_images_delete', renderer='json',request_method='POST')
def v1_job_images_delete(request):
    '''
    Delete a Job Image , takes id
    ''' 
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    url = request.json_body.get('image_url')

    sql = '''
    SELECT a.id, a.job_id, a.url FROM job_image as a
    JOIN job as b
    ON a.job_id = b.id
    WHERE b.posted_by = '''+str(user.id)+''' AND a.url = "'''+str(url)+'''"
    GROUP BY a.id
    HAVING (SELECT IFNULL(MAX(job_application.status),0) FROM job_application WHERE job_application.job_id = a.job_id AND job_application.employer_id = '''+str(user.id)+''') <= 4
    LIMIT 1
    '''
    try:
        img_id, img_job_id, img_url = DBSession.execute(sql).fetchone()
    except:
        pass

    DBSession.query(JobImage).filter(JobImage.url == img_url).delete()
    delete_image(url)

    return response(code='S002',extra='Deleted',extra_finn='Poistettu')

@view_config(route_name=v1+'_job_posted', renderer='json',request_method='POST')
def v1_job_posted(request):
    '''
    Gets all the job posted by user
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user',extra_finn='Käyttäjätiliä ei ole vahvistettu')

    sql = '''
    SELECT a.id,a.title, a.pay, a.category, a.created_at,
    (SELECT IFNULL(MAX(job_application.status),0) FROM job_application WHERE job_application.job_id = a.id) as status,
    (SELECT COUNT(*) FROM job_application WHERE job_application.job_id = a.id ORDER BY a.id) as count,
    (SELECT job_application.id from job_application WHERE job_application.status >= 2 AND job_application.job_id = a.id LIMIT 1) as accepted_application,
    (SELECT 
        (CASE WHEN job_application.status < 5 THEN "false" ELSE "true" END)
    FROM job_application WHERE job_application.status >= 5 AND job_application.job_id = a.id)  AS review_done
    FROM job AS a
    WHERE a.posted_by = '''+ str(user.id) +'''
    ORDER BY a.created_at DESC
    '''
    data = {}
    data['is_verified'] = user.is_verified
    data['has_cc'] = user.has_cc
    data['ssn'] = user.ssn if user.ssn else ''
    data['status_0'] = []
    data['status_1'] = []
    data['status_2'] = []
    data['status_3'] = []
    data['status_4'] = []
    data['status_5'] = []
    for id,title,pay,category,created_at,status,num_applicants,accepted_application, review_done in DBSession.execute(sql):
        
        d = {}
        d['job_id'] = id
        d['title'] = title
        d['pay'] = pay
        d['category'] = category
        d['status'] = status
        d['created_at'] = created_at.isoformat()
        d['num_applicants'] = num_applicants
        d['accepted_application'] = accepted_application
        if status == 0:
            data['status_0'].append(d)
        elif status == 1:
            data['status_1'].append(d)
        elif status == 2:
            data['status_2'].append(d)
        elif status == 3:
            data['status_3'].append(d)
        elif status == 4:
            data['status_4'].append(d)
        elif status == 5:
            data['status_5'].append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data = data)


@view_config(route_name=v1+'_job_get', renderer='json',request_method='POST')
def v1_job_get(request):
    '''
        Get the job with id
    ''' 
   
    user = get_authenticated_user(request)
    
    user_id = 99999 #Hack to fake the userid if not logged in
    if user:
        user_id = user.id

    jobid = request.matchdict.get('id')

    j = Job.by_id(jobid)
    if not j:
        return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')

    if j.posted_by == user_id:

        sql = '''
        SELECT COUNT(a.employee_id) FROM job_application as a
        WHERE a.job_id = '''+str(jobid)+''' 
        '''
        num_applicants, = DBSession.execute(sql).fetchone()
        job = j.serialize()

        job['num_applicants'] = num_applicants
        return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data = job )


    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data = j.serialize() )


@view_config(route_name=v1+'_jobcards', renderer='json',request_method='POST')
def v1_jobcards(request):
    '''
    Gets all the jobcards according to lat and long
    ''' 
    user = get_authenticated_user(request)

    user_id = 99999 #Hack to fake the userid if not logged in
    verified = False
    if user:
        user_id = user.id
        verified = user.is_verified

    left_top_lat = request.json_body.get('left_top_lat')
    left_top_long = request.json_body.get('left_top_long')
    right_bottom_lat = request.json_body.get('right_bottom_lat')
    right_bottom_long = request.json_body.get('right_bottom_long')
    device_lat = request.json_body.get('device_lat')
    device_long = request.json_body.get('device_long')

    page_num = request.json_body.get('page',0)

    category_list = request.json_body.get('category_list')
    keyword_list = request.json_body.get('keyword_list')

    if not (left_top_lat is not None and left_top_long is not None and right_bottom_lat is not None and right_bottom_long is not None):
        return response(code='E009',extra='Missing parameters')


    sql = '''
    SELECT a.id,a.title,a.pay,a.posted_by,a.expires_on,a.category,a.created_at, a.latitude, a.longitude, a.location_name ,GROUP_CONCAT(b.url),c.first_name, c.last_name,c.profile_pic,c.thumbs_up_employer,c.thumbs_down_employer, c.company_id,
    (SELECT COUNT(*) FROM job_application WHERE job_application.job_id = a.id AND job_application.employee_id = '''+str(user_id)+''') as has_applied,
    (SELECT IFNULL(MAX(job_application.status),0) FROM job_application WHERE job_application.job_id = a.id) as appl_status,
    (
        '''
    if keyword_list:
        sql = sql + '''
        + 
        '''.join(['''((LENGTH(CONCAT(LOWER(a.title),LOWER(a.desc))) - LENGTH(REPLACE(CONCAT(LOWER(a.title),LOWER(a.desc)),"'''+unicode(key.lower())+'''", ""))) / LENGTH("'''+unicode(key.lower())+'''"))''' for key in keyword_list])
    else:
        sql = sql + '''0'''

    sql = sql +'''
    ) AS occurrences
    FROM job AS a 
    LEFT JOIN job_image AS b 
    ON
    a.id = b.job_id
    LEFT JOIN user as c
    ON
    a.posted_by = c.id
    WHERE 
    (a.latitude BETWEEN '''+str(left_top_lat)+''' AND '''+str(right_bottom_lat)+''') 
    AND 
    (a.longitude BETWEEN '''+str(left_top_long)+''' AND '''+str(right_bottom_long)+''') 
    AND a.posted_by != '''+str(user_id)
    
    if category_list:
        sql = sql + '''
        AND a.category IN ('''+ ','.join([str(a) for a in category_list]) + ''') '''

    sql = sql + '''
    GROUP BY a.id
    HAVING 
    has_applied < 1
    AND 
    appl_status < 2'''

    if keyword_list:
       sql = sql + '''
       AND occurrences >= 1
       ORDER BY occurrences AND a.created_at DESC '''
    else:
        sql = sql + ''' ORDER BY a.created_at DESC '''
    if page_num is not None:
        sql = sql + ''' LIMIT '''+str(page_num*25)+''', 25'''

    data = []
    for id, title, pay, posted_by, expires_on, j_category,created_at, latitude, longitude,job_location_name ,urls, first_name, last_name, profile_pic,thumbs_up_employer,thumbs_down_employer, company_id, has_applied, appl_status, occurrences in DBSession.execute(sql):
        if not id:
            continue

        d = {}
        d['job_id'] = id
        d['title'] = title
        d['pay'] = pay
        d['expires_on'] = expires_on.isoformat() if expires_on else ''
        d['category'] = j_category
        d['latitude'] = latitude
        d['longitude'] = longitude
        if device_lat is not None and device_long is not None:
            d['distance_to_job'] = round(distance(device_lat,device_long,latitude,longitude),2)
        d['location_name'] = job_location_name if job_location_name else ''
        d['employer'] = get_user_info(posted_by,first_name,last_name,profile_pic,thumbs_up_employer,thumbs_down_employer, True if company_id else False)
        data.append(d)
    bubbleSort(data)
    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data = data)


@view_config(route_name=v1+'_job_applicants', renderer='json',request_method='POST')
def v1_job_applicants(request):
    '''
    Get Job Applicants
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

   
    jobId = request.matchdict.get('jobId')

    job = Job.by_id(jobId)

    if not job:
        return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')

    if job.posted_by != user.id:
        return response(code='E013',extra='This is not a job you have posted',extra_finn='Et ole antanut tätä tehtävää')

    sql= '''
    SELECT a.id as a_id,a.comment, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.thumbs_up, c.thumbs_down,c.stripe_account_id, c.company_id,d.title,d.desc,d.pay, d.category,
    (SELECT COUNT(*) FROM job_application JOIN job ON job_application.job_id = job.id WHERE job_application.status >= 4 AND job.category = d.category AND job_application.employee_id = c.id ) AS cnt
    FROM 
    job_application AS a
    JOIN user AS c
    ON
    a.employee_id = c.id
    JOIN job AS d
    ON
    a.job_id = d.id
    WHERE
    a.job_id = '''+str(job.id)+'''
    '''

    data = {}
    data['job_title'] = job.title
    data['job_desc'] = job.desc
    data['job_pay'] = job.pay
    data['job_hours'] = job.hours
    data['job_category'] = job.category
    data['applicants'] = []
    for appl_id,appl_comment,user_id, first_name, last_name, profile_pic, social_id, thumbs_up, thumbs_down,bank_account, company_id,job_title,job_desc,job_pay,category, num_completed in DBSession.execute(sql):

        d = {}
        d['employee'] = get_applicants_info(user_id,first_name,last_name,profile_pic, thumbs_up, thumbs_down,bank_account,True if company_id else False)
        d['application_id'] = appl_id
        d['comment'] = appl_comment
        d['num_completed'] = num_completed
        data['applicants'].append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data=data)

##########################################################################################################
## Application API
##########################################################################################################

@view_config(route_name=v1+'_application', renderer='json',request_method='POST')
def v1_application_post(request):
    '''
    Create application for a job
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:

        jobId = request.json_body.get('job_id')
        comment = request.json_body.get('comment')

        job = Job.by_id(jobId)
        if not job:
            return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')

        if job.expires_on < datetime.datetime.utcnow():
            return response(code='E013',extra='This job has expired',extra_finn='Tämä työ on vanhentunut')
        try:                
            temp_application = TempJobApplication(user.id, job.id, job.posted_by,comment)
            DBSession.add(temp_application)
            DBSession.flush()
        except IntegrityError:
            return response(code='E007', extra='You have applied for this job once',extra_finn='Olet hakenut tähän tehtävään')
        

        return response(code='E012',extra='The application has been saved',extra_finn='Hakemus on tallennettu')



    jobId = request.json_body.get('job_id')
    modified_pay = request.json_body.get('modified_pay')
    modified_hours = request.json_body.get('modified_hours')
    comment = request.json_body.get('comment')


    job = Job.by_id(jobId)

    if not job:
        return response(code='E017',extra='Job not found',extra_finn='Työtehtävää ei löydy')

    if job.posted_by == user.id:
        return response(code='E013',extra='You can not apply to your own job',extra_finn='Et voi hakea omaan työtehtävään')

    if job.expires_on < datetime.datetime.utcnow():
        return response(code='E013',extra='This job has expired',extra_finn='Tämä työ on vanhentunut')

    try:
        application = JobApplication(user.id,jobId,job.posted_by,(modified_pay if modified_pay else job.pay),(modified_hours if modified_hours else job.hours) ,comment)
        DBSession.add(application)
        DBSession.flush()
    except IntegrityError:
        return response(code='E007', extra='You have applied for this job once',extra_finn='Olet jo hakenut tähän') # Job application already exists



    DBSession.query(SavedJob).filter(SavedJob.job_id == jobId, SavedJob.user_id == user.id).delete()

    #Add fees to application
    #application.stripe_fees = int(application.modified_pay*2.9+30)
    application.wti_fees = application.modified_pay*10
    application.seeker_wti_fees = application.wti_fees
    
    if application.wti_fees < 200:
        application.wti_fees = 200
        application.seeker_wti_fees = application.wti_fees
    else:
        application.wti_fees = application.wti_fees
        application.seeker_wti_fees = application.wti_fees
    #insurrance_fees = #TODO: add insurrance fees
    application.new_modified_pay = application.modified_pay - application.wti_fees/100
    application.total_amount = application.modified_pay*100 + application.wti_fees

    #TyEl fees for the company
    application.employer_tyel = application.wti_fees*1/100
    application.seeker_tyel = round(float(application.wti_fees)*115/10000)

    #Added notification when seeker applied for a job
    text = user.first_name + ' ' + user.last_name + ' ' + u'applied' + ' for ' + job.title
    finn_text = user.first_name + ' ' + user.last_name + ' ' + u'haki työtehtävää'+ ' ' + job.title
    type = u'application'
    notification = Notifications(job.posted_by,text,finn_text,type,job.title,job.posted_by,application.id)
    DBSession.add(notification)

    
    #Post JobApplication on FireBase
    data = {}
    employer = User.by_id(job.posted_by)
    data['id'] = application.id
    data['employer'] = employer.first_name + " " + employer.last_name
    data['employee'] = user.first_name + " " + user.last_name    
    data['status'] = str(application.status) + ',' + str(user.id) + ',' + str(application.id) + ',s' + ',' + (text) + ',' + (finn_text) + ',' + str(application.job_id)
    data['modified'] = datetime.datetime.utcnow().isoformat()

    fb.put('/applications/',application.application_key, data)
    fb.post('/users/'+employer.user_key+'/applications', application.application_key)
    fb.post('/users/'+user.user_key+'/applications', application.application_key)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data=application.serialize())

@view_config(route_name=v1+'_application', renderer='json',request_method='PUT')
def v1_application_put(request):
    '''
    Modify an application
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user',extra_finn='Käyttäjätiliä ei ole vahvistettu')
    
    application_id = request.json_body.get('application_id')
    modified_pay = request.json_body.get('modified_pay')
    modified_hours = request.json_body.get('modified_hours')
    comment = request.json_body.get('comment')

    application = JobApplication.by_id(application_id)
    job = Job.by_id(application.job_id)

    if not application:
        return response(code='E017',extra='Application not found',extra_finn='Hakemusta ei löydy')
        
    if not ((application.employee_id == user.id) or (application.employer_id == user.id)):
        return response(code='E013',extra='You are not authorized to modify the application',extra_finn='Sinulla ei ole valtuuksia muuttaa hakemusta')

    if application.status > 3:
        return response(code='E013',extra='You are not authorized to modify the application as it has been started already',extra_finn='Et voi muuttaa hakemusta, koska se on jo hyväksytty')


    application.modified_pay = modified_pay if modified_pay else application.modified_pay
    application.modified_hours = modified_hours if modified_hours else application.modified_hours
    application.comment = comment if comment else application.comment

    #Add modified fees to application
    #application.stripe_fees = int((application.modified_pay*2.9)+30)
    application.wti_fees = application.modified_pay*10
    application.seeker_wti_fees = application.wti_fees

    if application.wti_fees < 200:
        application.wti_fees = 200
        application.seeker_wti_fees = application.wti_fees
    else:
        application.wti_fees = application.wti_fees
        application.seeker_wti_fees = application.wti_fees

    #insurrance_fees = #TODO: add insurrance fees
    application.new_modified_pay = application.modified_pay - application.wti_fees/100
    application.total_amount = application.modified_pay*100 + application.wti_fees

    #TyEl fees for company
    application.employer_tyel = application.wti_fees*1/100
    application.seeker_tyel = round(float(application.wti_fees)*115/10000)   

    #Update on FireBase that it has been modified
    fb.put('/applications/'+application.application_key+'/','modified', datetime.datetime.utcnow().isoformat())

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis', data=application.serialize())

@view_config(route_name=v1+'_application_delete', renderer='json',request_method='POST')
def v1_application_delete(request):
    '''
    Delete application for a job
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user',extra_finn='Käyttäjätiliä ei ole vahvistettu')
    
    application_id = request.json_body.get('application_id')

    application = JobApplication.by_id(application_id)

    if not application:
        return response(code='E017',extra='Application not found',extra_finn='Hakemusta ei löydy')
    if not ((application.employee_id == user.id) or (application.employer_id == user.id)):
        return response(code='E013',extra='You are not authorized to delete the application',extra_finn='Sinulla ei ole valtuuksia poistaa hakemusta')

    if application.status > 4:
        return response(code='E013', extra = 'Not authorized to delete at this stage',extra_finn='Ei valtuuksia poistaa tässä vaiheessa')

    DBSession.delete(application)
    employer = User.by_id(application.employer_id)
    employee = User.by_id(application.employee_id)
    
    #Update on FireBase
    fb.delete('/applications/',application.application_key)
    fb.delete('/users/'+employer.user_key+'/applications', application.application_key)
    fb.delete('/users/'+employee.user_key+'/applications', application.application_key)

    #TODO - Delete from both users

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successfully deleted',extra_finn='Hakemus peruttu')

@view_config(route_name=v1+'_application_status', renderer='json',request_method='POST')
def v1_application_status(request):
    '''
    Set the status of application
    ''' 
        
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user', extra_finn='Käyttäjätiliä ei ole vahvistettu')    

    application_id = request.json_body.get('application_id')

    application = JobApplication.by_id(application_id)

    if not application: # Application not found
        return response(code='E020',extra='Application not found',extra_finn='Hakemusta ei löydy')

    job = Job.by_id(application.job_id)
    type = u'application'
    text = u''
    finn_text = u''
    job_name = job.title
    employer_id = application.employer_id
    employer = User.by_id(employer_id)
    employee = User.by_id(application.employee_id)

    sql = '''
    SELECT COUNT(*) as count, amount_total, amount_left
    FROM payment_restriction 
    WHERE payment_restriction.for_employer_id = '''+str(application.employer_id)+''' 
    AND payment_restriction.seeker_id = '''+str(application.employee_id)+'''
    '''
    count, amount_total, amount_left, = DBSession.execute(sql).fetchone()
    p_r = DBSession.query(PaymentRestriction).filter(PaymentRestriction.for_employer_id==application.employer_id,PaymentRestriction.seeker_id==application.employee_id).first()

    #employee_job_done = SkillCategory.by_user_category_id(employee.id,job.category)
    #He is setting the status of the application
    if application.employee_id == user.id and application.status in [2,3]:
        for_user_id = employer_id
        if application.status == 2:

            text = user.first_name + ' ' + user.last_name + ' ' + u'started the job' + ' ' + job_name
            finn_text = user.first_name + ' ' + user.last_name + ' ' + u'aloitti työtehtävän' + ' ' + job_name
            
            #Delete the job from SavedJob
            for saved_jobs in DBSession.query(SavedJob).filter(SavedJob.job_id == application.job_id).all():
                DBSession.delete(saved_jobs)

        if application.status == 3:
            text = user.first_name + ' ' + user.last_name + ' ' + u'ended the job' + ' ' + job_name
            finn_text = user.first_name + ' ' + user.last_name + ' ' + u'suoritti työtehtävän' + ' ' + job_name

            if request.json_body.get('review'):
                re = Review()
                re.job_id = application.job_id
                re.review_by = user.id
                re.review_for = application.employer_id
                re.review = request.json_body.get('review')
                re.thumbs_up = request.json_body.get('thumbs_up')
                re.thumbs_down = request.json_body.get('thumbs_down')

                reviewed_user = User.by_id(application.employer_id)
                reviewed_user.total_thumbs_employer = reviewed_user.total_thumbs_employer + 1

                if request.json_body.get('thumbs_up'):
                    reviewed_user.num_thumbs_up_employer = reviewed_user.num_thumbs_up_employer + 1
                if request.json_body.get('thumbs_down'):
                    reviewed_user.num_thumbs_down_employer =  reviewed_user.num_thumbs_down_employer + 1

                reviewed_user.thumbs_up_employer = float(reviewed_user.num_thumbs_up_employer)/float(reviewed_user.total_thumbs_employer)
                reviewed_user.thumbs_down_employer = float(reviewed_user.num_thumbs_down_employer)/float(reviewed_user.total_thumbs_employer)

                DBSession.add(re)
                DBSession.flush()

            if not count:
                payment_res = PaymentRestriction(application.employer_id,application.employee_id,application.modified_pay,float(50)-application.modified_pay)
                DBSession.add(payment_res)
            else:
                p_r.amount_total = p_r.amount_total+application.modified_pay
                p_r.amount_left = float(50) - p_r.amount_total

            try:
                charge = stripe.Charge.create(
                    customer=employer.stripe_customer_id,
                    amount=application.total_amount,
                    currency='eur',
                    application_fee= application.wti_fees+application.seeker_wti_fees,
                    description='Job payment',
                    destination=employee.stripe_account_id
                )

                payment_info = PaymentInfo(application.id, charge.id)
                DBSession.add(payment_info)
            except stripe.error.CardError as e:
                return response(code='E003',extra="No credit card found")
            except stripe.error.InvalidRequestError as e:
                return response(code='E003',extra="No bank account found")

            #employee_job_done.job_done = employee_job_done.job_done + 1
        application.status = application.status + 1

        #Add notification to db
        notification = Notifications(for_user_id,text,finn_text,type,job_name,employer_id,application_id)
        DBSession.add(notification)

    elif application.employer_id == user.id and application.status in [1]:
        for_user_id = application.employee_id
        
        if DBSession.query(JobApplication).filter(JobApplication.job_id == application.job_id, JobApplication.status > 2).count() > 0:
                return response(code='E013',extra='You have already accepted another job offer',extra_finn='Olet jo hyväksynyt toisen hakijan')

        if application.status == 1:
            if count:                
                if amount_left < application.modified_pay:
                    return response(code='E013',extra='You cannot pay this seeker more than 50 eur/month',extra_finn='Sinun ei ole mahdollista maksaa yli 50,00euroa/ työntekijä kuukaudessa')

            application.get_actived_at()

            text = u'Employer' + '  ' + user.first_name + ' ' + user.last_name + ' ' + u'accepted' + ' ' + job_name
            finn_text = u'Työnantaja'+ ' ' + user.first_name + ' ' + user.last_name + ' ' + u'hyväksyi työtehtävän' + ' ' + job_name

        application.status = application.status + 1
        #Add notification to db
        notification = Notifications(for_user_id,text,finn_text,type,job_name,employer_id,application_id)
        DBSession.add(notification)

    else:
        return response(code='E013', extra = 'You are not authorized to do this',extra_finn='Sinulla ei ole valtuuksia tähän')

    DBSession.flush()
    
    fb.put('/applications/'+application.application_key+'/','status', str(application.status)+','+str(user.id)+','+str(application_id)+ ',' +('e' if user.id == application.employer_id else 's')+ ',' +(notification.text)+','+(notification.finn_text)+ ',' + str(application.job_id))

    #TODO: Remove application from both user's active application list in firebase


    return response(code='S002', wti_token=request.json_body.get('wti_token'),extra='Successfully Updated',extra_finn='Valmis' ,data=application.serialize())

@view_config(route_name=v1+'_application_applied', renderer='json',request_method='POST')
def v1_application_applied(request):
    '''
    Get all applied application
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user',extra_finn='Käyttäjätiliä ei ole vahvistettu')
    
    sql = '''
    SELECT a.id,a.status,a.comment,a.created_at, b.title,b.pay,b.category,b.location_name, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.thumbs_up,c.thumbs_down, c.company_id
    FROM job_application AS a 
    JOIN job AS b 
    ON
    a.job_id = b.id
    JOIN user AS c
    ON 
    a.employer_id = c.id
    WHERE a.employee_id = '''+str(user.id)+'''
    ORDER BY a.created_at DESC
    '''

    data = {}
    data['is_verified'] = user.is_verified
    data['has_bank_account'] = True if user.stripe_account_id else False
    data['ssn'] = user.ssn if user.ssn else ''
    data['status_1'] = []
    data['status_2'] = []
    data['status_3'] = []
    data['status_4'] = []
    data['status_5'] = []    

    for appl_id, appl_status, appl_comment,appl_created_at, job_title,job_pay,job_category,job_location,user_id,first_name, last_name,profile_pic,thumbs_up,thumbs_down,company_id in DBSession.execute(sql):
        d = {}
        d['application_id']  = appl_id
        d['status'] = appl_status
        d['comment'] = appl_comment
        d['created_at'] = appl_created_at.isoformat()
        d['job_title'] = job_title
        d['job_category'] = job_category
        d['job_location_name'] = job_location if job_location else ""
        d['job_pay'] = job_pay
        d['employer_name'] = first_name + " " + last_name
        #d['employer'] = get_user_info(user_id,first_name,last_name,profile_pic,thumbs_up,thumbs_down,True if company_id else False)
        if appl_status == 1:
            data['status_1'].append(d)
        elif appl_status == 2:
            data['status_2'].append(d)
        elif appl_status == 3:
            data['status_3'].append(d)
        elif appl_status == 4:
            data['status_4'].append(d)
        elif appl_status == 5:
            data['status_5'].append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)

@view_config(route_name=v1+'_application_active', renderer='json',request_method='POST')
def v1_application_active(request):
    '''
    Get all active application
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user',extra_finn='Käyttäjätiliä ei ole vahvistettu')
    
    sql = '''
    SELECT a.id,a.status,a.comment,a.created_at, a.actived_at, b.title,b.category, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.stars_as_employee, c.rated_by_as_employee,c.stars_as_employer,c.rated_by_as_employer, c.company_id
    FROM job_application AS a 
    JOIN job AS b 
    ON
    a.job_id = b.id
    JOIN user AS c
    ON 
    a.employer_id = c.id
    WHERE a.employee_id = '''+str(user.id)+'''
    AND a.status BETWEEN 2 AND 8
    '''

    data = []

    for appl_id, appl_status, appl_comment,appl_created_at,appl_actived_at, job_title,job_category,user_id,first_name, last_name,profile_pic,social_id,stars_as_employee,rated_by_as_employee, stars_as_employer, rated_by_as_employer,company_id in DBSession.execute(sql):
        d = {}
        d['application_id']  = appl_id
        d['status'] = appl_status
        d['comment'] = appl_comment
        d['created_at'] = appl_created_at.isoformat()
        d['actived_at'] = appl_actived_at.isoformat() if appl_actived_at else ''
        d['job_title'] = job_title
        d['job_category'] = job_category
        d['employer'] = get_user_info(user_id,first_name,last_name,profile_pic,social_id, stars_as_employee, rated_by_as_employee, stars_as_employer, rated_by_as_employer,True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_application_get', renderer='json',request_method='POST')
def v1_application_get(request):
    '''
    Get particular application
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    application_id = request.matchdict.get('application_id')

    application = JobApplication.by_id(application_id)

    if not application:
        return response(code='E020',extra='Application not found',extra_finn='Hakemusta ei löydy')


    if (user.id != application.employer_id and user.id != application.employee_id):
        return response(code='E013', extra = 'Not authorized , this does not belong to you',extra_finn='Ei sallittu')


    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=application.serialize())

@view_config(route_name=v1+'_application_done', renderer='json', request_method='POST')
def v1_application_done(request):
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    sql = '''
    SELECT a.id,a.status,a.comment,a.created_at, b.title,b.category, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.stars_as_employee, c.rated_by_as_employee,c.stars_as_employer,c.rated_by_as_employer, c.company_id
    FROM job_application AS a 
    JOIN job AS b 
    ON
    a.job_id = b.id
    JOIN user AS c
    ON 
    a.employer_id = c.id
    WHERE (a.employee_id = '''+str(user.id)+''' OR a.employer_id = '''+str(user.id)+''')
    AND a.status >= 8
    ORDER BY a.created_at DESC
    '''

    data = []

    for appl_id, appl_status, appl_comment,appl_created_at, job_title,job_category,user_id,first_name, last_name,profile_pic,social_id,stars_as_employee,rated_by_as_employee, stars_as_employer, rated_by_as_employer,company_id in DBSession.execute(sql):
        d = {}
        d['application_id']  = appl_id
        d['status'] = appl_status
        d['comment'] = appl_comment
        d['created_at'] = appl_created_at.isoformat()
        d['job_title'] = job_title
        d['job_category'] = job_category
        d['employer'] = get_user_info(user_id,first_name,last_name,profile_pic,social_id, stars_as_employee, rated_by_as_employee, stars_as_employer, rated_by_as_employer,True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


##########################################################################################################
## Reviews API
##########################################################################################################


@view_config(route_name=v1+'_review', renderer='json',request_method='POST')
def v1_review(request):
    '''
    Add a review 
    ''' 
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    application_id = request.matchdict.get('application_id')

    application = JobApplication.by_id(application_id)

    if not application:
        return response(code='E020', extra='Job Application Not Found',extra_finn='Hakemusta ei löydy')

    if (application.status < 4) or (application.status >= 5):
        return response(code='E013', extra = 'Not authorized , You can not review now',extra_finn='Ei valtuuksia. Et voi vielä arvostella')

    if not (user.id == application.employer_id):
        return response(code='E010',extra='You cannot review this application',extra_finn='Et voi arvostella tätä hakemusta')

    review = request.json_body.get('review')
    review_for = application.employee_id
    thumbs_up = request.json_body.get('thumbs_up')
    thumbs_down = request.json_body.get('thumbs_down')
    mark_as_favourite = request.json_body.get('mark_as_favourite')

    if not(review or review_for or thumbs_up or thumbs_down ):
        return response(code='E009',extra='Missing parameters',extra_finn='Arviointi ei voi olla tyhjä')

    if review.isspace():
        return response(code='E009',extra="Review cannot be blank",extra_finn='Arviointi ei voi olla tyhjä')

    for review_key in filtering_out_keywords:
        if review_key.get('key') in review.lower():
            return response(code='E009',extra='The review contains inappropriate words',extra_finn='Arviointi sisältää epäsoveliaita sanoja')

    re = Review()
    re.job_id = application.job_id
    re.review_by = user.id
    re.review_for = review_for
    re.review = review
    re.thumbs_up = thumbs_up
    re.thumbs_down = thumbs_down

    #Check and Set the application status
    if user.id == application.employer_id and application.status == 4:
        application.status = 5
        application.done_at = datetime.datetime.utcnow()
        employer = User.by_id(application.employer_id)
        employee = User.by_id(application.employee_id)
        fb.delete('/users/'+ employer.user_key, application.application_key )
        fb.delete('/users/'+ employee.user_key, application.application_key )


    #Update the User rating

    reviewed_user = User.by_id(review_for)
    reviewed_user.total_thumbs = reviewed_user.total_thumbs + 1

    if thumbs_up:
        reviewed_user.num_thumbs_up = reviewed_user.num_thumbs_up + 1

    if thumbs_down:
        reviewed_user.num_thumbs_down = reviewed_user.num_thumbs_down + 1

    reviewed_user.thumbs_up = float(reviewed_user.num_thumbs_up)/float(reviewed_user.total_thumbs)
    reviewed_user.thumbs_down = float(reviewed_user.num_thumbs_down)/float(reviewed_user.total_thumbs)

    DBSession.add(re)
    DBSession.flush()
    
    #Update it on Firebase
    fb.put('/applications/'+application.application_key+'/','status', str(application.status)+','+str(user.id)+','+str(application_id)+ ',' +('e' if user.id == application.employer_id else 's')+ ',Employer has approved your work. Payment is on the way.'+','+'Työnantaja on hyväksynyt työsi. Maksu välitetään tilillesi.'+','+str(application.job_id))

    return response(code='S002',wti_token=request.json_body.get('wti_token'), extra='Success',extra_finn='Valmis',data=re.serialize())

@view_config(route_name=v1+'_review_for_as_seeker', renderer='json',request_method='POST')
def v1_review_for_as_seeker(request):
    '''
    Get review for a user 
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user')

    id = request.matchdict.get('user_id')
    
    sql = '''
    SELECT DISTINCT a.id, a.review, a.thumbs_up, a.thumbs_down, a.created_at, b.title, b.category,  c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.thumbs_up, c.thumbs_down, c.company_id
    FROM review AS a
    JOIN job AS b 
    ON a.job_id = b.id
    JOIN user AS c
    ON a.review_by = c.id
    JOIN job_application AS d
    ON d.employee_id = '''+str(id)+''' AND d.job_id = a.job_id
    WHERE a.review_for = d.employee_id
    ORDER BY a.created_at DESC
    '''
    data= []
    for review_id, review, review_thumbs_up, review_thumbs_down, created_at,job_title,job_category, user_id,first_name, last_name,profile_pic,social_id,thumbs_up,thumbs_down,company_id in DBSession.execute(sql):
        d = {}
        d['review_id'] = review_id
        d['review'] = review
        d['review_thumbs_up'] = review_thumbs_up
        d['review_thumbs_down'] = review_thumbs_down
        d['created_at'] = created_at.isoformat()       
        d['job_title'] = job_title
        d['job_category'] = job_category
        d['review_by'] = get_user_info(user_id,first_name,last_name,profile_pic,"","",True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',data=data)

@view_config(route_name=v1+'_review_for_as_employer', renderer='json',request_method='POST')
def v1_review_for_as_employer(request):
    '''
    Get review for a user 
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user')

    id = request.matchdict.get('user_id')
    
    sql = '''
    SELECT DISTINCT a.id, a.review, a.stars, a.created_at, b.title, b.category,  c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.stars_as_employee, c.rated_by_as_employee, c.stars_as_employer, c.rated_by_as_employer, c.company_id
    FROM review AS a
    JOIN job AS b 
    ON a.job_id = b.id
    JOIN user AS c
    ON a.review_by = c.id
    JOIN job_application AS d
    ON d.employer_id = '''+str(id)+''' AND d.job_id = a.job_id
    WHERE a.review_for = d.employer_id
    ORDER BY a.created_at DESC
    '''
    data= []
    for review_id, review, stars, created_at,job_title,job_category, user_id,first_name, last_name,profile_pic,social_id,stars_as_employee,rated_by_as_employee,stars_as_employer,rated_by_as_employer,company_id in DBSession.execute(sql):
        d = {}
        d['review_id'] = review_id
        d['review'] = review
        d['stars'] = stars
        d['created_at'] = created_at.isoformat()       
        d['job_title'] = job_title
        d['job_category'] = job_category
        d['review_by'] = get_user_info(user_id,first_name,last_name,profile_pic,social_id, stars_as_employee, rated_by_as_employee, stars_as_employer, rated_by_as_employer,True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',data=data)


##########################################################################################################
## Saved User and Jobs API
##########################################################################################################

@view_config(route_name=v1+'_saved_jobs_post', renderer='json',request_method='POST')
def v1_saved_jobs_post(request):
    '''
    Save a job to view later
    ''' 
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user')
    
    job_id = request.json_body.get('job_id')

    if not job_id:
        return response(code='E009',extra='Missing parameters')

    if DBSession.query(Job).filter(Job.id == job_id).count() <1:
        return response(code='E017',extra='Job not found')

    try:
        su = SavedJob()
        su.user_id = user.id
        su.job_id = job_id
        DBSession.add(su)
        DBSession.flush()
    except:
        #This job has already been saved
        pass

    return response(code='S002',wti_token=request.json_body.get('wti_token'), extra='Success')

@view_config(route_name=v1+'_saved_jobs_get', renderer='json',request_method='POST')
def v1_saved_jobs_get(request): 
    '''
    Saved Job GET 
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user')

    
    sql = '''
    SELECT a.job_id, b.title, b.category,  c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.stars_as_employee, c.rated_by_as_employee, c.stars_as_employer, c.rated_by_as_employer, c.company_id
    FROM saved_jobs AS a
    JOIN job AS b 
    ON a.job_id = b.id
    JOIN user AS c
    ON b.posted_by = c.id
    WHERE a.user_id = '''+str(user.id)+'''
    '''
    data= []
    for id,title,category,  user_id,first_name, last_name,profile_pic,social_id,stars_as_employee,rated_by_as_employee,stars_as_employer,rated_by_as_employer,company_id in DBSession.execute(sql):
        d = {}
        d['job_id'] = id
        d['job_title'] = title
        d['job_category'] = category
        d['employer'] = get_user_info(user_id,first_name,last_name,profile_pic,social_id, stars_as_employee, rated_by_as_employee, stars_as_employer, rated_by_as_employer,True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',data=data)

@view_config(route_name=v1+'_saved_users_get', renderer='json',request_method='POST')
def v1_saved_users_get(request): 
    '''
    Saved Users GET 
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user')

    jobId = request.json_body.get('job_id')

    #Small Profile, 
    sql = '''
    SELECT a.for_user, a.fav_user_id, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.stars_as_employee, c.rated_by_as_employee, c.stars_as_employer, c.rated_by_as_employer, c.company_id
    FROM fav_users as a
    JOIN user AS c
    ON c.id = a.fav_user_id
    WHERE a.for_user = '''+str(user.id)+'''
    '''
    data= []
    for  for_user, fav_user_id, user_id,first_name, last_name,profile_pic,social_id,stars_as_employee,rated_by_as_employee,stars_as_employer,rated_by_as_employer,company_id in DBSession.execute(sql):
        d = {}
        d['user'] = get_user_info(user_id,first_name,last_name,profile_pic,social_id, stars_as_employee, rated_by_as_employee, stars_as_employer, rated_by_as_employer,True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',data=data)

@view_config(route_name=v1+'_suggested_users_get', renderer='json',request_method='POST')
def v1_suggested_users_get(request): 
    '''
    Suggested Users GET 
    ''' 

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user')

    jobId = request.json_body.get('job_id')
    left_top_lat = request.json_body.get('left_top_lat')
    left_top_long = request.json_body.get('left_top_long')
    right_bottom_lat = request.json_body.get('right_bottom_lat')
    right_bottom_long = request.json_body.get('right_bottom_long')

    #Small Profile, 
    sql = '''
    SELECT c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.social_id, c.stars_as_employee, c.rated_by_as_employee, c.stars_as_employer, c.rated_by_as_employer, c.company_id
    FROM user AS c 
    JOIN skill_category AS b 
    ON b.user_id = c.id
    WHERE b.category_id = (SELECT job.category FROM job WHERE job.id = '''+str(jobId)+''' and job.posted_by = '''+str(user.id)+''' LIMIT 1)
    AND
    (c.latitude BETWEEN '''+str(left_top_lat)+''' AND '''+str(right_bottom_lat)+''')
    AND
    (c.longitude BETWEEN '''+str(left_top_long)+''' AND '''+str(right_bottom_long)+''')
    AND 
    c.stars_as_employee >= 4
    AND 
    c.is_private = 0
    GROUP BY c_id
    HAVING (SELECT COUNT(*) FROM job_application WHERE job_application.job_id = '''+str(jobId)+''' AND job_application.employer_id = '''+str(user.id)+''' AND job_application.employee_id = c.id) < 1
    '''    
    data= []
    for  user_id,first_name, last_name,profile_pic,social_id,stars_as_employee,rated_by_as_employee,stars_as_employer,rated_by_as_employer,company_id in DBSession.execute(sql):
        d = {}
        d['user'] = get_user_info(user_id,first_name,last_name,profile_pic,social_id, stars_as_employee, rated_by_as_employee, stars_as_employer, rated_by_as_employer,True if company_id else False)
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',data=data)

@view_config(route_name=v1+'_suggested_user_apply', renderer='json',request_method='POST')
def _suggested_user_apply(request):
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user') 

    user_id = request.json_body.get('user_id')
    job_id = request.json_body.get('job_id')
    comment = request.json_body.get('comment')

    job = Job.by_id(job_id)

    if not job:
        return response(code='E017',extra='Job not found')

    if user_id == user.id:
        return response(code='E013',extra='You can not apply to your own job')

    employee = User.by_id(user_id)

    application = JobApplication(employee.id,job_id,user.id,job.pay,job.hours,comment)
    application.status = 2
    DBSession.add(application)
    DBSession.flush()

    #Post JobApplication on FireBase
    j = {}
    j['id'] = application.id
    j['employer'] = user.first_name + " " + user.last_name
    j['employee'] = employee.first_name + " " + employee.last_name
    j['status'] = str(application.status) + ',' + str(user.id) + ',' + str(application.id) + ',e'
    j['modified'] = datetime.datetime.utcnow().isoformat()

    fb.put('/applications/',application.application_key, j)
    fb.post('/users/'+employee.user_key+'/applications', application.application_key)
    fb.post('/users/'+user.user_key+'/applications', application.application_key)

    #Add notification to db
    text = u'You have been invited to this job ' + job.title
    finn_text = u'Sinut on kutsuttu tekemään työtehtävä ' + job.title
    type = 'application'

    notification = Notifications(user_id,text,finn_text,type,job.title,user.id,application.id)
    DBSession.add(notification)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful', data= application.serialize())

##########################################################################################################
## Chat API
##########################################################################################################

@view_config(route_name=v1+'_application_chat', renderer='json',request_method='POST')
def v1_application_chat(request): 
    '''
    Chat Post 
    ''' 
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if not user.is_verified:
        return response(code='E012',extra='Not verified user',extra_finn='Käyttäjätiliä ei ole vahvistettu')

    application_id = request.matchdict.get('application_id')
    application = JobApplication.by_id(application_id)
    sql = '''
        SELECT a.id, a.application_key, a.status, a.employer_id , b.title
        FROM job_application AS a 
        JOIN job AS b
        ON a.job_id = b.id 
        WHERE a.id = '''+str(application_id)+'''
    '''

    appl_id, appl_key,status, employer_id, job_title = DBSession.execute(sql).fetchone()

    if not application.actived_at:
        application.get_actived_at()

        if user.id == employer_id:            
            fb.put('/applications/'+appl_key+'/','status', str(application.status)+','+str(employer_id)+','+str(appl_id)+',e' )
        elif user.id == application.employee_id:
            fb.put('/applications/'+appl_key+'/','status', str(application.status)+','+str(application.employee_id)+','+str(appl_id)+',s' )

    #Change Status to 2
    last_msg = request.json_body.get('text')

    # for msg_key in filtering_out_keywords:
    #     if msg_key.get('key') in last_msg.lower():
    #         return response(code='E009',extra='The chat contains inappropriate words')

    application.last_message = request.json_body.get('text')
    application.last_message_at = datetime.datetime.utcnow()

    data = {}
    data['by'] = user.first_name + " " + user.last_name
    data['by_user_id'] = user.id
    data['by_user_profile_pic'] = user.get_profile_image()
    data['employer_id'] = application.employer_id
    data['text'] = request.json_body.get('text')
    data['id'] = str(uuid.uuid4())
    data['msg_id'] = request.json_body.get('msg_id','')
    data['application_id'] = appl_id
    data['job_title'] = job_title
    data['timestamp'] = datetime.datetime.utcnow().isoformat()

    if 'attachment' in request.json_body:
        try:
            result = upload_base64_image(request.json_body.get('attachment'))
            data['attachment'] = result
        except:
            print 'Could not upload image'

    fb.post('/applications/'+appl_key+'/messages', data)
    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Success',extra_finn='Valmis',data=data)


##########################################################################################################
## Notification API
##########################################################################################################
@view_config(route_name=v1+'_notification', renderer='json',request_method='POST')
def _notification(request):
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user') 
    
    page_num = request.json_body.get('page_num')
    sql = '''
    SELECT a.id, a.for_user_id, a.text, a.finn_text, a.type, a.job_name, a.employer_id, a.application_id, a.created_at, c.category
    FROM notifications as a
    JOIN job_application AS b ON a.application_id = b.id
    JOIN job as c ON b.job_id = c.id
    WHERE a.for_user_id = '''+str(user.id)+'''
    AND a.type = "application"
    ORDER BY a.created_at DESC
    '''
    if page_num:
        sql = sql + '''LIMIT ''' +str(page_num*25)+''',25'''

    data = []
    for id, for_user_id, text, finn_text, type, job_name, employer_id, application_id, created_at, category in DBSession.execute(sql):
        d = {}
        d['id'] = id
        d['for_user_id'] = for_user_id
        d['text'] = text
        d['finn_text'] = finn_text       
        d['type'] = type
        d['job_name'] = job_name
        d['employer_id'] = employer_id 
        d['application_id'] = application_id
        d['job_category'] = category
        d['created_at'] = created_at.isoformat()
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful', data=data)

@view_config(route_name=v1+'_notification_chats', renderer='json',request_method='POST')
def _notification_chats(request):
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi') 
    
    sql = '''
    SELECT a.id, a.employer_id , b.title , b.category, a.last_message, a.last_message_at, c.id as c_id, c.first_name, c.last_name,c.profile_pic
    FROM job_application AS a 
    JOIN job AS b 
    ON a.job_id = b.id
    JOIN user AS c 
    ON c.id = 
    (
    CASE
        WHEN a.employee_id = '''+str(user.id)+''' THEN a.employer_id
        ELSE a.employee_id
    END
    )
    WHERE 
    (a.employee_id = '''+str(user.id)+''' OR a.employer_id = '''+str(user.id)+''')
    AND
    (a.status BETWEEN 1 AND 5)
    AND
    a.comment is NOT NULL
    AND
    a.last_message is NOT NULL
    ORDER BY a.last_message_at DESC
    '''
    data = []

    for appl_id,employer_id, job_title, job_cat, last_message, last_message_at, user_id,first_name, last_name, profile_pic in DBSession.execute(sql):
        d = {}
        d['application_id'] = appl_id
        d['employer_id'] = employer_id
        d['job_title'] = job_title
        d['job_category'] = job_cat
        d['last_message'] = last_message
        d['last_message_at'] = last_message_at.isoformat()
        d['user'] = first_name +' '+ last_name
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)

@view_config(route_name=v1+'_notification_delete', renderer='json',request_method='POST')
def _notification_delete(request):
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi') 
    
    notification_id = request.json_body.get('notification_id')

    notification = Notifications.by_id(notification_id)

    if notification:
        DBSession.delete(notification)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis')


##########################################################################################################
## Constant Keywords API
##########################################################################################################

@view_config(route_name=v1+'_skill_keywords', renderer='string')
def _skill_keywords(request):
    return json.dumps(skill_keywords,ensure_ascii=False, encoding='utf8')

@view_config(route_name=v1+'_filter_keywords', renderer='string')
def _filter_keywords(request):
    return json.dumps(filtering_out_keywords,ensure_ascii=False, encoding='utf8')



##########################################################################################################
## Payment API
##########################################################################################################
@view_config(route_name=v1+'_payment_add',renderer='json', request_method='POST')
def v1_payment_add(request):
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if user.company_id:
        return response(code='E011',extra='You cannot add payment method')

    try:
        user.dob = datetime.datetime.strptime(request.json_body.get('birthday') ,"%d.%m.%Y") if request.json_body.get('birthday')  else user.dob
    except:
        return response(code='E011',extra='Invalid Social Security Number',extra_finn='Virheellinen henkilötunnus')

    #if not user.dob:
    #    return response(code='E010',extra='Please update your date of birth in profiles first',extra_finn='Anna ensin syntymäaikasi profiili-kohdassa')

    user.ssn = request.json_body.get('ssn')

    if request.json_body.get('promote_code'):
        promote_code = request.json_body.get('promote_code')
        user.promote_code = promote_code if (promote_code.lower() in pc) else None
    
    if request.json_body.get('address_line'):
        user.address_line = request.json_body.get('address_line')

    if request.json_body.get('address_city'):
        user.address_city = request.json_body.get('address_city')

    if request.json_body.get('address_postal_code'):
        user.address_postal_code = request.json_body.get('address_postal_code')

    if request.json_body.get('card_token'):
        token = request.json_body.get('card_token')

        customer = stripe.Customer.retrieve(user.stripe_customer_id)
        customer.sources.create(
            source=token
        )
        user.has_cc = True

    if request.json_body.get('bank_token'):
        token = request.json_body.get('bank_token')
        if not user.stripe_account_id:
            account = stripe.Account.create(
                managed = True,
                country = 'FI',
                email = user.mail       
            )
            user.add_stripe_account_id(account.id)
            account.external_accounts.create(
                external_account=token,
                default_for_currency = True
            )
            #Update legal_entity for transfering money
            acc = stripe.Account.retrieve(account.id)
            acc.legal_entity.first_name = user.first_name
            acc.legal_entity.last_name = user.last_name
            try:
                acc.legal_entity.dob.day = user.dob.day
                acc.legal_entity.dob.month = user.dob.month
                acc.legal_entity.dob.year = user.dob.year
            except:
                pass

            if not user.company_id:
                acc.legal_entity.type = 'individual'
            else:
                acc.legal_entity.type = 'company'
            acc.tos_acceptance.date = int(time.time())
            acc.tos_acceptance.ip = request.remote_addr            

            if request.json_body.get('address_city'):
                acc.legal_entity.address.city = user.address_city
                acc.legal_entity.personal_address.city = user.address_city
            if request.json_body.get('address_line'):
                acc.legal_entity.address.line1 = user.address_line
                acc.legal_entity.personal_address.line1 = user.address_line
            if request.json_body.get('address_postal_code'):
                acc.legal_entity.address.postal_code = user.address_postal_code
                acc.legal_entity.personal_address.postal_code = user.address_postal_code

            acc.save()            
        else:
            account = stripe.Account.retrieve(user.stripe_account_id)
            account.external_accounts.create(
                external_account=token,
                default_for_currency = True
            )
            acc = stripe.Account.retrieve(account.id)
            acc.legal_entity.first_name = user.first_name
            acc.legal_entity.last_name = user.last_name
            try:
                acc.legal_entity.dob.day = user.dob.day
                acc.legal_entity.dob.month = user.dob.month
                acc.legal_entity.dob.year = user.dob.year
            except:
                pass

            if request.json_body.get('address_city'):
                acc.legal_entity.address.city = user.address_city
                acc.legal_entity.personal_address.city = user.address_city
            if request.json_body.get('address_line'):
                acc.legal_entity.address.line1 = user.address_line
                acc.legal_entity.personal_address.line1 = user.address_line
            if request.json_body.get('address_postal_code'):
                acc.legal_entity.address.postal_code = user.address_postal_code
                acc.legal_entity.personal_address.postal_code = user.address_postal_code

            acc.save()

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis')

@view_config(route_name=v1+'_payment_get', renderer='json', request_method='POST')
def v1_payment_get(request):

    user = get_authenticated_user(request)

    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    data={}
    cards=[]
    banks=[]
    data['cards']=cards
    data['banks']=banks

    if user.has_stripe_customer():
        customer = stripe.Customer.retrieve(user.stripe_customer_id)
        for i in customer.sources.all().get('data'):
            c = {}
            c['id']=i.get('id')
            c['type']=i.get('object')
            c['last4']=i.get('last4')
            c['exp_month']=i.get('exp_month')
            c['exp_year']=i.get('exp_year')
            cards.append(c)

    if user.has_stripe_account():
        account = stripe.Account.retrieve(user.stripe_account_id)
        for i in account.external_accounts.all().get('data'):
            b = {}
            b['id']=i.get('id')
            b['type']=i.get('object')
            b['last4']=i.get('last4')
            b['default_for_currency'] = i.get('default_for_currency')
            banks.append(b)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_payment_delete', renderer='json', request_method='POST')
def v1_payment_delete(request):

    user = get_authenticated_user(request)

    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    if request.json_body.get('card_id') is not None:
        customer = stripe.Customer.retrieve(user.stripe_customer_id)
        data = customer.sources.retrieve(request.json_body.get('card_id')).delete()

    if request.json_body.get('bank_account_id'):
        account = stripe.Account.retrieve(user.stripe_account_id)

        if not (account.external_accounts.retrieve(request.json_body.get('bank_account_id')).default_for_currency == False):
            return response(code='E010',extra='You cannot delete your default bank account',extra_finn='Et voi poistaa oletuspankkitiliäsi')
        else:
            data = account.external_accounts.retrieve(request.json_body.get('bank_account_id')).delete()
            
    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_payment_paid', renderer='json', request_method='POST')
def v1_payment_paid(request):

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    sql='''
    SELECT a.id,a.application_id, b.employee_id, b.total_amount, b.done_at, c.title, c.category, d.first_name, d.last_name
    FROM payment_info as a
    JOIN job_application as b
    ON a.application_id = b.id
    JOIN job as c
    ON b.job_id = c.id
    JOIN user as d
    ON b.employee_id = d.id
    WHERE b.employer_id ='''+str(user.id)+'''
    ORDER BY b.done_at DESC
    '''

    data=[]

    for id, application_id, employee_id, total_amount,done_at, title, category, first_name, last_name in DBSession.execute(sql):
        payment_info = {}
        payment_info['id'] = id
        payment_info['application_id'] = application_id
        payment_info['employee_id'] = employee_id
        payment_info['total_amount'] = total_amount/float(100)
        payment_info['done_at'] = done_at.isoformat() if done_at else ''
        payment_info['title'] = title
        payment_info['category'] = category
        payment_info['seeker_name'] = first_name +' '+last_name
        data.append(payment_info)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_payment_paid_to', renderer='json', request_method='POST')
def v1_payment_paid_to(request):
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    application_id = request.matchdict.get('application_id')

    sql = '''
    SELECT a.id, a.application_id,b.total_amount, c.id, c.first_name, c.last_name, c.profile_pic, d.insurance, d.title, d.hours
    FROM payment_info as a
    JOIN job_application as b
    ON a.application_id = b.id AND b.employer_id='''+str(user.id)+'''
    JOIN user as c
    ON c.id = b.employee_id
    JOIN job as d
    ON d.id = b.job_id
    WHERE a.application_id = '''+str(application_id)+'''
    '''
    data=[]

    for id, appl_id, total_amount, seeker_id, first_name, last_name, profile_pic, insurance, title, hours in DBSession.execute(sql):
        d={}
        d['id'] = id
        d['application_id'] = appl_id
        d['total_amount'] = total_amount
        d['seeker_id'] = seeker_id
        d['seeker_name'] = first_name+' '+last_name
        d['profile_pic'] = User.by_id(seeker_id).get_profile_image()
        d['insurance'] = insurance
        d['job_title'] = title
        d['job_hours'] = hours
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_payment_received', renderer='json', request_method='POST')
def v1_payment_received(request):

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    sql='''
    SELECT a.id,a.application_id, b.employer_id, b.new_modified_pay, b.done_at, c.title, c.category, d.first_name, d.last_name
    FROM payment_info as a
    JOIN job_application as b
    ON a.application_id = b.id
    JOIN job as c
    ON b.job_id = c.id
    JOIN user as d
    ON b.employer_id = d.id
    WHERE b.employee_id ='''+str(user.id)+'''
    ORDER BY b.done_at DESC
    '''

    data=[]

    for id, application_id, employer_id, modified_pay, done_at, title, category, first_name, last_name in DBSession.execute(sql):
        payment_info = {}
        payment_info['id'] = id
        payment_info['application_id'] = application_id
        payment_info['employer_id'] = employer_id
        payment_info['modified_pay'] = modified_pay
        payment_info['done_at'] = done_at.isoformat() if done_at else ''
        payment_info['title'] = title
        payment_info['category'] = category
        payment_info['employer_name'] = first_name +' '+last_name
        data.append(payment_info)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)

@view_config(route_name=v1+'_payment_received_from', renderer='json', request_method='POST')
def v1_payment_received_from(request):
    
    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    application_id = request.matchdict.get('application_id')
    
    sql = '''
    SELECT a.id, a.application_id,b.modified_pay, c.id, c.first_name, c.last_name, c.profile_pic, d.insurance, d.title, d.hours
    FROM payment_info as a
    JOIN job_application as b
    ON a.application_id = b.id AND b.employee_id = '''+str(user.id)+'''
    JOIN user as c
    ON c.id = b.employer_id
    JOIN job as d
    ON d.id = b.job_id
    WHERE a.application_id = '''+str(application_id)+'''
    '''
    data=[]

    for id, appl_id, modified_pay, employer_id, first_name, last_name, profile_pic, insurance, title, hours in DBSession.execute(sql):
        d={}
        d['id'] = id
        d['application_id'] = appl_id
        d['modified_pay'] = modified_pay
        d['employer'] = employer_id
        d['employer_name'] = first_name+' '+last_name
        d['profile_pic'] = User.by_id(employer_id).get_profile_image()
        d['insurance'] = insurance
        d['job_title'] = title
        d['job_hours'] = hours
        data.append(d)

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)


@view_config(route_name=v1+'_payment_refund', renderer='json', request_method='POST')
def v1_payment_refund(request):

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    application_id = request.json_body.get('application_id')

    application = JobApplication.by_id(application_id)
    if not(user.id == application.employer_id):
        return response(code='E010',extra='This is not your job',extra_finn='Et ole antanut tätä tehtävää')

    payment = PaymentInfo.by_application_id(application_id)

    re = stripe.Refund.create(
            charge=payment.charge_id
        )
    payment.add_refund_id(re.id)
    
    data={}
    data['refund_id'] = re.id
    data['refund_amount'] = re.amount
    data['refund_currency'] = re.currency

    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)

@view_config(route_name=v1+'_payment_update', renderer='json', request_method='POST')
def v1_payment_update(request):

    user = get_authenticated_user(request)
    if not user:
        return response(code='E010',extra='Not logged in or you are not a user',extra_finn='Et ole vahvistanut tiliäsi')

    bank_account_id = request.json_body.get('bank_account_id')

    account = stripe.Account.retrieve(user.stripe_account_id)
    bank_account = account.external_accounts.retrieve(bank_account_id)
    bank_account.default_for_currency = True
    data = bank_account.save()
    return response(code='S002',wti_token=request.json_body.get('wti_token'),extra='Successful',extra_finn='Valmis', data=data)

##########################################################################################################
## Terms and Conditions API
##########################################################################################################
@view_config(route_name=v1+'_terms_and_conditions', renderer='json', request_method='POST')
def v1_tos(request):
    # user = get_authenticated_user(request)
    # if not user:
    #     return response(code='E010',extra='Not logged in or you are not a user')
    return response(code='S002',extra='Successful', data=tos)



@view_config(route_name=v1+'_certificate_verify')
def v1_certificate_verify(request):
    _cert = open(os.path.join( os.path.dirname(__file__) , 'static', '672762715E8EC03ED657C18B6E62F179.txt')).read()
    return pyResponse(content_type='text/plain', body=_cert)

##########################################################################################################
## Company API API
##########################################################################################################
@view_config(route_name=v1+'_company',renderer='json',request_method='POST')
def v1_company(request):
    email = request.json_body.get('email')

    generated_pw = str(uuid.uuid4())

    company_id = request.json_body.get('company_id')
    company_address = request.json_body.get('company_address')
    company_zipcode = request.json_body.get('company_zipcode')
    company_city = request.json_body.get('company_city')
    company_name = request.json_body.get('company_name')
    company_phone_number = request.json_body.get('company_phone_number')
    billing_address = request.json_body.get('billing_address')
    billing_zipcode = request.json_body.get('billing_zipcode')
    billing_city = request.json_body.get('billing_city')
    billing_vat_id = request.json_body.get('billing_vat_id')

    if not (company_id and company_address and company_zipcode and company_city and company_name and company_phone_number and billing_address and billing_zipcode and billing_city and billing_vat_id and email):
        return response(code='E005',extra='All parameters are required')
    
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return response(code='E006',extra = 'Invalid Email') #Invalid Email
    
    try:
        user = User(mail=email)
        user.password = pbkdf2_sha256.encrypt(generated_pw, rounds=200000, salt_size=16)
        DBSession.add(user)
        DBSession.flush()
    except IntegrityError:
        return response(code='E007', extra='User already exists') # User already exists

    company = ComapnyInformation(company_id,company_name,company_phone_number,company_address,company_zipcode,company_city,billing_address,billing_city,billing_zipcode,billing_vat_id)
    DBSession.add(company)
    DBSession.flush()

    user.is_verified = 1
    user.company_id = company.id

    send_password_mail(user.mail, generated_pw)
    send_welcome_mail(request.registry['mailer'],email,company_name)

    user.first_name = request.json_body.get('first_name') if request.json_body.get('first_name') else company.company_name
    user.last_name = request.json_body.get('last_name') if request.json_body.get('last_name') else u''

    return response(code='S002', data='Success') #Verification Email Sent



##########################################################################################################
## Extras API
##########################################################################################################

@notfound_view_config(append_slash=True,renderer='json')
def notfound(request):
    return response(code='E019',extra ='Page Not Found');

@view_config(route_name=v1+'_home', renderer='json')
def v1_home(request):
    return {'project': 'wetaskit', 'text':'Documentation at - '}

@view_config(route_name='web', renderer='json')
def v1_home(request):
    return HTTPFound(location='/web/')
