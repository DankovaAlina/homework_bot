import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import BadRequestException

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
    try:
        if not PRACTICUM_TOKEN:
            raise ValueError(
                'Отсутствует обязательная переменная '
                'окружения: PRACTICUM_TOKEN'
            )
        if not TELEGRAM_TOKEN:
            raise ValueError(
                'Отсутствует обязательная переменная '
                'окружения: TELEGRAM_TOKEN'
            )
        if not TELEGRAM_CHAT_ID:
            raise ValueError(
                'Отсутствует обязательная переменная '
                'окружения: TELEGRAM_CHAT_ID'
            )
    except Exception as error:
        logger.critical(error)
        raise


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.debug('Сообщение успешно отправлено.')
    except Exception:
        logger.error('Ошибка отправки сообщения в Telegram.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    try:
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=payload)
    except requests.RequestException:
        raise BadRequestException('Ошибка подключения к API.')

    if response.status_code == 200:
        return response.json()
    else:
        raise BadRequestException('Неожиданный код ответа.')


def check_response(response):
    """Проверяет ответ API на наличие необходимых ключей."""
    if type(response) is not dict:
        raise TypeError('Структура данных не соответствует ожиданиям.')

    if not ({'homeworks', 'current_date'} <= response.keys()):
        raise KeyError('Необходимые ключи отсутствуют в ответе.')

    if type(response['homeworks']) is not list:
        raise TypeError('Структура данных не соответствует ожиданиям.')


def parse_status(homework):
    """Проверяет статус домашней работы и формирует текст сообщения."""
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует в словаре.')
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует в словаре.')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError('Неожиданный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if len(response['homeworks']) == 0:
                logger.debug('Новые статусы отсутствуют.')
            for homework in response['homeworks']:
                message = parse_status(homework)
                send_message(bot, message)
            timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_error != message:
                send_message(bot, message)
                last_error = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
