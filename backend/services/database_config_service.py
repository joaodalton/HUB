from pathlib import Path

from dotenv import dotenv_values, set_key


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / '.env'


DEFAULTS = {
    'DATA_PROVIDER': 'google_drive',
    'GOOGLE_SERVICE_ACCOUNT_FILE': 'credentials.json',
    'GOOGLE_DRIVE_ROOT_FOLDER_ID': '',
    'GOOGLE_DRIVE_DATA_FILE': 'hub-data.json',
    'SQL_DRIVER': '',
    'SQL_HOST': '',
    'SQL_PORT': '',
    'SQL_DATABASE': '',
    'SQL_USER': '',
    'SQL_PASSWORD': ''
}


def get_database_config():
    values = _read_env()
    google_credentials_path = _resolve_backend_path(values['GOOGLE_SERVICE_ACCOUNT_FILE'])

    return {
        'provider': values['DATA_PROVIDER'],
        'googleDrive': {
            'configured': google_credentials_path.exists() and bool(values['GOOGLE_DRIVE_ROOT_FOLDER_ID']),
            'credentialsFile': values['GOOGLE_SERVICE_ACCOUNT_FILE'],
            'rootFolderId': values['GOOGLE_DRIVE_ROOT_FOLDER_ID'],
            'dataFile': values['GOOGLE_DRIVE_DATA_FILE'],
            'credentialsFound': google_credentials_path.exists()
        },
        'sql': {
            'configured': all([
                values['SQL_DRIVER'],
                values['SQL_HOST'],
                values['SQL_DATABASE'],
                values['SQL_USER']
            ]),
            'driver': values['SQL_DRIVER'],
            'host': values['SQL_HOST'],
            'port': values['SQL_PORT'],
            'database': values['SQL_DATABASE'],
            'user': values['SQL_USER'],
            'passwordConfigured': bool(values['SQL_PASSWORD'])
        }
    }


def save_provider(provider):
    if provider not in ['google_drive', 'sql']:
        raise ValueError('Provedor de dados invalido.')

    _set_env('DATA_PROVIDER', provider)
    return get_database_config()


def save_google_drive_config(data):
    _set_env('DATA_PROVIDER', 'google_drive')
    _set_env('GOOGLE_SERVICE_ACCOUNT_FILE', data.get('credentialsFile', 'credentials.json'))
    _set_env('GOOGLE_DRIVE_ROOT_FOLDER_ID', data.get('rootFolderId', ''))
    _set_env('GOOGLE_DRIVE_DATA_FILE', data.get('dataFile', 'hub-data.json'))
    return get_database_config()


def save_sql_config(data):
    _set_env('DATA_PROVIDER', 'sql')
    _set_env('SQL_DRIVER', data.get('driver', ''))
    _set_env('SQL_HOST', data.get('host', ''))
    _set_env('SQL_PORT', data.get('port', ''))
    _set_env('SQL_DATABASE', data.get('database', ''))
    _set_env('SQL_USER', data.get('user', ''))
    _set_env('SQL_PASSWORD', data.get('password', ''))
    return get_database_config()


def test_database_config(provider):
    config = get_database_config()

    if provider == 'google_drive':
        google = config['googleDrive']

        if not google['credentialsFound']:
            return False, 'Arquivo de credenciais nao encontrado no backend.'

        if not google['rootFolderId']:
            return False, 'ID da pasta raiz do Google Drive nao configurado.'

        return True, 'Configuracao do Google Drive pronta para uso.'

    if provider == 'sql':
        sql = config['sql']

        if not sql['configured']:
            return False, 'Preencha driver, host, banco e usuario para preparar o SQL.'

        return True, 'Configuracao SQL preenchida. Teste real sera ativado quando o driver for instalado.'

    return False, 'Provedor de dados invalido.'


def _read_env():
    values = {**DEFAULTS, **dotenv_values(ENV_FILE)}
    return {key: str(value or '') for key, value in values.items()}


def _set_env(key, value):
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), key, str(value or ''))


def _resolve_backend_path(value):
    path = Path(value or '')

    if path.is_absolute():
        return path

    return BASE_DIR / path
