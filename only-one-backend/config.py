import yaml
import os
import sys
import requests
import secrets


BACKEND_PATH = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
REPO_PATH = os.path.dirname(BACKEND_PATH).replace('\\', '/')


def resolve_project_path(*parts):
    return os.path.join(BACKEND_PATH, *parts).replace('\\', '/')


def resolve_repo_path(*parts):
    return os.path.join(REPO_PATH, *parts).replace('\\', '/')


def resolve_optional_path(env_name, backend_relative, legacy_relative=None):
    configured_path = os.environ.get(env_name)
    if configured_path:
        return os.path.abspath(configured_path).replace('\\', '/')

    backend_path = resolve_project_path(backend_relative)
    if os.path.exists(backend_path):
        return backend_path

    if legacy_relative:
        legacy_path = resolve_repo_path(legacy_relative)
        if os.path.exists(legacy_path):
            return legacy_path

    return backend_path


def ensure_directory(path):
    os.makedirs(path, exist_ok=True)
    return path


def install_statistics(project_path):
    try:
        with open(os.path.join(project_path, 'db', 'version')) as f:
            version = f.read().strip()
        res= requests.post('http://statistics.dx3906.info/install-statistics', json={'version': version}, timeout=5)
    except:
        pass

# 获取系统代理设置
def get_system_proxies():
    if sys.platform == 'win32':
        # Windows系统代理获取逻辑
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                proxy_enable = winreg.QueryValueEx(key, 'ProxyEnable')[0]
                if proxy_enable:
                    proxy_server = winreg.QueryValueEx(key, 'ProxyServer')[0]
                    return f'http://{proxy_server}'
        except:
            pass
    else:
        # Unix-like系统通常使用环境变量
        http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
        if http_proxy:
            return http_proxy

    return None

# 全局配置类
class Settings():

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 读取yaml配置文件
        config_path = os.environ.get('PLLM_CONFIG_PATH') or resolve_project_path('app_config.yaml')
        with open(config_path, 'r', encoding='utf-8') as file:
            yaml_config = yaml.safe_load(file)

        if yaml_config['database']['use_db'] == 'mysql':
            self.MYSQL_HOST = yaml_config['database']['mysql']['host']
            self.MYSQL_PORT = yaml_config['database']['mysql']['port']
            self.MYSQL_USER = yaml_config['database']['mysql']['user']
            self.MYSQL_PASSWORD = yaml_config['database']['mysql']['password']
            self.MYSQL_DATABASE = yaml_config['database']['mysql']['database']
        else:
            sqlite_path = yaml_config['database']['sqlite']['db_path']
            if not os.path.isabs(sqlite_path):
                sqlite_path = resolve_project_path(sqlite_path)
            self.SQLITE_PATH = sqlite_path

        self.USE_DB = yaml_config['database']['use_db']
        self.PROJECT_PATH = BACKEND_PATH
        self.REPO_PATH = REPO_PATH
        self.STATIC_PATH = ensure_directory(resolve_optional_path('PLLM_STATIC_PATH', 'static'))
        self.FRONTEND_DIST_PATH = resolve_optional_path('PLLM_FRONTEND_DIST_PATH', 'html/dist')
        self.SESSION_SECRET = os.environ.get('PLLM_SESSION_SECRET') or yaml_config.get('session', {}).get('secret')
        if not self.SESSION_SECRET:
            self.SESSION_SECRET = secrets.token_urlsafe(32)
        self.SESSION_HTTPS_ONLY = os.environ.get(
            'PLLM_SESSION_HTTPS_ONLY',
            str(yaml_config.get('session', {}).get('https_only', 'false'))
        ).lower() == 'true'

        # 代理设置
        if yaml_config['proxy']['type'] == 'system':
            self.PROXIES = get_system_proxies()
            self.HTTPX_PARAMS = {'timeout': 600, 'proxy': self.PROXIES}
        elif yaml_config['proxy']['type'] == 'manual':
            self.PROXIES = yaml_config['proxy']['url']
            self.HTTPX_PARAMS = {'timeout': 600, 'proxy': self.PROXIES}
        else:
            self.PROXIES = None
            self.HTTPX_PARAMS = {'timeout': 600}

        # 免费模型
        self.FREE_MODEL_BASE_URL = os.environ.get('PLLM_FREE_MODEL_BASE_URL') or yaml_config['free_model']['base_url']
        self.FREE_MODEL_API_KEY = os.environ.get('PLLM_FREE_MODEL_API_KEY') or yaml_config['free_model']['api_key']
        self.FREE_MODEL_MODEL = os.environ.get('PLLM_FREE_MODEL_MODEL') or yaml_config['free_model']['model']

        # aihubmix 推理时代优惠码
        self.AIHUBMIX_DISCOUNT_CODE = yaml_config['aihubmix_discount_code']

    # 设置免费模型
    def set_free_model(self, llm_obj):
        self.FREE_MODEL = llm_obj



# 创建全局配置实例
settings = Settings()
