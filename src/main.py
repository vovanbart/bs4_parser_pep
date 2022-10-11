import logging
import re
from collections import defaultdict
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import (BASE_DIR, DOWNLOADS_URL, EXPECTED_STATUS, MAIN_DOC_URL,
                       PEP_URL, WHATS_NEW_URL, LXML)
from outputs import control_output
from utils import find_tag, get_response


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


def download(session):
    if get_response(session, DOWNLOADS_URL) is None:
        raise KeyError('Не получен ответ')
    response = get_response(session, DOWNLOADS_URL)
    soup = BeautifulSoup(response.text, features=LXML)
    main_tag = find_tag(soup, 'div', attrs={'role': 'main'})
    table_tag = find_tag(main_tag, 'table', attrs={'class': 'docutils'})
    pdf_a4_tag = find_tag(table_tag, 'a',
                          attrs={'href': re.compile(r'.+pdf-a4\.zip$')})
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(DOWNLOADS_URL, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    response = get_response(session, PEP_URL)
    soup = BeautifulSoup(response.text, features=LXML)

    section_tag = find_tag(soup, 'section', attrs={'id': 'numerical-index'})
    tbody_tag = find_tag(section_tag, 'tbody')
    tr_tags = tbody_tag.find_all('tr')
    results = [('Cтатус', 'Количество')]
    pep_sum = defaultdict(list)
    total_sum = 0
    for tr_tag in tqdm(tr_tags):
        total_sum += 1
        a_tag = find_tag(tr_tag, 'a', attrs={'class': 'reference external'})
        pep_url = urljoin(PEP_URL, a_tag['href'])
        response = get_response(session, pep_url)
        soup = BeautifulSoup(response.text, features=LXML)
        dl_tag = find_tag(soup, 'dl',
                          attrs={'class': 'rfc2822 field-list simple'})
        dd_tag = find_tag(
            dl_tag, 'dt', attrs={'class': 'field-even'}
        ).find_next_sibling('dd')
        status = dd_tag.string
        status_in_page = find_tag(tr_tag, 'td').string[1:]
        try:
            if status not in EXPECTED_STATUS[status_in_page]:
                if (len(status_in_page) > 2 or
                        EXPECTED_STATUS[status_in_page] is None):
                    raise KeyError('Получен неожиданный статус')
                logging.info(
                    f'Несовпадающие статусы:\n {pep_url}\n'
                    f'Cтатус в карточке: {status}\n'
                    f'Ожидаемые статусы: {EXPECTED_STATUS[status_in_page]}'
                )
        except KeyError:
            logging.warning('Получен некорректный статус')
        else:
            pep_sum[status] = pep_sum.get(status, 0) + 1
    results.extend(pep_sum.items())
    results.append(('Total: ', total_sum))
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
