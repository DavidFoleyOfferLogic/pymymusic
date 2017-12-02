#!/usr/bin/env python

import cherrypy
import webbrowser
import functools
from exceptions import NoCredentialsFoundException
from models import User, GoogleAccounts, GoogleMusicPlayerAccounts, SpotifyAccounts, UserSongs, create_tables
import music_util
import logging
import argparse
import cherrypy.process.plugins
from providers import google_provider, spotify_provider
from config import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

redirect_uri = config.redirect_uri
state_seperator = config.state_seperator


class OauthHandler(object):
    """Documentation for OauthHandler
    """

    def __init__(self):
        super(OauthHandler, self).__init__()

    @cherrypy.expose
    def oauth_callback(self, code, state, **params):
        username, password, provider = state.split(state_seperator)
        logger.info("received code %s from provider: %s", provider, code)
        user = User.get(User.username == username)
        if provider == 'youtube':
          scope = cherrypy.request.params.get('scope')
          google_provider.auth_and_store_google_user(user, code, scope)
        elif provider == 'spotify':
          spotify_provider.auth_and_store_spotify_user(user, code)
        elif provider == 'lastfm':
          logger.warn("lastfm unsupported")
          pass
        else:
          raise Exception(f"unsupported provider: {provider}")


def create_user():
    logger.info("creating new user")
    username = input("Enter your email: ")
    password = input("Enter your password: ")
    download_path = input("Where should your songs be stored: (For Example ~/Music): ")
    user = User(username=username, password=password, download_path=download_path)
    user.save()
    return user


def load_user():
    username = input("Enter your email: ")
    users = User.select().where(User.username == username)
    if users:
        user = users[0]
        logger.info("loaded user: %s", username)
    else:
        logger.error("user not found %s", username)
        raise NoCredentialsFoundException("User not found")
    return user


def menu(user):
    options = {'link_account': link_account, 'sync': sync, 'quit': quit}
    prompt = "Please choose an action: "
    selected = show_options(list(options.keys()), prompt)
    command = options[list(options.keys())[selected]]
    logger.info("running command: %s", command)
    if command in (link_account, sync):
        functools.partial(command, user)()
    else:
        command()


def sync_google_account(user):
    try:
        logger.info("syncing user's google youtube account")
        google_provider.sync(user)
    except Exception as ex:
        logger.error("error syncing user's google account", ex)


def sync_spotify_account(user):
    try:
        logger.info("syncing user's spotify account")
        spotify_provider.sync(user)
    except Exception as ex:
        logger.error("error syncing user's spotify account", ex)


def sync_google_music_account(user):
    try:
        logger.info('syncing users gmusic account')
        gmusic_account = GoogleMusicPlayerAccounts.get(
            GoogleMusicPlayerAccounts.user == user)
        gmusic_account.sync()
    except Exception as ex:
        logger.error("Error syncing user's google music account", ex)


def sync(user):
    """Sync all users songs.
    Queries all a users linked streaming services for latest tracks and
    downloads any new ones.

    :param user: Currently logged in user
    :returns:
    :rtype:

    """
    sync_google_music_account(user)
    sync_google_account(user)
    sync_spotify_account(user)
    logger.info("finished syncing")
    usersongs = UserSongs.get_users_songs(user)
    music_util.download_users_new_songs(user, usersongs)


def link_google_music_player(user):
    """
    Link a user's google music player account.
    We don't use oauth here so we just store the raw username/password.
    """
    logger.info("linking user: %s google music player account", user.username)
    username = input("Enter your google music email: ")
    password = input("Enter your google music password: ")
    user_gmusic_account = GoogleMusicPlayerAccounts(
        id=None, user=user, username=username, password=password)
    user_gmusic_account.save()
    return user_gmusic_account


def start_oauthhandler(auth_uri):
    webbrowser.open(auth_uri, new=0)
    cherrypy.quickstart(OauthHandler())


def link_account(user):
    options = {
        'Google Music Player': link_google_music_player,
        'Youtube': google_provider.create_youtube_auth_uri,
        'Spotify': spotify_provider.create_spotify_auth_uri
    }
    prompt = "Select an account type that you want to link:"
    selected = show_options(list(options.keys()), prompt)
    create_auth_uri_function = options[list(options.keys())[selected]]
    logger.debug("user selected option: %s", create_auth_uri_function)
    selected_key = list(options.keys())[selected]
    is_account_already_linked = check_account_already_linked(selected_key, user)
    should_link = True
    if is_account_already_linked:
        should_link = input("Account already linked. Do you want to link again? (y/n): ")
        should_link = should_link.lower().startswith('y')
    if should_link:
        if create_auth_uri_function == link_google_music_player:
            link_google_music_player(user)
        else:
            auth_uri = create_auth_uri_function(user, redirect_uri)
            start_oauthhandler(auth_uri)


def check_account_already_linked(account_type, user):
    """Check is user already has a linked account for that account type
    :param account_type:
    :param user:
    :returns:
    :rtype:
    """
    logger.info(f"selected account type: {account_type}")
    account_type_check_function_map = {
        'Google Music Player': lambda user: GoogleMusicPlayerAccounts.get(GoogleMusicPlayerAccounts.user == user),
        'Youtube': lambda user: GoogleAccounts.get(GoogleAccounts.user == user),
        'Spotify': lambda user: SpotifyAccounts.get(SpotifyAccounts.user == user)
    }
    check_function = account_type_check_function_map[account_type]
    is_linked = False
    try:
        check_function(user)
        is_linked = True
    except Exception:
        is_linked = False
    return is_linked


def show_options(options, prompt):
    # print is required here because this is a cli menu
    print(prompt)
    for idx, element in enumerate(options):
        print("{}) {}".format(idx + 1, element))
    i = input("Enter number: ")
    try:
        if 0 < int(i) <= len(options):
            return (int(i) - 1)
    except:
        pass
    return None


def parse_arguments():
    parser = argparse.ArgumentParser(description='Configure music downloader')
    parser.add_argument('-i', '--interactive', action='store_true')
    return parser.parse_args()


def main():
    args = parse_arguments()
    create_tables()
    if args.interactive:
        try:
            user = load_user()
        except NoCredentialsFoundException:
            logger.debug("no credentials found for user")
            user = create_user()
        menu(user)
    else:
        logger.info("running non interactive")
        try:
            user = load_user()
            sync(user)
        except Exception as ex:
            logger.error("error running sync", ex)


if __name__ == '__main__':
    main()
