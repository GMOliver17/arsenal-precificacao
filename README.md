# Arsenal Precificação

Aplicativo desktop para organizar produtos e calcular preços, frete, lucro e margem em seis marketplaces: Mercado Livre, Amazon, Shopee, TikTok, Magalu e Kwai.

O projeto foi desenvolvido para facilitar a comparação de resultados por plataforma e manter os cálculos salvos no MySQL. Oferece cadastro de empresas, configuração de taxas e fretes, filtros e exportação para Excel.

## Funcionalidades

- Produtos e regras de precificação separados por empresa.
- Cálculo de frete por faixa de peso e preço, conforme as tabelas configuradas.
- Simulação Premium/Clássico no Mercado Livre.
- Cálculo e persistência dos resultados ao salvar alterações relevantes.
- Indicadores de ticket e margem média, comparação entre plataformas e histórico de alterações.
- Colunas selecionáveis e exportação para Excel.
- Interface com temas claro e escuro e layout adaptável à janela.
- Login com senhas protegidas por bcrypt.

As tabelas de tarifas são configuráveis. O aplicativo não consulta APIs dos marketplaces; quem utiliza o sistema precisa cadastrar e manter as regras comerciais aplicáveis.

## Tecnologias

Python, Flet, MySQL, MySQL Connector/Python, Decimal, bcrypt e openpyxl. O empacotamento para Windows utiliza PyInstaller.

## Executar localmente

Requisitos: Python 3.12, MySQL 8.0 ou superior e ambiente desktop. O fluxo de execução foi validado em Windows.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

1. Crie um banco vazio no MySQL.
2. Selecione esse banco no seu cliente SQL e execute `sql/estrutura_inicial.sql`.
3. Preencha `config.json` com seu servidor, porta, banco e credenciais.
4. Execute `python criar_administrador.py` para preparar as estruturas adicionais e cadastrar o primeiro administrador.
5. Execute `python main.py` e entre com o usuário criado.
6. Edite o cadastro da empresa inicial e configure taxas e fretes antes de cadastrar produtos.

O repositório contém apenas a estrutura vazia do banco. A empresa inicial utiliza dados fictícios; produtos, usuários e regras comerciais de produção não são distribuídos. As regras em `tests/fixtures` são referências para testes e não são carregadas no banco do aplicativo.

Para atualizar uma instalação antiga, faça backup, feche o aplicativo e execute `atualizar_banco_original.sql` no banco de destino. Esse arquivo prepara a estrutura e preserva os resultados existentes; o comando Recalcular do aplicativo atualiza os resultados com o motor atual. Dados obrigatórios ausentes geram resultados pendentes.

## Testes

```powershell
python -B -m unittest discover -s tests
```

A suíte verifica cálculos, limites de faixas de frete, persistência e isolamento entre empresas com SQLite em memória. Ela bloqueia conexões ao banco real. O adaptador SQLite não certifica a sintaxe nem os bloqueios do MySQL.

`python tests/validar_mysql_multiempresa.py` é uma validação de integração opcional: requer um banco configurado e permissão para criar e remover um banco temporário. O script copia os dados para esse banco temporário e testa a migração e o isolamento sem gravar no banco de origem.

## Organização

| Arquivo | Responsabilidade |
| --- | --- |
| `main.py` e `ui_*.py` | Navegação, formulários e apresentação |
| `precificacao.py` | Fórmulas com Decimal e seleção das faixas de frete |
| `servico_precificacao.py` | Gravação transacional das entradas e resultados |
| `produtos.py` e `fretes.py` | Consultas e manutenção dos dados |
| `empresas.py` | Cadastro e contexto da empresa selecionada |
| `migracao_multiempresa.py` | Atualização da estrutura com backup prévio |
| `auth.py` e `usuarios.py` | Autenticação e cadastro de usuários |
| `tests/` | Testes automatizados e prévia com dados de demonstração |

As tabelas das plataformas pertencem à empresa por meio do produto. O usuário de login é global: a separação de dados por empresa não implementa permissões individuais de acesso a cada empresa.

## Executável Windows

```powershell
python -m pip install -r requirements-dev.txt
python main.py
# Feche a janela após a primeira abertura: ela disponibiliza o cliente desktop do Flet.
python -m PyInstaller --noconfirm ArsenalPrecificacao.spec
```

O arquivo será gerado em `dist/ArsenalPrecificacao.exe`. Coloque sua própria cópia de `config.json` ao lado dele. O MySQL continua necessário. Não publique configurações com senhas nem pacotes contendo dados reais.
