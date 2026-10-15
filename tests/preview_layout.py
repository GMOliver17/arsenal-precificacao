"""Prévia manual do layout com SQLite em memória; nunca acessa o MySQL real."""
import sys
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.venv'/'Lib'/'site-packages'))
if '--web' in sys.argv:
    if not (ROOT/'.tmp'/'layout-deps'/'flet_web').is_dir():
        raise SystemExit('As dependencias temporarias da previa web foram removidas. Execute sem --web para usar a previa desktop.')
    sys.path.insert(0,str(ROOT/'.tmp'/'layout-deps'))
    os.environ['FLET_FORCE_WEB_SERVER']='true'
from test_precificacao import PersistenciaTests
caso=PersistenciaTests('test_kpi_inclui_prejuizo')
caso.setUp()
import servico_precificacao as svc
import empresas
import main
import fretes
fretes.get_connection=lambda:caso.conn
import flet as ft
from precificacao import PLATAFORMAS
for i in range(8):
    dados={**caso.dados,'sku':f'KIT-{i+1:03d}','descricao':f'Kit de ferramentas {i+1}',
           'marca':['ARSENAL','BESTFER','DCK'][i%3],'peso':str(.25+i*.1),'preco_real':100+i*10}
    pid=svc.salvar_produto(dados,None,'Mercado Livre')[0]
    for plat in PLATAFORMAS:
        if plat!='Mercado Livre':svc.salvar_produto({'preco_real':100+i*10},None,plat,pid)
main.listar_usuarios=lambda:[]
main.listar_historico=lambda:[]
main.carregar_colunas_salvas=lambda:{k:k in ['sku','descricao','peso','frete','preco_real','lucro','margem_lucro'] for k,_,_ in main.COLUNAS_PRODUTOS}

def preview(page):
    page.title='Arsenal — Validação de layout'
    page.window.width=1120
    page.window.height=800
    page.window.min_width=560
    page.window.min_height=480
    page.theme=ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.dark_theme=ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.theme_mode=ft.ThemeMode.LIGHT
    page.bgcolor=ft.Colors.SURFACE
    def tema(e):
        page.theme_mode=ft.ThemeMode.DARK if page.theme_mode==ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        page.update()
    def largura(valor):
        def alterar(e):
            page.window.width=valor
            if page.web:
                page.width=valor
                page.views[0].width=valor
                if page.on_resize: page.on_resize(None)
            page.update()
        return alterar
    page.appbar=ft.AppBar(title=ft.Text('Prévia com dados fictícios',size=14),actions=[
        ft.IconButton(ft.Icons.CONTRAST,on_click=tema,tooltip='Trocar tema'),
        ft.TextButton('600 px',on_click=largura(600)),ft.TextButton('1120 px',on_click=largura(1120))])
    main.abrir_app(page,{'id':1,'nome':'Validação','role':'admin'})

if __name__=='__main__':
    token=empresas._empresa_contexto.set(None)
    try:
        ft.run(preview, view=None, host="127.0.0.1", port=8765, no_cdn=True) if "--web" in sys.argv else ft.run(preview)
    finally:
        empresas._empresa_contexto.reset(token)
        caso.doCleanups()
