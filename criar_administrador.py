"""Prepara um banco configurado e cria o primeiro usuário, sem senha padrão."""
from getpass import getpass
from pathlib import Path

from db import _pasta_base
from servico_precificacao import inicializar
from usuarios import criar_usuario, listar_usuarios


def main():
    if not (Path(_pasta_base()) / 'config.json').is_file():
        raise SystemExit('Copie config.example.json para config.json e configure o banco primeiro.')
    inicializar()
    if listar_usuarios():
        raise SystemExit('O banco já tem usuários. Utilize o cadastro de usuários do aplicativo.')
    nome = input('Nome de usuário: ').strip()
    email = input('E-mail: ').strip()
    senha = getpass('Senha: ')
    confirmacao = getpass('Confirme a senha: ')
    if not nome or not email or not senha or senha != confirmacao:
        raise SystemExit('Preencha todos os dados e informe senhas iguais.')
    ok, mensagem = criar_usuario(nome, email, senha, 'admin')
    print(mensagem)
    if not ok:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
