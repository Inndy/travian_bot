import bs4
import json
import requests
import time

class TravianPageStatus(object):
    SIG_LOGIN_FAILED = '''<input class="text" type="password" name="pw" value=""'''

class TravianClient(object):
    RESOURCES_NAME = "木材 磚塊 鋼鐵 穀物".split()

    def __init__(self, config):
        """ initialize instance

            config	configure object
        """
        self.config = config
        self.session = requests.Session()
        self.last_dorf1 = None

    def http_get(self, url):
        if not (url.startswith("http://") or url.startswith("https://")):
            url = self.config.url(url)
        time.sleep(self.config.request_interval)
        return self.session.get(url)

    def _strip_tag(self, text):
        return text.replace('</body>', '').replace('</html>', '')

    def login(self):
        response = self.http_get('login.php')
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
        if TravianPageStatus.SIG_LOGIN_FAILED not in response.text:
            return True
        else:
            return False

    def clean_cache(self):
        self.last_dorf1 = None

    def request_dorf1(self, cache = True):
        if cache and self.last_dorf1:
            return self.last_dorf1
        response = self.http_get('dorf1.php')
        text = self._strip_tag(response.text)
        self.last_dorf1 = bs4.BeautifulSoup(text)
        return self.last_dorf1

    def info(self):
        model = self.request_dorf1()

        # Parse tiemr data
        self.timers = []
        for i in range(1, 10):
            timer = model.find('span', attrs = { 'id': 'timer' + str(i) })
            if timer:
                self.timers.append(timer.text)
            else:
                break

        # Parse resources data
        self.resources = []
        for i in range(1, 5):
            res = model.find('td', attrs = { 'id': 'l' + str(i) },
                             recursive = True)
            self.resources.append([ int(n) for n in res.text.split('/') ])
        self.resources.reverse()

    def dump_status(self):
        result = []
        result.append("=== Resources ===")
        for i, (m, n) in enumerate(self.resources):
            result.append("%s: %d / %d" %
                          (TravianClient.RESOURCES_NAME[i], m, n))
        result.append("")

        result.append("=== Timers ===")
        result += self.timers
        result.append("")

        print("\n".join(result))

    def parse_resource_farm(self, model):
        m = model.find('map', { 'id': 'rx' })
        if not m: return None
        self.resource_farm = []
        for area in m.find_all('area'):
            title = area.get('title')
            if 'Level' not in title: continue
            t, _, lv = title.split()
            self.resource_farm.append((t, int(lv), area.get('href')))

    def upgrade_resource(self, obj):
        response = self.http_get(obj[2])
        model = bs4.BeautifulSoup(self._strip_tag(response.text))
        build = model.find('a', { 'class': 'build' })
        if build and build.get('href'):
            self.http_get(build.get('href'))
            name, lv, _ = obj
            return 'Upgrade %s from lv.%d to lv.%d' % (name, lv, lv + 1)
        else:
            return False

    def timer_to_seconds(self, timer):
        timer = timer.split(':')
        for i, v in enumerate(timer):
            if '-' in v: v = '-' + v.split('-')[-1]
            timer[i] = int(v)
        return timer[0] * 3600 + timer[1] * 60 + timer [2]

    def get_villages(self):
        self.villages = []
        model = self.request_dorf1()
        villages = model.select('#vlist tr td a')[1:]
        self.villages = [ (m.text, m.get('href')) for m in villages ]

    def goto_village(self, village):
        url = village[1]
        if url[0] == '?': url = 'dorf1.php' + url
        self.http_get(url)




class TravianConfig(object):
    def __init__(self, data):
        """ Travian client configure object

            base_url                Ex: http://220.132.233.59/tra/
            username                Username
            password                Password
            min_wait_time           Minimal waiting time
            additional_wait_time    Additional wait time
            request_interval        Delay after request
        """

        # check for essential config
        loss = []
        for required in 'base_url username password'.split():
            if required not in data: loss.append(required)
        if loss: raise KeyError('Keys not found (%s)' % ', '.join(loss))

        base_url = data['base_url']
        if base_url[-1] != '/': base_url += '/'
        data['base_url'] = base_url

        self.min_wait_time = 11
        self.additional_wait_time = 2
        self.request_interval = 1

        for key, value in data.items():
            setattr(self, key, value)

    def url(self, url):
        if url[0] == '/':
            url = url[1:]
        return self.base_url + url

class TravianResourceFarmingBot(object):
    def __init__(self, client):
        self.client = client

    def run(self):
        model = self.client.request_dorf1()
        self.client.parse_resource_farm(model)
        if len(self.client.timers) < 2:
            # Find out minimal level
            m = min(self.client.resource_farm, key = lambda obj: obj[1])
            result = self.client.upgrade_resource(m)
            print(result if result else 'Upgrade failed.. (%s)' % m[0])

        if len(self.client.timers) > 1:
            timers = [ self.client.timer_to_seconds(t) for t in self.client.timers ]
            t = min(timers) + self.client.config.additional_wait_time
            t = max(t, self.client.config.min_wait_time)
            return t
        else:
            return self.client.config.min_wait_time

    def run_forever(self):
        while True:
            self.client.request_dorf1(False) # Don't use cache
            self.client.info()
            self.client.dump_status()

            print('Resource farming bot is running...')
            sleep_time = self.run()
            print('Resource farming bot is going to sleep for %d secs...' % sleep_time)
            time.sleep(sleep_time)


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

    if type(settings) is list:
        for i, setting in enumerate(settings):
            print("%2d. %s" % (i + 1, setting['username']))
        i = input("Choose one account: ")
        try:
            i = int(i) - 1
            settings = settings[i]
        except ValueError:
            return "Not a valid number"
        except IndexError:
            return "Account not exists (Index out of bound)"
    elif type(settings) is not dict:
        return "Invalid configfile"

    config = TravianConfig(settings)
    client = TravianClient(config)
    if not client.login():
        return 'Login failed'

    client.get_villages()
    if len(client.villages) > 1:
        for i, (name, url) in enumerate(client.villages):
            print("%2d. %s" % (i + 1, name))
        v = input("Choose one village: ")
        try:
            v = int(v) - 1
            village = client.villages[v]
        except ValueError:
            return "Not a valid number"
        except IndexError:
            return "Village not exists (Index out of bound)"
        client.goto_village(village)

    bot = TravianResourceFarmingBot(client)
    bot.run_forever()

    return 0

if __name__ == '__main__':
    import sys
    try:
        result = main()
    except KeyboardInterrupt:
        print("Goodbye.", file = sys.stderr)
        exit()

    if result:
        print(result, file = sys.stderr)
    else:
        print('Success', file = sys.stderr)
