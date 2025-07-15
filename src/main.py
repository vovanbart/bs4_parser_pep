import logging
import re
from collections import defaultdict
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.configs import configure_argument_parser, configure_logging
from constants import (BASE_DIR, DOWNLOADS_URL, EXPECTED_STATUS, MAIN_DOC_URL,
                       PEP_URL, WHATS_NEW_URL, LXML)
from src.outputs import control_output
from src.utils import find_tag, get_response


def whats_new(session):
    if get_response(session, WHATS_NEW_URL) is None:
        raise KeyError('Не получен ответ')
    response = get_response(session, WHATS_NEW_URL)
    soup = BeautifulSoup(response.text, features=LXML)
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all('li',
                                              attrs={'class': 'toctree-l1'})
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(WHATS_NEW_URL, href)
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, features=LXML)
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text)
        )
    return results


def latest_versions(session):
    if get_response(session, MAIN_DOC_URL) is None:
        raise KeyError('Не получен ответ')
    response = get_response(session, MAIN_DOC_URL)
    soup = BeautifulSoup(response.text, features=LXML)
    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session) -> str:
    """
    Скачивает PDF-архив в папку downloads/
    и возвращает абсолютный путь к файлу.
    """
    if get_response(session, DOWNLOADS_URL) is None:
        raise KeyError('Не получен ответ')
    response = get_response(session, DOWNLOADS_URL)
    soup = BeautifulSoup(response.text, features=LXML)
    main_tag = find_tag(soup, 'div', attrs={'role': 'main'})
    table_tag = find_tag(main_tag, 'table', attrs={'class': 'docutils'})
    pdf_a4_tag = find_tag(table_tag, 'a',
                          attrs={'href': re.compile(r'.+pdf-a4\.zip$')})
    archive_url = urljoin(DOWNLOADS_URL, pdf_a4_tag['href'])
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename

    # собственно скачиваем
    response = session.get(archive_url)
    with open(archive_path, 'wb') as f:
        f.write(response.content)

    logging.info(f'Архив был загружен и сохранён: {archive_path}')
    return str(archive_path)  # <-- возвращаем путь


def pep(session):
    # 1) URL числового индекса
    numerical_url = urljoin(PEP_URL, 'numerical/')
    response = get_response(session, numerical_url)
    if response is None:
        raise KeyError(f'Не получен ответ от {numerical_url}')
    soup = BeautifulSoup(response.text, features=LXML)

    # 2) Находим первую таблицу (там заголовок + строки PEP)
    table = soup.find('table')
    if table is None:
        raise KeyError('Не найдена таблица PEP на странице numerical/')
    rows = table.find_all('tr')
    if len(rows) <= 1:
        raise KeyError('В таблице нет строк с PEP')

    # 3) Считаем статусы
    counts = defaultdict(int)
    total = 0
    # Пропускаем заголовок таблицы (rows[0])
    for tr in rows[1:]:
        cols = tr.find_all('td')
        # Формат: <td>Статус</td><td>PEP номер</td><td>Название</td><td>Авторы</td>
        if not cols or len(cols) < 1:
            continue
        status = cols[0].get_text(strip=True)
        counts[status] += 1
        total += 1

    # 4) Собираем результат в виде списка кортежей
    results = [('Статус', 'Количество')]
    for status, num in counts.items():
        results.append((status, num))
    results.append(('Total', total))
    return results


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')
    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()
    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
