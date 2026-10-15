import bcrypt
from db import get_connection

def listar_usuarios() -> list[dict]:
    """Retorna todos os usuários cadastrados."""
    conn = get_connection()
    if conn is None:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, nome, email, role, ativo, created_at "
            "FROM usuarios ORDER BY nome"
        )
        return cursor.fetchall()
    finally:
        conn.close()

def buscar_usuario(user_id: int) -> dict | None:
    """Retorna os dados de um usuário pelo ID."""
    conn = get_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, nome, email, role, ativo, created_at "
            "FROM usuarios WHERE id = %s",
            (user_id,)
        )
        return cursor.fetchone()
    finally:
        conn.close()

def criar_usuario(nome: str, email: str, senha: str, role: str = "usuario") -> tuple[bool, str]:
    """
    Cria um novo usuário com senha hasheada.
    Retorna (sucesso, mensagem).
    """
    conn = get_connection()
    if conn is None:
        return False, "Falha ao conectar no banco."

    try:
        cursor = conn.cursor()

        # Verificar se o email já existe
        cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        if cursor.fetchone() is not None:
            return False, "Já existe um usuário com este e-mail."

        senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt())

        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, role) "
            "VALUES (%s, %s, %s, %s)",
            (nome, email, senha_hash.decode("utf-8"), role)
        )
        conn.commit()
        return True, "Usuário criado com sucesso."
    except Exception as e:
        return False, f"Erro ao criar usuário: {e}"
    finally:
        conn.close()

def atualizar_usuario(user_id: int, nome: str, email: str, role: str, nova_senha: str = "") -> tuple[bool, str]:
    """
    Atualiza os dados de um usuário.
    Se nova_senha não for vazia, atualiza a senha também.
    Retorna (sucesso, mensagem).
    """
    conn = get_connection()
    if conn is None:
        return False, "Falha ao conectar no banco."

    try:
        cursor = conn.cursor()

        # Verificar conflito de email com outro usuário
        cursor.execute(
            "SELECT id FROM usuarios WHERE email = %s AND id != %s",
            (email, user_id)
        )
        if cursor.fetchone() is not None:
            return False, "Outro usuário já usa este e-mail."

        if nova_senha:
            senha_hash = bcrypt.hashpw(nova_senha.encode("utf-8"), bcrypt.gensalt())
            cursor.execute(
                "UPDATE usuarios SET nome = %s, email = %s, role = %s, senha_hash = %s "
                "WHERE id = %s",
                (nome, email, role, senha_hash.decode("utf-8"), user_id)
            )
        else:
            cursor.execute(
                "UPDATE usuarios SET nome = %s, email = %s, role = %s "
                "WHERE id = %s",
                (nome, email, role, user_id)
            )

        conn.commit()
        return True, "Usuário atualizado com sucesso."
    except Exception as e:
        return False, f"Erro ao atualizar: {e}"
    finally:
        conn.close()

def alternar_ativo(user_id: int) -> tuple[bool, str, bool | None]:
    """
    Ativa ou desativa um usuário (toggle).
    Retorna (sucesso, mensagem, novo_estado_ativo).
    """
    conn = get_connection()
    if conn is None:
        return False, "Falha ao conectar no banco.", None

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT ativo FROM usuarios WHERE id = %s", (user_id,))
        resultado = cursor.fetchone()
        if resultado is None:
            return False, "Usuário não encontrado.", None

        ativo_atual = bool(resultado[0])
        novo_estado = not ativo_atual

        cursor.execute(
            "UPDATE usuarios SET ativo = %s WHERE id = %s",
            (novo_estado, user_id)
        )
        conn.commit()

        msg = "Usuário ativado." if novo_estado else "Usuário desativado."
        return True, msg, novo_estado
    except Exception as e:
        return False, f"Erro: {e}", None
    finally:
        conn.close()
