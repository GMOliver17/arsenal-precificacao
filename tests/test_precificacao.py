"""Testes sem MySQL: fórmulas e fluxos SQL em SQLite exclusivamente em memória.
O adaptador cobre transações/valores; não certifica sintaxe/locking do MySQL.
Execute: python -B -m unittest discover -s tests -v
"""
import ast
import copy
import io
import json
from pathlib import Path
import re
import sqlite3
import sys
import types
import unittest
from decimal import Decimal as D
from unittest.mock import patch, mock_open

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Isolamento persistente: os imports tardios das telas também recebem este módulo.
def banco_real_proibido(*args, **kwargs):
    raise AssertionError("A suíte não pode acessar o banco real")

fake_db = types.ModuleType("db")
fake_db.get_connection = banco_real_proibido
fake_db._pasta_base = lambda: str(ROOT)
fake_db.carregar_config_bd = lambda: {}
fake_db.salvar_config_bd = banco_real_proibido
fake_db.testar_conexao_bd = banco_real_proibido
sys.modules["db"] = fake_db
import servico_precificacao as svc
import produtos
import fretes
import precificacao as motor
import empresas
import migracao_multiempresa


def regras_dump():
    """Regras de referencia da suite; nao depende de dados de producao."""
    return json.loads((ROOT / "tests" / "fixtures" / "regras_precificacao.json").read_text(encoding="utf-8"))


class MotorTests(unittest.TestCase):
    def setUp(self):
        self.regras = regras_dump()
        self.produto = {"trib": 20, "embalagem": 2, "quantidade": 2, "peso": "0.8"}

    def test_seis_plataformas_preco_do_kit(self):
        esperados = {"Mercado Livre": "10.85", "Amazon": "17.30", "Shopee": "10.00",
                     "TikTok": "22.00", "Magalu": "26.00", "Kwai": "20.00"}
        for plataforma, lucro in esperados.items():
            with self.subTest(plataforma=plataforma):
                r = motor.calcular(plataforma, self.produto, {"preco_real": 100}, self.regras)
                self.assertEqual(r["status"], "calculado")
                self.assertEqual(r["lucro"], D(lucro))
                self.assertEqual(r["margem_lucro"], D(lucro))
                self.assertEqual(r["custo_itens"], 40)
                self.assertEqual(r["embalagem"], 2)
                self.assertEqual(r["preco_base"], 100)

    def test_amazon_peso_unidades_e_adicional(self):
        for peso, esperado in [("0.25", "11.95"), ("0.251", "12.85"), ("0.5", "12.85"),
                               ("0.8", "13.45"), ("10", "39.50"), ("11", "42.55")]:
            with self.subTest(peso=peso):
                self.assertEqual(motor.frete_amazon(self.regras, peso, 90), D(esperado))

    def test_ml_800_gramas_nao_usa_primeira_faixa(self):
        for peso in ('0.8', '0,8', '800 g', '0,8 kg'):
            r = motor.calcular('Mercado Livre', {**self.produto, 'peso': peso}, {'preco_real':100}, self.regras)
            self.assertEqual(r['frete'], D('16.15'), peso)
            self.assertEqual(r['lucro'], D('10.85'), peso)
        for peso, frete in [('0.3','14.35'), ('0.3001','15.45'), ('0.5','15.45'),
                            ('0.5001','16.15'), ('1','16.15'), ('1.0001','16.45')]:
            r = motor.calcular('Mercado Livre', {**self.produto,'peso':peso}, {'preco_real':100}, self.regras)
            self.assertEqual(r['frete'], D(frete), peso)

    def test_ml_faixa_de_preco_e_peso_sao_independentes(self):
        for preco, frete in [('18.99','6.05'), ('19','6.75'), ('49','7.95'), ('79','13.85'),
                             ('100','16.15'), ('120','18.45'), ('150','20.75'), ('200','23.65')]:
            r = motor.calcular('Mercado Livre', self.produto, {'preco_real':preco}, self.regras)
            self.assertEqual(r['frete'], D(frete), preco)

    def test_amazon_limites_de_preco(self):
        for preco, esperado in [(30, "4.50"), ("30.01", "6.50"), (50, "6.75"),
                                ("78.99", "6.75"), (79, "11.95"), (100, "13.95"), ("199.99", "17.95")]:
            self.assertEqual(motor.frete_amazon(self.regras, ".2", preco), D(esperado))

    def test_amazon_200_requer_regiao(self):
        r = motor.calcular("Amazon", self.produto, {"preco_real": 200}, self.regras)
        self.assertEqual(r["status"], "pendente")
        self.assertIsNone(r["lucro"])
        self.assertEqual(motor.frete_amazon(self.regras, ".2", 200, "sp_capital"), D("19.95"))

    def test_comissao_amazon_escolhe_padrao(self):
        self.regras["tabela_taxas_comissoes"].reverse()
        r = motor.calcular("Amazon", self.produto, {"preco_real": 100}, self.regras)
        self.assertEqual(r["taxa_percentual"], 11)

    def test_shopee_limites(self):
        for preco, frete in [("79.99", 4), (80, 16), (100, 20), (200, 26), (500, 26)]:
            self.assertEqual(motor.calcular("Shopee", self.produto, {"preco_real": preco}, self.regras)["frete"], frete)

    def test_tiktok_faixas_individuais(self):
        for preco, taxa, frete in [(50, 10, 4), ("50.01", 6, 6)]:
            r = motor.calcular("TikTok", self.produto, {"preco_real": preco}, self.regras)
            self.assertEqual((r["taxa_percentual"], r["frete"], r["afiliado_percentual"]), (taxa, frete, 10))

    def test_condicao_ml_e_preco_real(self):
        premium = motor.calcular("Mercado Livre", self.produto, {"preco_real": 100}, self.regras)
        classico = motor.calcular("Mercado Livre", self.produto, {"preco_real": 100, "condicao": "Clássico", "sugestao_preco": 500}, self.regras)
        self.assertEqual(classico["lucro"] - premium["lucro"], 5)
        self.assertEqual(classico["frete"], premium["frete"])

    def test_dados_ausentes_nao_sao_lucro_zero(self):
        for campo in ("trib", "embalagem", "quantidade", "peso"):
            p = {**self.produto, campo: None}
            r = motor.calcular("Mercado Livre", p, {"preco_real": 100}, self.regras)
            self.assertEqual(r["status"], "pendente")
            self.assertIsNone(r["lucro"])

    def test_centavos_e_markup(self):
        self.assertEqual(motor.dinheiro(D("2.675")), D("2.68"))
        self.assertEqual(motor.totais(100, 0, 0, 0, 2, 20, 2)["vinte_por_cento"], 120)
        for bad in ("NaN", "Infinity", -1):
            with self.assertRaises(ValueError):
                motor.numero(bad)


sqlite3.register_adapter(D, str)

class Cursor:
    def __init__(self, conn, dictionary=False):
        self.conn = conn
        self.raw = conn.raw.cursor()
        self.dictionary = dictionary

    def execute(self, sql, params=()):
        self.conn.queries.append(sql)
        if self.conn.fail and self.conn.fail in sql:
            raise RuntimeError("falha simulada de persistência")
        sql = sql.replace("%s", "?").replace(" FOR UPDATE", "")
        if " ON DUPLICATE KEY UPDATE " in sql:
            inicio, update = sql.split(" ON DUPLICATE KEY UPDATE ", 1)
            target = "produto_id, plataforma" if "precificacao_resultados" in inicio else "produto_id"
            update = re.sub(r"VALUES\((\w+)\)", r"excluded.\1", update)
            sql = inicio + f" ON CONFLICT ({target}) DO UPDATE SET " + update
        self.raw.execute(sql, params)
        self.lastrowid = self.raw.lastrowid
        self.description = self.raw.description
        self.rowcount = self.raw.rowcount
        return self

    def _row(self, row):
        if row is None:
            return None
        return dict(zip([c[0] for c in self.raw.description], row)) if self.dictionary else row

    def fetchall(self):
        return [self._row(row) for row in self.raw.fetchall()]

    def fetchone(self):
        return self._row(self.raw.fetchone())

    def close(self):
        self.raw.close()

class Connection:
    def __init__(self):
        self.raw = sqlite3.connect(":memory:")
        self.raw.execute("PRAGMA foreign_keys=ON")
        self.fail = None
        self.queries = []
    def cursor(self, dictionary=False, buffered=False):
        return Cursor(self, dictionary)
    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): pass

def controles_descendentes(control):
    yield control
    for child in getattr(control,'controls',[]) or []:
        yield from controles_descendentes(child)
    content=getattr(control,'content',None)
    if hasattr(content,'_i'):
        yield from controles_descendentes(content)


class PersistenciaTests(unittest.TestCase):
    def setUp(self):
        self.conn = Connection()
        self.addCleanup(self.conn.raw.close)
        c = self.conn.raw
        c.execute("CREATE TABLE empresas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, cnpj TEXT NOT NULL UNIQUE)")
        c.execute("INSERT INTO empresas VALUES (1,'Empresa inicial','00000000000000')")
        c.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT, descricao TEXT, marca TEXT, trib NUMERIC, embalagem TEXT, quantidade INTEGER, peso TEXT, target_minimo NUMERIC, empresa_id INTEGER NOT NULL DEFAULT 1 REFERENCES empresas(id))")
        for tabela in motor.PLATAFORMAS.values():
            c.execute(f"CREATE TABLE {tabela} (produto_id INTEGER UNIQUE, preco_real NUMERIC, sugestao_preco TEXT, condicao TEXT DEFAULT 'Premium', frete NUMERIC, lucro NUMERIC, margem_lucro NUMERIC, vinte_por_cento NUMERIC)")
        c.execute("CREATE TABLE precificacao_resultados (produto_id INTEGER, plataforma TEXT, status TEXT, mensagem TEXT, dados TEXT, PRIMARY KEY(produto_id,plataforma), FOREIGN KEY(produto_id) REFERENCES produtos(id) ON DELETE CASCADE)")
        c.execute("CREATE TABLE precificacao_controle (id INTEGER PRIMARY KEY, versao INTEGER)")
        c.execute("INSERT INTO precificacao_controle VALUES (1,1)")
        c.execute("CREATE TABLE historico_alteracoes (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, usuario_nome TEXT, tabela TEXT, registro_id INTEGER, acao TEXT, detalhes TEXT, data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP, empresa_id INTEGER NOT NULL DEFAULT 1 REFERENCES empresas(id))")
        for tabela, rows in regras_dump().items():
            cols = list(rows[0])
            tipos = [f'{k} '+('INTEGER PRIMARY KEY' if k == 'id' else ('TEXT' if isinstance(rows[0][k], str) else 'NUMERIC')) for k in cols]
            c.execute(f"CREATE TABLE {tabela} ({','.join(tipos)}, empresa_id INTEGER NOT NULL DEFAULT 1 REFERENCES empresas(id))")
            c.executemany(f"INSERT INTO {tabela} ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", [tuple(r.values()) for r in rows])
        c.commit()
        self.patches = [patch.object(svc, 'get_connection', return_value=self.conn), patch.object(produtos, 'get_connection', return_value=self.conn), patch.object(svc, '_schema'), patch.object(migracao_multiempresa, 'migrar'), patch.object(empresas, 'get_connection', return_value=self.conn)]
        for p in self.patches:
            p.start(); self.addCleanup(p.stop)
        self.empresa_contexto = empresas.usar_empresa(1)
        self.empresa_contexto.__enter__()
        self.addCleanup(self.empresa_contexto.__exit__, None, None, None)
        self.dados = {'sku': 'KIT-2', 'descricao': 'Kit teste', 'marca': 'Teste', 'trib': '20', 'quantidade': '2', 'embalagem': '2', 'peso': '0.8', 'preco_real': '100'}
        self.usuario = {'id': 1, 'nome': 'Teste'}

    def criar(self, plataforma='Kwai'):
        return svc.salvar_produto(self.dados, self.usuario, plataforma)[0]

    def produto(self, pid, plataforma='Kwai'):
        return produtos.buscar_produto(pid, plataforma)

    def test_shopee_cadastro_nao_apaga_numeros(self):
        pid = self.criar('Shopee')
        p = self.produto(pid, 'Shopee')
        self.assertEqual((p['preco_real'], p['trib'], p['quantidade'], p['lucro']), (100,20,2,10))

    def test_custo_compartilhado_atualiza_seis_plataformas(self):
        pid = self.criar()
        for plat in motor.PLATAFORMAS:
            svc.salvar_produto({'preco_real': 100}, self.usuario, plat, pid)
        antes = {plat: self.produto(pid, plat)['lucro'] for plat in motor.PLATAFORMAS}
        svc.salvar_produto({'trib': 25}, self.usuario, 'Kwai', pid)
        for plat in motor.PLATAFORMAS:
            self.assertEqual(D(str(self.produto(pid, plat)['lucro'])), D(str(antes[plat]))-10)

    def test_preco_de_uma_plataforma_nao_recalcula_as_outras(self):
        pid=self.criar('Mercado Livre')
        svc.salvar_produto({'preco_real':100},self.usuario,'Amazon',pid)
        self.conn.raw.execute('UPDATE produtos_amazon SET lucro=123 WHERE produto_id=?',(pid,))
        self.conn.commit()
        # O formulário envia novamente campos compartilhados; valores iguais não os alteram.
        svc.salvar_produto({**self.dados,'preco_real':120},self.usuario,'Mercado Livre',pid)
        self.assertEqual(self.produto(pid,'Mercado Livre')['frete'],18.45)
        self.assertEqual(self.produto(pid,'Amazon')['lucro'],123)

    def test_peso_800g_salva_normalizado_e_resultados_duram_na_busca(self):
        pid=svc.salvar_produto({**self.dados,'peso':'800 g'},self.usuario,'Mercado Livre')[0]
        self.assertEqual(D(str(self.produto(pid,'Mercado Livre')['peso'])),D('0.8'))
        with patch.object(motor,'calcular',side_effect=AssertionError('Buscar não calcula')):
            for _ in range(3):
                p=self.produto(pid,'Mercado Livre')
                self.assertEqual((p['frete'],p['lucro'],p['margem_lucro']),(16.15,10.85,10.85))
        svc.salvar_produto({'peso':'0.25'},self.usuario,'Mercado Livre',pid)
        self.assertEqual(self.produto(pid,'Mercado Livre')['frete'],14.35)
        self.assertEqual(produtos.determinar_peso_ml('800 g'),'De 0,5 a 1 kg')

    def test_resultado_antigo_sem_metadados_continua_visivel(self):
        pid=self.criar()
        self.conn.raw.execute('DELETE FROM precificacao_resultados WHERE produto_id=?',(pid,))
        self.conn.commit()
        with patch.object(motor,'calcular',side_effect=AssertionError('Buscar não calcula')):
            p=self.produto(pid)
        self.assertEqual((p['frete'],p['lucro'],p['margem_lucro']),(4,20,20))
        self.assertEqual(p['status_calculo'],'calculado')

    def test_alteracao_taxa_e_frete_salva_resultados(self):
        pid = self.criar()
        ok, msg = fretes.atualizar_taxa({'id': 6, 'taxa_percentual': 25, 'taxa_fixa_reais': 8})
        self.assertTrue(ok, msg)
        p = self.produto(pid)
        self.assertEqual((p['lucro'], p['frete'], p['taxa_percentual']), (11,8,25))

    def test_imposto_sem_cache_obsoleto(self):
        pid = self.criar()
        self.assertEqual(produtos.buscar_taxa_imposto(), 14)
        self.assertTrue(produtos.atualizar_taxa_comissao(1, 20)[0])
        self.assertEqual(produtos.buscar_taxa_imposto(), 20)
        self.assertEqual(self.produto(pid)['lucro'], 14)

    def test_buscar_apenas_select_e_nao_cria_plataforma(self):
        pid = self.criar()
        self.conn.queries.clear()
        with patch.object(svc, 'recalcular_cursor', side_effect=AssertionError('Busca não recalcula')):
            self.assertEqual(produtos.listar_produtos('KIT-2', 'Kwai')[0]['lucro'],20)
            self.assertEqual(self.produto(pid, 'Amazon')['status_calculo'],'pendente')
        self.assertTrue(all(q.lstrip().startswith('SELECT') for q in self.conn.queries))
        self.assertEqual(self.conn.raw.execute('SELECT COUNT(*) FROM produtos_amazon').fetchone()[0],0)

    def test_csv_e_formulario_mesmo_resultado(self):
        pid = self.criar()
        conteudo = b'\xef\xbb\xbfSKU;Trib;Quantidade;Embalagem;Peso;Preco_ML;Preco_Amazon;Preco_Shopee;Preco_TikTok;Preco_Magalu;Preco_Kwai\nKIT-2;20;2;2;0.8;100;100;100;100;100;100\n'
        with patch('builtins.open', mock_open(read_data=conteudo)):
            self.assertTrue(produtos.importar_dados_planilha('virtual.csv')['sucesso'])
        for plat in motor.PLATAFORMAS:
            antes = self.produto(pid, plat)
            svc.salvar_produto(self.dados, self.usuario, plat, pid)
            depois = self.produto(pid, plat)
            for campo in ('frete','lucro','margem_lucro','taxa_percentual'):
                self.assertEqual(antes[campo],depois[campo], (plat,campo))

    def test_recalcular_tiktok_por_preco(self):
        dados = {**self.dados, 'preco_real':40, 'trib':10, 'quantidade':1}
        pid = svc.salvar_produto(dados, self.usuario, 'TikTok')[0]
        self.assertTrue(produtos.recalcular_plataforma('TikTok')[0])
        self.assertEqual(self.produto(pid,'TikTok')['lucro'],10.4)

    def test_falha_regra_desfaz_regra_e_resultados(self):
        pid = self.criar()
        antes = self.produto(pid)
        self.conn.fail = 'INSERT INTO precificacao_resultados'
        ok, _ = produtos.atualizar_taxa_comissao(6, 25)
        self.assertFalse(ok)
        self.conn.fail = None
        self.assertEqual(self.produto(pid),antes)
        self.assertEqual(self.conn.raw.execute('SELECT taxa_percentual FROM tabela_taxas_comissoes WHERE id=6').fetchone()[0],20)

    def test_falha_historico_desfaz_produto(self):
        self.conn.fail = 'INSERT INTO historico_alteracoes'
        self.assertFalse(produtos.criar_produto(self.dados,self.usuario,'Kwai')[0])
        self.assertEqual(self.conn.raw.execute('SELECT COUNT(*) FROM produtos').fetchone()[0],0)

    def test_sku_duplicado_csv_nao_escolhe(self):
        pid=self.criar()
        self.conn.raw.execute("INSERT INTO produtos (sku,descricao) VALUES ('KIT-2','Duplicado')")
        self.conn.commit()
        with patch('builtins.open', mock_open(read_data=b'SKU;Trib\nKIT-2;99\n')):
            self.assertFalse(produtos.importar_dados_planilha('virtual.csv')['sucesso'])
        self.assertEqual(self.produto(pid)['trib'],20)
        self.assertFalse(produtos.excluir_produto_completo('KIT-2','Teste')[0])
        self.assertIsNone(produtos.comparar_plataformas('KIT-2'))

    def test_amazon_regiao_persiste_e_frete_altera(self):
        dados = {**self.dados, 'preco_real':200,'regiao':'sp_capital'}
        pid=svc.salvar_produto(dados,self.usuario,'Amazon')[0]
        self.assertEqual(self.produto(pid,'Amazon')['regiao'],'sp_capital')
        self.assertEqual(self.produto(pid,'Amazon')['frete'],21.45)
        self.assertTrue(fretes.atualizar_frete_amazon_brl200({'id':3,'sp_capital':30})[0])
        self.assertEqual(self.produto(pid,'Amazon')['frete'],30)

    def test_amazon_cursor_externo(self):
        cur=self.conn.cursor()
        self.assertEqual(produtos.calcular_frete_amazon('.8',90,cursor_ext=cur),13.45)

    def test_condicao_ml_preservada_ao_recalcular(self):
        pid=svc.salvar_produto({**self.dados,'condicao':'Clássico'}, self.usuario,'Mercado Livre')[0]
        self.assertTrue(produtos.recalcular_plataforma('Mercado Livre')[0])
        self.assertEqual(self.produto(pid,'Mercado Livre')['taxa_percentual'],12)

    def test_comparador_excel_e_lista_mesmos_valores(self):
        pid=self.criar()
        comparacao=produtos.comparar_plataformas('KIT-2')
        kwai=next(r for r in comparacao if r['plataforma']=='Kwai')
        self.assertEqual(kwai['lucro'],self.produto(pid)['lucro'])
        from openpyxl import Workbook, load_workbook
        stream=io.BytesIO()
        salvar=Workbook.save
        with patch.object(Workbook,'save',lambda wb,path:salvar(wb,stream)):
            ok,msg=produtos.gerar_relatorio_excel('Kwai',['sku','lucro'],'virtual.xlsx')
        self.assertTrue(ok,msg)
        stream.seek(0)
        linhas=list(load_workbook(stream).active.values)
        self.assertEqual(linhas[0],('SKU','Lucro (R$)'))
        self.assertEqual(linhas[1],('KIT-2',20))

    def test_inicializacao_nunca_recalcula_nem_altera_resultados(self):
        pid=self.criar()
        self.conn.raw.execute('UPDATE precificacao_controle SET versao=0')
        self.conn.raw.execute('UPDATE produtos_kwai SET lucro=123 WHERE produto_id=?',(pid,))
        self.conn.commit()
        with patch.object(svc,'recalcular_cursor',side_effect=AssertionError('Abrir não recalcula')):
            svc.inicializar()
            svc.inicializar()
        self.assertEqual(self.produto(pid)['lucro'],123)

    def test_kpi_inclui_prejuizo(self):
        pid=self.criar('Mercado Livre')
        svc.salvar_produto({'trib':100},self.usuario,'Mercado Livre',pid)
        self.assertLess(produtos.buscar_kpis_geral()['margem_media_geral'],0)

    def test_kpi_ticket_inclui_precos_sem_peso_ou_margem(self):
        pid=self.criar('Mercado Livre')
        svc.salvar_produto({**self.dados,'sku':'SEM-PESO','marca':'Sem peso','peso':None,'preco_real':300},self.usuario,'Mercado Livre')
        k=produtos.buscar_kpis_geral()
        self.assertEqual(k['ticket_medio_geral'],200)
        self.assertEqual(k['margem_media_geral'],10.85)
        marca=next(m for m in k['por_marca'] if m['marca']=='Sem peso')
        self.assertEqual(marca['ticket_medio'],300)
        self.assertIsNone(marca['margem_media'])

    def test_kpi_margem_usa_campo_salvo_sem_depender_do_frete(self):
        pid=self.criar('Mercado Livre')
        self.conn.raw.execute('UPDATE produtos_ml SET frete=NULL, margem_lucro=-5 WHERE produto_id=?',(pid,))
        self.conn.commit()
        self.assertEqual(produtos.buscar_kpis_geral()['margem_media_geral'],-5)

    def test_filtro_condicao_ml_altera_visualizacao_sem_escrever(self):
        pid=self.criar('Mercado Livre')
        antes=self.produto(pid,'Mercado Livre')
        self.conn.queries.clear()
        for condicao, lucro in [('Clássico',15.85),('Premium',10.85),('Clássico',15.85)]:
            p=produtos.listar_produtos_ml_condicao('KIT-2',condicao)[0]
            self.assertEqual(p['lucro'],D(str(lucro)))
            self.assertEqual(p['frete'],16.15)
        self.assertEqual(self.produto(pid,'Mercado Livre'),antes)
        self.assertTrue(all(q.lstrip().startswith('SELECT') for q in self.conn.queries))

    def test_filtro_condicao_ml_considera_tarifa_fixa_e_arredondamento(self):
        pid=self.criar('Mercado Livre')
        svc.atualizar_regras('tabela_taxas_comissoes',[{'id':2,'taxa_percentual':17.125,'taxa_fixa_reais':3},
                                                     {'id':3,'taxa_percentual':12.125,'taxa_fixa_reais':1}])
        simulado=produtos.listar_produtos_ml_condicao('KIT-2','Clássico')[0]
        svc.salvar_produto({'condicao':'Clássico'},self.usuario,'Mercado Livre',pid)
        salvo=self.produto(pid,'Mercado Livre')
        self.assertEqual(simulado['lucro'],D(str(salvo['lucro'])))
        self.assertEqual(simulado['margem_lucro'],D(str(salvo['margem_lucro'])))

    def test_filtro_condicao_ml_nao_inventa_lucro_ausente(self):
        svc.salvar_produto({**self.dados,'peso':None},self.usuario,'Mercado Livre')
        self.assertIsNone(produtos.listar_produtos_ml_condicao('KIT-2','Clássico')[0]['lucro'])

    def test_toggle_original_condicao_fica_na_listagem_e_atualiza_todas_as_linhas(self):
        ft=self._flet()
        import mercado_livre as ml
        import ui_precificacao as ui
        pid=self.criar('Mercado Livre')
        svc.salvar_produto({**self.dados,'sku':'KIT-SEGUNDO','preco_real':120},self.usuario,'Mercado Livre')
        page=types.SimpleNamespace(update=lambda:None)
        area=ft.Container()
        def controls(c):
            yield c
            for child in getattr(c,'controls',[]) or []:
                yield from controls(child)
            child=getattr(c,'content',None)
            if isinstance(child,ft.Control):
                yield from controls(child)
        with patch.dict(ml.condicao_visualizacao,{'valor':None}), patch('main.carregar_colunas_salvas', return_value={}):
            ml.tela_lista(page,self.usuario,area)
            toggle=next(c for c in controls(area) if isinstance(c,ft.SegmentedButton))
            self.assertEqual(toggle.selected,['Premium'])
            self.assertEqual([s.value for s in toggle.segments],['Premium','Clássico'])
            # Verifica o evento declarado que o Flet efetivamente despacha.
            from flet.controls.control_event import get_event_field_type
            self.assertIsNotNone(get_event_field_type(toggle,'on_change'))
            marca=next(c for c in controls(area) if isinstance(c,ft.Dropdown) and c.label=='Marca')
            self.assertIsNotNone(get_event_field_type(marca,'on_select'))
            self.conn.queries.clear()
            buscar=next(c for c in controls(area) if isinstance(c,ft.Button) and c.content=='Buscar')
            buscar.on_click(None)
            tabela=next(c for c in controls(area) if isinstance(c,ft.DataTable))
            from main import COLUNAS_PRODUTOS, carregar_colunas_salvas
            visiveis=carregar_colunas_salvas()
            chaves=[key for key,_,_ in COLUNAS_PRODUTOS if visiveis.get(key,True)]
            lucro_idx=chaves.index('lucro')
            margem_idx=chaves.index('margem_lucro')
            premium=[(row.cells[lucro_idx].content.value,row.cells[margem_idx].content.value) for row in tabela.rows]
            self.assertEqual(len(premium),2)
            for cond in ['Clássico','Premium','Clássico']:
                toggle.selected=[cond]
                toggle.on_change(None)
                valores=[(row.cells[lucro_idx].content.value,row.cells[margem_idx].content.value) for row in tabela.rows]
                if cond=='Premium':
                    self.assertEqual(valores,premium)
                else:
                    self.assertTrue(all(p!=v for p,v in zip(premium,valores)))
                    self.assertTrue(any(cell.content.value=='R$ 15.85' for cell in tabela.rows[0].cells))
            self.assertTrue(all(q.lstrip().startswith('SELECT') for q in self.conn.queries))
            ui.formulario(page,self.usuario,area,'Mercado Livre',lambda:None,pid,condicao_ml='Clássico')
            self.assertFalse(any(isinstance(c,ft.Dropdown) for c in controls(area)))
            lucro=next(c for c in controls(area) if isinstance(c,ft.TextField) and c.label=='Lucro (R$)')
            self.assertEqual(D(lucro.value),D('15.85'))
            botao=next(c for c in controls(area) if isinstance(c,ft.Button) and c.content=='Salvar')
            botao.on_click(None)
            self.assertEqual(self.produto(pid,'Mercado Livre')['condicao'],'Clássico')

    def test_dashboard_sem_margem_nao_falha(self):
        ft=self._flet()
        import main
        svc.salvar_produto({**self.dados,'peso':None},self.usuario,'Mercado Livre')
        area=ft.Container()
        main.tela_geral(types.SimpleNamespace(update=lambda:None),self.usuario,area)
        self.assertIsNotNone(area.content)

    def test_precos_invalidos_rollback_e_csv_vazio(self):
        pid = self.criar()
        self.assertFalse(produtos.atualizar_produto(pid, {'preco_real': '1.999'}, self.usuario, 'Kwai')[0])
        self.assertEqual(self.produto(pid)['preco_real'],100)
        self.assertFalse(produtos.atualizar_produto(pid, {'quantidade': '0'}, self.usuario, 'Kwai')[0])
        with patch('builtins.open', mock_open(read_data=b'')):
            self.assertFalse(produtos.importar_dados_planilha('virtual.csv')['sucesso'])

    def _flet(self):
        # Usa os controles reais sem abrir janela ou iniciar a sessão Flet.
        local = ROOT / '.venv' / 'Lib' / 'site-packages'
        if local.is_dir() and str(local) not in sys.path:
            sys.path.append(str(local))
        try:
            import flet as ft
        except ImportError:
            self.skipTest('Flet indisponível neste ambiente')
        return ft

    def test_formularios_flet_salvam_seis_plataformas(self):
        ft=self._flet()
        import ui_precificacao as ui
        page=types.SimpleNamespace(update=lambda:None)
        for i, plat in enumerate(motor.PLATAFORMAS):
            with self.subTest(plataforma=plat):
                area=ft.Container()
                ui.formulario(page,self.usuario,area,plat,lambda:None)
                controles=list(controles_descendentes(area))
                valores={'SKU *':f'UI-{i}', 'Descrição *':'Kit UI', 'Custo unitário (Trib)':'20',
                         'Unidades no kit':'2', 'Embalagem do kit (R$)':'2',
                         'Peso total do kit (kg)':'0.8', 'Preço final de venda do kit (R$)':'100'}
                for c in controles:
                    if isinstance(c,ft.TextField) and c.label in valores:
                        c.value=valores[c.label]
                peso_campo=next(c for c in controles if isinstance(c,ft.TextField) and c.label=='Peso total do kit (kg)')
                peso_campo.on_blur(None)
                self.assertEqual(self.conn.raw.execute('SELECT COUNT(*) FROM produtos WHERE sku=?',(f'UI-{i}',)).fetchone()[0],0)
                botao=next(c for c in controles if isinstance(c,ft.Button) and c.content=='Salvar')
                botao.on_click(None)
                p=produtos.listar_produtos(f'UI-{i}',plat)[0]
                self.assertEqual((p['preco_real'],p['quantidade'],p['status_calculo']),(100,2,'calculado'))
                botao.on_click(None)
                self.assertEqual(self.conn.raw.execute('SELECT COUNT(*) FROM produtos WHERE sku=?',(f'UI-{i}',)).fetchone()[0],1)

    def test_listas_flet_buscam_sem_recalcular(self):
        ft=self._flet()
        import importlib
        # Importar main define callbacks; o entry point não roda.
        import main
        pid=self.criar()
        page=types.SimpleNamespace(update=lambda:None)
        def controls(c):
            yield c
            for child in getattr(c,'controls',[]) or []:
                yield from controls(child)
            child=getattr(c,'content',None)
            if isinstance(child,ft.Control):
                yield from controls(child)
        for name in ['mercado_livre','amazon','shopee','tiktok','magalu','kwai']:
            area=ft.Container()
            with patch.object(svc,'recalcular_cursor',side_effect=AssertionError('Buscar não escreve')):
                importlib.import_module(name).tela_lista(page,self.usuario,area)
                botao=next(c for c in controls(area) if isinstance(c,ft.Button) and c.content=='Buscar')
                self.conn.queries.clear()
                botao.on_click(None)
                tabela=next(c for c in controls(area) if isinstance(c,ft.DataTable))
                self.assertEqual(len(tabela.rows),1,name)
                self.assertTrue(all(q.lstrip().startswith('SELECT') for q in self.conn.queries))

    def test_salvar_todas_taxas_ui_e_atomico(self):
        ft=self._flet()
        import main
        pid=self.criar()
        page=types.SimpleNamespace(update=lambda:None)
        area=ft.Container()
        main.tela_config_taxas(page,self.usuario,area)
        def controls(c):
            yield c
            for child in getattr(c,'controls',[]) or []:
                yield from controls(child)
            child=getattr(c,'content',None)
            if isinstance(child,ft.Control):
                yield from controls(child)
        campos=[c for c in controls(area) if isinstance(c,ft.TextField)]
        campos[0].value='20'
        campos[-2].value='inválido'
        botao=next(c for c in controls(area) if isinstance(c,ft.Button) and c.content=='Salvar Todas as Taxas')
        botao.on_click(None)
        self.assertEqual(produtos.buscar_taxa_imposto(),14)
        self.assertEqual(self.produto(pid)['lucro'],20)

    def test_falha_de_leitura_apos_commit_nao_diz_que_nao_salvou(self):
        ft=self._flet()
        import ui_precificacao as ui
        area=ft.Container()
        ui.formulario(types.SimpleNamespace(update=lambda:None),self.usuario,area,'Kwai',lambda:None)
        controles=list(controles_descendentes(area))
        valores={'SKU *':'POS-COMMIT','Descrição *':'Teste','Custo unitário (Trib)':'20',
                 'Unidades no kit':'2','Embalagem do kit (R$)':'2','Preço final de venda do kit (R$)':'100'}
        for c in controles:
            if isinstance(c,ft.TextField) and c.label in valores:
                c.value=valores[c.label]
        botao=next(c for c in controles if isinstance(c,ft.Button) and c.content=='Salvar')
        with patch.object(ui,'buscar_produto',side_effect=RuntimeError('leitura indisponível')):
            botao.on_click(None)
        self.assertEqual(self.conn.raw.execute("SELECT COUNT(*) FROM produtos WHERE sku='POS-COMMIT'").fetchone()[0],1)
        self.assertTrue(any('Os dados foram salvos' in str(c.value) for c in controles if isinstance(c,ft.Text)))

if __name__ == '__main__':
    unittest.main()
