import http.cookiejar
import re
import sqlite3
import urllib
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup
import requests

from hstest import CheckResult, FlaskTest

INITIAL_RECORDS = [
    ('[a-zA-Z]+_66!', 'Thrawn_66!', True),
    ('^.*$', '34534o', False),
    ('HELLO WORLD', 'HELLO WORLD', True),
    ('(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)', 'some text', False),
    ('(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)', 'example@gmail.com', True),
]


class RegexToolTest(FlaskTest):
    source = 'app'
    use_database = True
    cookie_jar = http.cookiejar.CookieJar()
    CSRF_PATTERN = r'<input[^>]+name="csrfmiddlewaretoken" ' \
                   r'value="(?P<csrf>\w+)"[^>]*>'
    input_pattern = '''<input[^>]+name=['"][a-zA-Z\d/_]+['"][^>]*>'''
    link_pattern = '''<a[^>]+href=['"][a-zA-Z\d/_]+['"][^>]*>(.+?)</a>'''

    testing_regex = [('[0-9]?[0-9]:[0-9][0-9]', '17:50', True),
                     ('\d{5}-\d{4}|\d{5}', 'zipcode', False)]


    def check_create_record(self) -> CheckResult:

        connection = sqlite3.connect("db.sqlite3")
        cursor = connection.cursor()
        try:
            cursor.executemany(
                "INSERT INTO record "
                " ('regex', 'text', 'result')"
                " VALUES (?, ?, ?)",
                INITIAL_RECORDS
            )
            connection.commit()
            cursor.execute("SELECT regex, text, result FROM record")
            result = cursor.fetchall()
            for item in INITIAL_RECORDS:
                if item not in result:
                    return CheckResult.wrong(('Check your Record model: '
                                              '"regex" and "text" should be of the string type, '
                                              '"result" should be of the "bool" type'))
            return CheckResult.correct()
        except sqlite3.DatabaseError as error:
            return CheckResult.wrong(str(error))

    def check_data_types(self) -> CheckResult:
        connection = sqlite3.connect("db.sqlite3")
        cursor = connection.cursor()
        table_columns = [{"name": "regex", "count": 50}, {"name": "text", "count": 1024}]
        for column in table_columns:
            cursor.execute("SELECT type FROM pragma_table_info('record') where name='{}'".format(column["name"]))
            result = cursor.fetchone()
            if result is None or len(result)==0:
                return CheckResult.wrong('Table "record" has no column named "{}", '
                                         'if you want to change model in existing database, remember to use migrate, ALTER TABLE, or delete database file.'.format(column["name"]))
            if str(column["count"]) not in result[0]:
                return CheckResult.wrong(
                    'Check your Record model : ' 
                    'column "{}" must be a string type with {} symbols, now: {}, '
                    'if you want to change model in existing database, remember to use migrate, ALTER TABLE, or delete database file.'.format(column["name"], column["count"], result[0]))
        return CheckResult.correct()

    def check_home_page_greeting(self) -> CheckResult:
        try:
            main_page = self.get(self.get_url())
            soup = BeautifulSoup(main_page, 'html.parser')
            try:
                h2_content = soup.find('h2').text.lower()
            except AttributeError:
                return CheckResult.wrong('Tag h2 is to be used')
            if 'welcome to regex testing tool' not in h2_content:
                return CheckResult.wrong(
                    'Main page should contain "Welcome to regex testing tool!" line'
                )
            try:
                inputs = soup.find_all('input')
                if len(inputs) != 4:
                    button = soup.find('button')
                    if button is not None:
                        inputs.append(button)
                if 'name' not in inputs[0].attrs:
                    return CheckResult.wrong('The first field should have name attribute')
                if inputs[0].attrs['name'] != 'regex':
                    return CheckResult.wrong('The first field should have name "regex"')
                if 'type' in inputs[0].attrs:
                    if inputs[0].attrs['type'] != 'text':
                        return CheckResult.wrong('The first field should have type "text"')
                if 'name' not in inputs[1].attrs:
                    return CheckResult.wrong('The second field should have name attribute')
                if inputs[1].attrs['name'] != 'text':
                    return CheckResult.wrong('The second field should have name "text"')
                if 'type' in inputs[1].attrs:
                    if inputs[1].attrs['type'] != 'text':
                        return CheckResult.wrong('The second field should have type "text"')
                buttons = soup.find_all('button')
                if 'type' not in buttons[0].attrs:
                    return CheckResult.wrong('The button should have type attribute')
                if buttons[0].attrs['type'] != 'submit':
                    return CheckResult.wrong(('Make sure there is a button wih the type '
                                              '"submit" on your page'))
            except IndexError:
                return CheckResult.wrong('The form lacks some of the fields')
            try:
                a_href = soup.find('a').attrs['href']
            except AttributeError:
                return CheckResult.wrong('The link to the history page is missing')
            href = '/history/'
            if a_href != href:
                return CheckResult.wrong(f'The "href" attribute is to be equal to {href}')
            return CheckResult.correct()
        except urllib.error.URLError:
            return CheckResult.wrong(
                'Cannot connect to the menu page.'
            )



    def check_home_page_layout(self) -> CheckResult:
        number_of_input_tags = 2
        main_page = self.get(self.get_url())

        input_tags = re.findall(self.input_pattern, main_page)

        if len(input_tags) < number_of_input_tags:
            return CheckResult.wrong("Missing input tags or name attribute")

        link_tag = re.findall(self.link_pattern, main_page)
        if not link_tag:
            return CheckResult.wrong("Main page should contain link to history page")

        return CheckResult.correct()

    def check_create_regex_test(self) -> CheckResult:

        URL = self.get_url()
        client = requests.session()
        client.get(URL)
        try:
            for regex in self.testing_regex:
                regex_data = dict(regex=regex[0], text=regex[1])
                response = client.post(URL, data=regex_data, headers=dict(Referer=URL))
                if not response.ok:
                    return CheckResult.wrong("Bad response.")
                if str(regex[2]) not in response.text:
                    return CheckResult.wrong((f"Match result is wrong. "
                                              f"For regex {regex[0]} and text {regex[1]} "
                                              f"should be {regex[2]}"))
        except urllib.error.URLError as err:
            return CheckResult.wrong(f'Cannot create test: {err.reason}. Check the form method.')
        return CheckResult.correct()

    def check_write_to_database(self) -> CheckResult:
        connection = sqlite3.connect("db.sqlite3")
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT regex, text, result FROM record")
            result = cursor.fetchall()

            for item in self.testing_regex:
                if item not in result:
                    return CheckResult.wrong('New tests are not in database')
            return CheckResult.correct()
        except sqlite3.DatabaseError as error:
            return CheckResult.wrong(str(error))

    def check_redirect_result_page(self) -> CheckResult:
        connection = sqlite3.connect("db.sqlite3")
        cursor = connection.cursor()
        cursor.execute("DELETE FROM record")
        connection.commit()
        URL = self.get_url()
        client = requests.session()
        client.get(URL)
        regex_data = dict(regex='\d?\d/\d?\d/\d\d\d\d', text='12/25/2009')
        response = client.post(URL, data=regex_data, headers=dict(Referer=URL))
        if response.status_code!=200:
            return CheckResult.wrong("""The attempt to add data was unsuccessful, regex: \"{}\", text: \"{}\"""".format(regex_data['regex'], regex_data['text']))

        cursor.execute("PRAGMA table_info('record')")
        result = cursor.fetchone()
        id_name = result[1]
        result = cursor.execute("SELECT "+id_name+" FROM record ORDER BY "+id_name+" DESC").fetchone()

        if len(result)==0:
            return CheckResult.wrong("""Data not added to the database, regex: \"{}\", text: \"{}\"""".format(regex_data['regex'], regex_data['text']))
        result = result[0]
        expected_url = self.get_url(f"result/{result}/")
        if expected_url != response.url:
            return CheckResult.wrong(("""Request was not redirected correctly, 
                                      it should have been redirected to the result page"""))
        return CheckResult.correct()

    def check_result_page(self) -> CheckResult:
        connection = sqlite3.connect("db.sqlite3")
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM record")
        records = cursor.fetchall()
        index = 0
        for record in records:
            if index >= 5:
                break
            text = f"Text: {record[2]}"
            regex = f"Regex: {record[1]}"
            result = f"{bool(record[3])}"
            result_page = self.get(self.get_url(f"result/{record[0]}/"))
            if regex not in result_page:
                return CheckResult.wrong("Regex should be in the page")
            if text not in result_page:
                return CheckResult.wrong("Testing string should appear in the page")
            if result not in result_page:
                return CheckResult.wrong("Result of testing also must be in the page")
            index += 1
        return CheckResult.correct()

    def check_result_links(self) -> CheckResult:
        history_page_url = self.get_url('history/')
        history_page = self.get(history_page_url)
        soup = BeautifulSoup(history_page, features="html.parser")
        names = ['[a-zA-Z]+_66!', '^.*$', 'HELLO WORLD',
                 '(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$)',
                 '(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$)',
                 '[0-9]?[0-9]:[0-9][0-9]', '\\d{5}-\\d{4}|\\d{5}',
                 '\\d?\\d/\\d?\\d/\\d\\d\\d\\d']
        connection = sqlite3.connect('db.sqlite3')
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM record ORDER BY id DESC ")

        result = cursor.fetchall()
        all_a = soup.findAll('a')
        if len(all_a) != len(result):
            return CheckResult.wrong("Wrong number of links on history page")
        for link in all_a:
            try:
                self.get(self.get_url(link.get('href')))
            except urllib.error.URLError:
                return CheckResult.wrong(
                    f"Cannot connect to the {link.get('href')} page."
                )
            if link.text not in names:
                return CheckResult.wrong(f'The link {link.attrs["href"]} has a wrong name')
        return CheckResult.correct()
