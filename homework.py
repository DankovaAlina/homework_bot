import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv
from varname import nameof

from exceptions import BadRequestException, ConvertException

load_dotenv()


logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    filename='program.log',
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        nameof(PRACTICUM_TOKEN): PRACTICUM_TOKEN,
        nameof(TELEGRAM_TOKEN): TELEGRAM_TOKEN,
        nameof(TELEGRAM_CHAT_ID): TELEGRAM_CHAT_ID
    }
    for token_name, token_value in tokens.items():
        if token_value is None:
            message = (f'Отсутствует обязательная переменная '
                       f'окружения: {token_name}')
            logger.critical(message)
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.debug('Отправка сообщения.')
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except telegram.TelegramError:
        logger.error('Ошибка отправки сообщения в Telegram.')
    else:
        logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    logger.debug(f'Начат запрос к узлу {ENDPOINT} '
                 f'с параметрами {payload} и хедером {HEADERS}')
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=payload)
    except requests.RequestException:
        raise BadRequestException(
            f'Ошибка при запросе к узлу {ENDPOINT} '
            f'с параметрами {payload} и хедером {HEADERS}'
        )

    if response.status_code != HTTPStatus.OK:
        raise BadRequestException('Неожиданный код ответа.')
    try:
        return response.json()
    except JSONDecodeError:
        raise ConvertException('Ошибка приведения JSON к объекту.')


def check_response(response):
    """Проверяет ответ API на наличие необходимых ключей."""
    if not isinstance(response, dict):
        raise TypeError('Структура данных не соответствует ожиданиям.')
    required_keys = [
        'homeworks',
        'current_date'
    ]
    if not all(key in response for key in required_keys):
        raise ValueError('Отсутствуют ключи: {}'.format(
            ','.join(required_keys - response.keys())
        ))
    if not isinstance(response['homeworks'], list):
        raise TypeError('Структура данных не соответствует ожиданиям.')


def parse_status(homework):
    """Проверяет статус домашней работы и формирует текст сообщения."""
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует в словаре.')
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует в словаре.')
    homework_name = homework['homework_name']
    status = homework['status']
    if not status:
        raise ValueError('Статус пустой.')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Неожиданный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit(1)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if not response['homeworks']:
                logger.debug('Новые статусы отсутствуют.')
            else:
                homework = response['homeworks'][0]
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_error != message:
                send_message(bot, message)
                last_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
