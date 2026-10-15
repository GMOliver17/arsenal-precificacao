"""Layout compartilhado para formulários e tabelas, respeitando o tema ativo."""
import flet as ft


def menu_colunas(colunas, visiveis, salvar, atualizar, page):
    """Seleção de colunas em duas etapas: marcar opções e depois Aplicar."""
    pendentes = {k: bool(visiveis.get(k, padrao)) for k, _, padrao in colunas}
    itens = {}

    def atualizar_itens():
        ultima = sum(pendentes.values()) == 1
        for chave, item in itens.items():
            marcado = pendentes[chave]
            item.leading.icon = ft.Icons.CHECK_BOX if marcado else ft.Icons.CHECK_BOX_OUTLINE_BLANK
            item.disabled = ultima and marcado

    def abrir(e):
        pendentes.update({k: bool(visiveis.get(k, padrao)) for k, _, padrao in colunas})
        atualizar_itens()
        page.update()

    def alternar(chave):
        def handler(e):
            if itens[chave].disabled:
                return
            pendentes[chave] = not pendentes[chave]
            atualizar_itens()
            page.update()
        return handler

    def aplicar(e):
        visiveis.update(pendentes)
        salvar(visiveis)
        atualizar()

    for chave, rotulo, _ in colunas:
        itens[chave] = ft.MenuItemButton(
            content=rotulo, close_on_click=False,
            leading=ft.Icon(ft.Icons.CHECK_BOX_OUTLINE_BLANK, size=20, color=ft.Colors.PRIMARY),
            on_click=alternar(chave),
            style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE),
        )
    atualizar_itens()
    submenu = ft.SubmenuButton(
        content="Colunas",
        leading=ft.Icon(ft.Icons.VIEW_COLUMN_OUTLINED, size=18, color=ft.Colors.PRIMARY),
        trailing=ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18),
        style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE),
        menu_style=ft.MenuStyle(
            alignment=ft.Alignment.BOTTOM_LEFT, bgcolor=ft.Colors.SURFACE_CONTAINER,
            max_size=ft.Size(280, 480),
        ),
        on_open=abrir,
        controls=[*itens.values(), ft.Divider(), ft.MenuItemButton(
            content="Aplicar", close_on_click=True, on_click=aplicar,
            leading=ft.Icon(ft.Icons.CHECK, size=18),
            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
        )],
    )
    return ft.MenuBar(
        controls=[submenu],
        style=ft.MenuStyle(bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH, elevation=0,
                           shape=ft.RoundedRectangleBorder(radius=20)),
    )


def campo_tema(campo):
    campo.color = ft.Colors.ON_SURFACE
    campo.border_color = ft.Colors.OUTLINE
    campo.focused_border_color = ft.Colors.PRIMARY
    campo.filled = True
    campo.fill_color = ft.Colors.SURFACE_CONTAINER_LOW
    if isinstance(campo, ft.TextField):
        campo.label_style = ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT)
    return campo


def grade_campos(campos, colunas=None):
    for campo in campos:
        campo_tema(campo)
        campo.width = None
        campo.col = colunas or {"xs": 12, "md": 6}
    return ft.ResponsiveRow(list(campos), spacing=16, run_spacing=16)


def tabela_rolavel(tabela):
    return ft.Row(
        [ft.Column([tabela], scroll=ft.ScrollMode.AUTO)],
        scroll=ft.ScrollMode.ALWAYS, expand=True,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )


def cartao_tabela(linhas):
    return ft.Container(
        content=ft.Row(
            [ft.Column(linhas, spacing=0, scroll=ft.ScrollMode.AUTO)],
            scroll=ft.ScrollMode.ALWAYS, vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        height=min(420, 88 + max(0, len(linhas)-2) * 52),
        padding=16, border_radius=12,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
    )
