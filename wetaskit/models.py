from sqlalchemy import (
    Column,
    Index,
    Integer,
    String,
    BigInteger,
    Float,
    Text,
    UnicodeText,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    )
from sqlalchemy.orm import relationship,backref,joinedload

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )

from zope.sqlalchemy import ZopeTransactionExtension

import datetime,uuid,dateutil.parser
from passlib.hash import pbkdf2_sha256
from constants import VERIFICATION_MAIL_EXPIRES_IN,RESET_MAIL_EXPIRES_IN,default_profile_pic,default_job_pic
from utils import get_user_info

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

def _get_date():
    return datetime.datetime.utcnow()

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


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    first_name = Column(UnicodeText, default=u'')
    last_name = Column(UnicodeText, default=u'')
    dob = Column(DateTime)
    mail = Column(String(64), nullable=False, unique = True)
    password = Column(Text, nullable=False)
    profile_pic = Column(Text)
    about_me = Column(UnicodeText, default=u'')
    last_use = Column(Integer) #0 = employer, 1 = seeker

    is_private = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    latitude = Column(Float(precision='10,7'))
    longitude = Column(Float(precision='10,7'))

    #Address
    address_line = Column(UnicodeText, default=u'')
    address_city = Column(UnicodeText, default=u'')
    address_postal_code = Column(UnicodeText, default=u'')

    #For chat
    user_key = Column(Text)
    #gcm_key = Column(Text) #TODO

    #Rating
    thumbs_up = Column(Float(precision='4,2'),default = 0.0)
    num_thumbs_up = Column(Integer,default = 0)
    thumbs_down = Column(Float(precision='4,2'),default = 0.0)
    num_thumbs_down = Column(Integer,default = 0)
    total_thumbs = Column(Integer,default = 0)

    thumbs_up_employer = Column(Float(precision='4,2'),default = 0.0)
    num_thumbs_up_employer = Column(Integer,default = 0)
    thumbs_down_employer = Column(Float(precision='4,2'),default = 0.0)
    num_thumbs_down_employer = Column(Integer,default = 0)
    total_thumbs_employer = Column(Integer,default = 0)

    #Social Login
    social_login_type = Column(Integer, default = 0 ) #0=Custom Login , 1 = FB, 2 = BOTH
    social_id = Column(Text) #Saves ID in case of FB

    #Metadata
    created_at = Column(DateTime,default=_get_date)

    #Payment Related
    stripe_account_id = Column(Text, default='')
    stripe_customer_id = Column(Text, default='')
    has_cc = Column(Boolean, default=False)

    #Comapny related information
    company_id = Column(Integer)
    cover_pic = Column(Text, default='')

    #promote code
    promote_code = Column(Text, default='')
    ssn = Column(Text)


    def __init__(self,mail = None, password = None,first_name = None,last_name = None):
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
        self.password = pbkdf2_sha256.encrypt(password, rounds=200000, salt_size=16) if password else str(uuid.uuid4()) #TODO - Taking a lot of time
        self.user_key = str(uuid.uuid4())

    # @classmethod
    # def fb_init(cls,fb_obj,stripe_customer_id):
    #     u = cls()
    #     u.first_name = fb_obj['first_name']
    #     u.last_name = fb_obj['last_name']
    #     u.mail = fb_obj['email']
    #     u.dob = datetime.datetime.strptime(fb_obj.get('birthday'),"%m/%d/%Y") if 'birthday' in fb_obj else None
    #     u.social_login_type  = 1
    #     u.social_id = fb_obj['id']
    #     u.is_verified = True
    #     u.stripe_customer_id = stripe_customer_id
    #     return u

    @classmethod
    def by_email(cls,mail):
        return DBSession.query(User).filter(User.mail == mail).first()
    
    @classmethod
    def by_id(cls,id):
        return DBSession.query(User).filter(User.id == id).first()

    def verify_password(self,password):
        return pbkdf2_sha256.verify(password, self.password)
    
    def reset_password(self,new_password=None):
        self.password = pbkdf2_sha256.encrypt(new_password, rounds=200000, salt_size=16) if new_password else str(uuid.uuid4())

    def serialize(self, own_info= False):
        u = {}
        u['user_id'] = self.id
        u['first_name'] = self.first_name
        u['last_name'] = self.last_name
        u['profile_pic'] = self.get_profile_image()
        u['created_at_utc'] = self.created_at.isoformat()
        u['thumbs_up'] = self.thumbs_up
        u['thumbs_down'] = self.thumbs_down
        #u['has_cc'] = True if self.has_cc else False
        #u['is_company'] = True if self.company_id else False
        u['user_key'] = self.user_key
        u['last_use'] = self.last_use
        
        # re_sql = '''
        # SELECT a.review, a.stars, a.created_at, b.title, b.category,  c.id as c_id
        # FROM review AS a
        # JOIN job AS b 
        # ON a.job_id = b.id
        # JOIN user AS c
        # ON a.review_by = c.id
        # JOIN job_application AS d
        # ON d.employee_id = '''+str(self.id)+''' AND d.job_id = a.job_id
        # WHERE a.review_for = d.employee_id
        # ORDER BY a.created_at DESC
        # LIMIT 1
        # '''
        # review = []
        # for a_review, a_stars, a_created_at, b_title, b_category, c_id in DBSession.execute(re_sql):
        #     re = {}
        #     re['review'] = a_review
        #     re['stars'] = a_stars
        #     re['created_at'] = a_created_at.isoformat()
        #     re['job_title'] = b_title
        #     re['job_category'] = b_category
        #     re['review_by'] = User.by_id(c_id).info()
        #     review.append(re)

        # u['review'] = review

        # if own_info:
        #     u['mail'] = self.mail

        # sql = '''
        # SELECT DISTINCT(a.category_id) , (SELECT COUNT(*) FROM job_application JOIN job ON job_application.job_id = job.id WHERE job.category = a.category_id AND job_application.status >= 8 AND job_application.employee_id = a.user_id)
        # FROM skill_category AS a
        # WHERE a.user_id = '''+str(self.id)+'''
        # '''

        # skill_to_cat = []

        # for cat, count in DBSession.execute(sql):
        #     if cat:
        #         d = {}
        #         d['category'] = cat
        #         d['num_jobs_completed'] = count
        #         skill_to_cat.append(d)

        # u['skills'] = skill_to_cat
        return u

    def info(self):
        u={}
        u['user_id'] = self.id
        u['name'] = self.first_name + ' ' + self.last_name
        u['profile_pic'] = self.get_profile_image()
        u['thumbs_up'] = self.thumbs_up
        u['thumbs_down'] = self.thumbs_down
        u['is_company'] = True if self.company_id else False
        return u

    def info_employer(self):
        u={}
        u['user_id'] = self.id
        u['name'] = self.first_name + ' ' + self.last_name
        u['profile_pic'] = self.get_profile_image()
        u['thumbs_up'] = self.thumbs_up_employer
        u['thumbs_down'] = self.thumbs_down_employer
        u['is_company'] = True if self.company_id else False
        return u

    def get_profile_image(self):
        if self.profile_pic:
            return self.profile_pic
        if self.social_id:
            return "https://graph.facebook.com/"+self.social_id+"/picture?type=large"
        return default_profile_pic

    def is_complete(self):
        return True #(self.phone_number is not None)

    def add_stripe_customer_id(self,stripe_customer_id):
        self.stripe_customer_id = stripe_customer_id

    def add_stripe_account_id(self,stripe_account_id):
        self.stripe_account_id = stripe_account_id

    def has_stripe_customer(self):
        if self.stripe_customer_id:
            return True
        else:
            return False

    def has_stripe_account(self):
        if self.stripe_account_id:
            return True
        else:
            return False

    def is_company(self):
        if self.company_id:
            return True
        else:
            return False

#Index('user_index', User.mail,  mysql_length=255) MySQL Indexes the Unique Key http://docs.sqlalchemy.org/en/rel_1_0/dialects/mysql.html#mysql-unique-constraints-and-reflection

#Each Job that is created
class Job(Base):
    __tablename__ = 'job'
    id = Column(Integer, primary_key=True)
    posted_by = Column(Integer)
    title = Column(UnicodeText, default = u'')
    desc = Column(UnicodeText, default = u'')
    pay = Column(BigInteger,nullable=False)
    hours = Column(Integer, nullable= False)
    expires_on = Column(DateTime)
    latitude = Column(Float(precision='10,7'))
    longitude = Column(Float(precision='10,7'))
    location_name = Column(UnicodeText, default = u'')
    category = Column(Integer,default=1) #1 = Cleaning 2 = Gardening , 3 = House , 4 = Delivery, 5= Pets , 6 = Companion 7 = Others

    #metadata
    created_at = Column(DateTime,default=_get_date)
    modified_at = Column(DateTime,onupdate=_get_date)
    deleted_at = Column(DateTime)


    def __init__(self,posted_by,title,desc,pay,category,hours,expires_on,latitude,longitude,location_name):
        self.posted_by = posted_by
        self.title = title
        self.desc = desc
        self.pay = pay
        self.category = category
        self.hours = hours
        try:
            self.expires_on = dateutil.parser.parse(expires_on)
        except:
            self.expires_on = datetime.datetime.utcnow()+datetime.timedelta(days=30)
        self.latitude = latitude if latitude else None
        self.longitude = longitude if longitude else None
        self.location_name = location_name if location_name else ''

    def update(self,title,desc,pay,hours,expires_on,latitude,longitude,location_name):
        self.title = title
        self.desc = desc if desc else self.desc
        self.pay = pay if pay else self.pay
        self.hours = hours if hours else self.hours
        try:
            self.expires_on = dateutil.parser.parse(expires_on)
        except:
            pass

        self.latitude = latitude if latitude else self.latitude
        self.longitude = longitude if longitude else self.longitude
        self.location_name = location_name if location_name else self.location_name

    def serialize(self):
        j = {}
        j['job_id'] = self.id
        j['employer'] = User.by_id(self.posted_by).info_employer()
        j['title'] = self.title
        j['description'] = self.desc
        j['pay'] = self.pay if self.pay else 0
        j['category'] = self.category if self.category else 0
        j['images'] = self.get_images()
        j['hours'] = self.hours if self.hours else 0
        j['expires_on'] = self.expires_on.isoformat() if self.expires_on else ''
        j['longitude'] = self.longitude if self.longitude else 0
        j['latitude'] = self.latitude if self.latitude else 0
        j['location_name'] = self.location_name if self.location_name else ''
        j['created_at'] = self.created_at.isoformat() if self.created_at else ''
        return j
      
    def get_images(self):

        imgs = []
        jimgs = JobImage.by_jobid(self.id)
        if jimgs:
            for ji in jimgs:
                imgs.append(ji.url)
        else:
            return imgs
        return imgs

    @classmethod
    def by_id(self,id):
        return DBSession.query(Job).filter(Job.id == id).first()
    
    @classmethod
    def by_employer_id(self,uid):
        return DBSession.query(Job).filter(Job.posted_by == uid).first()

Index('job_lat_long_index', Job.latitude, Job.longitude, Job.category)


#User's skill Category
class SkillCategory(Base):
    __tablename__ = 'skill_category'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    category_id = Column(Integer, nullable=False)
    job_done = Column(Integer, default=0)

    @classmethod
    def by_user_category_id(self,uid,cat_id):
        return DBSession.query(SkillCategory).filter(SkillCategory.user_id == uid, SkillCategory.category_id == cat_id).first()

Index('skill_cat_index', SkillCategory.user_id, SkillCategory.category_id, unique = True)


#Containing the URL of the images
class JobImage(Base):
    __tablename__ = 'job_image'
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer)
    url = Column(Text)

    def __init__(self,job_id,url):
        self.job_id = job_id
        self.url = url

    def serialize(self):
        ji = {}
        ji['id'] = self.job_id
        ji['url'] = self.url
        return ji

    @classmethod
    def by_jobid(cls,id):
        return DBSession.query(JobImage).filter(JobImage.job_id == id).all()
 
    @classmethod
    def default(cls):
        return default_job_pic

Index('job_image_index', JobImage.job_id)


#Containing all Job Applications
class TempJobApplication(Base):
    __tablename__ = 'temp_job_application'
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer)
    employee_id = Column(Integer)
    employer_id = Column(Integer)
    comment = Column(UnicodeText)
    #other fees

    def __init__(self,employee_id,jobId,employer_id,comment):
        self.job_id = jobId
        job = Job.by_id(jobId)
        self.employee_id = employee_id
        self.employer_id = employer_id
        #self.modified_pay = pay
        #self.modified_hours = modified_hours
        self.comment = comment if comment else ""
        #self.status = 1
        #self.application_key = str(uuid.uuid4())

    
    # def serialize(self):

    #     sql = '''
    #     SELECT a.id, a.comment, a.status, a.modified_pay, a.seeker_wti_fees, a.stripe_fees, a.wti_fees, a.total_amount , a.modified_hours,a.application_key, b.id, b.title , b.desc, b.latitude, b.longitude , b.location_name, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.thumbs_up,c.thumbs_down, c.company_id, d.id as d_id, d.first_name, d.last_name,d.profile_pic,d.thumbs_up,d.thumbs_down, d.company_id
    #     FROM job_application AS a
    #     JOIN job AS b
    #     ON a.job_id = b.id
    #     JOIN user AS c
    #     ON a.employee_id = c.id
    #     JOIN user as d 
    #     ON a.employer_id = d.id
    #     WHERE a.id = '''+str(self.id)+''' LIMIT 1       
    #     '''
    #     id, comment, status, modified_pay,seeker_wti_fees,stripe_fees,wti_fees,total_amount, modified_hours, application_key, job_id , job_title, job_desc, job_lat , job_long , job_location, employee_id , employee_fname, employee_lname , employee_ppic, employee_thumbs_up, employee_thumbs_down, employee_company_id, employer_id , employer_fname, employer_lname , employer_ppic, employer_thumbs_up, employer_thumbs_down, employer_company_id = DBSession.execute(sql).fetchone()
        
    #     application = {}
    #     application['application_id'] = id
    #     application['employee'] = get_applicants_info(employee_id , employee_fname, employee_lname , employee_ppic, employee_thumbs_up, employee_thumbs_down, employee_company_id)
    #     application['employer'] = get_user_info(employer_id , employer_fname, employer_lname , employer_ppic, employer_thumbs_up, employer_thumbs_down, employer_company_id)
    #     application['pay'] = modified_pay
    #     application['seeker_wti_fees'] = seeker_wti_fees
    #     #application['stripe_fees'] = stripe_fees
    #     application['wti_fees'] = wti_fees
    #     application['total_amount'] = total_amount
    #     application['hours'] = modified_hours
    #     application['comment'] = comment
    #     application['status'] = status
    #     application['job_id'] = job_id
    #     application['job_title'] = job_title
    #     application['job_desc'] = job_desc
    #     application['job_images'] = Job.by_id(job_id).get_images()
    #     application['job_latitude'] = job_lat
    #     application['job_longitude'] = job_long
    #     application['job_location'] = job_location
    #     application['application_key'] = application_key
    #     return application


    @classmethod
    def by_employee_id(cls,id):
        return DBSession.query(TempJobApplication).filter(TempJobApplication.employee_id == id)

    # @classmethod
    # def by_employer_id(cls,id):
    #     return DBSession.query(TempJobApplication).filter(TempJobApplication.employer_id == id)

    # @classmethod
    # def by_jobid(cls,id):
    #     return DBSession.query(TempJobApplication).filter(TempJobApplication.job_id == id)

    # @classmethod
    # def by_id(cls,id):
    #     return DBSession.query(TempJobApplication).filter(TempJobApplication.id == id).first()

    # def get_actived_at(self):
    #     self.actived_at = datetime.datetime.utcnow()

Index('temp_job_appl_index', TempJobApplication.job_id, TempJobApplication.employee_id,unique=True)

class JobApplication(Base):
    __tablename__ = 'job_application'
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer)
    employee_id = Column(Integer)
    employer_id = Column(Integer)
    modified_pay = Column(BigInteger)
    new_modified_pay = Column(BigInteger)
    modified_hours= Column(Integer)
    comment = Column(UnicodeText)
    created_at = Column(DateTime, default=_get_date)
    payment_key = Column(Text)
    status = Column(Integer,default=1)  #1 = APPLIED,( 2 = CHATTED, 3 = ACCEPTED_BY_EMPLOYER, | 4 = ACCEPTED_BY_SEEKER, 5 = STARTED_JOB, 6 = ENDED_JOB, 7 = REVIEWED_BY_SEEKER, 8 = REVIEWED_BY_EMPLOYER, 9 = PAYMENT_DONE), 10 = CANCELLED
    application_key = Column(Text)
    last_message = Column(UnicodeText)
    actived_at = Column(DateTime)
    last_message_at = Column(DateTime)
    done_at = Column(DateTime)
    #other fees
    stripe_fees = Column(BigInteger) #In cents
    wti_fees = Column(BigInteger) #In cents
    seeker_wti_fees = Column(BigInteger) #In cents
    insurrance_fees = Column(BigInteger) #In cents
    seeker_tyel = Column(BigInteger) #In cents
    employer_tyel = Column(BigInteger) #In cents
    total_amount = Column(BigInteger) #In cents


    def __init__(self,employee_id,jobId,employer_id,pay,modified_hours,comment):
        self.job_id = jobId
        job = Job.by_id(jobId)
        self.employee_id = employee_id
        self.employer_id = employer_id
        self.modified_pay = pay
        self.modified_hours = modified_hours
        self.comment = comment if comment else ""
        self.status = 1
        self.application_key = str(uuid.uuid4())

    
    def serialize(self):

        sql = '''
        SELECT a.id, a.comment, a.status, a.modified_pay, a.seeker_wti_fees, a.stripe_fees, a.wti_fees, a.total_amount , a.modified_hours,a.application_key, b.id, b.title , b.desc, b.category, b.latitude, b.longitude , b.location_name, c.id as c_id, c.first_name, c.last_name,c.profile_pic,c.thumbs_up,c.thumbs_down,c.stripe_account_id, c.company_id, d.id as d_id, d.first_name, d.last_name,d.profile_pic,d.thumbs_up_employer,d.thumbs_down_employer, d.company_id
        FROM job_application AS a
        JOIN job AS b
        ON a.job_id = b.id
        JOIN user AS c
        ON a.employee_id = c.id
        JOIN user as d 
        ON a.employer_id = d.id
        WHERE a.id = '''+str(self.id)+''' LIMIT 1       
        '''
        id, comment, status, modified_pay,seeker_wti_fees,stripe_fees,wti_fees,total_amount, modified_hours, application_key, job_id , job_title, job_desc, job_cate, job_lat , job_long , job_location, employee_id , employee_fname, employee_lname , employee_ppic, employee_thumbs_up, employee_thumbs_down, bank_account, employee_company_id, employer_id , employer_fname, employer_lname , employer_ppic, employer_thumbs_up, employer_thumbs_down, employer_company_id = DBSession.execute(sql).fetchone()
        
        application = {}
        application['application_id'] = id
        application['employee'] = get_applicants_info(employee_id , employee_fname, employee_lname , employee_ppic, employee_thumbs_up, employee_thumbs_down, bank_account, employee_company_id)
        application['employer'] = get_user_info(employer_id , employer_fname, employer_lname , employer_ppic, employer_thumbs_up, employer_thumbs_down, employer_company_id)
        application['pay'] = modified_pay
        application['seeker_wti_fees'] = seeker_wti_fees
        #application['stripe_fees'] = stripe_fees
        application['wti_fees'] = wti_fees
        application['total_amount'] = total_amount
        application['hours'] = modified_hours
        application['comment'] = comment
        application['status'] = status
        application['job_id'] = job_id
        application['job_title'] = job_title
        application['job_desc'] = job_desc
        application['job_category'] = job_cate
        application['job_images'] = Job.by_id(job_id).get_images()
        application['job_latitude'] = job_lat
        application['job_longitude'] = job_long
        application['job_location'] = job_location
        application['application_key'] = application_key
        return application


    @classmethod
    def by_employee_id(cls,id):
        return DBSession.query(JobApplication).filter(JobApplication.employee_id == id)

    @classmethod
    def by_employer_id(cls,id):
        return DBSession.query(JobApplication).filter(JobApplication.employer_id == id)

    @classmethod
    def by_jobid(cls,id):
        return DBSession.query(JobApplication).filter(JobApplication.job_id == id)

    @classmethod
    def by_id(cls,id):
        return DBSession.query(JobApplication).filter(JobApplication.id == id).first()

    def get_actived_at(self):
        self.actived_at = datetime.datetime.utcnow()

Index('job_appl_index', JobApplication.job_id, JobApplication.employee_id,unique=True)


class ComapnyInformation(Base):
    __tablename__ = 'company_info'
    id = Column(Integer, primary_key=True)
    company_id = Column(Text, default='')
    company_address = Column(Text, default='')
    company_zipcode = Column(Text, default='')
    company_city = Column(Text, default='')

    company_name = Column(UnicodeText, default=u'')
    company_phone_number = Column(Text, default='')

    billing_address = Column(Text, default='')
    billing_zipcode = Column(Text, default='')
    billing_city = Column(Text, default='')
    billing_vat_id = Column(Text, default='')

    def __init__(self,company_id,company_name,company_phone_number,company_address,company_zipcode,company_city,billing_address,billing_city,billing_zipcode,billing_vat_id):
        self.company_id = company_id
        self.company_name = company_name
        self.company_phone_number = company_phone_number
        self.company_address = company_address
        self.company_zipcode = company_zipcode
        self.company_city = company_city
        self.billing_address = billing_address
        self.billing_zipcode = billing_zipcode
        self.billing_city = billing_city
        self.billing_vat_id = billing_vat_id


class SavedJob(Base):
    __tablename__ = 'saved_jobs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    job_id = Column(Integer)

    @classmethod
    def by_user_id(cls,id):
        DBSession.query(SavedJob).filter(SavedJob.user_id == id).all()

    @classmethod
    def by_job_id(cls,jobid):
        DBSession.query(SavedJob).filter(SavedJob.job_id == jobid).first()

Index('saved_job_index', SavedJob.user_id, SavedJob.job_id, unique = True)

class FavouriteUser(Base):
    __tablename__ = 'fav_users'
    id = Column(Integer, primary_key=True)
    for_user= Column(Integer)
    fav_user_id = Column(Integer)

    @classmethod
    def by_userid(cls,id):
        DBSession.query(FavouriteUser).filter(FavouriteUser.for_user == id).all()
Index('fav_user_index', FavouriteUser.for_user, FavouriteUser.fav_user_id, unique = True)


class Token(Base):
    __tablename__ = 'tokens'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"), index = True)
    token = Column(Text, default='')
    expiry = Column(DateTime)
    type = Column(Integer) #1= Verify , 2 = Reset
    
    user = relationship('User',primaryjoin='Token.user_id == User.id', lazy="joined",innerjoin=True)

    def __init__(self):
        self.token= str(uuid.uuid4())

    @classmethod
    def generate(cls,uid,type=1):
        t = Token()
        t.user_id = uid
        t.type = type
        t.expiry = datetime.datetime.utcnow()+datetime.timedelta(days=VERIFICATION_MAIL_EXPIRES_IN if type is 1 else RESET_MAIL_EXPIRES_IN)
        DBSession.add(t)
        return t
    
    @classmethod
    def by_token(cls,token):
        return DBSession.query(Token).filter(Token.token == token).first()

Index('token_index', Token.token, mysql_length=255)

#All Logins
class Session(Base):
    __tablename__ = 'session'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="CASCADE"), index = True)
    auth_token = Column(Text, default='')

    user = relationship('User',lazy="joined",innerjoin=True)
    
    def __init__(self):
        self.auth_token= str(uuid.uuid4())

    @classmethod
    def generate(cls,uid):
        s = Session()
        s.user_id = uid
        DBSession.add(s)
        return s


    @classmethod
    def by_token(cls,token):
        return DBSession.query(Session).filter(Session.auth_token == token).first()


Index('session_index', Session.auth_token, mysql_length=255)


#All reviews
class Review(Base):
    __tablename__ = 'review'
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer)
    review_by = Column(Integer)
    review_for = Column(Integer)
    review = Column(UnicodeText)
    thumbs_up = Column(Boolean)
    thumbs_down = Column(Boolean)
    created_at = Column(DateTime,default=_get_date)

    @classmethod
    def by_userid(cls,uid):
        return DBSession.query(Review).filter(Review.review_for == uid)

    def serialize(self):
        r = {}
        r['review_id'] = self.id
        r['review_by'] = User.by_id(self.review_by).info()
        r['review_for'] = User.by_id(self.review_for).info()
        r['review'] = self.review
        r['thumbs_up'] = self.thumbs_up
        r['thumbs_down'] = self.thumbs_down
        r['created_at'] =self.created_at.isoformat()
        return r

Index('review_index', Review.review_by, Review.review_for)


#All Messages
class Message(Base):
    __tablename__ = 'message'
    id = Column(Integer, primary_key=True)

    job_id = Column(Integer) #Job Context
    user_id_1 = Column(Integer)
    user_id_2 = Column(Integer)
    text = Column(Text)

Index('message_index', Message.job_id, Message.user_id_1, Message.user_id_2)

#Response table 
class Response(Base):
    __tablename__ = 'response'
    id = Column(Integer, primary_key = True)
    primary_code = Column(Integer)
    type = Column(Text)
    secondary_code = Column(Text)
    message = Column(UnicodeText)

    def __init__(self,primary_code,type,secondary_code,message=''):
        self.primary_code = primary_code
        self.type = type
        self.secondary_code = secondary_code
        self.message = message

    @classmethod
    def by_code(cls, code):
        return DBSession.query(Response).filter(Response.secondary_code == code).first()

    def serialize(self):
        r = {}
        r['primary_code'] = self.primary_code
        r['secondary_code'] = self.secondary_code
        r['type'] = self.type
        r['message'] = self.message
        return r


#Notification table
class Notifications(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key = True)
    for_user_id = Column(Integer)
    text = Column(UnicodeText)
    type = Column(UnicodeText)
    job_name = Column(UnicodeText)
    employer_id = Column(Integer)
    application_id = Column(Integer)
    created_at = Column(DateTime,default=_get_date)
    finn_text = Column(UnicodeText)

    def __init__(self,for_user_id,text,finn_text,type,job_name,employer_id,application_id):
        self.for_user_id = for_user_id
        self.text = text
        self.finn_text = finn_text
        self.type = type
        self.job_name = job_name
        self.employer_id = employer_id
        self.application_id = application_id

    def serialize(self):
        notification = {}
        notification['id'] = self.id
        notification['for_user_id'] = self.for_user_id
        notification['text'] = self.text
        notification['finn_text'] = self.finn_text
        notification['type'] = self.type
        notification['job_name'] = self.job_name
        notification['employer_id'] = self.employer_id
        notification['application_id'] = self.application_id
        return notification

    @classmethod
    def by_id(cls,id):
        return DBSession.query(Notifications).filter(Notifications.id == id ).first()

#Payment info table
class PaymentInfo(Base):
    __tablename__= 'payment_info'
    id = Column(Integer, primary_key = True)
    application_id = Column(Integer)    
    charge_id = Column(Text)
    refund_id = Column(Text)

    def __init__(self, application_id, charge_id):
        self.application_id = application_id
        self.charge_id = charge_id

    def serialize(self):
        payment_info = {}        
        return payment_info

    @classmethod
    def by_application_di(cls,application_id):
        return DBSession.query(PaymentInfo).filter(PaymentInfo.application_id == application_id).first()

    def add_refund_id(self, refund_id):
        self.refund_id = refund_id

#Reported job table
class ReportedJob(Base):
    __tablename__= 'reported_job'
    id = Column(Integer, primary_key = True)
    job_id = Column(Integer)    
    by_user_id = Column(Integer)


#Payment restriction table
class PaymentRestriction(Base):
    __tablename__= 'payment_restriction'
    id = Column(Integer, primary_key = True)
    for_employer_id = Column(Integer)    
    seeker_id = Column(Integer)
    amount_total = Column(BigInteger)    
    amount_left = Column(BigInteger)    
    created_at = Column(DateTime, default=datetime.datetime.utcnow())

    def __init__(self,for_employer_id,seeker_id,amount_total,amount_left):
        self.for_employer_id = for_employer_id
        self.seeker_id = seeker_id
        self.amount_total = amount_total
        self.amount_left = amount_left