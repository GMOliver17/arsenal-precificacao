import precificacao as motor
import servico_precificacao as servico
from db import get_connection
import json
import re
from decimal import Decimal
from empresas import empresa_id

def criar_tabela_historico():
    """Cria a tabela de histórico se não existir."""
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_alteracoes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario_id INT,
                usuario_nome VARCHAR(100),
                tabela VARCHAR(50),
                registro_id INT,
                acao VARCHAR(50),
                detalhes TEXT,
                data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                empresa_id INT NOT NULL
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"[ERRO] Ao criar tabela de histórico: {e}")
    finally:
        conn.close()

def registrar_historico(usuario, tabela, registro_id, acao,
                        valores_antigos=None, valores_novos=None):
    conn = get_connection()
    if conn is None:
        return
    try:
        cursor = conn.cursor()
        detalhes = {}
        if valores_antigos:
            detalhes["valores_anteriores"] = {
                k: str(v) for k, v in valores_antigos.items()
                if k not in ("created_at", "updated_at", "senha_hash")
            }
        if valores_novos:
            detalhes["valores_novos"] = {
                k: str(v) for k, v in valores_novos.items()
            }
        cursor.execute(
            "INSERT INTO historico_alteracoes "
            "(usuario_id, usuario_nome, tabela, registro_id, acao, detalhes, empresa_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (usuario["id"], usuario["nome"], tabela, registro_id, acao,
             json.dumps(detalhes), empresa_id())
        )
        conn.commit()
    except Exception as e:
        print(f"[ERRO] Ao registrar histórico: {e}")
    finally:
        conn.close()

def listar_historico(limite=200):
    """Retorna os últimos registros do histórico."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute(
            "SELECT id, usuario_nome, tabela, registro_id, acao, detalhes, "
            "data_alteracao FROM historico_alteracoes "
            "WHERE empresa_id=%s ORDER BY id DESC LIMIT %s",
            (empresa_id(), limite)
        )
        return cursor.fetchall()
    except Exception as e:
        print(f"[ERRO listar_historico] {e}")
        return []
    finally:
        conn.close()


def listar_produtos(busca="", plataforma="Mercado Livre"):
    return _ler_produtos(plataforma, busca=busca)

def listar_produtos_ml_condicao(busca, condicao=None):
    dados = listar_produtos(busca, "Mercado Livre")
    if condicao is None:
        return dados
    regras = _regras_atuais()
    return [motor.simular_condicao_ml(p, condicao, regras) for p in dados]

def buscar_produto(produto_id, plataforma="Mercado Livre", condicao_ml=None):
    linhas = _ler_produtos(plataforma, produto_id=produto_id)
    if not linhas:
        return None
    if plataforma == "Mercado Livre" and condicao_ml is not None:
        return motor.simular_condicao_ml(linhas[0], condicao_ml, _regras_atuais())
    return linhas[0]

def criar_produto(dados, usuario, plataforma="Mercado Livre"):
    try:
        pid, total, pendentes = servico.salvar_produto(dados, usuario, plataforma)
        return True, f"Produto salvo; {total} resultados atualizados, {pendentes} pendentes de dados.", pid
    except Exception as e:
        return False, f"Não foi salvo: {e}", None

def atualizar_produto(produto_id, dados, usuario, plataforma="Mercado Livre"):
    try:
        _, total, pendentes = servico.salvar_produto(dados, usuario, plataforma, produto_id)
        return True, f"Produto salvo; {total} resultados atualizados, {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Não foi salvo: {e}"

def listar_marcas():
    """Retorna todas as marcas distintas cadastradas."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT marca FROM produtos "
            "WHERE empresa_id=%s AND marca IS NOT NULL AND marca != '' ORDER BY marca",
            (empresa_id(),)
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

# ──────────────────────────────────────────────
#  FRETE MERCADO LIVRE — BUSCA PARA PRODUTOS
# ──────────────────────────────────────────────
def buscar_pesos_frete_ml():
    """Retorna todos os valores da coluna peso da tabela_frete_ml."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT peso FROM tabela_frete_ml WHERE empresa_id=%s ORDER BY id", (empresa_id(),))
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

def formatar_nome_faixa(nome_coluna):
    """Transforma o nome técnico da coluna em texto legível.
    Ex: faixa_0_18_99  ->  'Faixa R$ 0,00 até R$ 18,99'
        faixa_200_mais ->  'Faixa R$ 200,00 ou mais'
    """
    partes = nome_coluna.replace('faixa_', '').split('_')
    if 'mais' in partes:
        return f"Faixa R$ {partes[0]},00 ou mais"
    if len(partes) == 3:
        return f"Faixa R$ {partes[0]},00 até R$ {partes[1]},{partes[2]}"
    return nome_coluna

def buscar_faixas_preco_ml():
    """Retorna lista de tuplas (nome_coluna, nome_formatado) das faixas de preço."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'tabela_frete_ml'
            AND TABLE_SCHEMA = DATABASE()
            AND COLUMN_NAME NOT IN ('id', 'peso', 'empresa_id')
            ORDER BY ORDINAL_POSITION
        """)
        colunas = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
    return [(col, formatar_nome_faixa(col)) for col in colunas]

def buscar_frete_ml(peso_selecionado, faixa_coluna):
    """Busca o valor do frete na interseção do peso (linha) e faixa (coluna)."""
    permitidas = {motor.coluna_ml(Decimal(p)) for p in ("0", "19", "49", "79", "100", "120", "150", "200")}
    if faixa_coluna not in permitidas:
        raise ValueError("Faixa de preço inválida.")
    conn = get_connection()
    if conn is None:
        print("[DEBUG buscar_frete_ml] conexão é None")
        return None
    try:
        cursor = conn.cursor()
        query = f"SELECT `{faixa_coluna}` FROM tabela_frete_ml WHERE peso = %s AND empresa_id=%s"
        cursor.execute(query, (peso_selecionado, empresa_id()))
        resultado = cursor.fetchone()
        if resultado:
            valor = float(resultado[0])

            return valor

        return None
    finally:
        conn.close()
# ──────────────────────────────────────────────
#  TAXAS E COMISSÕES
# ──────────────────────────────────────────────
def listar_taxas_comissoes():
    """Retorna todas as linhas da tabela_taxas_comissoes."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM tabela_taxas_comissoes WHERE empresa_id=%s ORDER BY id", (empresa_id(),))
        return cursor.fetchall()
    except Exception as e:
        print(f"[ERRO listar_taxas_comissoes] {e}")
        return []
    finally:
        conn.close()

def atualizar_taxa_comissao(taxa_id, taxa_percentual=None, taxa_fixa_reais=None):
    linha = {"id": taxa_id}
    if taxa_percentual is not None:
        linha["taxa_percentual"] = taxa_percentual
    if taxa_fixa_reais is not None:
        linha["taxa_fixa_reais"] = taxa_fixa_reais
    return atualizar_taxas_lote([linha])

def buscar_taxa_imposto():
    regras = _regras_atuais()
    return float(motor.unica(motor.canal(regras, "Imposto"), "Imposto")["taxa_percentual"])

def buscar_taxa_ml(condicao):
    r = motor.taxa_padrao(_regras_atuais(), "Mercado Livre", condicao)
    return float(r["taxa_percentual"]), float(r.get("taxa_fixa_reais") or 0)

def calcular_lucro_ml(preco_real, taxa_percentual, imposto_percentual, frete, embalagem, trib, quantidade):
    return float(motor.totais(preco_real, taxa_percentual, imposto_percentual, frete, embalagem, trib, quantidade)["lucro"])

def calcular_margem_lucro(lucro, preco_real):
    return float(motor.dinheiro(Decimal(str(lucro)) / Decimal(str(preco_real)) * 100)) if preco_real and preco_real > 0 else 0.0

def calcular_vinte_por_cento(preco_real):
    return float(motor.dinheiro(motor.numero(preco_real, padrao=0) * Decimal("1.20")))

def determinar_faixa_preco_ml(preco):
    try:
        return motor.coluna_ml(motor.numero(preco, "preço"))
    except ValueError:
        return None


def determinar_peso_ml(peso):
    """Seleciona a faixa cadastrada com a mesma regra usada ao salvar."""
    try:
        linha, _, _ = motor.selecionar_faixa_peso(_regras_atuais()["tabela_frete_ml"], peso)
        return linha["peso"]
    except ValueError:
        return None

# ──────────────────────────────────────────────
#  AMAZON — FRETE E CÁLCULOS
def buscar_frete_amazon(preco):
    return calcular_frete_amazon(None, preco)

def buscar_taxa_amazon():
    return float(motor.taxa_padrao(_regras_atuais(), "Amazon")["taxa_percentual"])

def calcular_lucro_amazon(preco_real, taxa_percentual, imposto_percentual, frete, embalagem, trib, quantidade):
    return float(motor.totais(preco_real, taxa_percentual, imposto_percentual, frete, embalagem, trib, quantidade)["lucro"])

def calcular_frete_amazon(peso, preco, cursor_ext=None, regiao=None):
    try:
        if cursor_ext is None:
            regras = _regras_atuais()
        else:
            regras = {}
            for tabela in servico.TABELAS_REGRAS:
                cursor_ext.execute(f"SELECT * FROM {tabela} WHERE empresa_id=%s ORDER BY id", (empresa_id(),))
                linhas = cursor_ext.fetchall()
                colunas = [d[0] for d in cursor_ext.description]
                regras[tabela] = [r if isinstance(r, dict) else dict(zip(colunas, r)) for r in linhas]
        return float(motor.frete_amazon(regras, peso, preco, regiao))
    except motor.Incompleto:
        return None

# ════════════════════════════════════════════════════
#  SHOPEE — TAXAS E CÁLCULOS
# ════════════════════════════════════════════════════
def buscar_taxa_shopee(preco_real):
    regras = _regras_atuais()
    r = motor.por_faixa(regras["tabela_frete_shopee"], "valor_do_produto", motor.numero(preco_real))
    return float(r["taxa_percentual"]), float(r["taxa_fixa_reais"])

def calcular_lucro_shopee(preco_real, taxa_percentual, taxa_fixa, imposto, embalagem, trib, quantidade=1):
    return float(motor.totais(preco_real, taxa_percentual, imposto, taxa_fixa, embalagem, trib, quantidade)["lucro"])

# ════════════════════════════════════════════════════
#  TIKTOK — TAXAS E CÁLCULOS
# ════════════════════════════════════════════════════
def buscar_taxa_tiktok(preco_real):
    regras = _regras_atuais()
    linhas = motor.canal(regras, "TikTok")
    r = motor.por_faixa(linhas, "condicao", motor.numero(preco_real))
    af = [x for x in linhas if "afiliado" in motor.normalizar(x["condicao"])]
    return float(r["taxa_percentual"]), float(r["taxa_fixa_reais"]), float(motor.unica(af, "Afiliado")["taxa_percentual"]) if af else 0

def calcular_lucro_tiktok(preco_real, taxa_percentual, frete, afiliado_pct, imposto, embalagem, trib, quantidade=1):
    return float(motor.totais(preco_real, taxa_percentual, imposto, frete, embalagem, trib, quantidade, afiliado_pct or 0)["lucro"])

# ════════════════════════════════════════════════════
#  MAGALU — TAXAS E CÁLCULOS
# ════════════════════════════════════════════════════
def buscar_taxa_magalu(preco_real):
    regras = _regras_atuais()
    r = motor.taxa_padrao(regras, "Magalu")
    return float(r["taxa_percentual"]), 0, 0

def calcular_lucro_magalu(preco_real, taxa_percentual, frete, afiliado_pct, imposto, embalagem, trib, quantidade=1):
    return float(motor.totais(preco_real, taxa_percentual, imposto, frete, embalagem, trib, quantidade, afiliado_pct or 0)["lucro"])

# ════════════════════════════════════════════════════
#  KWAI — TAXAS E CÁLCULOS
# ════════════════════════════════════════════════════
def buscar_taxa_kwai(preco_real):
    regras = _regras_atuais()
    r = motor.taxa_padrao(regras, "Kwai")
    return float(r["taxa_percentual"]), float(r.get("taxa_fixa_reais") or 0), 0

def calcular_lucro_kwai(preco_real, taxa_percentual, frete, afiliado_pct, imposto, embalagem, trib, quantidade=1):
    return float(motor.totais(preco_real, taxa_percentual, imposto, frete, embalagem, trib, quantidade, afiliado_pct or 0)["lucro"])

# ════════════════════════════════════════════════════
#  KPIs — ABA GERAL
# ════════════════════════════════════════════════════
def buscar_kpis_geral():
    dados = listar_produtos(plataforma="Mercado Livre")
    marcas = {}
    for p in dados:
        marcas.setdefault(p.get("marca") or "Sem Marca", []).append(p)
    def media(linhas, campo):
        valores = [p[campo] for p in linhas if p.get(campo) is not None]
        return sum(valores)/len(valores) if valores else None
    return {"total_produtos": len(dados), "ticket_medio_geral": media(dados, "preco_real"),
            "margem_media_geral": media(dados, "margem_lucro"),
            "por_marca": [{"marca": m, "quantidade": len(rows), "ticket_medio": media(rows, "preco_real"),
                           "margem_media": media(rows, "margem_lucro")} for m, rows in sorted(marcas.items())]}

# ════════════════════════════════════════════════════
#  COMPARADOR — ABA GERAL
# ════════════════════════════════════════════════════
def comparar_plataformas(sku):
    conn = get_connection()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM produtos WHERE sku=%s AND empresa_id=%s", (sku, empresa_id()))
        ids = cur.fetchall()
        if len(ids) != 1:
            return None  # ambiguidade nunca escolhe arbitrariamente um duplicado
        pid = ids[0][0]
        resultados = []
        for plataforma in motor.PLATAFORMAS:
            # Mesma conexão/snapshot de leitura nas seis plataformas.
            p = _ler_produtos(plataforma, produto_id=pid, conn_ext=conn)[0]
            pronto = p.get("status_calculo") == "calculado"
            resultados.append({"plataforma": plataforma, "preco_real": p.get("preco_real") or 0,
                               "frete": p.get("frete"), "lucro": p.get("lucro"), "margem": p.get("margem_lucro"),
                               "cadastrado": pronto, "mensagem": p.get("mensagem_calculo") or "Sem preço nesta plataforma"})
        return resultados
    finally:
        conn.close()

# ════════════════════════════════════════════════════
#  IMPORTAÇÃO EM LOTE — CSV
# ════════════════════════════════════════════════════
def importar_dados_planilha(caminho_arquivo):
    try:
        qtd, pendentes = servico.importar_csv(caminho_arquivo)
        return {"sucesso": True, "atualizados": qtd, "erros": [], "avisos": [f"{pendentes} resultados pendentes de dados."] if pendentes else []}
    except Exception as e:
        return {"sucesso": False, "atualizados": 0, "erros": [str(e)], "avisos": []}

def recalcular_plataforma(plataforma):
    try:
        total, pendentes = servico.transacao(lambda cur: servico.recalcular_cursor(cur, [plataforma]))
        return True, f"{total} resultados salvos; {pendentes} pendentes de dados.", total
    except Exception as e:
        return False, f"Recálculo cancelado: {e}", 0

def excluir_produto_completo(sku, usuario_nome):
    try:
        def excluir(cur):
            cur.execute("SELECT id FROM produtos WHERE sku=%s AND empresa_id=%s FOR UPDATE", (sku, empresa_id()))
            ids = cur.fetchall()
            if len(ids) != 1:
                raise ValueError("SKU ausente ou duplicado. Exclusão cancelada.")
            pid = ids[0]["id"]
            for tabela in motor.PLATAFORMAS.values():
                cur.execute(f"DELETE FROM {tabela} WHERE produto_id=%s", (pid,))
            cur.execute("DELETE FROM produtos WHERE id=%s AND empresa_id=%s", (pid, empresa_id()))
            servico._historico(cur, {"nome": usuario_nome}, pid, "excluir", {"sku": sku})
        servico.transacao(excluir)
        return True, "Produto excluído."
    except Exception as e:
        return False, str(e)

def gerar_relatorio_excel(plataforma, colunas, caminho_arquivo):
    """Gera um Excel com os produtos da plataforma escolhida.
    colunas: lista de chaves (ex: ['sku', 'frete', 'preco_real'])
    Retorna (ok, mensagem)."""
    if not colunas:
        return False, "Selecione pelo menos uma coluna."
    titulos = {
        "sku": "SKU",
        "descricao": "Descrição",
        "marca": "Marca",
        "trib": "Trib",
        "embalagem": "Embalagem",
        "quantidade": "Qtd",
        "peso": "Peso (kg)",
        "frete": "Frete (R$)",
        "sugestao_preco": "Sug. Preço (R$)",
        "preco_real": "Preço Real (R$)",
        "lucro": "Lucro (R$)",
        "margem_lucro": "Margem (%)",
        "vinte_por_cento": "20% (R$)",
        "target_minimo": "Target Mínimo (R$)",
    }
    colunas = list(dict.fromkeys(colunas))
    dados = listar_produtos("", plataforma)
    if not dados:
        return False, f"Nenhum produto cadastrado para {plataforma}."
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = plataforma[:30]
        ws.append([titulos.get(c, c) for c in colunas])
        for p in dados:
            linha = []
            for c in colunas:
                val = p.get(c)
                if c in ("sku", "descricao", "marca", "status_calculo", "mensagem_calculo"):
                    linha.append(str(val) if val is not None else "")
                else:
                    linha.append(float(val) if val is not None else "")
            ws.append(linha)
        # Largura das colunas
        for idx in range(1, len(colunas) + 1):
            letra = ws.cell(row=1, column=idx).column_letter
            ws.column_dimensions[letra].width = 20
        wb.save(caminho_arquivo)
        return True, f"Relatório gerado com {len(dados)} produto(s)."
    except Exception as e:
        print(f"[ERRO gerar_relatorio_excel] {e}")
        return False, f"Erro ao gerar relatório: {e}"


def _regras_atuais():
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Sem conexão com o banco.")
    try:
        return servico.carregar_regras(conn.cursor(dictionary=True, buffered=True))
    finally:
        conn.close()

def _ler_produtos(plataforma, busca="", produto_id=None, conn_ext=None):
    tabela = motor.PLATAFORMAS[plataforma]
    conn = conn_ext or get_connection()
    if conn is None:
        return []
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        condicao = "o.condicao" if plataforma == "Mercado Livre" else "NULL"
        query = f"""SELECT p.*, o.preco_real, o.sugestao_preco, o.frete, o.lucro,
                    o.margem_lucro, o.vinte_por_cento, {condicao} AS condicao,
                    s.status AS status_calculo, s.mensagem AS mensagem_calculo, s.dados AS snapshot
                    FROM produtos p LEFT JOIN {tabela} o ON o.produto_id=p.id
                    LEFT JOIN precificacao_resultados s ON s.produto_id=p.id AND s.plataforma=%s WHERE p.empresa_id=%s"""
        params = [plataforma, empresa_id()]
        if busca:
            query += " AND (p.sku LIKE %s OR p.descricao LIKE %s)"
            params += [f"%{busca}%", f"%{busca}%"]
        if produto_id is not None:
            query += " AND p.id=%s"
            params.append(produto_id)
        cur.execute(query + " ORDER BY p.sku", params)
        rows = cur.fetchall()
        for row in rows:
            detalhe = servico._snapshot(row.pop("snapshot", None))
            row["regiao"] = detalhe.get("parametros", {}).get("regiao")
            for k in ("taxa_percentual", "imposto_percentual", "afiliado_percentual", "taxa_fixa", "comissao", "imposto", "afiliado", "custo_itens"):
                row[k] = float(detalhe[k]) if detalhe.get(k) is not None else None
            # A tabela da plataforma é a fonte dos valores salvos, inclusive antigos.
            # Ausência de metadados auxiliares não apaga resultados na leitura.
            pronto = all(row.get(k) is not None for k in ("frete", "lucro", "margem_lucro", "vinte_por_cento"))
            row["status_calculo"] = "calculado" if pronto else "pendente"
            row["mensagem_calculo"] = row.get("mensagem_calculo") or ("" if row["status_calculo"] == "calculado" else "Sem cálculo salvo; informe os dados e salve ou use Recalcular.")
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
        return rows
    finally:
        if conn_ext is None:
            conn.close()

def atualizar_taxas_lote(linhas):
    try:
        total, pendentes = servico.atualizar_regras("tabela_taxas_comissoes", linhas)
        return True, f"Taxas e {total} resultados salvos; {pendentes} pendentes de dados."
    except Exception as e:
        return False, f"Nada foi salvo: {e}"
