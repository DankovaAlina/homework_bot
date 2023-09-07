import os
import time

import requests
import telegram
from dotenv import load_dotenv

from logger import logger

load_dotenv()


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
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message
    )
    logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    response = requests.get(ENDPOINT,
                            headers=HEADERS,
                            params=payload)
    return response.json()


def check_response(response):
    """Проверяет ответ API на наличие необходимых ключей."""
    if response is None or not (
        {'homeworks', 'current_date'} <= response.keys()
    ):
        raise KeyError('Необходимые ключи отсутствуют в ответе.')


def parse_status(homework):
    """Проверяет статус домашней работы и формирует текст сообщения."""
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
