# coding: utf-8
# Импортирует поддержку UTF-8.
from __future__ import unicode_literals

# Импортируем модули для работы с JSON и логами.
import json
import logging
import Database

# Импортируем подмодули Flask для запуска веб-сервиса.
from flask import Flask, request
app = Flask(__name__)


logging.basicConfig(filename='log.txt', level=logging.DEBUG)

# Хранилище данных о сессиях.
sessionStorage = {}
sessionKeyToLog = [
    'user_id',
    'session',
    'stage',
    'locale',
    'timezone',
    'this_statement',
    'symptom_id',
    'version',
]
database = Database.connect()


# Задаем параметры приложения Flask.
@app.route("/", methods=['POST'])
# Функция получает тело запроса и возвращает ответ.
def main():
    logging.info('Start')
    request_json = request.get_json(force=True)
    print(request_json)
    logging.info('Request: %r', request_json)

    response = {
        "version": request_json['version'],
        "session": request_json['session'],
        "meta": request_json['meta'],
        "response": {
            "end_session": False
        }
    }

    handle_dialog(request_json, response)

    logging.info('Response: %r', response)

    return json.dumps(
        response,
        ensure_ascii=False,
        indent=2
    )


# Функция для непосредственной обработки диалога.
def handle_dialog(req, res):
    logging.info('handle_dialog')
    user_id = req['session']['user_id']
    sessionStorage[user_id] = get_session(user_id)
    logging.info('go session')
    if not sessionStorage[user_id]:
        logging.info('no session saved, make mew')
        sessionStorage[user_id] = {
            'session_id': 0,
            'version': req['version'],
            'locale': req['meta']['locale'],
            'timezone': req['meta']['timezone'],
            'user_id': user_id,
            'session': req['session']['session_id'],
        }

    if req['session']['new']:
        logging.info('new user')
        # Это новый пользователь.
        # Инициализируем сессию и поприветствуем его.
        res['response']['text'] = 'Привет! Я твой домашний доктор! Я помогу тебе с твоим недугом!'
        res['response']['buttons'] = get_init_phrases(user_id)
        save_session(user_id)
        logging.info('end')
        return

    session = sessionStorage[user_id]
    print(session)
    logging.info('session: %r', session)

    # Обрабатываем ответ пользователя.
    user_answer = req['request']['original_utterance'].lower()
    print(user_answer)
    if session['stage'] == 1:
        symptom_id = get_symptom_id_by_init_phrase(user_id, user_answer)
        print(symptom_id)
        statement = get_symptom_statement(user_id, symptom_id, 0, '')
        print(statement)
    elif session['stage'] == 2:
        allowed_answers = [
            'да',
            'нет',
        ]
        statement = {}
        if user_answer in allowed_answers:
            statement = get_symptom_statement(user_id, session['symptom_id'], session['this_statement'], user_answer)
    else:
        statement = {}

    res['response']['text'] = statement['StatementBody']
    res['response']['buttons'] = [
        'Да',
        'Нет',
    ]

    save_session(user_id)


def get_init_phrases(user_id):
    session = sessionStorage[user_id]
    init_phrases = database.get_all('select * from `InitPhrases` p group by p.SymptomID order by rand()')

    init_phrases = [
        {'title': phrase['PhraseBody'], 'hide': True}
        for phrase in init_phrases[:3]
    ]

    session['init_phrases'] = init_phrases
    session['stage'] = 1
    sessionStorage[user_id] = session

    return init_phrases


def get_symptom_id_by_init_phrase(user_id, init_phrase):
    symptom_info = database.get_item(
        "select SymptomID from `InitPhrases` p where lower(p.PhraseBody) = %s", (init_phrase,))
    symptom_id = symptom_info['SymptomID']
    sessionStorage[user_id]['symptom_id'] = symptom_id
    return symptom_id


def get_symptom_statement(user_id, symptom_id, this_statement=0, user_answer=''):
    statement = ''

    if this_statement == 0:
        sessionStorage[user_id]['stage'] = 2
        statement = database.get_item("select St.* "
                                      "from Symptoms S "
                                      "inner join Statements St on S.StartFromStatmentID = St.StatementID "
                                      "where S.SymptomID = %s", (str(symptom_id),))
        sessionStorage[user_id]['this_statement'] = statement['StatementID']
    elif this_statement != 0 and user_answer != '':
        if user_answer == 'да':
            statement = database.get_item("select St.* "
                                          "from Statements S "
                                          "inner join Statements St on S.NextOnTrueStatementID = St.StatementID "
                                          "where S.StatementID = %s", (str(this_statement),))
        else:
            statement = database.get_item("select St.* "
                                          "from Statements S "
                                          "inner join Statements St on S.NextOnFalseStatementID = St.StatementID "
                                          "where S.StatementID = %s", (str(this_statement),))
        sessionStorage[user_id]['this_statement'] = statement['StatementID']

    return statement


# Функция возвращает две подсказки для ответа.
def get_session(user_id):
    session_storage = database.get_item('select * from UserSessions us where us.user_id = %s', (user_id,))
    return session_storage


def save_session(user_id):
    sql_vars = []
    for key, session_item in sessionStorage[user_id].items():
        if key in sessionKeyToLog:
            sql_vars.append(str(key) + "='" + str(session_item) + "'")
    sql_vars_str = ','.join(sql_vars)

    if sessionStorage[user_id]['session_id'] == 0:
        sql = "insert into UserSessions set " + sql_vars_str
    else:
        sql = "update UserSessions set " + sql_vars_str
    database.query(sql)


@app.route("/test", methods=['GET'])
def test():
    return json.dumps(
        "hello world",
        ensure_ascii=False,
        indent=2
    )

