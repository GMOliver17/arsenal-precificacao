"""Migração aditiva e retomável, com backup antes de alterar o banco existente."""
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from db import _pasta_base

TABELAS = ("produtos", "tabela_taxas_comissoes", "tabela_frete_ml", "tabela_frete_shopee",
           "tabela_frete_amazon", "tabela_frete_amazon_brl200", "historico_alteracoes")
NOME_INICIAL = "Empresa inicial"
CNPJ_INICIAL = "00000000000000"


def _literal(valor):
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, (int, float, Decimal)):
        return str(valor)
    if isinstance(valor, bytes):
        return "X'" + valor.hex() + "'"
    if isinstance(valor, (datetime, date)):
        valor = valor.isoformat(sep=" ") if isinstance(valor, datetime) else valor.isoformat()
    texto = str(valor).replace("\\", "\\\\").replace("'", "\\'")
    texto = texto.replace("\0", "\\0").replace("\n", "\\n").replace("\r", "\\r")
    return "'" + texto + "'"


def backup_tabelas(conn):
    pasta = Path(_pasta_base()) / "backups"
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"antes_multiempresa_{datetime.now():%Y%m%d_%H%M%S_%f}.sql"
    conn.commit()
    conn.start_transaction(consistent_snapshot=True, readonly=True)
    cur = conn.cursor(buffered=True)
    try:
        cur.execute("SHOW TABLES")
        tabelas = [r[0] for r in cur.fetchall()]
        with destino.open("x", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write("-- Backup de estrutura e dados das tabelas antes da migração multiempresa.\n")
            arquivo.write("SET NAMES utf8mb4;\nSET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\nSET FOREIGN_KEY_CHECKS=0;\n")
            for tabela in tabelas:
                identificador = "`" + tabela.replace("`", "``") + "`"
                cur.execute(f"SHOW CREATE TABLE {identificador}")
                arquivo.write(cur.fetchone()[1] + ";\n")
                cur.execute(f"SELECT * FROM {identificador}")
                colunas = ",".join("`" + d[0].replace("`", "``") + "`" for d in cur.description)
                for linha in cur.fetchall():
                    arquivo.write(f"INSERT INTO {identificador} ({colunas}) VALUES ({','.join(_literal(v) for v in linha)});\n")
            arquivo.write("SET FOREIGN_KEY_CHECKS=1;\n")
        conn.commit()
        return destino
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def migrar(conn):
    cur = conn.cursor(dictionary=True, buffered=True)
    bloqueado = False
    try:
        cur.execute("SELECT GET_LOCK('arsenal_multiempresa_v1', 30) AS adquirido")
        bloqueado = cur.fetchone()["adquirido"] == 1
        if not bloqueado:
            raise RuntimeError("Outra sessão está preparando o banco; tente novamente em instantes.")
        cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='migracoes_sistema'")
        if cur.fetchone():
            cur.execute("SELECT versao FROM migracoes_sistema WHERE chave='multiempresa'")
            versao = cur.fetchone()
            if versao and versao["versao"] >= 1:
                return None
        backup = backup_tabelas(conn)
        cur.execute("""CREATE TABLE IF NOT EXISTS empresas (
            id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(160) NOT NULL,
            cnpj VARCHAR(14) NOT NULL UNIQUE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cur.execute("INSERT IGNORE INTO empresas (id,nome,cnpj) VALUES (1,%s,%s)", (NOME_INICIAL, CNPJ_INICIAL))
        cur.execute("SELECT id FROM empresas WHERE id=1")
        if not cur.fetchone():
            raise RuntimeError("Não foi possível preparar a empresa dos dados existentes.")
        conn.commit()
        for tabela in TABELAS:
            cur.execute("SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='empresa_id'", (tabela,))
            coluna = cur.fetchone()
            if coluna is None:
                cur.execute(f"ALTER TABLE {tabela} ADD COLUMN empresa_id INT NULL")
            cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND EXTRA LIKE '%%on update%%'", (tabela,))
            preservar = "".join(f", `{r['COLUMN_NAME']}`=`{r['COLUMN_NAME']}`" for r in cur.fetchall())
            cur.execute(f"UPDATE {tabela} SET empresa_id=1{preservar} WHERE empresa_id IS NULL")
            conn.commit()
            if coluna is None or coluna["IS_NULLABLE"] == "YES":
                cur.execute(f"ALTER TABLE {tabela} MODIFY COLUMN empresa_id INT NOT NULL")
            indice = "idx_empresa_sku" if tabela == "produtos" else "idx_empresa"
            cur.execute("SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME=%s", (tabela, indice))
            if not cur.fetchone():
                campos = "empresa_id,sku" if tabela == "produtos" else "empresa_id"
                cur.execute(f"CREATE INDEX {indice} ON {tabela} ({campos})")
            restricao = f"fk_{tabela}_empresa"
            cur.execute("SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s AND CONSTRAINT_NAME=%s", (tabela, restricao))
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {tabela} ADD CONSTRAINT {restricao} FOREIGN KEY (empresa_id) REFERENCES empresas(id)")
        cur.execute("""CREATE TABLE IF NOT EXISTS migracoes_sistema (
            chave VARCHAR(80) PRIMARY KEY, versao INT NOT NULL,
            aplicado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cur.execute("INSERT INTO migracoes_sistema (chave,versao) VALUES ('multiempresa',1) ON DUPLICATE KEY UPDATE versao=VALUES(versao)")
        conn.commit()
        return backup
    except Exception:
        conn.rollback()
        raise
    finally:
        if bloqueado:
            cur.execute("SELECT RELEASE_LOCK('arsenal_multiempresa_v1')")
            cur.fetchone()
        cur.close()
