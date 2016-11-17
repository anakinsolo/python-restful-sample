from pyramid.config import Configurator
from sqlalchemy import engine_from_config
from pyramid_mailer.mailer import Mailer
from pyramid.events import NewRequest

from .models import (
    DBSession,
    Base,
    )

v1_root = '/api/v1/'
v1 = 'v1'

def add_cors_headers_response_callback(event):
    def cors_headers(request, response):
        response.headers.update({
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST,GET,DELETE,PUT',
        'Access-Control-Allow-Headers': 'Origin, Content-Type, Accept, Authorization',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Max-Age': '1728000',
        })
    event.request.add_response_callback(cors_headers)


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    config = Configurator(settings=settings)

    config.add_subscriber(add_cors_headers_response_callback, NewRequest)

    #Mailer to send mail
    config.registry['mailer'] = Mailer.from_settings(settings)

    config.add_static_view('/web/', 'web', cache_max_age=3600)
    config.add_static_view('/shitto/', 'docs', cache_max_age=3600)


    ##########################################################################################################
    ## Static File
    ##########################################################################################################
    config.add_route(v1+'_certificate_verify', '/672762715E8EC03ED657C18B6E62F179.txt')


    config.add_route('web', '/')
    config.add_route(v1+'_home', v1_root)


    config.add_route('pingping', '/pingping')

    ##########################################################################################################
    ## v1 User API
    ##########################################################################################################
    config.add_route(v1+'_user', v1_root+'user')
    config.add_route(v1+'_user_login', v1_root+'user/login')
    config.add_route(v1+'_user_login_fb', v1_root+'user/login/fb')
    config.add_route(v1+'_user_logout', v1_root+'user/logout')
    config.add_route(v1+'_user_get', v1_root+'user/{id}')
    config.add_route(v1+'_user_verify', '/verify_email/{token}')
    config.add_route(v1+'_user_forgot', v1_root+'forgot_password')
    config.add_route(v1+'_user_reset', v1_root+'reset_password')
    config.add_route(v1+'_user_change_password', v1_root+'change_password')
    config.add_route(v1+'_user_feedback', v1_root+'feedback')
    config.add_route(v1+'_user_resend_mail', v1_root+'resend')


    ##########################################################################################################
    ## v1 Job API
    ##########################################################################################################
    config.add_route(v1+'_job', v1_root+'job')
    config.add_route(v1+'_job_delete', v1_root+'job/delete')
    config.add_route(v1+'_job_posted', v1_root+'job/posted')
    config.add_route(v1+'_job_report', v1_root+'job/report')
    config.add_route(v1+'_job_get', v1_root+'job/{id}')
    config.add_route(v1+'_job_applicants', v1_root+'job/{jobId}/applicants')
    config.add_route(v1+'_jobcards', v1_root+'jobcards')
    config.add_route(v1+'_quick_jobcards', v1_root+'jobcards/quick')
    config.add_route(v1+'_job_images_delete', v1_root+'job/images/delete')

    ##########################################################################################################
    ## v1 Job Application API
    ##########################################################################################################
    config.add_route(v1+'_application', v1_root+'application')
    config.add_route(v1+'_application_delete', v1_root+'application/delete')
    config.add_route(v1+'_application_status', v1_root+'application/status/next')
    config.add_route(v1+'_application_applied', v1_root+'application/applied')
    config.add_route(v1+'_application_done', v1_root+'application/done')
    config.add_route(v1+'_application_active', v1_root+'application/active')
    config.add_route(v1+'_application_get', v1_root+'application/{application_id}')
    config.add_route(v1+'_application_chat', v1_root+'application/{application_id}/chat')

    ##########################################################################################################
    ## v1 Reviews API
    ##########################################################################################################
    config.add_route(v1+'_review', v1_root+'review/{application_id}')
    config.add_route(v1+'_review_for_as_seeker', v1_root+'user/review/seeker/{user_id}')
    config.add_route(v1+'_review_for_as_employer', v1_root+'user/review/employer/{user_id}')

    
    ##########################################################################################################
    ## v1 Saved Jobs and Users API
    ##########################################################################################################
    config.add_route(v1+'_saved_jobs_post', v1_root+'saved/job')
    config.add_route(v1+'_saved_jobs_get', v1_root+'saved/job/get')
    config.add_route(v1+'_saved_users_get', v1_root+'saved/users')
    config.add_route(v1+'_suggested_users_get', v1_root+'suggested/users')
    config.add_route(v1+'_suggested_user_apply', v1_root+'suggested/users/apply')

    ##########################################################################################################
    ## v1 Payement API
    ##########################################################################################################
    config.add_route(v1+'_payment_add', v1_root+'payment/add')
    config.add_route(v1+'_payment_get', v1_root+'payment/get')
    config.add_route(v1+'_payment_delete', v1_root+'payment/delete')
    config.add_route(v1+'_payment_paid', v1_root+'payment/paid')
    config.add_route(v1+'_payment_paid_to', v1_root+'payment/paid/{application_id}')
    config.add_route(v1+'_payment_received', v1_root+'payment/received')
    config.add_route(v1+'_payment_received_from', v1_root+'payment/received/{application_id}')
    config.add_route(v1+'_payment_refund',v1_root+'payment/refund')
    config.add_route(v1+'_payment_update',v1_root+'payment/update')


    ##########################################################################################################
    ## v1 Notification API
    ##########################################################################################################
    config.add_route(v1+'_notification', v1_root+'notification')
    config.add_route(v1+'_notification_delete', v1_root+'notification/delete')
    config.add_route(v1+'_notification_chats', v1_root+'notification/chats')

    ##########################################################################################################
    ## v1 Constants API
    ##########################################################################################################
    config.add_route(v1+'_skill_keywords', v1_root+'keywords/skills')
    config.add_route(v1+'_filter_keywords', v1_root+'keywords/filters')

    ##########################################################################################################
    ## v1 Terms and Conditions API
    ##########################################################################################################
    config.add_route(v1+'_terms_and_conditions', v1_root+'tos')


    ##########################################################################################################
    ## v1 Company API
    ##########################################################################################################    
    config.add_route(v1+'_company', v1_root+'company')


    config.scan()
    return config.make_wsgi_app()
