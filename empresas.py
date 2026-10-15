"""Cadastro e contexto de empresa por sessão, sem seleção global compartilhada."""
from contextlib import contextmanager
from contextvars import ContextVar
import re
from db import get_connection

_empresa_contexto = ContextVar("empresa_da_operacao", default=None)


def pagina_atual():
    try:
        import flet as ft
        return ft.context.page
    except (RuntimeError, AssertionError, AttributeError):
        return None


def empresa_id():
    identificador = _empresa_contexto.get()
    if identificador is None:
        pagina = pagina_atual()
        identificador = (getattr(pagina, "_empresa_atual", None) or {}).get("id")
    if identificador is None:
        raise RuntimeError("Selecione uma empresa antes de consultar ou alterar seus dados.")
    return int(identificador)


def garantir_empresa(identificador):
    if empresa_id() != identificador:
        raise RuntimeError("A empresa selecionada mudou. Reabra esta tela na empresa desejada.")


@contextmanager
def usar_empresa(identificador):
    if isinstance(identificador, bool) or int(identificador) <= 0:
        raise ValueError("Empresa inválida.")
    token = _empresa_contexto.set(int(identificador))
    try:
        yield
    finally:
        _empresa_contexto.reset(token)


def normalizar_cnpj(cnpj):
    texto = str(cnpj or "").strip()
    if not re.fullmatch(r"[0-9.\-/\s]+", texto):
        raise ValueError("Informe um CNPJ com 14 números.")
    numeros = re.sub(r"\D", "", texto)
    if len(numeros) != 14:
        raise ValueError("Informe um CNPJ com 14 números.")
    return numeros


def formatar_cnpj(cnpj):
    numeros = str(cnpj or "")
    if len(numeros) != 14:
        return ""
    return f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/{numeros[8:12]}-{numeros[12:]}"


def listar_empresas():
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sem conexão com o banco.")
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute("SELECT id, nome, cnpj FROM empresas ORDER BY nome, id")
        return cur.fetchall()
    finally:
        conn.close()


def selecionar_empresa(page, identificador):
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sem conexão com o banco.")
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute("SELECT id, nome, cnpj FROM empresas WHERE id=%s", (identificador,))
        empresa = cur.fetchone()
        if empresa is None:
            raise ValueError("Empresa não encontrada.")
        page._empresa_atual = empresa
        page._filtro_marca = {"valor": "Todas"}
        page._condicao_ml = {"valor": "Premium"}
        return empresa
    finally:
        conn.close()


def salvar_empresa(nome, cnpj, identificador=None):
    from servico_precificacao import transacao, TABELAS_REGRAS
    nome = str(nome or "").strip()
    if not nome or len(nome) > 160:
        raise ValueError("Informe o nome da empresa (até 160 caracteres).")
    cnpj = normalizar_cnpj(cnpj)
    origem = empresa_id()

    def salvar(cur):
        cur.execute("SELECT id FROM empresas WHERE cnpj=%s", (cnpj,))
        existente = cur.fetchone()
        if existente and existente["id"] != identificador:
            raise ValueError("Já existe uma empresa com este CNPJ.")
        if identificador is not None:
            cur.execute("SELECT id FROM empresas WHERE id=%s", (identificador,))
            if not cur.fetchone():
                raise ValueError("Empresa não encontrada.")
            cur.execute("UPDATE empresas SET nome=%s, cnpj=%s WHERE id=%s", (nome, cnpj, identificador))
            return identificador
        cur.execute("INSERT INTO empresas (nome, cnpj) VALUES (%s,%s)", (nome, cnpj))
        novo_id = cur.lastrowid
        # Cópia inicial independente de taxas/fretes; nenhum produto é copiado.
        for tabela in TABELAS_REGRAS:
            cur.execute(f"SELECT * FROM {tabela} WHERE empresa_id=%s ORDER BY id", (origem,))
            for regra in cur.fetchall():
                dados = {k: v for k, v in regra.items() if k not in ("id", "empresa_id")}
                dados["empresa_id"] = novo_id
                campos = list(dados)
                cur.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['%s']*len(campos))})",
                            tuple(dados.values()))
        return novo_id

    return transacao(salvar)
