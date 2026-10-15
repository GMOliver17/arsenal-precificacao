"""Formulário compartilhado. Prévia e gravação utilizam o mesmo motor."""
import flet as ft
from precificacao import REGIOES_AMAZON
from servico_precificacao import previa
from produtos import buscar_produto, criar_produto, atualizar_produto
from ui_layout import grade_campos
from empresas import empresa_id, garantir_empresa


def formulario(page, usuario, area, plataforma, voltar, produto_id=None, condicao_ml=None):
    empresa_do_formulario = empresa_id()
    produto = buscar_produto(produto_id, plataforma, condicao_ml=condicao_ml) if produto_id is not None else {}
    if produto is None:
        area.content = ft.Text("Produto não encontrado.")
        page.update()
        return
    rotulos = [("sku", "SKU *"), ("descricao", "Descrição *"), ("marca", "Marca"),
               ("trib", "Custo unitário (Trib)"), ("quantidade", "Unidades no kit"),
               ("embalagem", "Embalagem do kit (R$)"), ("peso", "Peso total do kit (kg)"),
               ("preco_real", "Preço final de venda do kit (R$)"),
               ("sugestao_preco", "Sugestão de preço (R$)"),
               ("target_minimo", "Preço mínimo alvo (R$)")]
    campos = {}
    for chave, rotulo in rotulos:
        valor = produto.get(chave, 1 if chave == "quantidade" else "")
        campos[chave] = ft.TextField(label=rotulo, value=str(valor) if valor is not None else "")
    condicao = condicao_ml or produto.get("condicao") or "Premium"
    regiao = ft.Dropdown(label="Região Amazon (necessária a partir de R$ 200)", width=520,
                        value=produto.get("regiao"),
                        options=[ft.dropdown.Option(k, v) for k, v in REGIOES_AMAZON.items()])
    saidas = {k: ft.TextField(label=label, value=str(produto[k]) if produto.get(k) is not None else "",
                             read_only=True, width=250)
              for k, label in [("frete", "Frete / tarifa fixa (R$)"), ("lucro", "Lucro (R$)"),
                               ("margem_lucro", "Margem (%)"), ("vinte_por_cento", "Preço + 20% (R$)")]}
    mensagem = ft.Text(produto.get("mensagem_calculo") or "", selectable=True)

    def dados():
        d = {k: (campo.value or "").strip() for k, campo in campos.items()}
        if plataforma == "Mercado Livre":
            d["condicao"] = condicao
        if plataforma == "Amazon":
            d["regiao"] = regiao.value
        return d

    def atualizar_previa(e=None):
        try:
            garantir_empresa(empresa_do_formulario)
            d = dados()
            resultado = previa(plataforma, d, d)
            for k, campo in saidas.items():
                campo.value = str(resultado[k]) if resultado.get(k) is not None else ""
            mensagem.value = resultado["mensagem"] or "Prévia atualizada. Clique em Salvar para gravar."
            mensagem.color = ft.Colors.ORANGE_700 if resultado["status"] != "calculado" else ft.Colors.BLUE_700
        except Exception as exc:
            for campo in saidas.values():
                campo.value = ""
            mensagem.value = str(exc)
            mensagem.color = ft.Colors.RED
        page.update()

    def salvar(e=None):
        nonlocal produto_id
        botao_salvar.disabled = True
        page.update()
        try:
            garantir_empresa(empresa_do_formulario)
            if produto_id is None:
                ok, msg, novo_id = criar_produto(dados(), usuario, plataforma)
                if ok:
                    produto_id = novo_id
            else:
                ok, msg = atualizar_produto(produto_id, dados(), usuario, plataforma)
            mensagem.value = msg
            mensagem.color = ft.Colors.GREEN if ok else ft.Colors.RED
            if ok:
                # Continua no formulário, tornando explícitos inclusive os resultados pendentes.
                botao_salvar.disabled = False
                try:
                    salvo = buscar_produto(produto_id, plataforma, condicao_ml=condicao_ml)
                    if salvo:
                        for k, campo in saidas.items():
                            campo.value = str(salvo[k]) if salvo.get(k) is not None else ""
                except Exception:
                    mensagem.value += " Os dados foram salvos, mas a prévia não pôde ser recarregada."
            else:
                botao_salvar.disabled = False
        except Exception as exc:
            mensagem.value = f"Não foi salvo: {exc}"
            mensagem.color = ft.Colors.RED
            botao_salvar.disabled = False
        page.update()

    for chave in ("trib", "quantidade", "embalagem", "peso", "preco_real"):
        campos[chave].on_blur = atualizar_previa
    regiao.on_select = atualizar_previa
    botao_salvar = ft.Button("Salvar", on_click=salvar)
    controles = [ft.Button("← Voltar", on_click=lambda e: voltar()),
                 ft.Text(f"{plataforma} — {'Editar' if produto_id is not None else 'Novo'} produto", size=22),
                 grade_campos(list(campos.values()))]
    if plataforma == "Amazon":
        controles.append(grade_campos([regiao]))
    controles.extend([ft.Divider(), grade_campos(list(saidas.values()), {"xs": 12, "sm": 6, "lg": 3}),
                      mensagem, botao_salvar])
    area.content = ft.Column(controles, spacing=16, scroll=ft.ScrollMode.AUTO, expand=True,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    page.update()
