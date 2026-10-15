from servico_precificacao import atualizar_regras
from db import get_connection
from empresas import empresa_id

# ──────────────────────────────────────────────
#  MERCADO LIVRE
# ──────────────────────────────────────────────
def listar_frete_ml() -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, peso, faixa_0_18_99, faixa_19_48_99, faixa_49_78_99, "
            "faixa_79_99_99, faixa_100_119_99, faixa_120_149_99, "
            "faixa_150_199_99, faixa_200_mais "
            "FROM tabela_frete_ml WHERE empresa_id=%s ORDER BY id",
            (empresa_id(),)
        )
        return cursor.fetchall()
    finally:
        conn.close()

def atualizar_frete_ml(linha):
    try:
        total, pendentes = atualizar_regras("tabela_frete_ml", [linha])
        return True, f"Regra e {total} resultados salvos; {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Nada foi salvo: {e}"

# ──────────────────────────────────────────────
#  SHOPEE
# ──────────────────────────────────────────────
def listar_frete_shopee() -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, faixa, valor_do_produto, taxa_percentual, taxa_fixa_reais "
            "FROM tabela_frete_shopee WHERE empresa_id=%s ORDER BY id",
            (empresa_id(),)
        )
        return cursor.fetchall()
    finally:
        conn.close()

def atualizar_frete_shopee(linha):
    try:
        total, pendentes = atualizar_regras("tabela_frete_shopee", [linha])
        return True, f"Regra e {total} resultados salvos; {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Nada foi salvo: {e}"

# ──────────────────────────────────────────────
#  TAXAS E COMISSÕES (TikTok, Magalu, Kwai, Amazon < R$ 79)
# ──────────────────────────────────────────────
def listar_taxas_por_canal(canal: str) -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, canal, condicao, taxa_percentual, taxa_fixa_reais "
            "FROM tabela_taxas_comissoes WHERE canal = %s AND empresa_id=%s ORDER BY id",
            (canal, empresa_id())
        )
        return cursor.fetchall()
    finally:
        conn.close()

def atualizar_taxa(linha):
    try:
        total, pendentes = atualizar_regras("tabela_taxas_comissoes", [linha])
        return True, f"Regra e {total} resultados salvos; {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Nada foi salvo: {e}"

# ──────────────────────────────────────────────
#  AMAZON FRETE (R$ 79 a 199,99)
# ──────────────────────────────────────────────
def listar_frete_amazon() -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, peso, faixa_79_99_99, faixa_100_119_99, "
            "faixa_120_149_99, faixa_150_199_99 "
            "FROM tabela_frete_amazon WHERE empresa_id=%s ORDER BY id",
            (empresa_id(),)
        )
        return cursor.fetchall()
    finally:
        conn.close()

def atualizar_frete_amazon(linha):
    try:
        total, pendentes = atualizar_regras("tabela_frete_amazon", [linha])
        return True, f"Regra e {total} resultados salvos; {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Nada foi salvo: {e}"

# ──────────────────────────────────────────────
#  AMAZON FRETE (acima de R$ 200)
# ──────────────────────────────────────────────
def listar_frete_amazon_brl200() -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, peso, sp_capital, outras_capitais_sul_sudeste, "
            "interior_sul_sudeste, centro_oeste_norte_nordeste "
            "FROM tabela_frete_amazon_BRL200 WHERE empresa_id=%s ORDER BY id",
            (empresa_id(),)
        )
        return cursor.fetchall()
    finally:
        conn.close()

def atualizar_frete_amazon_brl200(linha):
    try:
        total, pendentes = atualizar_regras("tabela_frete_amazon_brl200", [linha])
        return True, f"Regra e {total} resultados salvos; {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Nada foi salvo: {e}"
