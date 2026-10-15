import sys
import json
import os
import mysql.connector
from mysql.connector import pooling

DB_CONFIG = {
    "host": "localhost",       # Troque pelo IP do servidor se o MySQL estiver em outra máquina
    "user": "root",
    "password": "",
    "database": "arsenal_precificacao",
    "port": "3389"
}

def _pasta_base():
    """Pasta onde o config.json deve ficar.
    No exe compilado: a pasta do .exe. Rodando pelo Python: a pasta do script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

_config_cache = None

def carregar_config_bd():
    """Lê o config.json (com cache em memória). Se não existir, retorna os padrões."""
    global _config_cache
    if _config_cache is not None:
        return dict(_config_cache)
    config_path = os.path.join(_pasta_base(), "config.json")
    padrao = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "arsenal_precificacao",
        "port": 3389,
    }
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                salvo = json.load(f)
            padrao.update(salvo)
    except Exception:
        pass
    _config_cache = dict(padrao)
    return dict(padrao)

def salvar_config_bd(cfg):
    """Salva o config.json na pasta do exe/script."""
    global _config_cache
    config_path = os.path.join(_pasta_base(), "config.json")
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=4)
    _config_cache = dict(cfg)

def testar_conexao_bd(cfg):
    """Testa a conexão sem salvar. Retorna (ok, mensagem)."""
    try:
        conn = mysql.connector.connect(
            host=cfg["host"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            port=int(cfg.get("port", 3389)),
            connection_timeout=5,
        )
        conn.close()
        return True, "Conexão bem-sucedida!"
    except Exception as e:
        return False, str(e)

_pool = None
_pool_cfg = None

def _get_pool():
    """Cria o pool uma única vez. Recria só se o config mudar."""
    global _pool, _pool_cfg
    cfg = carregar_config_bd()
    assinatura = (cfg["host"], cfg["user"], cfg["database"], str(cfg.get("port", 3389)))
    if _pool is None or _pool_cfg != assinatura:
        _pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="arsenal_pool",
            pool_size=5,
            pool_reset_session=True,
            host=cfg["host"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            port=int(cfg.get("port", 3389)),
            connection_timeout=10,
        )
        _pool_cfg = assinatura
    return _pool

def get_connection():
    try:
        return _get_pool().get_connection()
    except Exception as e:
        print(f"[ERRO CONEXAO] {e}")
        return None
    
