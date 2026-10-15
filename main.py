from produtos import atualizar_taxas_lote
from servico_precificacao import inicializar
import flet as ft
from ui_layout import cartao_tabela, tabela_rolavel, campo_tema
from empresas import empresa_id, garantir_empresa
from ui_empresas import barra_empresa, tela_empresas
import json
import os
import amazon as az
import mercado_livre as ml
import shopee as sp
import tiktok as tk
import magalu as mg
import kwai as kw
from auth import validar_login
from db import carregar_config_bd, salvar_config_bd, testar_conexao_bd
from produtos import (
    criar_tabela_historico,
    listar_historico,
    listar_produtos, buscar_produto,
    criar_produto, atualizar_produto,
    listar_marcas,
    buscar_faixas_preco_ml, buscar_frete_ml,
    determinar_peso_ml, determinar_faixa_preco_ml,
    listar_taxas_comissoes, atualizar_taxa_comissao,
    buscar_taxa_imposto, buscar_taxa_ml,
    calcular_lucro_ml, calcular_margem_lucro, calcular_vinte_por_cento,
    buscar_kpis_geral,
    comparar_plataformas,
    importar_dados_planilha,
    recalcular_plataforma,
    excluir_produto_completo,
    gerar_relatorio_excel,
)
from fretes import (
    listar_frete_ml, atualizar_frete_ml,
    listar_frete_shopee, atualizar_frete_shopee,
    listar_taxas_por_canal, atualizar_taxa,
    listar_frete_amazon, atualizar_frete_amazon,
    listar_frete_amazon_brl200, atualizar_frete_amazon_brl200,
)
from usuarios import (
    listar_usuarios,
    buscar_usuario,
    criar_usuario,
    atualizar_usuario,
    alternar_ativo,
)
# ──────────────────────────────────────────────
#  PRODUTOS — LISTA, NOVO, EDITAR
# ──────────────────────────────────────────────
filtro_marca_global = {"valor": "Todas"}


def estado_filtro_marca(page):
    if not hasattr(page, "_filtro_marca"):
        page._filtro_marca = {"valor": "Todas"}
    return page._filtro_marca

COLUNAS_PRODUTOS = [
    ("sku", "SKU", True),
    ("descricao", "Descrição", True),
    ("trib", "Trib", False),
    ("embalagem", "Embalagem", False),
    ("quantidade", "Qtd", True),
    ("peso", "Peso", False),
    ("frete", "Frete", False),
    ("sugestao_preco", "Sug. Preço", False),
    ("preco_real", "Preço Real", True),
    ("lucro", "Lucro", False),
    ("margem_lucro", "Margem", False),
    ("vinte_por_cento", "20%", False),
    ("target_minimo", "Target", False),
]

# Caminho do arquivo que salva as colunas visíveis
ARQUIVO_COLUNAS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "colunas_visiveis.json"
)

def carregar_colunas_salvas():
    """Lê o arquivo JSON e retorna quais colunas estão visíveis."""
    padrao = {col[0]: col[2] for col in COLUNAS_PRODUTOS}
    try:
        if os.path.exists(ARQUIVO_COLUNAS):
            with open(ARQUIVO_COLUNAS, "r") as f:
                salvo = json.load(f)
            padrao.update({k: v for k, v in salvo.items() if k in padrao})
    except Exception:
        pass
    return padrao

def salvar_colunas(visiveis):
    """Salva as colunas visíveis no arquivo JSON."""
    try:
        with open(ARQUIVO_COLUNAS, "w") as f:
            json.dump(visiveis, f)
    except Exception:
        pass

def fmt_reais(val):
    if val is None or val == "":
        return "-"
    try:
        return f"R$ {float(val):.2f}"
    except (ValueError, TypeError):
        return str(val)

def fmt_pct(val):
    """Formata valor como porcentagem."""
    if val is None or val == "":
        return "-"
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return str(val)

def cor_lucro(val):
    if val is None or val == "":
        return ft.Colors.GREY_500
    try:
        return ft.Colors.RED if float(val) < 4.0 else ft.Colors.GREEN
    except (ValueError, TypeError):
        return ft.Colors.GREY_500

def cor_margem(val):
    if val is None or val == "":
        return ft.Colors.GREY_500
    try:
        return ft.Colors.RED if float(val) < 10.0 else ft.Colors.GREEN
    except (ValueError, TypeError):
        return ft.Colors.GREY_500

def fmt_val(val):
    if val is None:
        return "-"
    return str(val)

def fmt_celula(coluna, val, row=None):
    colunas_reais = {"trib", "embalagem", "frete", "preco_real", "lucro",
                     "vinte_por_cento", "target_minimo", "sugestao_preco", "comissao", "imposto", "afiliado"}
    if coluna == "status_calculo":
        motivo = (row or {}).get("mensagem_calculo", "")
        return ft.Text("Calculado" if val == "calculado" else f"Pendente: {motivo}", size=12,
                       color=ft.Colors.GREEN if val == "calculado" else ft.Colors.ORANGE_700)
    if val is None:
        return ft.Text("—", size=13)
    if coluna in ("margem_lucro", "taxa_percentual"):
        return ft.Text(fmt_pct(val), size=13, weight=ft.FontWeight.BOLD,
                       color=cor_margem(val))
    elif coluna == "lucro":
        return ft.Text(fmt_reais(val), size=13, weight=ft.FontWeight.BOLD,
                       color=cor_lucro(val))
    elif coluna == "preco_real" and row is not None:
        # Verifica se preço está abaixo do target mínimo
        target = row.get("target_minimo")
        cor = ft.Colors.ON_SURFACE
        try:
            if target and float(target) > 0 and float(val) < float(target):
                cor = ft.Colors.RED
        except (ValueError, TypeError):
            pass
        return ft.Text(fmt_reais(val), size=13, weight=ft.FontWeight.BOLD, color=cor)
    elif coluna in colunas_reais:
        return ft.Text(fmt_reais(val), size=13)
    else:
        return ft.Text(fmt_val(val), size=13)

def tela_geral(page: ft.Page, usuario_logado: dict, area_conteudo: ft.Container):
    """Visão geral — KPIs e dashboard."""
    empresa_da_tela = empresa_id()
    def make_card(titulo, valor, icon, cor):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icon, color=cor, size=28),
                    
                ], wrap=True, run_spacing=12),
                ft.Text(str(valor), size=28, weight=ft.FontWeight.BOLD, color=cor),
                ft.Text(titulo, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ]),
            padding=20,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, cor),
            border=ft.BorderSide(1, ft.Colors.with_opacity(0.2, cor)),
            col={"xs": 12, "sm": 6, "xl": 3},
        )
    def make_card_marca(marca, qtd, ticket, margem):
        cor_margem = ft.Colors.GREY_500 if margem is None else (
            ft.Colors.GREEN if margem > 20 else (ft.Colors.ORANGE if margem > 0 else ft.Colors.RED))
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.BRANDING_WATERMARK_OUTLINED,
                            color=ft.Colors.BLUE_400, size=22),
                    
                    ft.Text(f"{qtd} prod.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], wrap=True, run_spacing=12),
                ft.Text(marca, size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1),
                ft.Row([
                    ft.Column([
                        ft.Text("Ticket Médio", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(fmt_reais(ticket), size=14, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Container(width=15),
                    ft.Column([
                        ft.Text("Margem Média", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(fmt_pct(margem), size=14, weight=ft.FontWeight.BOLD,
                                color=cor_margem),
                    ]),
                ], wrap=True, run_spacing=12),
            ]),
            padding=15,
            border_radius=10,
            border=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.GREY_400)),
            col={"xs": 12, "md": 6, "xl": 4},
        )

    kpis = buscar_kpis_geral()
    if kpis is None:
        area_conteudo.content = ft.Column([
            ft.Text("Erro ao carregar KPIs.", color=ft.Colors.RED, size=16),
        ], expand=True)
        page.update()
        return

    # KPIs principais (linha de cards)
    cards_principais = ft.ResponsiveRow([
        make_card("Total de Produtos", kpis["total_produtos"],
                  ft.Icons.INVENTORY_2_OUTLINED, ft.Colors.ORANGE_700),
        make_card("Ticket Médio Geral", fmt_reais(kpis['ticket_medio_geral']),
                  ft.Icons.ATTACH_MONEY_OUTLINED, ft.Colors.GREEN_700),
        make_card("Margem Média Geral", fmt_pct(kpis['margem_media_geral']),
                  ft.Icons.TRENDING_UP_OUTLINED,
                  ft.Colors.GREEN if (kpis["margem_media_geral"] or 0) > 20 else ft.Colors.ORANGE),
        make_card("Marcas Cadastradas", len(kpis["por_marca"]),
                  ft.Icons.BRANDING_WATERMARK_OUTLINED, ft.Colors.PURPLE_700),
    ], spacing=16, run_spacing=16)

    # Cards por marca (grade)
    cards_marcas = []
    for m in kpis["por_marca"]:
        cards_marcas.append(
            make_card_marca(m["marca"], m["quantidade"],
                           m["ticket_medio"], m["margem_media"])
        )

    # Container scrollável para os cards de marca
    grade_marcas = ft.ResponsiveRow(cards_marcas, spacing=16, run_spacing=16)

    btn_novo = ft.Button(
        "+ Novo Produto",
        on_click=lambda e: tela_novo_produto(page, usuario_logado, area_conteudo, "Geral"),
        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
    )
    # --- Comparador de plataformas ---
    txt_comparar_sku = campo_tema(ft.TextField(
        label="Digite o SKU para comparar", width=250, dense=True,
    ))
    painel_comparacao = ft.Column([], scroll=ft.ScrollMode.AUTO)

    # --- Gerar Relatório (Excel) ---
    dropdown_rel_plataforma = campo_tema(ft.Dropdown(
        label="Plataforma",
        width=300,
        value="Mercado Livre",
        options=[
            ft.dropdown.Option("Mercado Livre"),
            ft.dropdown.Option("Amazon"),
            ft.dropdown.Option("Shopee"),
            ft.dropdown.Option("TikTok"),
            ft.dropdown.Option("Magalu"),
            ft.dropdown.Option("Kwai"),
        ],
    ))
    COLUNAS_RELATORIO = [
        ("sku", "SKU"),
        ("descricao", "Descrição"),
        ("marca", "Marca"),
        ("frete", "Frete (R$)"),
        ("preco_real", "Preço Real (R$)"),
        ("lucro", "Lucro (R$)"),
        ("margem_lucro", "Margem (%)"),
        ("vinte_por_cento", "20% (R$)"),
        ("target_minimo", "Target Mínimo (R$)"),
        ("peso", "Peso (kg)"),
        ("embalagem", "Embalagem"),
        ("trib", "Trib"),
    ]
    PADRAO_RELATORIO = {"sku", "frete", "preco_real"}
    checkboxes_relatorio = []
    for key, label in COLUNAS_RELATORIO:
        checkboxes_relatorio.append(
            ft.Checkbox(label=label, value=key in PADRAO_RELATORIO)
        )
    txt_rel_status = ft.Text("", size=13)

    def fechar_relatorio(e=None):
        dlg_relatorio.open = False
        page.update()

    def abrir_relatorio(e=None):
        txt_rel_status.value = ""
        if dlg_relatorio not in page.overlay:
            page.overlay.append(dlg_relatorio)
        dlg_relatorio.open = True
        page.update()

    def gerar_rel(e=None):
        garantir_empresa(empresa_da_tela)
        colunas_sel = [COLUNAS_RELATORIO[i][0] for i, cb in enumerate(checkboxes_relatorio) if cb.value]
        if not colunas_sel:
            txt_rel_status.value = "❌ Selecione pelo menos uma coluna."
            txt_rel_status.color = ft.Colors.RED
            page.update()
            return
        if "sku" not in colunas_sel:
            colunas_sel = ["sku"] + colunas_sel
        plataforma_rel = dropdown_rel_plataforma.value
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        caminho = filedialog.asksaveasfilename(
            title="Salvar relatório",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"relatorio_{plataforma_rel.replace(' ', '_').lower()}.xlsx",
        )
        root.destroy()
        if not caminho:
            return
        ok, msg = gerar_relatorio_excel(plataforma_rel, colunas_sel, caminho)
        txt_rel_status.value = ("✅ " if ok else "❌ ") + msg
        txt_rel_status.color = ft.Colors.GREEN if ok else ft.Colors.RED
        page.update()

    btn_gerar_rel = ft.Button(
        "Gerar Excel",
        icon=ft.Icons.TABLE_VIEW_OUTLINED,
        on_click=gerar_rel,
        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
    )

    dlg_relatorio = ft.AlertDialog(
        title=ft.Text("Gerar Relatório"),
        content=ft.Container(
            content=ft.Column(
                [
                    dropdown_rel_plataforma,
                    ft.Text("Colunas do relatório:", size=13, weight=ft.FontWeight.BOLD),
                    ft.Column(
                        [
                            ft.Row(checkboxes_relatorio[0:4], spacing=8, wrap=True, run_spacing=12),
                            ft.Row(checkboxes_relatorio[4:8], spacing=8, wrap=True, run_spacing=12),
                            ft.Row(checkboxes_relatorio[8:12], spacing=8, wrap=True, run_spacing=12),
                        ],
                        spacing=8,
                    ),
                    txt_rel_status,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=420,
        ),
        actions=[
            btn_gerar_rel,
            ft.TextButton("Cancelar", on_click=lambda e: fechar_relatorio()),
        ],
    )

    btn_relatorio = ft.Button(
        "Gerar Relatório",
        icon=ft.Icons.DESCRIPTION_OUTLINED,
        on_click=abrir_relatorio,
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
    )

    # --- Importação via Tkinter (seletor nativo) ---
    def _fechar_dialog(dlg_ref):
        dlg_ref.open = False
        page.update()

    def abrir_seletor_csv():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        caminho = filedialog.askopenfilename(
            title="Selecionar arquivo CSV",
            filetypes=[("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*")],
        )
        root.destroy()
        if not caminho:
            return
        processar_import_csv(caminho)

    def processar_import_csv(caminho):
        garantir_empresa(empresa_da_tela)
        resultado = importar_dados_planilha(caminho)

        detalhes = []
        if resultado["sucesso"]:
            header = ft.Text(
                f"✅ {resultado['atualizados']} produto(s) atualizado(s)! "
                f"{len(resultado['avisos'])} aviso(s).",
                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN,
            )
        else:
            header = ft.Text(
                "❌ Erro na importação.",
                size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.RED,
            )

        for erro in resultado["erros"]:
            detalhes.append(ft.Text(f"❌ {erro}", size=12, color=ft.Colors.RED))
        for aviso in resultado["avisos"]:
            detalhes.append(ft.Text(f"⚠️ {aviso}", size=12, color=ft.Colors.ORANGE))

        dlg = ft.AlertDialog(
            title=ft.Text("Resultado da Importação"),
            content=ft.Container(
                content=ft.Column(
                    [header] + detalhes,
                    scroll=ft.ScrollMode.AUTO,
                    tight=True,
                ),
                width=550,
                height=400,
            ),
            actions=[
                ft.TextButton("OK", on_click=lambda e: setattr(dlg, 'open', False) or page.update()),
            ],
        )
        dlg.open = True
        page.dialog = dlg
        page.update()
        # Recarrega KPIs após fechar
        tela_geral(page, usuario_logado, area_conteudo)

    def comparar(e=None):
        sku = txt_comparar_sku.value.strip() if txt_comparar_sku.value else ""
        if not sku:
            painel_comparacao.controls.clear()
            painel_comparacao.controls.append(
                ft.Text("Digite um SKU.", size=13, color=ft.Colors.RED)
            )
            page.update()
            return

        resultados = comparar_plataformas(sku)
        if resultados is None:
            painel_comparacao.controls.clear()
            painel_comparacao.controls.append(
                ft.Text("SKU não encontrado ou duplicado; confira o cadastro.", size=13, color=ft.Colors.RED)
            )
            page.update()
            return

        cadastrados = [r for r in resultados if r["cadastrado"] and r["preco_real"] > 0]
        if cadastrados:
            melhor = max(cadastrados, key=lambda x: x["lucro"])
        else:
            melhor = None

        def make_card_comp(res):
            if not res["cadastrado"]:
                return ft.Container(
                    content=ft.Column([
                        ft.Text(res["plataforma"], size=14, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(res.get("mensagem") or "Sem cálculo salvo", size=12, color=ft.Colors.ORANGE_700),
                    ]),
                    padding=12, border_radius=10, width=160,
                    border=ft.BorderSide(1, ft.Colors.with_opacity(0.1, ft.Colors.GREY_400)),
                )
            lucro = res["lucro"]
            margem = res["margem"]
            cor_lucro = ft.Colors.GREEN if lucro > 0 else ft.Colors.RED
            cor_margem = ft.Colors.GREEN if margem > 20 else (
                ft.Colors.ORANGE if margem > 0 else ft.Colors.RED
            )
            is_melhor = melhor and res["plataforma"] == melhor["plataforma"]
            cor_borda = ft.Colors.GREEN_700 if is_melhor else ft.Colors.with_opacity(0.15, ft.Colors.GREY_400)
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(res["plataforma"], size=14, weight=ft.FontWeight.BOLD),
                        
                        ft.Icon(ft.Icons.STAR if is_melhor else ft.Icons.STAR_BORDER,
                                color=ft.Colors.AMBER if is_melhor else ft.Colors.GREY_300,
                                size=18),
                    ], wrap=True, run_spacing=12),
                    ft.Divider(height=1),
                    ft.Text(f"Preço: R$ {res['preco_real']:.2f}", size=12),
                    ft.Text(f"Frete: R$ {res['frete']:.2f}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(f"Lucro: R$ {lucro:.2f}", size=14, weight=ft.FontWeight.BOLD,
                            color=cor_lucro),
                    ft.Text(f"Margem: {margem:.1f}%", size=14, weight=ft.FontWeight.BOLD,
                            color=cor_margem),
                ]),
                padding=12, border_radius=10, width=160,
                border=ft.BorderSide(2, cor_borda),
                bgcolor=ft.Colors.with_opacity(0.05, cor_borda) if is_melhor else None,
            )

        painel_comparacao.controls.clear()
        if melhor:
            painel_comparacao.controls.append(
                ft.Text(f"⭐ Melhor lucro: {melhor['plataforma']} — R$ {melhor['lucro']:.2f}",
                        size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700)
            )
        cards = [make_card_comp(r) for r in resultados]
        painel_comparacao.controls.append(
            ft.Row(cards, spacing=10, scroll=ft.ScrollMode.AUTO)
        )
        page.update()

    txt_comparar_sku.on_submit = comparar
    area_conteudo.content = ft.Column([
        ft.Row([
            ft.Text("Dashboard", size=24, weight=ft.FontWeight.BOLD),
            
            btn_novo,
            btn_relatorio,
        ], wrap=True, run_spacing=12),
        ft.Divider(),
        ft.Text("Visão Geral — preços e margens do Mercado Livre", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
        cards_principais,
        ft.Divider(height=20),
        ft.Text("Produtos por Marca", size=16, weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT),
        ft.Column([grade_marcas], scroll=ft.ScrollMode.AUTO),
        ft.Divider(height=20),
        ft.Text("Comparador de Plataformas", size=16, weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT),
        ft.Row([
            txt_comparar_sku,
            ft.Button("Comparar", icon=ft.Icons.COMPARE_ARROWS_OUTLINED,
                      on_click=comparar),
        ], spacing=5, wrap=True, run_spacing=12),
        painel_comparacao,
    ], scroll=ft.ScrollMode.AUTO, expand=True)
    page.update()


def tela_produtos(page: ft.Page, usuario_logado: dict, area_conteudo: ft.Container,
                  plataforma: str = "Mercado Livre"):

    """Página de produtos — barra de plataforma no topo, delega para o módulo."""
    empresa_da_tela = empresa_id()
    CORES_PLATAFORMAS = {
        "Mercado Livre": ft.Colors.YELLOW_700,
        "Amazon": ft.Colors.ORANGE_700,
        "Shopee": ft.Colors.RED_600,
        "TikTok": ft.Colors.PINK_600,
        "Magalu": ft.Colors.BLUE_600,
        "Kwai": ft.Colors.GREEN_600,
    }
    def btn_style(ativo, cor):
        if ativo:
            texto = ft.Colors.BLACK if cor in (ft.Colors.YELLOW_700, ft.Colors.ORANGE_700) else ft.Colors.WHITE
            return ft.ButtonStyle(bgcolor=cor, color=texto)
        return ft.ButtonStyle(color=ft.Colors.ON_SURFACE, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)
    btn_ml = ft.Button("Mercado Livre",
        on_click=lambda e: tela_produtos(page, usuario_logado, area_conteudo, "Mercado Livre"),
        style=btn_style(plataforma == "Mercado Livre", CORES_PLATAFORMAS["Mercado Livre"]))
    btn_amazon = ft.Button("Amazon",
        on_click=lambda e: tela_produtos(page, usuario_logado, area_conteudo, "Amazon"),
        style=btn_style(plataforma == "Amazon", CORES_PLATAFORMAS["Amazon"]))
    btn_shopee = ft.Button("Shopee",
        on_click=lambda e: tela_produtos(page, usuario_logado, area_conteudo, "Shopee"),
        style=btn_style(plataforma == "Shopee", CORES_PLATAFORMAS["Shopee"]))
    btn_tiktok = ft.Button("TikTok",
        on_click=lambda e: tela_produtos(page, usuario_logado, area_conteudo, "TikTok"),
        style=btn_style(plataforma == "TikTok", CORES_PLATAFORMAS["TikTok"]))
    btn_magalu = ft.Button("Magalu",
        on_click=lambda e: tela_produtos(page, usuario_logado, area_conteudo, "Magalu"),
        style=btn_style(plataforma == "Magalu", CORES_PLATAFORMAS["Magalu"]))
    btn_kwai = ft.Button("Kwai",
        on_click=lambda e: tela_produtos(page, usuario_logado, area_conteudo, "Kwai"),
        style=btn_style(plataforma == "Kwai", CORES_PLATAFORMAS["Kwai"]))

    # --- Botão Recalcular ---
    def fazer_recalculo(e=None):
        garantir_empresa(empresa_da_tela)
        resultado = recalcular_plataforma(plataforma)
        dlg = ft.AlertDialog(
            title=ft.Text("Recálculo Concluído"),
            content=ft.Text(resultado[1], size=14),
            actions=[
                ft.TextButton("OK", on_click=lambda e: (
                    setattr(dlg, 'open', False),
                    page.update(),
                    tela_produtos(page, usuario_logado, area_conteudo, plataforma)
                )),
            ],
        )
        dlg.open = True
        page.dialog = dlg
        page.update()

    btn_recalc = ft.Button(
        "Recalcular",
        icon=ft.Icons.REFRESH,
        on_click=fazer_recalculo,
        style=ft.ButtonStyle(bgcolor=ft.Colors.ORANGE, color=ft.Colors.BLACK),
    )
    # --- Excluir Produto ---
    txt_sku_excluir = campo_tema(ft.TextField(label="SKU do produto", width=300))
    txt_excluir_status = ft.Text("", size=13)

    def confirmar_exclusao(e=None):
        garantir_empresa(empresa_da_tela)
        sku = txt_sku_excluir.value.strip() if txt_sku_excluir.value else ""
        if not sku:
            txt_excluir_status.value = "❌ Digite o SKU."
            txt_excluir_status.color = ft.Colors.RED
            page.update()
            return
        ok, msg = excluir_produto_completo(sku, usuario_logado["nome"])
        txt_excluir_status.value = ("✅ " if ok else "❌ ") + msg
        txt_excluir_status.color = ft.Colors.GREEN if ok else ft.Colors.RED
        page.update()
        if ok:
            fechar_excluir()
            tela_produtos(page, usuario_logado, area_conteudo, plataforma)

    def abrir_excluir(e=None):
        txt_sku_excluir.value = ""
        txt_excluir_status.value = ""
        if dlg_excluir not in page.overlay:
            page.overlay.append(dlg_excluir)
        dlg_excluir.open = True
        page.update()

    def fechar_excluir(e=None):
        dlg_excluir.open = False
        page.update()

    dlg_excluir = ft.AlertDialog(
        title=ft.Text("Excluir Produto", color=ft.Colors.RED),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "⚠️ ATENÇÃO: o produto será excluído de TODAS as plataformas "
                        "(Mercado Livre, Amazon, Shopee, TikTok, Magalu e Kwai) e do "
                        "cadastro principal. Essa ação não pode ser desfeita.",
                        size=13, color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    txt_sku_excluir,
                    txt_excluir_status,
                ],
                tight=True,
            ),
            width=380,
        ),
        actions=[
            ft.TextButton("Excluir", on_click=confirmar_exclusao,
                          style=ft.ButtonStyle(color=ft.Colors.RED)),
            ft.TextButton("Cancelar", on_click=lambda e: fechar_excluir()),
        ],
    )

    btn_excluir = ft.Button(
        "Excluir Produto",
        icon=ft.Icons.DELETE_OUTLINE,
        on_click=abrir_excluir,
        style=ft.ButtonStyle(
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.RED_700,
        ),
    )
    # --- Barra de botões (sempre visível) ---
    barra_botoes = ft.Column([
        ft.Row([
            ft.Text("Produtos", size=22, weight=ft.FontWeight.BOLD),
            
            btn_recalc,
            btn_excluir,
        ], wrap=True, run_spacing=12),
        ft.Row([btn_ml, btn_amazon, btn_shopee, btn_tiktok, btn_magalu, btn_kwai], spacing=5, wrap=True),
        ft.Divider(),
    ])

    # --- Sub-área que cada módulo preenche ---
    sub_area = ft.Container(expand=True)

    area_conteudo.content = ft.Column([barra_botoes, sub_area], expand=True)
    page.update()

    # --- Delega para o módulo da plataforma ---
    if plataforma == "Mercado Livre":
        ml.tela_lista(page, usuario_logado, sub_area)
        return
    if plataforma == "Amazon":
        az.tela_lista(page, usuario_logado, sub_area)
        return
    if plataforma == "Shopee":
        sp.tela_lista(page, usuario_logado, sub_area)
        return
    if plataforma == "TikTok":
        tk.tela_lista(page, usuario_logado, sub_area)
        return
    if plataforma == "Magalu":
        mg.tela_lista(page, usuario_logado, sub_area)
        return
    if plataforma == "Kwai":
        kw.tela_lista(page, usuario_logado, sub_area)
        return
    # --- Plataformas sem módulo ainda ---
    sub_area.content = ft.Column([
        ft.Text(f"{plataforma} — módulo em desenvolvimento", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
    ], expand=True)
    page.update()

def tela_novo_produto(page: ft.Page, usuario_logado: dict, area_conteudo: ft.Container, plataforma: str='Mercado Livre'):
    from ui_precificacao import formulario
    canal = "Mercado Livre" if plataforma == "Geral" else plataforma
    formulario(page, usuario_logado, area_conteudo, canal,
               lambda: tela_geral(page, usuario_logado, area_conteudo) if plataforma == "Geral" else tela_produtos(page, usuario_logado, area_conteudo, plataforma),
               condicao_ml=ml.estado_condicao(page)["valor"] if canal == "Mercado Livre" else None)

def tela_editar_produto(page: ft.Page, usuario_logado: dict, area_conteudo: ft.Container, produto_id: int, plataforma: str='Mercado Livre'):
    from ui_precificacao import formulario
    canal = "Mercado Livre" if plataforma == "Geral" else plataforma
    formulario(page, usuario_logado, area_conteudo, canal,
               lambda: tela_geral(page, usuario_logado, area_conteudo) if plataforma == "Geral" else tela_produtos(page, usuario_logado, area_conteudo, plataforma), produto_id=produto_id,
               condicao_ml=ml.estado_condicao(page)["valor"] if canal == "Mercado Livre" else None)

# ──────────────────────────────────────────────
#  TELA DE LOGIN
# ──────────────────────────────────────────────
def tela_login(page: ft.Page):
    page.appbar = None
    page._empresa_atual = None
    def fazer_login(e):
        user = txt_usuario.value.strip()
        pwd = txt_senha.value
        if not user or not pwd:
            txt_erro.value = "Preencha usuário e senha."
            page.update()
            return
        resultado = validar_login(user, pwd)
        if resultado is None:
            txt_erro.value = "Usuário ou senha inválidos."
            page.update()
            return
        try:
            criar_tabela_historico()
            inicializar()
        except Exception as exc:
            txt_erro.value = f"Não foi possível preparar os cálculos: {exc}"
            page.update()
            return
        abrir_app(page, resultado)
    txt_usuario = campo_tema(ft.TextField(label="Usuário", autofocus=True, width=300))
    txt_senha = campo_tema(ft.TextField(
        label="Senha", password=True, can_reveal_password=True,
        width=300, on_submit=fazer_login,
    ))
    txt_erro = ft.Text(value="", color=ft.Colors.RED, size=13)

    # ── Configuração do Banco de Dados ──
    cfg_atual = carregar_config_bd()
    txt_host = campo_tema(ft.TextField(
        label="Host / Servidor",
        value=str(cfg_atual.get("host", "localhost")),
        width=350,
    ))
    txt_user_bd = campo_tema(ft.TextField(
        label="Usuário do BD",
        value=str(cfg_atual.get("user", "root")),
        width=350,
    ))
    txt_pwd_bd = campo_tema(ft.TextField(
        label="Senha do BD",
        value=str(cfg_atual.get("password", "")),
        password=True, can_reveal_password=True,
        width=350,
    ))
    txt_db = campo_tema(ft.TextField(
        label="Banco de Dados",
        value=str(cfg_atual.get("database", "arsenal_precificacao")),
        width=350,
    ))
    txt_port = campo_tema(ft.TextField(
        label="Porta",
        value=str(cfg_atual.get("port", 3389)),
        width=350,
    ))
    txt_bd_status = ft.Text("", size=13)

    def salvar_bd(e):
        cfg = {
            "host": txt_host.value.strip(),
            "user": txt_user_bd.value.strip(),
            "password": txt_pwd_bd.value or "",
            "database": txt_db.value.strip(),
            "port": txt_port.value.strip() or 3389,
        }
        txt_bd_status.value = "Testando conexão..."
        txt_bd_status.color = ft.Colors.GREY_600
        page.update()
        ok, msg = testar_conexao_bd(cfg)
        if ok:
            salvar_config_bd(cfg)
            txt_bd_status.value = "✅ Conectado e salvo com sucesso!"
            txt_bd_status.color = ft.Colors.GREEN
        else:
            txt_bd_status.value = f"❌ Falha na conexão: {msg}"
            txt_bd_status.color = ft.Colors.RED
        page.update()

    dlg_bd = ft.AlertDialog(
        title=ft.Text("Conexão com o Banco de Dados"),
        content=ft.Container(
            content=ft.Column(
                [txt_host, txt_user_bd, txt_pwd_bd, txt_db, txt_port, txt_bd_status],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=380,
        ),
        actions=[
            ft.TextButton("Testar e Salvar", on_click=salvar_bd),
            ft.TextButton(
                "Fechar",
                on_click=lambda e: fechar_bd(),
            ),
        ],
    )
    def fechar_bd(e=None):
        dlg_bd.open = False
        page.update()

    def abrir_config_bd(e=None):
        txt_bd_status.value = ""
        if dlg_bd not in page.overlay:
            page.overlay.append(dlg_bd)
        dlg_bd.open = True
        page.update()

    btn_bd = ft.TextButton(
        "⚙ Configurar Banco de Dados",
        icon=ft.Icons.SETTINGS_OUTLINED,
        on_click=abrir_config_bd,
    )

    page.clean()
    page.add(
        ft.Column(
            [
                ft.Icon(ft.Icons.LOCK_OUTLINE, size=60, color=ft.Colors.BLUE_400),
                ft.Text("Arsenal Precificação", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(height=1),
                txt_usuario,
                txt_senha,
                txt_erro,
                ft.Button("Entrar", on_click=fazer_login, width=300, height=45),
                btn_bd,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    page.update()

# ──────────────────────────────────────────────
#  CONFIGURAÇÕES — ABAS (Usuários + Frete)
# ──────────────────────────────────────────────
def tela_config_usuarios(page: ft.Page, usuario_logado: dict):
    """Página de Configurações com abas: Usuários e Frete."""

    def voltar_inicio(e):
        abrir_app(page, usuario_logado)

    # ── Aba Usuários: tabela ──
    tabela_usuarios = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Nome")),
            ft.DataColumn(ft.Text("E-mail")),
            ft.DataColumn(ft.Text("Cargo")),
            ft.DataColumn(ft.Text("Status")),
        ],
        rows=[],
        border_radius=8,
        horizontal_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY_500)),
    )

    def recarregar_usuarios():
        lista = listar_usuarios()
        tabela_usuarios.rows.clear()
        for idx, u in enumerate(lista):
            cor = ft.Colors.GREEN if u["ativo"] else ft.Colors.RED
            status = "Ativo" if u["ativo"] else "Inativo"
            tabela_usuarios.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(u["id"]), size=13, color=ft.Colors.ON_SURFACE_VARIANT)),
                        ft.DataCell(ft.Text(u["nome"], size=14, weight=ft.FontWeight.W_600)),
                        ft.DataCell(ft.Text(u["email"], size=13, color=ft.Colors.ON_SURFACE_VARIANT)),
                        ft.DataCell(
                            ft.Text(u["role"].upper(), size=12, color=ft.Colors.ORANGE_700, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(status, size=12, weight=ft.FontWeight.BOLD, color=cor),
                            padding=5,
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.1, cor),
                        )),
                    ],
                    on_select_change=lambda e, uid=u["id"]: tela_editar_usuario(page, usuario_logado, uid),
                )
            )
        page.update()

    recarregar_usuarios()

    conteudo_usuarios = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Usuários", size=20, weight=ft.FontWeight.BOLD),
                    
                    ft.Button(
                        "Novo Usuário",
                        icon=ft.Icons.PERSON_ADD_OUTLINED,
                        on_click=lambda e: tela_novo_usuario(page, usuario_logado),
                    ),
                ]
            , wrap=True, run_spacing=12),
            ft.Divider(),
            tabela_rolavel(tabela_usuarios),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        expand=True,
    )

    # ── Aba Frete: seleção de plataforma + tabela ──
    dropdown_plataforma = campo_tema(ft.Dropdown(
        label="Plataforma",
        width=250,
        options=[
            ft.dropdown.Option("Mercado Livre"),
            ft.dropdown.Option("Shopee"),
            ft.dropdown.Option("Amazon"),
            ft.dropdown.Option("TikTok"),
            ft.dropdown.Option("Magalu"),
            ft.dropdown.Option("Kwai"),
        ],
    ))

    area_tabela_frete = ft.Column([], scroll=ft.ScrollMode.AUTO, expand=True)
    txt_frete_msg = ft.Text("", size=13, color=ft.Colors.GREEN)

    def carregar_tabela_frete(e=None):
        plataforma = dropdown_plataforma.value

        if not plataforma:
            return

        area_tabela_frete.controls.clear()
        txt_frete_msg.value = ""
        txt_frete_msg.color = ft.Colors.RED

        try:
            if plataforma == "Mercado Livre":
                dados = listar_frete_ml()
                if not dados:
                    area_tabela_frete.controls.append(
                        ft.Text("Nenhum dado encontrado ou erro na consulta.", color=ft.Colors.RED)
                    )
                else:
                    colunas = ["peso", "faixa_0_18_99", "faixa_19_48_99", "faixa_49_78_99",
                               "faixa_79_99_99", "faixa_100_119_99", "faixa_120_149_99",
                               "faixa_150_199_99", "faixa_200_mais"]
                    titulos = ["Peso", "R$ 0-18,99", "R$ 19-48,99", "R$ 49-78,99",
                               "R$ 79-99,99", "R$ 100-119,99", "R$ 120-149,99",
                               "R$ 150-199,99", "R$ 200+"]
                    montar_tabela_ml_shopee(dados, colunas, titulos, "ml", area_tabela_frete, txt_frete_msg, page)

            elif plataforma == "Shopee":
                dados = listar_frete_shopee()
                if not dados:
                    area_tabela_frete.controls.append(
                        ft.Text("Nenhum dado encontrado ou erro na consulta.", color=ft.Colors.RED)
                    )
                else:
                    colunas = ["faixa", "valor_do_produto", "taxa_percentual", "taxa_fixa_reais"]
                    titulos = ["Faixa", "Valor do Produto", "Taxa %", "Taxa Fixa (R$)"]
                    montar_tabela_ml_shopee(dados, colunas, titulos, "shopee", area_tabela_frete, txt_frete_msg, page)

            elif plataforma == "Amazon":
                dados_comissao = listar_taxas_por_canal("Amazon")
                dados_frete_79 = listar_frete_amazon()
                dados_frete_200 = listar_frete_amazon_brl200()
                if not dados_comissao and not dados_frete_79 and not dados_frete_200:
                    area_tabela_frete.controls.append(
                        ft.Text("Nenhum dado encontrado ou erro na consulta.", color=ft.Colors.RED)
                    )
                else:
                    montar_tabela_amazon(dados_comissao, dados_frete_79, dados_frete_200,
                                         area_tabela_frete, txt_frete_msg, page)

            elif plataforma in ("TikTok", "Magalu", "Kwai"):
                dados = listar_taxas_por_canal(plataforma)
                if not dados:
                    area_tabela_frete.controls.append(
                        ft.Text("Nenhum dado encontrado ou erro na consulta.", color=ft.Colors.RED)
                    )
                else:
                    montar_tabela_taxas(dados, area_tabela_frete, txt_frete_msg, page)

        except Exception as ex:
            txt_frete_msg.value = f"Erro ao carregar: {ex}"
            area_tabela_frete.controls.append(
                ft.Text(f"Detalhe do erro: {ex}", color=ft.Colors.RED, size=12)
            )

        page.update()

    dropdown_plataforma.on_select = carregar_tabela_frete

    btn_carregar = ft.Button(
        "Carregar",
        icon=ft.Icons.SEARCH_OUTLINED,
        on_click=carregar_tabela_frete,
    )

    conteudo_frete = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Frete e Taxas", size=20, weight=ft.FontWeight.BOLD),
                    
                    dropdown_plataforma,
                    btn_carregar,
                ]
            , wrap=True, run_spacing=12),
            ft.Divider(),
            txt_frete_msg,
            area_tabela_frete,
        ],
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        expand=True,
    )

    # ── Container que troca de conteúdo conforme o botão ──
    area_conteudo_config = ft.Container(content=conteudo_usuarios, expand=True)

    def selecionar_taxas(e):
        btn_tab_empresas.style = ft.ButtonStyle(color=ft.Colors.ON_SURFACE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        btn_tab_usuarios.style = ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        btn_tab_frete.style = ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        btn_tab_taxas.style = ft.ButtonStyle(color=ft.Colors.BLACK, bgcolor=ft.Colors.ORANGE_700)
        page.update()
        tela_config_taxas(page, usuario_logado, area_conteudo_config)

    btn_tab_usuarios = ft.Button(
        "Usuários",
        icon=ft.Icons.PEOPLE_OUTLINE,
        on_click=lambda e: trocar_conteudo("usuarios"),
        style=ft.ButtonStyle(
            color=ft.Colors.BLACK,
            bgcolor=ft.Colors.ORANGE_700,
        ),
    )
    btn_tab_frete = ft.Button(
        "Frete",
        icon=ft.Icons.LOCAL_SHIPPING_OUTLINED,
        on_click=lambda e: trocar_conteudo("frete"),
        style=ft.ButtonStyle(
            color=ft.Colors.ON_SURFACE_VARIANT,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        ),
    )
    btn_tab_taxas = ft.Button(
        "Taxas",
        icon=ft.Icons.PERCENT,
        on_click=selecionar_taxas,
        style=ft.ButtonStyle(
            color=ft.Colors.ON_SURFACE_VARIANT,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        ),
    )

    def atualizar_barra_empresas():
        page.appbar = barra_empresa(page, lambda: abrir_app(page, usuario_logado))

    def selecionar_empresas(e):
        for botao in (btn_tab_usuarios, btn_tab_frete, btn_tab_taxas):
            botao.style = ft.ButtonStyle(color=ft.Colors.ON_SURFACE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        btn_tab_empresas.style = ft.ButtonStyle(color=ft.Colors.BLACK, bgcolor=ft.Colors.ORANGE_700)
        tela_empresas(page, area_conteudo_config, atualizar_barra_empresas,
                      lambda: abrir_app(page, usuario_logado))

    btn_tab_empresas = ft.Button("Empresas", icon=ft.Icons.BUSINESS_OUTLINED,
                                 on_click=selecionar_empresas)

    def trocar_conteudo(alvo):
        btn_tab_empresas.style = ft.ButtonStyle(color=ft.Colors.ON_SURFACE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        btn_tab_taxas.style = ft.ButtonStyle(color=ft.Colors.ON_SURFACE, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW)
        if alvo == "usuarios":
            area_conteudo_config.content = conteudo_usuarios
            btn_tab_usuarios.style = ft.ButtonStyle(
                color=ft.Colors.BLACK, bgcolor=ft.Colors.ORANGE_700,
            )
            btn_tab_frete.style = ft.ButtonStyle(
                color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW
            )
        else:
            area_conteudo_config.content = conteudo_frete
            btn_tab_usuarios.style = ft.ButtonStyle(
                color=ft.Colors.ON_SURFACE_VARIANT, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW
            )
            btn_tab_frete.style = ft.ButtonStyle(
                color=ft.Colors.BLACK, bgcolor=ft.Colors.ORANGE_400
            )
        page.update()

    page.controls.clear()
    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Button(
                            "← Voltar ao Início",
                            on_click=voltar_inicio,
                            style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                        ),
                        
                        ft.Text("Configurações", size=22, weight=ft.FontWeight.BOLD),
                    ]
                , wrap=True, run_spacing=12),
                ft.Divider(),
                ft.Row([btn_tab_usuarios, btn_tab_frete, btn_tab_taxas, btn_tab_empresas], spacing=5, wrap=True, run_spacing=12),
                ft.Divider(height=1),
                area_conteudo_config,
            ],
            expand=True,
        )
    )
    page.update()

# ──────────────────────────────────────────────
#  MONTAGEM DE TABELAS DE FRETE (editáveis)
# ──────────────────────────────────────────────
def montar_tabela_ml_shopee(dados, colunas, titulos, tipo, container, txt_msg, page):
    """Monta tabela editável para Mercado Livre ou Shopee."""
    if not dados:
        container.controls.append(ft.Text("Nenhum dado encontrado.", color=ft.Colors.ON_SURFACE_VARIANT))
        return
    LARGURA_COL = 75
    fields = []
    for row in dados:
        row_fields = []
        for col in colunas:
            val = row[col]
            if val is None:
                val = 0
            row_fields.append(
                campo_tema(ft.TextField(
                    value=str(val), width=(190 if col == "peso" else LARGURA_COL), text_size=14, dense=True,
                    color=ft.Colors.ON_SURFACE,
                    border_color=ft.Colors.OUTLINE,
                    focused_border_color=ft.Colors.PRIMARY,
                    text_align=ft.TextAlign.CENTER,
                ))
            )
        fields.append((row["id"], row_fields))
    header = ft.Row(
        [ft.Text("ID", size=11, weight=ft.FontWeight.BOLD, width=30, color=ft.Colors.ON_SURFACE)] +
        [ft.Text(t, size=13, weight=ft.FontWeight.BOLD, width=(190 if i == 0 else LARGURA_COL), color=ft.Colors.ON_SURFACE,
                 text_align=ft.TextAlign.CENTER) for i, t in enumerate(titulos)] +
        [ft.Text("", width=40)],
        spacing=4,
    )
    linhas = [header, ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT)]
    for i, (rid, rf) in enumerate(fields):
        cor_fundo = ft.Colors.with_opacity(0.45, ft.Colors.SURFACE_CONTAINER_HIGHEST) if i % 2 == 0 else None
        linha = ft.Container(
            content=ft.Row(
                [ft.Text(str(rid), size=11, width=30, color=ft.Colors.ON_SURFACE,
                         text_align=ft.TextAlign.CENTER)] + rf +
                [
                    ft.IconButton(
                        icon=ft.Icons.SAVE_OUTLINED,
                        icon_size=16,
                        icon_color=ft.Colors.BLUE_600,
                        tooltip="Salvar",
                        on_click=lambda e, r=rid, rfs=rf: salvar_linha_ml_shopee(
                            r, rfs, colunas, tipo, txt_msg, page
                        ),
                    )
                ],
                spacing=4,
            ),
            bgcolor=cor_fundo,
            padding=4,
        )
        linhas.append(linha)
    card = cartao_tabela(linhas)
    container.controls.append(card)

def salvar_linha_ml_shopee(rid, row_fields, colunas, tipo, txt_msg, page):
    linha = {"id": rid, **{col: (campo.value or "").strip() for col, campo in zip(colunas, row_fields)}}
    ok, msg = (atualizar_frete_ml(linha) if tipo == "ml" else atualizar_frete_shopee(linha))
    txt_msg.value = msg
    txt_msg.color = ft.Colors.GREEN if ok else ft.Colors.RED
    page.update()

def montar_tabela_taxas(dados, container, txt_msg, page):
    """Monta tabela editável para TikTok, Magalu, Kwai (tabela_taxas_comissoes)."""
    if not dados:
        container.controls.append(ft.Text("Nenhum dado encontrado.", color=ft.Colors.ON_SURFACE_VARIANT))
        return
    colunas = ["canal", "condicao", "taxa_percentual", "taxa_fixa_reais"]
    titulos = ["Canal", "Condição", "Taxa %", "Taxa Fixa"]
    header = ft.Row(
        [ft.Text("ID", size=11, weight=ft.FontWeight.BOLD, width=30, color=ft.Colors.ON_SURFACE)] +
        [ft.Text(t, size=13, weight=ft.FontWeight.BOLD, width=120, color=ft.Colors.ON_SURFACE,
                 text_align=ft.TextAlign.CENTER) for t in titulos] +
        [ft.Text("Salvar", size=11, weight=ft.FontWeight.BOLD, width=40, color=ft.Colors.ON_SURFACE)],
        spacing=5,
    )
    linhas = [header, ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT)]
    for i, row in enumerate(dados):
        row_fields = []
        for col in colunas:
            val = row[col]
            if val is None:
                val = 0
            row_fields.append(
                campo_tema(ft.TextField(
                    value=str(val), width=120, text_size=14, dense=True,
                    color=ft.Colors.ON_SURFACE,
                    border_color=ft.Colors.OUTLINE,
                    focused_border_color=ft.Colors.PRIMARY,
                    text_align=ft.TextAlign.CENTER,
                ))
            )
        rid = row["id"]
        cor_fundo = ft.Colors.with_opacity(0.45, ft.Colors.SURFACE_CONTAINER_HIGHEST) if i % 2 == 0 else None
        linha = ft.Container(
            content=ft.Row(
                [ft.Text(str(rid), size=11, width=30, color=ft.Colors.ON_SURFACE,
                         text_align=ft.TextAlign.CENTER)] + row_fields +
                [
                    ft.IconButton(
                        icon=ft.Icons.SAVE_OUTLINED,
                        icon_size=16,
                        icon_color=ft.Colors.BLUE_600,
                        tooltip="Salvar",
                        on_click=lambda e, r=rid, rf=row_fields: salvar_linha_taxa(
                            r, rf, colunas, txt_msg, page
                        ),
                    )
                ],
                spacing=5,
            ),
            bgcolor=cor_fundo,
            padding=4,
        )
        linhas.append(linha)
    card = cartao_tabela(linhas)
    container.controls.append(card)

def salvar_linha_taxa(rid, row_fields, colunas, txt_msg, page):
    linha = {"id": rid, **{col: (campo.value or "").strip() for col, campo in zip(colunas, row_fields)}}
    ok, msg = atualizar_taxa(linha)
    txt_msg.value = msg
    txt_msg.color = ft.Colors.GREEN if ok else ft.Colors.RED
    page.update()

def montar_tabela_amazon(dados_comissao, dados_frete_79, dados_frete_200, container, txt_msg, page):
    """Monta as 3 seções da Amazon com cards visuais."""
    def _montar_secao(titulo, colunas, titulos, dados, func_salvar):
        header = ft.Row(
            [ft.Text("ID", size=11, weight=ft.FontWeight.BOLD, width=30, color=ft.Colors.ON_SURFACE)] +
            [ft.Text(t, size=13, weight=ft.FontWeight.BOLD, width=110, color=ft.Colors.ON_SURFACE,
                     text_align=ft.TextAlign.CENTER) for t in titulos] +
            [ft.Text("Salvar", size=10, weight=ft.FontWeight.BOLD, width=40, color=ft.Colors.ON_SURFACE)],
            spacing=5,
        )
        linhas = [header, ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT)]
        for i, row in enumerate(dados):
            row_fields = []
            for col in colunas:
                val = row[col]
                if val is None:
                    val = 0
                row_fields.append(
                    campo_tema(ft.TextField(
                        value=str(val), width=110, text_size=14, dense=True,
                        color=ft.Colors.ON_SURFACE,
                        border_color=ft.Colors.OUTLINE,
                        focused_border_color=ft.Colors.PRIMARY,
                        text_align=ft.TextAlign.CENTER,
                    ))
                )
            rid = row["id"]
            cor_fundo = ft.Colors.with_opacity(0.45, ft.Colors.SURFACE_CONTAINER_HIGHEST) if i % 2 == 0 else None
            linha = ft.Container(
                content=ft.Row(
                    [ft.Text(str(rid), size=11, width=30, color=ft.Colors.ON_SURFACE,
                             text_align=ft.TextAlign.CENTER)] + row_fields +
                    [
                        ft.IconButton(
                            icon=ft.Icons.SAVE_OUTLINED, icon_size=16,
                            icon_color=ft.Colors.BLUE_600, tooltip="Salvar",
                            on_click=lambda e, r=rid, rf=row_fields: func_salvar(
                                r, rf, colunas, txt_msg, page
                            ),
                        )
                    ],
                    spacing=5,
                ),
                bgcolor=cor_fundo,
                padding=4,
            )
            linhas.append(linha)
        container.controls.append(
            ft.Text(titulo, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
        )
        container.controls.append(
            cartao_tabela(linhas)
        )
        container.controls.append(ft.Divider(height=20))

    _montar_secao("Amazon — Até R$ 79 (Tarifa Fixa)",
                  ["canal", "condicao", "taxa_percentual", "taxa_fixa_reais"],
                  ["Canal", "Condição", "Taxa %", "Taxa Fixa"],
                  dados_comissao, salvar_linha_taxa)
    _montar_secao("Amazon — R$ 79 a R$ 199,99 (Frete × Preço)",
                  ["peso", "faixa_79_99_99", "faixa_100_119_99", "faixa_120_149_99", "faixa_150_199_99"],
                  ["Peso", "R$ 79-99", "R$ 100-119", "R$ 120-149", "R$ 150-199"],
                  dados_frete_79, salvar_linha_amazon)
    _montar_secao("Amazon — Acima de R$ 200 (Frete × Região)",
                  ["peso", "sp_capital", "outras_capitais_sul_sudeste",
                   "interior_sul_sudeste", "centro_oeste_norte_nordeste"],
                  ["Peso", "SP Capital", "Cap. Sul/SE", "Interior S/SE", "CO/N/NE"],
                  dados_frete_200, salvar_linha_amazon_brl200)

def salvar_linha_amazon(rid, row_fields, colunas, txt_msg, page):
    linha = {"id": rid, **{col: (campo.value or "").strip() for col, campo in zip(colunas, row_fields)}}
    ok, msg = atualizar_frete_amazon(linha)
    txt_msg.value = msg
    txt_msg.color = ft.Colors.GREEN if ok else ft.Colors.RED
    page.update()

def salvar_linha_amazon_brl200(rid, row_fields, colunas, txt_msg, page):
    linha = {"id": rid, **{col: (campo.value or "").strip() for col, campo in zip(colunas, row_fields)}}
    ok, msg = atualizar_frete_amazon_brl200(linha)
    txt_msg.value = msg
    txt_msg.color = ft.Colors.GREEN if ok else ft.Colors.RED
    page.update()
def tela_config_taxas(page: ft.Page, usuario_logado: dict, area_conteudo: ft.Container):
    """Página de Configurações — Taxas e Comissões (editável)."""
    taxas = listar_taxas_comissoes()
    campos_editaveis = {}
    def voltar(e):
        tela_config_usuarios(page, usuario_logado)
    def salvar_todas(e):
        linhas = []
        for taxa_id, campos in campos_editaveis.items():
            linha = {"id": taxa_id}
            for chave, campo in campos.items():
                valor = (campo.value or "").strip()
                if valor:
                    linha[chave] = valor
            if len(linha) > 1:
                linhas.append(linha)
        ok, msg = atualizar_taxas_lote(linhas)
        txt_status.value = msg
        txt_status.color = ft.Colors.GREEN if ok else ft.Colors.RED
        page.update()
    # --- Monta a tabela editável com card ---
    header = ft.Row(
        [ft.Text("ID", size=12, weight=ft.FontWeight.BOLD, width=40, color=ft.Colors.ON_SURFACE)] +
        [ft.Text("Canal", size=12, weight=ft.FontWeight.BOLD, width=120, color=ft.Colors.ON_SURFACE,
                 text_align=ft.TextAlign.CENTER)] +
        [ft.Text("Condição", size=12, weight=ft.FontWeight.BOLD, width=200, color=ft.Colors.ON_SURFACE,
                 text_align=ft.TextAlign.CENTER)] +
        [ft.Text("Taxa %", size=12, weight=ft.FontWeight.BOLD, width=100, color=ft.Colors.ON_SURFACE,
                 text_align=ft.TextAlign.CENTER)] +
        [ft.Text("Taxa Fixa (R$)", size=12, weight=ft.FontWeight.BOLD, width=100, color=ft.Colors.ON_SURFACE,
                 text_align=ft.TextAlign.CENTER)],
        spacing=5,
    )
    linhas = [header, ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT)]
    for i, t in enumerate(taxas):
        tp = float(t.get("taxa_percentual")) if t.get("taxa_percentual") is not None else None
        tf_val = float(t.get("taxa_fixa_reais")) if t.get("taxa_fixa_reais") is not None else None
        campo_tp = campo_tema(ft.TextField(
            value=str(tp) if tp is not None else "",
            width=100, dense=True, text_size=14,
            color=ft.Colors.ON_SURFACE,
            border_color=ft.Colors.OUTLINE,
            focused_border_color=ft.Colors.PRIMARY,
            text_align=ft.TextAlign.CENTER,
        ))
        campo_tf = campo_tema(ft.TextField(
            value=str(tf_val) if tf_val is not None else "",
            width=100, dense=True, text_size=12,
            color=ft.Colors.ON_SURFACE,
            border_color=ft.Colors.OUTLINE,
            focused_border_color=ft.Colors.PRIMARY,
            text_align=ft.TextAlign.CENTER,
        ))
        campos_editaveis[t["id"]] = {
            "taxa_percentual": campo_tp,
            "taxa_fixa_reais": campo_tf,
        }
        cor_fundo = ft.Colors.with_opacity(0.45, ft.Colors.SURFACE_CONTAINER_HIGHEST) if i % 2 == 0 else None
        linha = ft.Container(
            content=ft.Row(
                [
                    ft.Text(str(t["id"]), size=12, width=40, color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(str(t.get("canal", "")), size=12, width=120, color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(str(t.get("condicao", "") or "-"), size=12, width=200, color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER),
                    campo_tp,
                    campo_tf,
                ],
                spacing=5,
            ),
            bgcolor=cor_fundo,
            padding=4,
        )
        linhas.append(linha)
    txt_status = ft.Text("", size=13)
    card_taxas = cartao_tabela(linhas)
    area_conteudo.content = ft.Column(
        [
            ft.Row([
                ft.Button("← Voltar", on_click=voltar,
                          style=ft.ButtonStyle(color=ft.Colors.PRIMARY)),
                
                ft.Text("Configurações — Taxas e Comissões", size=24, weight=ft.FontWeight.BOLD,
                        color=ft.Colors.PRIMARY),
            ], wrap=True, run_spacing=12),
            ft.Divider(),
            ft.Text(
                "Edite os valores diretamente na tabela e clique em Salvar. "
                "Estas taxas são usadas em todos os cálculos de precificação.",
                size=12, color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Divider(),
            card_taxas,
            txt_status,
            ft.Button("Salvar Todas as Taxas", on_click=salvar_todas,
                      style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE),
                      height=45),
        ],
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )
    page.update()

def tela_novo_usuario(page: ft.Page, usuario_logado: dict):
    """Formulário para cadastrar um novo usuário."""

    def voltar(e):
        tela_config_usuarios(page, usuario_logado)

    def salvar(e):
        nome = txt_nome.value.strip() if txt_nome.value else ""
        email = txt_email.value.strip() if txt_email.value else ""
        senha = txt_senha.value if txt_senha.value else ""
        role = dropdown_role.value

        if not nome or not email or not senha:
            txt_erro.value = "Preencha todos os campos."
            page.update()
            return

        ok, msg = criar_usuario(nome, email, senha, role)
        if ok:
            tela_config_usuarios(page, usuario_logado)
        else:
            txt_erro.value = msg
            page.update()

    txt_nome = campo_tema(ft.TextField(label="Nome", autofocus=True, width=400))
    txt_email = campo_tema(ft.TextField(label="E-mail", width=400))
    txt_senha = campo_tema(ft.TextField(
        label="Senha", password=True, can_reveal_password=True, width=400
    ))
    dropdown_role = campo_tema(ft.Dropdown(
        label="Cargo",
        width=400,
        value="usuario",
        options=[
            ft.dropdown.Option("usuario", "Usuário"),
            ft.dropdown.Option("admin", "Admin"),
        ],
    ))
    txt_erro = ft.Text(value="", color=ft.Colors.RED, size=13)

    page.controls.clear()
    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Button("← Voltar", on_click=voltar),
                        
                        ft.Text("Novo Usuário", size=22, weight=ft.FontWeight.BOLD),
                    ]
                , wrap=True, run_spacing=12),
                ft.Divider(),
                txt_nome,
                txt_email,
                txt_senha,
                dropdown_role,
                txt_erro,
                ft.Button("Salvar", on_click=salvar, width=400, height=45),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    )
    page.update()

def tela_editar_usuario(page: ft.Page, usuario_logado: dict, user_id: int):
    """Tela de edição de um usuário existente."""

    def voltar(e):
        tela_config_usuarios(page, usuario_logado)

    def salvar_alteracoes(e):
        nome = txt_nome.value.strip() if txt_nome.value else ""
        email = txt_email.value.strip() if txt_email.value else ""
        role = dropdown_role.value
        nova_senha = txt_nova_senha.value if txt_nova_senha.value else ""

        if not nome or not email:
            txt_erro.value = "Nome e e-mail são obrigatórios."
            page.update()
            return

        ok, msg = atualizar_usuario(user_id, nome, email, role, nova_senha)
        if ok:
            txt_sucesso.value = msg
            txt_erro.value = ""
            txt_nova_senha.value = ""
            page.update()
            # Recarrega o estado do botão ativo
            u = buscar_usuario(user_id)
            if u:
                atualizar_botao_ativo(u["ativo"])
        else:
            txt_erro.value = msg
            txt_sucesso.value = ""
            page.update()

    def toggle_ativo(e):
        ok, msg, novo_estado = alternar_ativo(user_id)
        if ok:
            txt_sucesso.value = msg
            txt_erro.value = ""
            atualizar_botao_ativo(novo_estado)
            page.update()
        else:
            txt_erro.value = msg
            page.update()

    def atualizar_botao_ativo(ativo: bool):
        if ativo:
            btn_ativo.text = "Desativar Usuário"
            btn_ativo.icon = ft.Icons.PERSON_OFF_OUTLINED
            btn_ativo.color = ft.Colors.RED
            chip_status.value = "Ativo"
            chip_status.bgcolor = ft.Colors.GREEN_100
            chip_status.color = ft.Colors.GREEN_700
        else:
            btn_ativo.text = "Ativar Usuário"
            btn_ativo.icon = ft.Icons.PERSON_OUTLINE
            btn_ativo.color = ft.Colors.GREEN
            chip_status.value = "Inativo"
            chip_status.bgcolor = ft.Colors.RED_100
            chip_status.color = ft.Colors.RED_700
        page.update()

    # Buscar dados atuais
    usuario = buscar_usuario(user_id)
    if usuario is None:
        voltar(None)
        return

    txt_nome = campo_tema(ft.TextField(
        label="Nome", value=usuario["nome"], width=400
    ))
    txt_email = campo_tema(ft.TextField(
        label="E-mail", value=usuario["email"], width=400
    ))
    txt_nova_senha = campo_tema(ft.TextField(
        label="Nova Senha (deixe em branco para manter)",
        password=True,
        can_reveal_password=True,
        width=400,
    ))
    dropdown_role = campo_tema(ft.Dropdown(
        label="Cargo",
        width=400,
        value=usuario["role"],
        options=[
            ft.dropdown.Option("usuario", "Usuário"),
            ft.dropdown.Option("admin", "Admin"),
        ],
    ))
    txt_erro = ft.Text(value="", color=ft.Colors.RED, size=13)
    txt_sucesso = ft.Text(value="", color=ft.Colors.GREEN, size=13)

    chip_status = ft.Container(
        content=ft.Text(
            "Ativo" if usuario["ativo"] else "Inativo",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_700 if usuario["ativo"] else ft.Colors.RED_700,
        ),
        bgcolor=ft.Colors.GREEN_100 if usuario["ativo"] else ft.Colors.RED_100,
        padding=12,
        border_radius=20,
    )

    btn_ativo = ft.Button(
        "Desativar Usuário" if usuario["ativo"] else "Ativar Usuário",
        icon=ft.Icons.PERSON_OFF_OUTLINED if usuario["ativo"] else ft.Icons.PERSON_OUTLINE,
        color=ft.Colors.RED if usuario["ativo"] else ft.Colors.GREEN,
        on_click=toggle_ativo,
        width=200,
    )

    page.controls.clear()
    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Button("← Voltar", on_click=voltar),
                        
                        ft.Text("Editar Usuário", size=22, weight=ft.FontWeight.BOLD),
                    ]
                , wrap=True, run_spacing=12),
                ft.Divider(),
                ft.Row([ft.Text("Status: "), chip_status], wrap=True, run_spacing=12),
                txt_nome,
                txt_email,
                txt_nova_senha,
                dropdown_role,
                ft.Divider(),
                txt_erro,
                txt_sucesso,
                ft.Row(
                    [
                        ft.Button("Salvar Alterações", on_click=salvar_alteracoes, height=45),
                        btn_ativo,
                    ]
                , wrap=True, run_spacing=12),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    )
    page.update()

# ──────────────────────────────────────────────
#  NAVEGAÇÃO PRINCIPAL (com barra lateral)
# ──────────────────────────────────────────────
def abrir_app(page: ft.Page, usuario: dict):
    page.appbar = barra_empresa(page, lambda: abrir_app(page, usuario))


    # Container da área de Configurações (será preenchido dinamicamente)
    conteudo_config = ft.Column(
        [
            ft.Text("Configurações", size=22, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text("Carregando...", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def tela_historico(e=None):
        registros = listar_historico()
        tabela = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Data/Hora")),
                ft.DataColumn(ft.Text("Usuário")),
                ft.DataColumn(ft.Text("Tabela")),
                ft.DataColumn(ft.Text("Ação")),
                ft.DataColumn(ft.Text("ID Reg.")),
                ft.DataColumn(ft.Text("Detalhes")),
            ],
            rows=[],
            horizontal_lines=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.GREY_500)),
        )
        cores_acao = {
            "criar": ft.Colors.GREEN,
            "atualizar": ft.Colors.ORANGE_700,
            "excluir": ft.Colors.RED,
        }
        for r in registros:
            detalhes = ""
            try:
                d = json.loads(r["detalhes"] or "{}")
                partes = []
                if d.get("valores_anteriores"):
                    partes.append("Antes: " + json.dumps(d["valores_anteriores"], ensure_ascii=False)[:100])
                if d.get("valores_novos"):
                    partes.append("Depois: " + json.dumps(d["valores_novos"], ensure_ascii=False)[:100])
                detalhes = " | ".join(partes) if partes else "-"
            except Exception:
                detalhes = str(r.get("detalhes") or "-")
            data = str(r["data_alteracao"])
            acao = str(r["acao"])
            tabela.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(data, size=12, color=ft.Colors.ON_SURFACE_VARIANT)),
                        ft.DataCell(ft.Text(str(r["usuario_nome"] or "-"), size=13, weight=ft.FontWeight.W_600)),
                        ft.DataCell(ft.Text(str(r["tabela"] or "-"), size=12)),
                        ft.DataCell(ft.Text(acao.upper(), size=12, weight=ft.FontWeight.BOLD,
                                            color=cores_acao.get(acao, ft.Colors.BLUE))),
                        ft.DataCell(ft.Text(str(r["registro_id"]), size=12)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(detalhes, size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                            width=400,
                        )),
                    ]
                )
            )
        if not tabela.rows:
            area_conteudo.content = ft.Column(
                [
                    ft.Row([
                        ft.Button("← Voltar", on_click=lambda e: abrir_app(page, usuario),
                                  style=ft.ButtonStyle(color=ft.Colors.PRIMARY)),
                        
                        ft.Text("Histórico", size=22, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.ORANGE_400),
                    ], wrap=True, run_spacing=12),
                    ft.Divider(),
                    ft.Container(
                        content=ft.Text(
                            "Nenhum registro de histórico encontrado ainda.\n"
                            "As alterações em produtos aparecem aqui automaticamente.",
                            size=14, color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        padding=40,
                        alignment=ft.Alignment.CENTER,
                    ),
                ],
                expand=True,
            )
            page.update()
            return
        area_conteudo.content = ft.Column(
            [
                ft.Row([
                    ft.Button("← Voltar", on_click=lambda e: abrir_app(page, usuario),
                              style=ft.ButtonStyle(color=ft.Colors.PRIMARY)),
                    
                    ft.Text("Histórico de Alterações", size=22, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ORANGE_400),
                    ft.Container(width=20),
                    ft.Button("Atualizar", icon=ft.Icons.REFRESH,
                              on_click=tela_historico),
                ], wrap=True, run_spacing=12),
                ft.Divider(),
                ft.Container(
                    content=tabela_rolavel(tabela),
                    padding=10,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.GREY_400),
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        page.update()

    area_conteudo = ft.Container(expand=True, padding=20)

    def trocar_secao(e):
        indice = e.control.selected_index
        if indice == 0:
            # Geral
            tela_geral(page, usuario, area_conteudo)
            return
        elif indice == 1:
            # Produtos
            tela_produtos(page, usuario, area_conteudo)
            return
        elif indice == 2:
            # Configurações
            tela_config_usuarios(page, usuario)
            return
        elif indice == 3:
            # Histórico
            tela_historico()
            return
        page.update()

    rail = ft.NavigationRail(
        selected_index=0,
        on_change=trocar_secao,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=180,
        min_extended_width=200,
        leading=ft.Column(
            [
                ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=32, color=ft.Colors.BLUE_400),
                ft.Text("Arsenal", size=14, weight=ft.FontWeight.BOLD),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.LIST_OUTLINED,
                selected_icon=ft.Icons.LIST_ROUNDED,
                label="Geral",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.INVENTORY_OUTLINED,
                selected_icon=ft.Icons.INVENTORY,
                label="Produtos",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label="Configurações",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.HISTORY_OUTLINED,
                selected_icon=ft.Icons.HISTORY,
                label="Histórico",
            ),
        ],
        trailing=ft.Column(
            [
                ft.Divider(),
                ft.Container(
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.PERSON_OUTLINE, size=20, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(usuario["nome"], size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(usuario["role"].upper(), size=10, color=ft.Colors.BLUE_400),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                ft.TextButton(
                    "Sair",
                    icon=ft.Icons.LOGOUT_OUTLINED,
                    on_click=lambda e: tela_login(page),
                ),
            ],
        ),
    )

    estrutura = ft.Row(
        [rail, ft.VerticalDivider(width=1), area_conteudo], expand=True, spacing=0,
    )

    def ajustar_largura(e=None):
        if estrutura not in page.controls:
            return
        compacto = (page.width or 1100) < 900 or (getattr(page, "height", 650) or 650) < 600
        rail.min_width = 80 if compacto else 180
        rail.label_type = ft.NavigationRailLabelType.NONE if compacto else ft.NavigationRailLabelType.ALL
        rail.leading.controls[1].visible = not compacto
        rail.trailing.controls[1].visible = not compacto
        rail.trailing.controls[2].content = "" if compacto else "Sair"
        rail.trailing.controls[2].tooltip = "Sair"
        area_conteudo.padding = 12 if compacto else 24
        page.padding = 8 if compacto else 16
        page.update()

    page.on_resize = ajustar_largura
    page.clean()
    page.add(estrutura)
    ajustar_largura()
    tela_geral(page, usuario, area_conteudo)
    page.update()

# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
def main(page: ft.Page):
    criar_tabela_historico()
    page.title = "Arsenal Precificação"
    page.window.width = 1100
    page.window.height = 650
    page.window.min_width = 560
    page.window.min_height = 480
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.bgcolor = ft.Colors.SURFACE
    page.padding = 16
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    tela_login(page)

if __name__ == "__main__":
    ft.run(main)
