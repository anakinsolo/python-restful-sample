from constants import default_profile_pic

def get_user_info(id, first_name, last_name, profile_pic, thumbs_up, thumbs_down, is_company):
    u = {}
    u['user_id'] = id
    u['name'] = (first_name if first_name else '')+' '+(last_name if last_name else '')
    u['thumbs_up'] = thumbs_up
    u['thumbs_down'] = thumbs_down
    u['is_company'] = True if is_company else False
    if profile_pic:
        u['profile_pic'] = profile_pic
    else:
        u['profile_pic'] = default_profile_pic
    return u


