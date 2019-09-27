# Custom porting of https://github.com/ewjoachim/bitwarden-keyring
# Author Guillaume GILL
'''
MIT License

Copyright (c) 2018, Joachim Jablon

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
import base64
import json
import os
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from keyring_plugins import BaseKeyringPlugin

PRIORITY = 10  # Doc is oddly vague


def get_db_location(environ, platform):
    """
    This is a port of
    https://github.com/bitwarden/cli/blob/783e7fc8348d02853983211fa28dd8448247ba92/src/bw.ts#L67-L75
    """
    env = environ.get("BITWARDENCLI_APPDATA_DIR")
    if env:
        path = os.path.expanduser(env)

    elif platform == "darwin":
        path = os.path.expanduser("~/Library/Application Support/Bitwarden CLI")

    elif platform == "win32":
        path = os.path.expandvars("%AppData%/Bitwarden CLI")

    else:
        path = os.path.expanduser("~/snap/bw/current/.config/Bitwarden CLI")
        if not os.path.exists(path):
            path = os.path.expanduser("~/.config/Bitwarden CLI")

    return os.path.join(path, "data.json")


def open_db(db_location):
    try:
        with open(db_location, "r") as file:
            return json.load(file)
    except IOError:
        return {}


def extract_logged_user(db):
    return db.get("userEmail")


def bitwarden_cli_installed():
    return bool(shutil.which("bw"))


def ask_for_session(is_authenticated):
    command = ask_for_session_command(is_authenticated)
    result = bw(command, "--raw")
    return result


def ask_for_session_command(is_authenticated):
    return "unlock" if is_authenticated else "login"


def wrong_password(output):
    if "Username or password is incorrect" in output:
        return True
    elif "Invalid master password" in output:
        return True
    return False


def bw(*args, session=None):

    cli_args = ["bw"]
    if session:
        cli_args += ["--session", session]

    cli_args += list(args)

    while True:
        try:
            result = subprocess.run(
                cli_args, stdout=subprocess.PIPE, check=True
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            output = exc.stdout.decode("utf-8")
            if wrong_password(output):
                print(output)
                continue
            raise ValueError(output) from exc
        else:
            break

    return result


def display_credentials(mapping):
    result = []
    for val, match in mapping.items():
        result.append(f"{val}) {display_credential(match)}")

    return "\n".join(result)


def display_credential(match):
    return f"{match.get('name', 'no name')} - {match['login']['username']}"


def select_match(matches):
    try:
        return select_single_match(matches)
    except ValueError:
        return select_from_multiple_matches(matches)


def encode(payload):
    return base64.b64encode(json.dumps(payload).encode("utf-8"))


def get_session(environ):
    if "BW_SESSION" in environ:
        try:
            # Check that the token works.
            bw("sync")
        except ValueError:
            pass
        else:
            return environ["BW_SESSION"]

    location = get_db_location(environ, sys.platform)

    db = open_db(location)

    user = extract_logged_user(db)

    return ask_for_session(bool(user))


def get_password(service, username):
    session = get_session(os.environ)

    # Making sure we're up to date
    bw("sync", session=session)

    password = bw("get", "password", service, session=session)

    return password


def set_password(service, username, password):
    session = get_session(os.environ)

    template_str = bw("get", "template", "item", session=session)

    template = json.loads(template_str)
    template.update(
        {
            "name": service,
            "notes": None,
            "login": {
                "uris": [{"match": None, "uri": None}],
                "username": "ansible-vault",
                "password": password,
            },
        }
    )

    payload = encode(template)

    bw("create", "item", payload)


def confirm_delete(session, credential):

    print("The following match will be DELETED:")
    print(display_credential(credential))
    if input("Confirm ? (type 'yes')").lower() == "yes":
        bw("delete", "item", credential["id"], session=session)
        print("Deleted.")
        return
    print("Cancelled.")


def delete_password(service, username):
    session = get_session(os.environ)

    bw("sync", session=session)

    result = bw("get", "item", service, session=session)

    credential = json.loads(result)

    confirm_delete(session, credential)


class KeyringPlugin(BaseKeyringPlugin):
    def __init__(self):
        super(KeyringPlugin, self).__init__()
        if not bitwarden_cli_installed():
            raise RuntimeError(
                "This plugin requires bitwarden cli: https://help.bitwarden.com/article/cli/"
            )

    def parse_vault_id(self, vault_id):
        vault_id = vault_id.split(':')
        service=vault_id[0]
        username=vault_id[1]

        return (service, username)

    def fetch(self, vault_id):
        service, username = self.parse_vault_id(vault_id)
        return get_password(service, username)

    def get_usable_ids(self, vault_path):
        pass

    def encrypt(self, vault_id, vault_path):
        pass

    def change_password(self, vault_id, vault_path):
        return set_password(service, username, password)

    def set_password(self, id, password):
        name, username = self.parse_vault_id(id)
        return set_password(name, username, password) 
