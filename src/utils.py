import os
import json

login_creds_file = os.path.expanduser("~/.music_dl_creds.json")
state_seperator = '|||'


def safe_expand_directory(directory):
    full_path = ""
    if os.path.exists(directory):
        full_path = os.path.expanduser(directory)
    else:
        os.mkdirs(directory)
        full_path = os.path.expanduser(directory)
    return full_path


def save_login_creds(login_creds):
    json_data = tuple_to_json(login_creds)
    write_json_to_file(json_data, login_creds_file)


def tuple_to_json(tuple):
    tuple_dict = tuple._asdict()
    return tuple_dict


def write_json_to_file(file):
    with open(login_creds_file, 'w') as file:
        json.dump(json, file)


def build_state_string(user, provider):
    state_string = state_seperator.join([user.username, user.password, provider])
    return state_string


def quit():
    print("exiting app")
    os.sys.exit(0)
