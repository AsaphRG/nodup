import os, hashlib, pathlib, sqlite3

# localização, nome do arquivo, hash gerado

def main(path_parameter: str, progress_callback=None, total_callback=None, cancel_callback=None):
    path = pathlib.Path(path_parameter)
    if not path.exists() or not path.is_dir():
        raise ValueError("O caminho especificado não existe ou não é um diretório válido.")

    # Conectar ao SQLite e criar a tabela se não existir
    db_path = './imagens.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caminho TEXT NOT NULL,
            nome TEXT NOT NULL,
            hash TEXT NOT NULL
        )
    ''')
    conn.commit()

    # Mapear todos os arquivos primeiro (rápido) para saber o total
    arquivos_validos = []
    for root, dirs, files in os.walk(path):
        for file in files:
            parts = file.split('.')
            if len(parts) > 1 and parts[-1].lower() in ["png", "jpeg", "jpg"]:
                arquivos_validos.append((root, file))

    total_arquivos = len(arquivos_validos)
    if total_callback:
        total_callback(total_arquivos)

    # Obter os registros existentes para evitar inserções duplicadas
    cursor.execute("SELECT caminho, nome, hash FROM imagens")
    existentes = cursor.fetchall()
    # Dicionário mapeando (caminho, nome) -> hash
    existentes_dict = {(row[0], row[1]): row[2] for row in existentes}

    dados_para_salvar = []
    erros = []
    count = 0
    is_interrupted = False

    # Processar cada arquivo (lento, com hashing)
    for root, file in arquivos_validos:
        if cancel_callback and cancel_callback():
            is_interrupted = True
            break
        try:
            file_path = os.path.join(root, file)
            with open(file_path, 'rb') as img:
                content = img.read()
                hash_gerado = hashlib.sha256(content).hexdigest()
                
                chave = (root, file)
                if chave in existentes_dict:
                    # Se o hash mudou, remove o registro antigo do banco e prepara para salvar o novo
                    if existentes_dict[chave] != hash_gerado:
                        cursor.execute("DELETE FROM imagens WHERE caminho = ? AND nome = ?", chave)
                        dados_para_salvar.append((root, file, hash_gerado))
                    # Se o hash é idêntico, ignora a inserção
                else:
                    # Registro novo, prepara para salvar
                    dados_para_salvar.append((root, file, hash_gerado))
                
                count += 1
                
                if progress_callback:
                    progress_callback(count)
        except Exception as e:
            erros.append(f'{e}: {file}')

    if dados_para_salvar:
        cursor.executemany('''
            INSERT INTO imagens (caminho, nome, hash)
            VALUES (?, ?, ?)
        ''', dados_para_salvar)
        conn.commit()

    cursor.close()
    conn.close()

    return {
        "total_processado": count,
        "erros": erros,
        "interrompido": is_interrupted
    }

def buscar_duplicados():
    db_path = './imagens.db'
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Busca apenas os arquivos que possuem hash com contagem maior que 1
    cursor.execute('''
        SELECT id, caminho, nome, hash 
        FROM imagens 
        WHERE hash IN (
            SELECT hash FROM imagens GROUP BY hash HAVING COUNT(*) > 1
        )
        ORDER BY hash, caminho, nome
    ''')
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return [
        {"id": row[0], "caminho": row[1], "nome": row[2], "hash": row[3]}
        for row in rows
    ]

def excluir_registro_e_arquivo(id_registro: int):
    db_path = './imagens.db'
    if not os.path.exists(db_path):
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT caminho, nome FROM imagens WHERE id = ?", (id_registro,))
    row = cursor.fetchone()
    if row:
        caminho, nome = row
        file_path = os.path.join(caminho, nome)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        cursor.execute("DELETE FROM imagens WHERE id = ?", (id_registro,))
        conn.commit()
        
    cursor.close()
    conn.close()
    return True

if __name__ == "__main__":
    # Exemplo de uso CLI caso executado diretamente
    import sys
    if len(sys.argv) > 1:
        resultado = main(sys.argv[1])
        print(f"Varredura concluída. Imagens processadas: {resultado['total_processado']}")
        if resultado['erros']:
            print(f"Erros encontrados: {len(resultado['erros'])}")
    else:
        print("Uso: python main.py <caminho_da_pasta>")



