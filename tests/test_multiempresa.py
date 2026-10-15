"""Testes de isolamento entre empresas; nenhum acesso ao MySQL real."""
import io
import sys
import types
import unittest
from unittest.mock import patch, mock_open, Mock
from pathlib import Path

import test_precificacao as base
import empresas
import produtos
import servico_precificacao as svc
import fretes


class MultiempresaTests(unittest.TestCase):
    def setUp(self):
        self.base = base.PersistenciaTests('test_kpi_inclui_prejuizo')
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.conn = self.base.conn
        self.usuario = {**self.base.usuario, 'role':'admin'}
        self.dados = self.base.dados
        self.pid_a = self.base.criar('Mercado Livre')
        self.empresa_b = empresas.salvar_empresa('Empresa B', '11.222.333/0001-81')

    def criar_b(self, plataforma='Mercado Livre', **alteracoes):
        with empresas.usar_empresa(self.empresa_b):
            return svc.salvar_produto({**self.dados, **alteracoes}, self.usuario, plataforma)[0]

    def test_empresa_nova_sem_produtos_com_configuracoes_independentes(self):
        with empresas.usar_empresa(self.empresa_b):
            self.assertEqual(produtos.listar_produtos(), [])
            self.assertEqual(produtos.listar_marcas(), [])
            self.assertEqual(produtos.buscar_kpis_geral()['total_produtos'], 0)
            regras = svc.carregar_regras(self.conn.cursor(dictionary=True))
            self.assertTrue(all(regras.values()))
            self.assertTrue(all(r['empresa_id'] == self.empresa_b for rows in regras.values() for r in rows))

    def test_mesmo_sku_com_precos_distintos_em_empresas_distintas(self):
        pid_b = self.criar_b(preco_real=200, marca='Marca B')
        self.assertNotEqual(pid_b, self.pid_a)
        self.assertEqual(produtos.listar_produtos('KIT-2')[0]['preco_real'], 100)
        with empresas.usar_empresa(self.empresa_b):
            self.assertEqual(produtos.listar_produtos('KIT-2')[0]['preco_real'], 200)
            self.assertEqual(produtos.listar_marcas(), ['Marca B'])
            self.assertEqual(produtos.buscar_kpis_geral()['ticket_medio_geral'], 200)
            self.assertFalse(produtos.criar_produto(self.dados, self.usuario, 'Kwai')[0])

    def test_id_de_outra_empresa_nao_pode_ser_lido_ou_editado(self):
        antes = produtos.buscar_produto(self.pid_a)
        with empresas.usar_empresa(self.empresa_b):
            self.assertIsNone(produtos.buscar_produto(self.pid_a))
            self.assertFalse(produtos.atualizar_produto(self.pid_a, {'trib':999}, self.usuario)[0])
            self.assertFalse(produtos.atualizar_produto(self.pid_a, {'preco_real':999}, self.usuario, 'Amazon')[0])
        self.assertEqual(produtos.buscar_produto(self.pid_a), antes)

    def test_exclusao_do_mesmo_sku_remove_so_empresa_selecionada(self):
        pid_b = self.criar_b()
        with empresas.usar_empresa(self.empresa_b):
            self.assertTrue(produtos.excluir_produto_completo('KIT-2', 'Teste')[0])
            self.assertIsNone(produtos.buscar_produto(pid_b))
        self.assertIsNotNone(produtos.buscar_produto(self.pid_a))
        with empresas.usar_empresa(self.empresa_b):
            self.assertFalse(produtos.excluir_produto_completo('KIT-2', 'Teste')[0])

    def test_csv_so_atualiza_empresa_selecionada(self):
        pid_b = self.criar_b()
        csv = b'SKU;Trib;Preco_ML\nKIT-2;25;150\n'
        with empresas.usar_empresa(self.empresa_b), patch('builtins.open', mock_open(read_data=csv)):
            self.assertTrue(produtos.importar_dados_planilha('teste.csv')['sucesso'])
            self.assertEqual(produtos.buscar_produto(pid_b)['trib'],25)
        self.assertEqual(produtos.buscar_produto(self.pid_a)['trib'],20)
        self.assertEqual(produtos.buscar_produto(self.pid_a)['preco_real'],100)

    def test_csv_nao_encontra_sku_exclusivo_de_outra_empresa(self):
        with empresas.usar_empresa(self.empresa_b), patch('builtins.open', mock_open(read_data=b'SKU;Trib\nKIT-2;999\n')):
            self.assertFalse(produtos.importar_dados_planilha('teste.csv')['sucesso'])
        self.assertEqual(produtos.buscar_produto(self.pid_a)['trib'],20)

    def test_recalculo_e_alteracao_de_imposto_nao_afetam_outra_empresa(self):
        pid_b = self.criar_b()
        antes = produtos.buscar_produto(self.pid_a)
        with empresas.usar_empresa(self.empresa_b):
            imposto = next(r for r in produtos.listar_taxas_comissoes() if r['canal']=='Imposto')
            self.assertTrue(produtos.atualizar_taxa_comissao(imposto['id'],20)[0])
            self.assertEqual(produtos.buscar_taxa_imposto(),20)
            self.assertTrue(produtos.recalcular_plataforma('Mercado Livre')[0])
            self.assertEqual(produtos.buscar_produto(pid_b)['lucro'],4.85)
            self.assertFalse(produtos.atualizar_taxa_comissao(1,99)[0])
        self.assertEqual(produtos.buscar_taxa_imposto(),14)
        self.assertEqual(produtos.buscar_produto(self.pid_a),antes)

    def test_frete_e_cursor_externo_selecionam_empresa(self):
        with empresas.usar_empresa(self.empresa_b):
            cur = self.conn.cursor(dictionary=True)
            cur.execute('SELECT id FROM tabela_frete_amazon WHERE empresa_id=%s AND peso=%s',(self.empresa_b,'500 g a 1 kg'))
            rid = cur.fetchone()['id']
            self.assertTrue(fretes.atualizar_frete_amazon({'id':rid,'faixa_79_99_99':30})[0])
            self.assertEqual(produtos.calcular_frete_amazon('.8',90,cursor_ext=self.conn.cursor()),30)
            self.assertFalse(fretes.atualizar_frete_amazon({'id':3,'faixa_79_99_99':99})[0])
        self.assertEqual(produtos.calcular_frete_amazon('.8',90,cursor_ext=self.conn.cursor()),13.45)

    def test_lote_com_id_de_outra_empresa_desfaz_tudo(self):
        with empresas.usar_empresa(self.empresa_b):
            r = next(r for r in produtos.listar_taxas_comissoes() if r['canal']=='Imposto')
            self.assertFalse(produtos.atualizar_taxas_lote([{'id':r['id'],'taxa_percentual':20},
                                                         {'id':1,'taxa_percentual':99}])[0])
            self.assertEqual(produtos.buscar_taxa_imposto(),14)

    def test_comparador_excel_kpis_e_historico_isolados(self):
        self.criar_b(preco_real=200, marca='Marca B')
        with empresas.usar_empresa(self.empresa_b):
            comparacao = produtos.comparar_plataformas('KIT-2')
            self.assertEqual(next(r for r in comparacao if r['plataforma']=='Mercado Livre')['preco_real'],200)
            self.assertEqual(produtos.buscar_kpis_geral()['por_marca'][0]['marca'],'Marca B')
            self.assertTrue(all(r['registro_id']!=self.pid_a for r in produtos.listar_historico()))
            from openpyxl import Workbook,load_workbook
            stream=io.BytesIO(); salvar=Workbook.save
            with patch.object(Workbook,'save',lambda wb,path:salvar(wb,stream)):
                self.assertTrue(produtos.gerar_relatorio_excel('Mercado Livre',['sku','preco_real'],'teste.xlsx')[0])
            stream.seek(0)
            self.assertEqual(list(load_workbook(stream).active.values)[1],('KIT-2',200))
        self.assertTrue(all(r['registro_id']==self.pid_a for r in produtos.listar_historico()))

    def test_cnpj_normalizado_unico_e_nome_editavel(self):
        cadastradas=empresas.listar_empresas()
        self.assertEqual(next(e for e in cadastradas if e['id']==self.empresa_b)['cnpj'],'11222333000181')
        self.assertEqual(empresas.formatar_cnpj('00000000000000'),'00.000.000/0000-00')
        with self.assertRaises(ValueError): empresas.salvar_empresa('Duplicada','11.222.333/0001-81')
        with self.assertRaises(ValueError): empresas.salvar_empresa('Invalida','123')
        empresas.salvar_empresa('Empresa B editada','11222333000181',self.empresa_b)
        self.assertEqual(next(e for e in empresas.listar_empresas() if e['id']==self.empresa_b)['nome'],'Empresa B editada')

    def test_sessoes_e_ausencia_de_empresa(self):
        p1=types.SimpleNamespace(_empresa_atual={'id':1})
        p2=types.SimpleNamespace(_empresa_atual={'id':self.empresa_b})
        token=empresas._empresa_contexto.set(None)
        try:
            with patch.object(empresas,'pagina_atual',return_value=p1): self.assertEqual(empresas.empresa_id(),1)
            with patch.object(empresas,'pagina_atual',return_value=p2): self.assertEqual(empresas.empresa_id(),self.empresa_b)
            with patch.object(empresas,'pagina_atual',return_value=None):
                with self.assertRaises(RuntimeError): produtos.listar_produtos()
        finally: empresas._empresa_contexto.reset(token)

    def test_formulario_antigo_nao_salva_apos_troca_de_empresa(self):
        ft=self.base._flet();import ui_precificacao as ui
        area=ft.Container();page=types.SimpleNamespace(update=lambda:None)
        ui.formulario(page,self.usuario,area,'Mercado Livre',lambda:None)
        controles=list(base.controles_descendentes(area))
        for c in controles:
            if isinstance(c,ft.TextField) and c.label in {'SKU *','Descrição *'}:c.value='Novo'
        salvar=next(c for c in controles if isinstance(c,ft.Button) and c.content=='Salvar')
        with empresas.usar_empresa(self.empresa_b): salvar.on_click(None)
        self.assertEqual(self.conn.raw.execute('SELECT COUNT(*) FROM produtos WHERE empresa_id=?',(self.empresa_b,)).fetchone()[0],0)

    def test_seletor_flet_troca_empresa_e_carrega_dados_dela(self):
        self.base._flet();import main
        page=types.SimpleNamespace(controls=[],overlay=[],width=1100,update=lambda:None,show_dialog=Mock())
        page.add=lambda *controls:page.controls.extend(controls)
        page.clean=lambda:page.controls.clear()
        token=empresas._empresa_contexto.set(None)
        try:
            with patch.object(empresas,'pagina_atual',return_value=page):
                main.abrir_app(page,self.usuario)
                self.assertEqual(empresas.empresa_id(),1)
                seletor=page.appbar.actions[0].content
                seletor.value=str(self.empresa_b)
                seletor.on_select(types.SimpleNamespace(control=seletor))
                self.assertEqual(empresas.empresa_id(),self.empresa_b)
                self.assertEqual(produtos.buscar_kpis_geral()['total_produtos'],0)
                self.assertFalse(page.show_dialog.called)
        finally: empresas._empresa_contexto.reset(token)

    def test_cadastro_de_empresa_na_configuracao_so_pede_nome_e_cnpj(self):
        ft=self.base._flet();import ui_empresas
        page=types.SimpleNamespace(update=lambda:None,overlay=[])
        empresas.selecionar_empresa(page,1)
        area=ft.Container();atualizar=Mock()
        ui_empresas.tela_empresas(page,area,atualizar,Mock())
        controles=list(base.controles_descendentes(area))
        campos=[c for c in controles if isinstance(c,ft.TextField)]
        self.assertEqual({c.label for c in campos},{'Nome da empresa','CNPJ'})
        for c in campos:c.value='Empresa C' if c.label=='Nome da empresa' else '22.333.444/0001-55'
        campo_cnpj=next(c for c in campos if c.label=='CNPJ')
        campo_cnpj.value='22333444000155'
        campo_cnpj.on_blur(None)
        self.assertEqual(campo_cnpj.value,'22.333.444/0001-55')
        botao=next(c for c in controles if isinstance(c,ft.Button) and c.content=='Cadastrar empresa')
        botao.on_click(None)
        self.assertTrue(atualizar.called)
        self.assertTrue(any(e['cnpj']=='22333444000155' for e in empresas.listar_empresas()))
        self.assertEqual(page._empresa_atual['id'],1)


if __name__=='__main__': unittest.main()
