import bs4
import json
import requests

class TravianPageStatus(object):
    SIG_LOGIN_FAILED = '''<input class="text" type="password" name="pw" value=""'''

class TravianClient(object):
    def __init__(self, config):
        """ initialize instance

            config	configure object
        """
        self.config = config
        self.session = requests.Session()

    def login(self):
        response = self.session.get(self.config.url('login.php'))
        model = bs4.BeautifulSoup(response.text)
        inp = model.find('input', attrs = { 'type': 'hidden', 'name': 'ft' })
        ft = inp.get('value')
        data = {
            'ft': ft,
            'user': self.config.username,
            'pw': self.config.password,
            's1.x': 0,
            's1.y': 0
        }
        response = self.session.post(self.config.url('login.php'), data = data)
        return not TravianPageStatus.SIG_LOGIN_FAILED in response.text

class TravianConfig(object):
    def __init__(self, base_url, username, password):
        """ Travian client configure object

            base_url    Ex: http://220.132.233.59/tra/
            username	Username
            password	Password
        """

        if base_url[-1] != '/':
            base_url += '/'
        self.base_url = base_url
        self.username = username
        self.password = password

    def url(self, url):
        if url[0] == '/':
            url = url[1:]
        return self.base_url + url



def main():
    try:
        fobj = open('settings.json', 'r')
        settings = json.load(fobj)
        print("Setting was load from settings.json")
    except IOError:
        import getpass
        settings = {
            'base_url': input('Base URL: '),
            'username': input('Usename: '),
            'password': getpass.getpass()
        }
    config = TravianConfig(settings['base_url'], settings['username'],
                           settings['password'])
    client = TravianClient(config)
    if not client.login():
        return 'Login failed'

    return 0

if __name__ == '__main__':
    result = main()
    import sys
    if result:
        print(result, file = sys.stderr)
    else:
        print('Success', file = sys.stderr)
