"""Seleção da empresa ativa e cadastro simples em Configurações."""
import flet as ft
from empresas import listar_empresas, selecionar_empresa, salvar_empresa, formatar_cnpj, normalizar_cnpj
from ui_layout import campo_tema, grade_campos


def barra_empresa(page, ao_trocar):
    cadastradas = listar_empresas()
    if not cadastradas:
        raise RuntimeError("Nenhuma empresa cadastrada.")
    atual = getattr(page, "_empresa_atual", None)
    escolhida = next((e for e in cadastradas if atual and e["id"] == atual["id"]), None)
    if escolhida is None:
        escolhida = next((e for e in cadastradas if e["id"] == 1), cadastradas[0])
        selecionar_empresa(page, escolhida["id"])
    else:
        page._empresa_atual = escolhida
    seletor = campo_tema(ft.Dropdown(
        label="Empresa", width=280, dense=True, value=str(escolhida["id"]),
        options=[ft.dropdown.Option(str(e["id"]), e["nome"]) for e in cadastradas],
        tooltip=f"{escolhida['nome']} — {formatar_cnpj(escolhida['cnpj'])}",
    ))

    def trocar(e):
        anterior = page._empresa_atual
        try:
            if int(seletor.value) == anterior["id"]:
                return
            selecionar_empresa(page, int(seletor.value))
            page.overlay.clear()
            page.clean()
            ao_trocar()
        except Exception as exc:
            page._empresa_atual = anterior
            seletor.value = str(anterior["id"])
            page.clean()
            page.add(ft.Text(f"Não foi possível carregar a empresa: {exc}", color=ft.Colors.ERROR))
            page.update()

    seletor.on_select = trocar
    return ft.AppBar(
        title=ft.Text("Arsenal Precificação", size=18),
        actions=[ft.Container(seletor, padding=8)], toolbar_height=72,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
    )


def tela_empresas(page, area, atualizar_barra, ao_selecionar):
    nome = ft.TextField(label="Nome da empresa")
    cnpj = ft.TextField(label="CNPJ", hint_text="00.000.000/0000-00")
    editando = {"id": None}
    mensagem = ft.Text("", selectable=True)
    titulo = ft.Text("Cadastrar empresa", size=20, weight=ft.FontWeight.BOLD)
    tabela = ft.DataTable(columns=[ft.DataColumn(ft.Text(t)) for t in ("Empresa", "CNPJ", "Ações")], rows=[])

    def formatar_campo(e):
        try:
            cnpj.value = formatar_cnpj(normalizar_cnpj(cnpj.value))
        except ValueError:
            return
        page.update()

    cnpj.on_blur = formatar_campo

    def editar(empresa):
        editando["id"] = empresa["id"]
        nome.value = empresa["nome"]
        cnpj.value = formatar_cnpj(empresa["cnpj"])
        titulo.value = "Editar empresa"
        botao.content = "Salvar empresa"
        mensagem.value = ""
        page.update()

    def selecionar(empresa):
        selecionar_empresa(page, empresa["id"])
        page.overlay.clear()
        ao_selecionar()

    def carregar():
        atual = page._empresa_atual["id"]
        tabela.rows = [ft.DataRow(cells=[
            ft.DataCell(ft.Text(e["nome"])),
            ft.DataCell(ft.Text(formatar_cnpj(e["cnpj"]))),
            ft.DataCell(ft.Row([
                ft.Button("Selecionada" if e["id"] == atual else "Selecionar",
                          disabled=e["id"] == atual, on_click=lambda ev, empresa=e: selecionar(empresa)),
                ft.TextButton("Editar", on_click=lambda ev, empresa=e: editar(empresa)),
            ], tight=True)),
        ]) for e in listar_empresas()]

    def salvar(e):
        try:
            salvar_empresa(nome.value, cnpj.value, editando["id"])
            mensagem.value = "Empresa salva."
            mensagem.color = ft.Colors.PRIMARY
            editando["id"] = None
            nome.value = cnpj.value = ""
            titulo.value = "Cadastrar empresa"
            botao.content = "Cadastrar empresa"
            try:
                atualizar_barra()
                carregar()
            except Exception:
                mensagem.value = "Empresa salva. Reabra Configurações para atualizar a lista."
        except Exception as exc:
            mensagem.value = str(exc)
            mensagem.color = ft.Colors.ERROR
        page.update()

    botao = ft.Button("Cadastrar empresa", on_click=salvar)
    carregar()
    area.content = ft.Column([
        titulo, grade_campos([nome, cnpj]), botao, mensagem,
        ft.Divider(), ft.Row([tabela], scroll=ft.ScrollMode.ALWAYS),
    ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    page.update()
