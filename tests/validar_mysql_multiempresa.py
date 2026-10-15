"""Validação MySQL em banco temporário criado e removido por este script."""
from pathlib import Path
import sys
import uuid
from contextlib import ExitStack
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.venv' / 'Lib' / 'site-packages'))
import mysql.connector
from db import carregar_config_bd
import migracao_multiempresa as mig
import servico_precificacao as svc
import produtos
import empresas
import fretes


def validar():
    cfg = carregar_config_bd()
    cfg['port'] = int(cfg['port'])
    origem = cfg['database']
    temporario = 'arsenal_validacao_multiempresa_' + uuid.uuid4().hex[:12]
    assert temporario != origem and temporario.startswith('arsenal_validacao_multiempresa_')
    source = mysql.connector.connect(**cfg)
    admin = mysql.connector.connect(**{k:v for k,v in cfg.items() if k!='database'})
    criado = False
    conn = None
    try:
        a = admin.cursor(buffered=True)
        a.execute(f'CREATE DATABASE `{temporario}` CHARACTER SET utf8mb4')
        criado = True
        test_cfg = {**cfg, 'database':temporario}
        conn = mysql.connector.connect(**test_cfg)
        cur = conn.cursor(buffered=True)
        src = source.cursor(buffered=True)
        src.execute('SHOW TABLES')
        tabelas = [r[0] for r in src.fetchall()]
        antes = {}
        cur.execute('SET FOREIGN_KEY_CHECKS=0')
        for tabela in tabelas:
            src.execute(f'SHOW CREATE TABLE `{tabela}`')
            ddl = src.fetchone()[1].replace(f'`{origem}`.', f'`{temporario}`.')
            cur.execute(ddl)
            src.execute(f'SELECT * FROM `{tabela}`')
            colunas = [d[0] for d in src.description]
            linhas = src.fetchall()
            antes[tabela] = (colunas, linhas)
            if linhas:
                cols = ','.join(f'`{c}`' for c in colunas)
                comando = f'INSERT INTO `{tabela}` ({cols}) VALUES ({",".join(["%s"]*len(colunas))})'
                for linha in linhas:
                    cur.execute(comando, linha)
        cur.execute('SET FOREIGN_KEY_CHECKS=1')
        conn.commit()
        src.close()
        teste_pasta = ROOT / 'tests' / '.tmp_mysql'
        teste_pasta.mkdir(exist_ok=True)
        with patch.object(mig,'_pasta_base',return_value=str(teste_pasta)):
            backup = mig.migrar(conn)
            if backup is not None:
                assert backup.is_file()
            assert mig.migrar(conn) is None
        for tabela, (colunas, linhas) in antes.items():
            cols = ','.join(f'`{c}`' for c in colunas)
            cur.execute(f'SELECT {cols} FROM `{tabela}`')
            depois = cur.fetchall()
            assert sorted(linhas,key=repr)==sorted(depois,key=repr), f'Migração alterou dados existentes em {tabela}'
        print('MYSQL_MIGRACAO_OK: dados e datas de todas as tabelas preservados; segunda execução sem alterações')
        conn.close()
        conn = None
        def conectar(): return mysql.connector.connect(**test_cfg)
        with ExitStack() as stack:
            for modulo in (svc, produtos, empresas, fretes):
                stack.enter_context(patch.object(modulo,'get_connection',side_effect=conectar))
            stack.enter_context(empresas.usar_empresa(1))
            existentes = {e['cnpj'] for e in empresas.listar_empresas()}
            cnpj = '00000000000001'
            while cnpj in existentes:
                cnpj = str(int(cnpj)+1).zfill(14)
            b = empresas.salvar_empresa('Empresa temporária de validação', cnpj)
            sku = 'MULTI-TESTE-' + uuid.uuid4().hex[:8]
            dados = {'sku':sku,'descricao':'Teste isolado','trib':20,'quantidade':2,
                     'embalagem':2,'peso':'.8','preco_real':100}
            pid_a = svc.salvar_produto(dados,None,'Mercado Livre')[0]
            antes_a = produtos.buscar_produto(pid_a)
            with empresas.usar_empresa(b):
                assert produtos.listar_produtos()==[]
                pid_b = svc.salvar_produto({**dados,'preco_real':200},None,'Mercado Livre')[0]
                assert produtos.listar_produtos(sku)[0]['preco_real']==200
                assert produtos.buscar_produto(pid_a) is None
                assert not produtos.atualizar_produto(pid_a,{'trib':999},None)[0]
                taxas = produtos.listar_taxas_comissoes()
                imposto = next(r for r in taxas if r['canal']=='Imposto')
                assert produtos.atualizar_taxa_comissao(imposto['id'],20)[0]
                assert produtos.recalcular_plataforma('Mercado Livre')[0]
                assert produtos.excluir_produto_completo(sku,'Validação')[0]
                assert produtos.buscar_produto(pid_b) is None
            assert produtos.buscar_produto(pid_a)==antes_a
        print('MYSQL_ISOLAMENTO_OK: cadastro, mesmo SKU, leitura, edição, imposto, recálculo e exclusão')
    finally:
        if conn: conn.close()
        source.close()
        if criado:
            assert temporario.startswith('arsenal_validacao_multiempresa_') and temporario!=origem
            a = admin.cursor(buffered=True)
            a.execute(f'DROP DATABASE `{temporario}`')
            a.close()
            print('BANCO_TEMPORARIO_REMOVIDO; banco de origem não alterado')
        admin.close()


if __name__=='__main__': validar()
