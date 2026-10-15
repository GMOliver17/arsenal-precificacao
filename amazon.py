import flet as ft
from ui_layout import tabela_rolavel, campo_tema, menu_colunas
from produtos import listar_produtos, listar_marcas

# ════════════════════════════════════════════════════
#  AMAZON — LISTA DE PRODUTOS
# ════════════════════════════════════════════════════
def tela_lista(page, usuario, area_conteudo):
    from main import COLUNAS_PRODUTOS, carregar_colunas_salvas, salvar_colunas, fmt_val, fmt_celula, estado_filtro_marca
    from produtos import listar_marcas

    filtro_marca_global = estado_filtro_marca(page)
    visiveis = carregar_colunas_salvas()
    txt_busca = campo_tema(ft.TextField(
        label="Buscar por SKU ou descrição", width=250, dense=True
    ))

    # Dropdown de marca com estado global
    dropdown_marca = campo_tema(ft.Dropdown(
        label="Marca", width=150, dense=True,
        options=[ft.dropdown.Option("Todas")],
        value=filtro_marca_global["valor"],
    ))
    marcas = listar_marcas()
    for m in marcas:
        dropdown_marca.options.append(ft.dropdown.Option(m))

    status_busca = ft.Text("")
    tabela = ft.DataTable(
        columns=[], rows=[],
        horizontal_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY_500)),
    )

    # Colunas iniciais
    for col_key, col_label, _ in COLUNAS_PRODUTOS:
        if visiveis.get(col_key, True):
            tabela.columns.append(ft.DataColumn(ft.Text(col_label, size=14)))

    def reconstruir_tabela():
        busca = (txt_busca.value or "").strip()
        marca_sel = dropdown_marca.value or "Todas"
        filtro_marca_global["valor"] = marca_sel
        try:
            dados = listar_produtos(busca, plataforma='Amazon')
            if marca_sel != "Todas":
                dados = [p for p in dados if p.get("marca") == marca_sel]
            tabela.columns = [ft.DataColumn(ft.Text(label)) for key, label, _ in COLUNAS_PRODUTOS if visiveis.get(key, True)]
            tabela.rows = [ft.DataRow(
                cells=[ft.DataCell(fmt_celula(key, p.get(key), p)) for key, _, _ in COLUNAS_PRODUTOS if visiveis.get(key, True)],
                on_select_change=lambda e, pid=p["id"]: tela_editar(page, usuario, area_conteudo, pid)) for p in dados]
            status_busca.value = f"{len(dados)} produto(s)."
        except Exception as exc:
            tabela.rows = []
            status_busca.value = f"Não foi possível consultar: {exc}"
        page.update()

    dropdown_marca.on_select = lambda e: reconstruir_tabela()

    def buscar(e=None):
        reconstruir_tabela()

    txt_busca.on_submit = buscar

    seletor_colunas = menu_colunas(COLUNAS_PRODUTOS, visiveis, salvar_colunas, reconstruir_tabela, page)

    area_conteudo.content = ft.Column([
        ft.Row([
            ft.Text("Produtos — Amazon", size=22, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
        ]),
        ft.Divider(),
        ft.Row([
            txt_busca,
            dropdown_marca,
            ft.Button("Buscar", icon=ft.Icons.SEARCH_OUTLINED, on_click=buscar),
            seletor_colunas,
        ], spacing=12, run_spacing=12, wrap=True),
        ft.Divider(height=1),
        ft.Text("Digite um SKU ou descrição e clique em Buscar (ou pressione Enter) para carregar os produtos.",
                size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        status_busca,
        tabela_rolavel(tabela),
    ], spacing=12, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    page.update()

# ════════════════════════════════════════════════════
#  AMAZON — NOVO PRODUTO
# ════════════════════════════════════════════════════
def tela_novo(page, usuario, area_conteudo):
    from ui_precificacao import formulario
    formulario(page, usuario, area_conteudo, 'Amazon',
               lambda: tela_lista(page, usuario, area_conteudo))

# ════════════════════════════════════════════════════
#  AMAZON — EDITAR PRODUTO
# ════════════════════════════════════════════════════
def tela_editar(page, usuario, area_conteudo, produto_id):
    from ui_precificacao import formulario
    formulario(page, usuario, area_conteudo, 'Amazon',
               lambda: tela_lista(page, usuario, area_conteudo), produto_id=produto_id)
