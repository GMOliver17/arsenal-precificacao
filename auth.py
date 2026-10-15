import bcrypt
from db import get_connection

def validar_login(username: str, password: str) -> dict | None:
    """
    Valida as credenciais do usuário contra o banco.

    Retorna um dict com id, nome, email e role se válido.
    Retorna None se inválido ou inativo.
    """
    conn = get_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, nome, email, senha_hash, role, ativo "
            "FROM usuarios WHERE nome = %s",
            (username,)
        )
        usuario = cursor.fetchone()

        if usuario is None:
            return None

        if not usuario["ativo"]:
            return None

        # senha_hash vem como string do banco — converte para bytes
        senha_hash = usuario["senha_hash"]
        if isinstance(senha_hash, str):
            senha_hash = senha_hash.encode("utf-8")

        if not bcrypt.checkpw(password.encode("utf-8"), senha_hash):
            return None

        return {
            "id": usuario["id"],
            "nome": usuario["nome"],
            "email": usuario["email"],
            "role": usuario["role"],
        }
    finally:
        conn.close()
