# coding: utf-8
# Импортирует поддержку UTF-8.
from __future__ import unicode_literals

# Импортируем модули для работы с JSON и логами.
import json
import logging
import Database
import time
import random

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

# Наборы фраз для ответов
thanksPhrases = [
    {'Body': 'И это все! Попробуйте снова, если у вас остались какие-то вопросы'},
    {'Body': 'Помогла, чем смогла, дальше дело за вами!'},
    {'Body': 'Не стоит благодарности, это моя работа.'},
    {'Body': 'Всегда рада вам помочь!'},
    {'Body': 'На этом все! Большое спасибо, что воспользовались мной!'},
    {'Body': 'Мне больше нечем вам помочь. Спасибо за ваш интерес!'},
]

onlyYesOrNoPhrases = [
    {'Body': 'Отвечайте, пожалуйста, только Да или Нет.'},
    {'Body': 'Отвечая Да или Нет, вы приближаетесь к результату!'},
    {'Body': 'Не могу понять. Наверное вы отвечаете на вопросы не так...'},
    {'Body': 'Пожалуйста, отвечайте только Да или Нет.'},
    {'Body': 'Да или Нет, только так и никак иначе!'},
    {'Body': 'Пожалуйста, используйте только Да и Нет в ответах.'},
]

greetingsPhrases = [
    {'Body': 'Доброго времени суток! Что с вами случилось?'},
    {'Body': 'Привет! Я ваш домашний доктор, что с вами не так?'},
    {'Body': 'Приветствую! Вас что-то беспокоит?'},
    {'Body': 'Привет! С вами говорит ваш домашний советчик, что с вами случилось?'},
]

repeatQuestion = [
    'повтори'
]


# Задаем параметры приложения Flask.
@app.route("/", methods=['POST'])
def main():
    logging.info('Start')
    request_json = request.get_json(force=True)
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
        greetings_phrase = random.choice(greetingsPhrases)
        res['response']['text'] = greetings_phrase['Body']
        res['response']['tts'] = greetings_phrase['Body']
        res['response']['buttons'] = get_init_phrases(user_id)
        save_session(user_id)
        logging.info('end')
        return

    try:
        rough_language = req['request']['markup']['dangerous_context']
    except KeyError:
        rough_language = False

    session = sessionStorage[user_id]
    logging.info('session: %r', session)

    # Обрабатываем ответ пользователя.
    user_answer = req['request']['original_utterance'].lower()
    if session['stage'] == 1:
        symptom_id = get_symptom_id_by_init_phrase(user_id, user_answer)
        if not symptom_id:
            init_phrases = try_find_init_phrase(user_id, req['request']['nlu']['tokens'])
            if init_phrases:
                response_text = 'Не могу найти симптом, возможно вы имели ввиду что-то из этого?'
                response_speech = 'Не могу найти симптом, возможно вы имели ввиду что-то из этого?'
                session_end = False
                buttons = [
                    {'title': init_phrase['PhraseBody'], 'hide': True}
                    for init_phrase in init_phrases[:2]
                ]
            else:
                response_text = 'Не могу понять, что с вами, попробуйте перефразировать.'
                response_speech = 'Не могу понять, что с вами, попробуйте перефразировать.'
                session_end = False
                buttons = get_init_phrases(user_id)
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

        if user_answer in repeatQuestion:
            statement = get_statement_by_id(session['this_statement'])
            buttons = [
                {'title': 'Да', 'hide': False},
                {'title': 'Нет', 'hide': False},
            ]
            session_end = False
            response_text = statement['StatementBody']
            response_speech = statement['StatementSpeech']
        elif user_answer in allowed_answers:
            statement = get_symptom_statement(user_id, session['symptom_id'], session['this_statement'], user_answer)
            if statement:
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
                    sessionStorage[user_id]['stage'] = 3
                elif statement['TypeID'] == 3:
                    sessionStorage[user_id]['symptom_id'] = statement['NextSymptomID']
                    statement = get_symptom_statement(user_id, statement['NextSymptomID'], 0, '')
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
            text = random.choice(onlyYesOrNoPhrases)
            buttons = [
                        {'title': 'Да', 'hide': True},
                        {'title': 'Нет', 'hide': True},
                        {'title': random.choice(repeatQuestion).title(), 'hide': True},
                    ]
            session_end = False
            response_text = text['Body']
            response_speech = text['Body']
    elif session['stage'] == 3:
        text = random.choice(thanksPhrases)
        response_text = text['Body']
        response_speech = text['Body']
        session_end = True
        buttons = []
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
    symptom_info = database.get_item(
        "select SymptomID from `InitPhrases` p where lower(p.PhraseBody) = %s", (init_phrase,))
    try:
        symptom_id = symptom_info['SymptomID']
        sessionStorage[user_id]['symptom_id'] = symptom_id
        return symptom_id
    except TypeError:
        return False


def get_statement_by_id(statement_id):
    statement = database.get_item("select S.* "
                                  "from Statements S "
                                  "where S.StatementID = %s", (str(statement_id),))
    return statement


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
    if len(user_answer_by_words) < 5:
        for word in user_answer_by_words:
            if len(word) > 2:
                compare_str = '"%' + word + '%"'
                init_phrase_temp = database.get_all("select SymptomID from InitPhrases where PhraseBody like " + compare_str)
                if init_phrase_temp:
                    for item in init_phrase_temp:
                        suppose_symptoms.append(item)
        if suppose_symptoms:
            symptoms_frequency = {}
            for entry in suppose_symptoms:
                try:
                    symptoms_frequency[entry['SymptomID']] += 1
                except KeyError:
                    symptoms_frequency[entry['SymptomID']] = 1
            max_value = max(symptoms_frequency.values())
            symptoms = [k for k, v in symptoms_frequency.items() if v == max_value]
            if symptoms:
                variables = ','.join(['%s' for _ in range(0, len(symptoms))])
                return database.get_all("select * "
                                        "from InitPhrases "
                                        "where SymptomID in (" + variables + ") "
                                        "group by SymptomID "
                                        "order by rand() "
                                        "limit 3",
                                        tuple(symptoms))

    return False


@app.route("/test", methods=['GET'])
def test():
    now = time.strftime("%H:%M")
    return json.dumps(
        now,
        ensure_ascii=False,
        indent=2
    )

