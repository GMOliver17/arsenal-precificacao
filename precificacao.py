"""Motor puro: preço e embalagem do kit; custo unitário × unidades do kit."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata

VERSAO = 1
PLATAFORMAS = {"Mercado Livre": "produtos_ml", "Amazon": "produtos_amazon",
               "Shopee": "produtos_shopee", "TikTok": "produtos_tiktok",
               "Magalu": "produtos_magalu", "Kwai": "produtos_kwai"}
REGIOES_AMAZON = {"sp_capital": "SP Capital", "outras_capitais_sul_sudeste": "Outras capitais Sul/Sudeste",
                  "interior_sul_sudeste": "Interior Sul/Sudeste", "centro_oeste_norte_nordeste": "Centro-Oeste/Norte/Nordeste"}
ZERO = Decimal("0")

class Incompleto(ValueError):
    pass

def numero(valor, nome="Valor", padrao=None):
    if valor is None or str(valor).strip() == "":
        if padrao is not None:
            return Decimal(str(padrao))
        raise Incompleto(f"Informe {nome}.")
    try:
        n = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"{nome} inválido.") from None
    if not n.is_finite() or n < 0:
        raise ValueError(f"{nome} deve ser um número não negativo.")
    return n

def dinheiro(n):
    return n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def normalizar(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto).lower()) if not unicodedata.combining(c))

def numeros(texto):
    return [Decimal(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", str(texto))]

def faixa_preco(texto, preco):
    txt = normalizar(texto)
    nums = numeros(txt)
    if not nums:
        return False
    if "acima" in txt:
        return preco > nums[0]
    if "mais" in txt:
        return preco >= nums[0]  # compatível com a tabela existente (500 incluso)
    if "ate" in txt:
        return preco <= nums[-1]
    return len(nums) >= 2 and nums[0] <= preco <= nums[-1]

def por_faixa(linhas, campo, preco):
    # Ordenação explícita: no limite sobreposto 30, a faixa "até 30" prevalece.
    for linha in sorted(linhas, key=lambda r: r.get("id", 0)):
        if faixa_preco(linha.get(campo, ""), preco):
            return linha
    raise Incompleto(f"Faixa de preço não cadastrada para {preco}.")

def unica(linhas, descricao):
    if len(linhas) != 1:
        raise Incompleto(f"{descricao}: esperado um registro, encontrados {len(linhas)}.")
    return linhas[0]

def canal(regras, nome):
    return [r for r in regras["tabela_taxas_comissoes"] if normalizar(r["canal"]) == normalizar(nome)]

def taxa_padrao(regras, nome, condicao="Padrão"):
    return unica([r for r in canal(regras, nome) if normalizar(r["condicao"]) == normalizar(condicao)], f"Taxa {nome}/{condicao}")

def limites_peso(label):
    txt = normalizar(label)
    tokens = re.findall(r"(\d+(?:[.,]\d+)?)\s*(kg|g)?", txt)
    if not tokens:
        return None
    unidade_final = next((u for _, u in reversed(tokens) if u), "kg")
    vals = [Decimal(n.replace(",", ".")) / (1000 if (u or unidade_final) == "g" else 1) for n, u in tokens]
    if len(vals) == 1:
        return (vals[0], Decimal("Infinity")) if "mais" in txt or "acima" in txt else (ZERO, vals[0])
    return vals[0], vals[-1]

def peso_em_kg(valor):
    """Sem unidade, o cadastro usa kg; unidades explícitas g/kg são convertidas."""
    if isinstance(valor, str):
        m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(kg|g)\s*", valor, re.I)
        if m:
            n = numero(m[1], "peso")
            return n / 1000 if m[2].lower() == "g" else n
    return numero(valor, "peso em kg")

def selecionar_faixa_peso(linhas, peso):
    peso = peso_em_kg(peso)
    faixas = []
    adicional = None
    for r in linhas:
        if "adicional" in normalizar(r["peso"]):
            adicional = r
            continue
        limites = limites_peso(r["peso"])
        if limites:
            faixas.append((*limites, r))
    faixas.sort(key=lambda f: (f[1], f[0]))
    for minimo, maximo, r in faixas:
        if minimo <= peso <= maximo:
            return r, ZERO, None
    if faixas and adicional is not None and peso > faixas[-1][1]:
        _, maximo, r = faixas[-1]
        return r, peso - maximo, adicional
    raise Incompleto("Faixa de peso não cadastrada.")

def frete_peso(linhas, coluna, peso):
    linha, excedente, adicional = selecionar_faixa_peso(linhas, peso)
    frete = numero(linha.get(coluna), "frete")
    if adicional is not None:
        frete += excedente * numero(adicional.get(coluna), "valor por kg adicional")
    return dinheiro(frete)

def coluna_ml(preco):
    for limite, coluna in [("18.99", "faixa_0_18_99"), ("48.99", "faixa_19_48_99"),
                           ("78.99", "faixa_49_78_99"), ("99.99", "faixa_79_99_99"),
                           ("119.99", "faixa_100_119_99"), ("149.99", "faixa_120_149_99"),
                           ("199.99", "faixa_150_199_99")]:
        if preco <= Decimal(limite):
            return coluna
    return "faixa_200_mais"

def frete_amazon(regras, peso, preco, regiao=None):
    preco = numero(preco, "preço")
    if preco < 79:
        r = por_faixa(canal(regras, "Amazon"), "condicao", preco)
        return numero(r.get("taxa_fixa_reais"), "tarifa Amazon")
    if preco >= 200:
        if regiao not in REGIOES_AMAZON:
            raise Incompleto("Selecione a região Amazon para preço a partir de R$ 200.")
        return frete_peso(regras["tabela_frete_amazon_brl200"], regiao, peso)
    for limite, coluna in [("99.99", "faixa_79_99_99"), ("119.99", "faixa_100_119_99"),
                           ("149.99", "faixa_120_149_99"), ("199.99", "faixa_150_199_99")]:
        if preco <= Decimal(limite):
            return frete_peso(regras["tabela_frete_amazon"], coluna, peso)
    raise Incompleto("Preço fora da faixa Amazon.")

def totais(preco, taxa, imposto, frete, embalagem, custo, quantidade, afiliado=0, fixa=0):
    preco = numero(preco, "preço")
    qtd = numero(quantidade, "unidades do kit")
    if qtd < 1 or qtd != qtd.to_integral_value():
        raise Incompleto("Unidades do kit deve ser um inteiro maior que zero.")
    valores = {"comissao": preco * numero(taxa, "comissão") / 100,
               "imposto": preco * numero(imposto, "imposto") / 100,
               "afiliado": preco * numero(afiliado, "afiliado") / 100,
               "taxa_fixa": numero(fixa, "taxa fixa"), "frete": numero(frete, "frete"),
               "embalagem": numero(embalagem, "embalagem"),
               "custo_itens": numero(custo, "custo unitário") * qtd}
    # Centavos por componente, mantendo o total auditável pela soma dos descontos.
    valores = {k: dinheiro(v) for k, v in valores.items()}
    lucro = dinheiro(preco - sum(valores.values()))
    return {**valores, "lucro": lucro, "margem_lucro": dinheiro(lucro / preco * 100) if preco else ZERO,
            "vinte_por_cento": dinheiro(preco * Decimal("1.20"))}

def simular_condicao_ml(produto, condicao, regras):
    """Troca somente a comissão/tarifa do anúncio sobre o resultado salvo."""
    destino = taxa_padrao(regras, "Mercado Livre", condicao)
    resultado = dict(produto)
    if produto.get("preco_real") is None or produto.get("lucro") is None:
        return resultado
    preco = numero(produto["preco_real"], "preço")
    if preco <= 0:
        return resultado
    origem = taxa_padrao(regras, "Mercado Livre", produto.get("condicao") or "Premium")
    taxa_antiga = produto.get("taxa_percentual")
    fixa_antiga = produto.get("taxa_fixa")
    taxa_antiga = origem["taxa_percentual"] if taxa_antiga is None else taxa_antiga
    fixa_antiga = origem.get("taxa_fixa_reais") if fixa_antiga is None else fixa_antiga
    comissao_antiga = dinheiro(preco * numero(taxa_antiga) / 100)
    comissao_nova = dinheiro(preco * numero(destino["taxa_percentual"]) / 100)
    fixa_antiga = dinheiro(numero(fixa_antiga, padrao=0))
    fixa_nova = dinheiro(numero(destino.get("taxa_fixa_reais"), padrao=0))
    lucro = dinheiro(Decimal(str(produto["lucro"])) + comissao_antiga + fixa_antiga - comissao_nova - fixa_nova)
    resultado.update(lucro=lucro, margem_lucro=dinheiro(lucro / preco * 100),
                     condicao=condicao, taxa_percentual=numero(destino["taxa_percentual"]),
                     comissao=comissao_nova, taxa_fixa=fixa_nova)
    return resultado

def calcular(plataforma, produto, oferta, regras):
    if plataforma not in PLATAFORMAS:
        raise ValueError("Plataforma inválida.")
    parametros = {"condicao": oferta.get("condicao") or "Premium", "regiao": oferta.get("regiao")}
    base = {"versao": VERSAO, "parametros": parametros}
    try:
        preco = numero(oferta.get("preco_real"), "preço final do kit")
        if preco <= 0:
            raise Incompleto("Informe preço final do kit maior que zero.")
        if preco != dinheiro(preco):
            raise ValueError("Preço deve ter no máximo duas casas decimais.")
        imposto = numero(unica(canal(regras, "Imposto"), "Imposto")["taxa_percentual"], "imposto")
        taxa = afiliado = fixa = frete = ZERO
        if plataforma == "Mercado Livre":
            r = taxa_padrao(regras, plataforma, parametros["condicao"])
            taxa = numero(r["taxa_percentual"])
            fixa = numero(r.get("taxa_fixa_reais"), padrao=0)
            frete = frete_peso(regras["tabela_frete_ml"], coluna_ml(preco), produto.get("peso"))
        elif plataforma == "Amazon":
            taxa = numero(taxa_padrao(regras, plataforma)["taxa_percentual"])
            frete = frete_amazon(regras, produto.get("peso"), preco, parametros["regiao"])
        elif plataforma == "Shopee":
            r = por_faixa(regras["tabela_frete_shopee"], "valor_do_produto", preco)
            taxa, frete = numero(r["taxa_percentual"]), numero(r["taxa_fixa_reais"])
        elif plataforma == "TikTok":
            linhas = canal(regras, plataforma)
            r = por_faixa(linhas, "condicao", preco)
            taxa, frete = numero(r["taxa_percentual"]), numero(r["taxa_fixa_reais"])
            af = [r for r in linhas if "afiliado" in normalizar(r["condicao"])]
            afiliado = numero(unica(af, "Afiliado TikTok")["taxa_percentual"]) if af else ZERO
        else:
            r = taxa_padrao(regras, plataforma)
            taxa = numero(r["taxa_percentual"])
            # Magalu preserva a regra existente sem frete/afiliado.
            frete = numero(r.get("taxa_fixa_reais"), padrao=0) if plataforma == "Kwai" else ZERO
        resultado = totais(preco, taxa, imposto, frete, produto.get("embalagem"), produto.get("trib"),
                           produto.get("quantidade"), afiliado, fixa)
        return {**base, **resultado, "status": "calculado", "mensagem": "",
                "taxa_percentual": taxa, "imposto_percentual": imposto, "afiliado_percentual": afiliado,
                "preco_base": preco}
    except Incompleto as e:
        return {**base, "status": "pendente", "mensagem": str(e), "frete": None, "lucro": None,
                "margem_lucro": None, "vinte_por_cento": None}
