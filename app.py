from flask import (
    Flask, render_template, request, send_file
)
import logging
import requests_cache

from src.configs import configure_logging
from src.main    import MODE_TO_FUNCTION

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
configure_logging()
session = requests_cache.CachedSession()

@app.route('/', methods=('GET', 'POST'))
def index():
    modes   = sorted(MODE_TO_FUNCTION.keys())
    results = None
    error   = None

    if request.method == 'POST':
        mode        = request.form.get('mode')
        clear_cache = bool(request.form.get('clear_cache'))
        if clear_cache:
            session.cache.clear()
            logging.info('HTTP-кеш очищен по запросу пользователя')

        try:
            if mode == 'download':
                # скачиваем файл и сразу отдаем его браузеру
                file_path = MODE_TO_FUNCTION['download'](session)
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name = file_path.rsplit('/', 1)[-1]
                )
            else:
                # остальные режимы возвращают таблицу
                results = MODE_TO_FUNCTION[mode](session)
        except Exception as e:
            logging.exception(f'Ошибка при выполнении режима "{mode}"')
            error = str(e)

    return render_template(
        'index.html',
        modes=modes,
        results=results,
        error=error
    )