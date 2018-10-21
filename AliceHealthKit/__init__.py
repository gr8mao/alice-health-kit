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
        res['response']['text'] = 'Привет! Я твой домашний доктор! Что с вами случилось?'
        res['response']['tts'] = 'Привет! Я твой домашний доктор! Что с вами случилось?'
        res['response']['buttons'] = get_init_phrases(user_id)
        save_session(user_id)
        logging.info('end')
        return

    session = sessionStorage[user_id]
    print(session)
    logging.info('session: %r', session)

    # Обрабатываем ответ пользователя.
    user_answer = req['request']['original_utterance'].lower()
    print(session['stage'])
    if session['stage'] == 1:
        symptom_id = get_symptom_id_by_init_phrase(user_id, user_answer)
        print(symptom_id)
        if not symptom_id:
            init_phrases = try_find_init_phrase(user_id, req['request']['nlu']['tokens'])
            print(init_phrases)
            if init_phrases:
                response_text = 'Не могу найти симптом, возможно вы имели ввиду что-то из этого?'
                response_speech = 'Не могу найти симптом, возможно вы имели ввиду что-то из этого?'
                session_end = False
                print(response_text)
                buttons = [
                    {'title': init_phrase['PhraseBody'], 'hide': True}
                    for init_phrase in init_phrases[:2]
                ]
            else:
                response_text = 'Не могу понять, что с вами, попробуйте перефразировать.'
                response_speech = 'Не могу понять, что с вами, попробуйте перефразировать.'
                print(response_text)
                session_end = False
                buttons = []
        else:
            statement = get_symptom_statement(user_id, symptom_id, 0, '')
            if statement:
                response_text = statement['StatementBody']
                response_speech = statement['StatementSpeech']
                session_end = False
                buttons = [
                    {'title': 'Да', 'hide': False},
                    {'title': 'Нет', 'hide': False},
                ]
            else:
                response_text = 'Что-то пошло не так! Попробуйте запустить навык заново!'
                response_speech = 'Что-то пошло не так! Попробуйте запустить навык заново!'
                session_end = True
                buttons = []
    elif session['stage'] == 2:
        allowed_answers = [
            'да',
            'нет',
        ]

        if user_answer in allowed_answers:
            statement = get_symptom_statement(user_id, session['symptom_id'], session['this_statement'], user_answer)

            print(statement)
            if statement:
                print(statement['TypeID'])
                print(statement['TypeID'] == 3)
                if statement['TypeID'] == 1:
                    buttons = [
                        {'title': 'Да', 'hide': False},
                        {'title': 'Нет', 'hide': False},
                    ]
                    session_end = False
                    response_text = statement['StatementBody']
                    response_speech = statement['StatementSpeech']
                elif statement['TypeID'] == 2:
                    buttons = {}
                    session_end = True
                    response_text = statement['StatementBody']
                    response_speech = statement['StatementSpeech']
                elif statement['TypeID'] == 3:
                    print(statement['NextSymptomID'])
                    sessionStorage[user_id]['symptom_id'] = statement['NextSymptomID']
                    statement = get_symptom_statement(user_id, statement['NextSymptomID'], 0, '')
                    print(statement)
                    buttons = [
                        {'title': 'Да', 'hide': False},
                        {'title': 'Нет', 'hide': False},
                    ]
                    session_end = False
                    response_text = statement['StatementBody']
                    response_speech = statement['StatementSpeech']
            else:
                response_text = 'Не удалось найти следующий этап. Попробуйте снова!'
                response_speech = 'Не удалось найти следующий этап. Попробуйте снова!'
                session_end = True
                buttons = []
        else:
            buttons = {}
            session_end = False
            response_text = "На этом этапе следует отвечать только Да или Нет."
            response_speech = "На этом этапе следует отвечать только Да или Нет."
    else:
        response_text = 'Как вы здесь оказались?!'
        response_speech = 'Как вы здесь оказались?!'
        session_end = True
        buttons = []

    res['response']['text'] = response_text
    res['response']['tts'] = response_speech
    if buttons:
        res['response']['buttons'] = buttons
    res['response']['end_session'] = session_end

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
    print(init_phrase)
    symptom_info = database.get_item(
        "select SymptomID from `InitPhrases` p where lower(p.PhraseBody) = %s", (init_phrase,))
    print(symptom_info)
    if symptom_info:
        symptom_id = symptom_info['SymptomID']
        sessionStorage[user_id]['symptom_id'] = symptom_id
        return symptom_id
    else:
        return False


def get_symptom_statement(user_id, symptom_id, this_statement=0, user_answer=''):
    statement = ''

    if this_statement == 0:
        sessionStorage[user_id]['stage'] = 2
        statement = database.get_item("select St.* "
                                      "from Symptoms S "
                                      "inner join Statements St on S.StartFromStatmentID = St.StatementID "
                                      "where S.SymptomID = %s", (str(symptom_id),))

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
    if statement:
        sessionStorage[user_id]['this_statement'] = statement['StatementID']
        return statement
    else:
        return False


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


def try_find_init_phrase(user_id, user_answer_by_words):
    suppose_symptoms = []
    print(user_answer_by_words)
    print(len(user_answer_by_words))
    if len(user_answer_by_words) < 5:
        for word in user_answer_by_words:
            print(word)
            if len(word) > 2:
                compare_str = '"%' + word + '%"'
                print(compare_str)
                init_phrase_temp = database.get_item("select SymptomID from InitPhrases where PhraseBody like " + compare_str)
                print(init_phrase_temp)
                if init_phrase_temp:
                    suppose_symptoms.append(init_phrase_temp)

        if suppose_symptoms:
            my_map = {}
            for entry in suppose_symptoms:
                try:
                    my_map[entry['SymptomID']] += 1
                except KeyError:
                    my_map[entry['SymptomID']] = 1

            symptom_id = max(my_map, key=my_map.get)
            print(symptom_id)
            if symptom_id:
                return database.get_all("select * from InitPhrases where SymptomID = %s order by rand() limit 1", (symptom_id,))

    return False


@app.route("/test", methods=['GET'])
def test():
    return json.dumps(
        "hello world",
        ensure_ascii=False,
        indent=2
    )

