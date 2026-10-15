"""Persistência transacional: entradas, resultados e taxas aplicadas na mesma transação."""
import csv
import io
import json
from decimal import Decimal
from db import get_connection
from precificacao import PLATAFORMAS, calcular, numero, dinheiro, peso_em_kg
from empresas import empresa_id, usar_empresa

TABELAS_REGRAS = ("tabela_taxas_comissoes", "tabela_frete_ml", "tabela_frete_shopee",
                  "tabela_frete_amazon", "tabela_frete_amazon_brl200")
CAMPOS = ("sku", "descricao", "marca", "trib", "embalagem", "quantidade", "peso", "target_minimo")

def carregar_regras(cursor):
    regras = {}
    for tabela in TABELAS_REGRAS:
        cursor.execute(f"SELECT * FROM {tabela} WHERE empresa_id=%s ORDER BY id", (empresa_id(),))
        regras[tabela] = cursor.fetchall()
    return regras

def _schema(conn):
    # DDL somente antes da transação comercial. Nunca ALTER/DROP nas tabelas existentes.
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS precificacao_controle (
        id INT PRIMARY KEY, versao INT NOT NULL DEFAULT 0) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("""CREATE TABLE IF NOT EXISTS precificacao_resultados (
        produto_id INT NOT NULL, plataforma VARCHAR(30) NOT NULL,
        status VARCHAR(20) NOT NULL, mensagem TEXT, dados JSON NOT NULL,
        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (produto_id, plataforma),
        FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    cur.execute("INSERT IGNORE INTO precificacao_controle (id, versao) VALUES (1, 0)")
    conn.commit()
    cur.close()

def _json(value):
    return json.dumps(value, ensure_ascii=False, default=str)

def _snapshot(valor):
    if isinstance(valor, dict):
        return valor
    return json.loads(valor or "{}")

def recalcular_cursor(cursor, plataformas=None, produto_ids=None, parametros=None):
    regras = carregar_regras(cursor)
    total = pendentes = 0
    for plataforma in plataformas or PLATAFORMAS:
        tabela = PLATAFORMAS[plataforma]
        condicao = "o.condicao" if plataforma == "Mercado Livre" else "NULL"
        query = f"""SELECT p.*, o.preco_real, o.sugestao_preco, {condicao} AS condicao,
                    s.dados AS snapshot
                    FROM produtos p INNER JOIN {tabela} o ON o.produto_id=p.id
                    LEFT JOIN precificacao_resultados s ON s.produto_id=p.id AND s.plataforma=%s
                    WHERE p.empresa_id=%s"""
        args = [plataforma, empresa_id()]
        if produto_ids is not None:
            if not produto_ids:
                continue
            query += " AND p.id IN (" + ",".join(["%s"] * len(produto_ids)) + ")"
            args.extend(produto_ids)
        cursor.execute(query, args)
        for row in cursor.fetchall():
            extra = _snapshot(row.get("snapshot")).get("parametros", {})
            oferta = {**extra, "preco_real": row.get("preco_real")}
            if row.get("condicao"):
                oferta["condicao"] = row["condicao"]
            oferta.update((parametros or {}).get((row["id"], plataforma), {}))
            resultado = calcular(plataforma, row, oferta, regras)
            cursor.execute(f"UPDATE {tabela} SET frete=%s, lucro=%s, margem_lucro=%s, vinte_por_cento=%s WHERE produto_id=%s",
                           tuple(resultado[k] for k in ("frete", "lucro", "margem_lucro", "vinte_por_cento")) + (row["id"],))
            cursor.execute("""INSERT INTO precificacao_resultados (produto_id, plataforma, status, mensagem, dados)
                VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE status=VALUES(status),
                mensagem=VALUES(mensagem), dados=VALUES(dados)""",
                           (row["id"], plataforma, resultado["status"], resultado["mensagem"], _json(resultado)))
            total += 1
            pendentes += resultado["status"] != "calculado"
    return total, pendentes

def transacao(operacao):
    identificador = empresa_id()
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sem conexão com o banco.")
    try:
        _schema(conn)
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute("SELECT id FROM empresas WHERE id=%s", (identificador,))
        if cur.fetchone() is None:
            raise ValueError("Empresa não encontrada.")
        # Serializa alterações do app para não publicar resultados com regras concorrentes antigas.
        cur.execute("SELECT versao FROM precificacao_controle WHERE id=1 FOR UPDATE")
        cur.fetchone()
        with usar_empresa(identificador):
            resultado = operacao(cur)
        conn.commit()
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def inicializar():
    # Abrir o aplicativo prepara a estrutura, mas nunca recalcula os produtos.
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sem conexão com o banco.")
    try:
        _schema(conn)
        from migracao_multiempresa import migrar
        migrar(conn)
    finally:
        conn.close()

def _historico(cursor, usuario, produto_id, acao, dados):
    if usuario:
        cursor.execute("""INSERT INTO historico_alteracoes
            (usuario_id, usuario_nome, tabela, registro_id, acao, detalhes, empresa_id)
            VALUES (%s,%s,'produtos',%s,%s,%s,%s)""",
                       (usuario.get("id"), usuario.get("nome"), produto_id, acao, _json({"valores_novos": dados}), empresa_id()))

def salvar_produto(dados, usuario, plataforma, produto_id=None):
    if plataforma not in PLATAFORMAS:
        raise ValueError("Plataforma inválida.")
    def salvar(cur):
        valores = {k: v for k, v in dados.items() if k in CAMPOS}
        for k in ("trib", "embalagem", "quantidade", "peso", "target_minimo"):
            if k in valores:
                v = valores[k]
                valores[k] = None if v is None or str(v).strip() == "" else (peso_em_kg(v) if k == "peso" else numero(v, k))
                if k == "quantidade" and valores[k] is not None:
                    if valores[k] != valores[k].to_integral_value() or valores[k] < 1:
                        raise ValueError("Unidades do kit deve ser um inteiro maior que zero.")
                    valores[k] = int(valores[k])
        for k in ("sku", "descricao"):
            if k in valores and not str(valores[k] or "").strip():
                raise ValueError(f"{k} é obrigatório.")
        if produto_id is not None:
            cur.execute("SELECT * FROM produtos WHERE id=%s AND empresa_id=%s FOR UPDATE", (produto_id, empresa_id()))
            anterior = cur.fetchone()
            if not anterior:
                raise ValueError("Produto não encontrado.")
        else:
            anterior = {}
            if not valores.get("sku") or not valores.get("descricao"):
                raise ValueError("SKU e descrição são obrigatórios.")
        if valores.get("sku") and valores["sku"] != anterior.get("sku"):
            cur.execute("SELECT id FROM produtos WHERE sku=%s AND empresa_id=%s", (valores["sku"], empresa_id()))
            if cur.fetchall():
                raise ValueError("SKU já cadastrado. Edite o produto existente para adicionar outra plataforma.")
        if produto_id is None:
            valores["empresa_id"] = empresa_id()
            cols = list(valores)
            cur.execute(f"INSERT INTO produtos ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))})", tuple(valores.values()))
            pid = cur.lastrowid
        else:
            pid = produto_id
            if valores:
                cur.execute("UPDATE produtos SET " + ",".join(f"{k}=%s" for k in valores) + " WHERE id=%s AND empresa_id=%s",
                            tuple(valores.values()) + (pid, empresa_id()))
        oferta = {}
        for k in ("preco_real", "sugestao_preco"):
            if k in dados:
                oferta[k] = None if dados[k] is None or str(dados[k]).strip() == "" else numero(dados[k], k)
        if plataforma == "Mercado Livre" and "condicao" in dados:
            if dados["condicao"] not in ("Premium", "Clássico"):
                raise ValueError("Condição Mercado Livre inválida.")
            oferta["condicao"] = dados["condicao"]
        if oferta.get("preco_real") is not None and oferta["preco_real"] != dinheiro(oferta["preco_real"]):
            raise ValueError("Preço deve ter no máximo duas casas decimais.")
        tabela = PLATAFORMAS[plataforma]
        cur.execute(f"SELECT produto_id FROM {tabela} WHERE produto_id=%s", (pid,))
        existe = cur.fetchone()
        if existe and oferta:
            cur.execute(f"UPDATE {tabela} SET " + ",".join(f"{k}=%s" for k in oferta) + " WHERE produto_id=%s", tuple(oferta.values()) + (pid,))
        elif not existe:
            campos = ["produto_id", *oferta]
            cur.execute(f"INSERT INTO {tabela} ({','.join(campos)}) VALUES ({','.join(['%s']*len(campos))})", (pid, *oferta.values()))
        parametros = {(pid, plataforma): {"regiao": dados["regiao"]}} if "regiao" in dados else None
        financeiros = ("trib", "embalagem", "quantidade", "peso")
        compartilhado_alterado = produto_id is None or any(
            k in valores and valores[k] != (
                None if anterior.get(k) is None or str(anterior[k]).strip() == ""
                else (peso_em_kg(anterior[k]) if k == "peso" else numero(anterior[k], k))
            ) for k in financeiros)
        plataformas = None if compartilhado_alterado else [plataforma]
        total, pendentes = recalcular_cursor(cur, plataformas, produto_ids=[pid], parametros=parametros)
        _historico(cur, usuario, pid, "criar" if produto_id is None else "atualizar", dados)
        return pid, total, pendentes
    return transacao(salvar)

def atualizar_regras(tabela, alteracoes):
    permitidos = {
        "tabela_taxas_comissoes": {"canal", "condicao", "taxa_percentual", "taxa_fixa_reais"},
        "tabela_frete_shopee": {"faixa", "valor_do_produto", "taxa_percentual", "taxa_fixa_reais"},
        "tabela_frete_ml": {"peso", "faixa_0_18_99", "faixa_19_48_99", "faixa_49_78_99", "faixa_79_99_99", "faixa_100_119_99", "faixa_120_149_99", "faixa_150_199_99", "faixa_200_mais"},
        "tabela_frete_amazon": {"peso", "faixa_79_99_99", "faixa_100_119_99", "faixa_120_149_99", "faixa_150_199_99"},
        "tabela_frete_amazon_brl200": {"peso", "sp_capital", "outras_capitais_sul_sudeste", "interior_sul_sudeste", "centro_oeste_norte_nordeste"},
    }
    if tabela not in permitidos:
        raise ValueError("Tabela de regras inválida.")
    def salvar(cur):
        for linha in alteracoes:
            cur.execute(f"SELECT id FROM {tabela} WHERE id=%s AND empresa_id=%s", (linha["id"], empresa_id()))
            if not cur.fetchone():
                raise ValueError("Regra não encontrada.")
            dados = {k: v for k, v in linha.items() if k in permitidos[tabela]}
            for k, v in dados.items():
                if k in ("canal", "condicao", "peso", "faixa", "valor_do_produto"):
                    if not str(v or "").strip():
                        raise ValueError(f"{k} é obrigatório.")
                else:
                    dados[k] = None if k == "taxa_fixa_reais" and (v is None or str(v).strip() == "") else numero(v, k)
            if dados:
                cur.execute(f"UPDATE {tabela} SET " + ",".join(f"{k}=%s" for k in dados) + " WHERE id=%s AND empresa_id=%s", tuple(dados.values()) + (linha["id"], empresa_id()))
        plataformas = {"tabela_frete_ml": ["Mercado Livre"], "tabela_frete_shopee": ["Shopee"],
                       "tabela_frete_amazon": ["Amazon"], "tabela_frete_amazon_brl200": ["Amazon"]}.get(tabela)
        return recalcular_cursor(cur, plataformas)
    return transacao(salvar)

def importar_csv(caminho):
    with open(caminho, "rb") as arquivo:
        raw = arquivo.read()
    try:
        texto = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = raw.decode("cp1252")
    if not texto.strip():
        raise ValueError("CSV vazio.")
    cabecalho = texto.splitlines()[0]
    delimitador = ";" if ";" in cabecalho else ("\t" if "\t" in cabecalho else ",")
    reader = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    if not reader.fieldnames or "sku" not in [c.strip().lower() for c in reader.fieldnames]:
        raise ValueError("Coluna SKU obrigatória.")
    linhas = [{k.strip().lower(): (v or "").strip() for k, v in row.items() if k} for row in reader]
    def salvar(cur):
        ids = set()
        for linha in linhas:
            sku = linha.get("sku")
            if not sku:
                continue
            cur.execute("SELECT id FROM produtos WHERE sku=%s AND empresa_id=%s", (sku, empresa_id()))
            encontrados = cur.fetchall()
            if len(encontrados) != 1:
                raise ValueError(f"SKU {sku}: esperado um produto, encontrados {len(encontrados)}. Nada importado.")
            pid = encontrados[0]["id"]
            for campo in ("embalagem", "trib", "quantidade", "peso"):
                if linha.get(campo):
                    valor = peso_em_kg(linha[campo]) if campo == "peso" else numero(linha[campo], campo)
                    if campo == "quantidade" and (valor < 1 or valor != valor.to_integral_value()):
                        raise ValueError("Unidades do kit deve ser um inteiro maior que zero.")
                    cur.execute(f"UPDATE produtos SET {campo}=%s WHERE id=%s AND empresa_id=%s", (valor, pid, empresa_id()))
            for coluna, plataforma in {"preco_ml": "Mercado Livre", "preco_amazon": "Amazon", "preco_shopee": "Shopee",
                                      "preco_tiktok": "TikTok", "preco_magalu": "Magalu", "preco_kwai": "Kwai"}.items():
                if linha.get(coluna):
                    preco = numero(linha[coluna], coluna)
                    if preco != dinheiro(preco):
                        raise ValueError("Preço deve ter no máximo duas casas decimais.")
                    tabela = PLATAFORMAS[plataforma]
                    cur.execute(f"INSERT INTO {tabela} (produto_id, preco_real) VALUES (%s,%s) ON DUPLICATE KEY UPDATE preco_real=VALUES(preco_real)", (pid, preco))
            ids.add(pid)
        _, pendentes = recalcular_cursor(cur, produto_ids=sorted(ids))
        return len(ids), pendentes
    return transacao(salvar)

def previa(plataforma, produto, oferta):
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sem conexão com o banco.")
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        return calcular(plataforma, produto, oferta, carregar_regras(cur))
    finally:
        conn.close()
