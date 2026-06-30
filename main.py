import os, hashlib, pathlib, sqlite3, send2trash, collections

# localização, nome do arquivo, hash gerado

def inicializar_banco():
    db_path = './imagens.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caminho TEXT NOT NULL,
            nome TEXT NOT NULL,
            hash TEXT NOT NULL,
            hash_perceptivo TEXT
        )
    ''')
    conn.commit()

    try:
        cursor.execute("ALTER TABLE imagens ADD COLUMN hash_perceptivo TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagens_hash ON imagens(hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_imagens_hash_perceptivo ON imagens(hash_perceptivo)")
    conn.commit()

    cursor.close()
    conn.close()

def main(path_parameter: str, progress_callback=None, total_callback=None, cancel_callback=None):
    inicializar_banco()

    path = pathlib.Path(path_parameter)
    if not path.exists() or not path.is_dir():
        raise ValueError("O caminho especificado não existe ou não é um diretório válido.")

    db_path = './imagens.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
    cursor.execute("SELECT caminho, nome, hash, hash_perceptivo FROM imagens")
    existentes = cursor.fetchall()
    # Dicionário mapeando (caminho, nome) -> (hash, hash_perceptivo)
    existentes_dict = {(row[0], row[1]): (row[2], row[3]) for row in existentes}

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
                sha256 = hashlib.sha256()
                while chunk := img.read(65536):
                    sha256.update(chunk)
                hash_gerado = sha256.hexdigest()
                
                # Calcular hash perceptivo
                hash_perceptivo = None
                try:
                    from PIL import Image
                    import imagehash
                    with Image.open(file_path) as pimg:
                        hash_perceptivo = str(imagehash.dhash(pimg))
                except Exception:
                    pass

                chave = (root, file)
                if chave in existentes_dict:
                    old_hash, old_phash = existentes_dict[chave]
                    # Se o hash mudou, ou se não tinha hash perceptivo, recarrega
                    if old_hash != hash_gerado or old_phash is None:
                        cursor.execute("DELETE FROM imagens WHERE caminho = ? AND nome = ?", chave)
                        dados_para_salvar.append((root, file, hash_gerado, hash_perceptivo))
                else:
                    dados_para_salvar.append((root, file, hash_gerado, hash_perceptivo))
                
                count += 1
                
                if progress_callback:
                    progress_callback(count)
        except Exception as e:
            erros.append(f'{e}: {file}')

    if dados_para_salvar:
        cursor.executemany('''
            INSERT INTO imagens (caminho, nome, hash, hash_perceptivo)
            VALUES (?, ?, ?, ?)
        ''', dados_para_salvar)
        conn.commit()

    cursor.close()
    conn.close()

    return {
        "total_processado": count,
        "erros": erros,
        "interrompido": is_interrupted
    }

def buscar_duplicados(modo="exato", tolerancia=4):
    inicializar_banco()
    
    db_path = './imagens.db'
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if modo == "exato":
        cursor.execute('''
            SELECT id, caminho, nome, hash, hash_perceptivo 
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
            {"id": row[0], "caminho": row[1], "nome": row[2], "hash": row[3], "hash_perceptivo": row[4]}
            for row in rows
        ]
    else:
        # Modo Similar (Visual): buscar todas as imagens com hash perceptivo
        cursor.execute('''
            SELECT id, caminho, nome, hash, hash_perceptivo 
            FROM imagens 
            WHERE hash_perceptivo IS NOT NULL AND hash_perceptivo != ''
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        imagens = [
            {"id": row[0], "caminho": row[1], "nome": row[2], "hash_original": row[3], "hash_perceptivo": row[4]}
            for row in rows
        ]
        
        # Agrupamento via Union-Find baseado na distância de Hamming
        parent = {img["id"]: img["id"] for img in imagens}
        
        def find(i):
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]
            
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j
                
        def hamming_distance(h1, h2):
            try:
                diff = int(h1, 16) ^ int(h2, 16)
                return bin(diff).count('1')
            except ValueError:
                return 999
        
        # Comparação em pares
        n = len(imagens)
        for i in range(n):
            for j in range(i + 1, n):
                if hamming_distance(imagens[i]["hash_perceptivo"], imagens[j]["hash_perceptivo"]) <= tolerancia:
                    union(imagens[i]["id"], imagens[j]["id"])
                    
        # Agrupar por raiz
        grupos_dict = collections.defaultdict(list)
        for img in imagens:
            root_id = find(img["id"])
            grupos_dict[root_id].append(img)
            
        # Filtrar apenas grupos com duplicados (> 1)
        resultado = []
        for root_id, grupo in grupos_dict.items():
            if len(grupo) > 1:
                grupo.sort(key=lambda x: (x["caminho"], x["nome"]))
                # Usar o hash perceptivo do representante para compatibilidade de agrupamento na UI
                hash_grupo = grupo[0]["hash_perceptivo"]
                for img in grupo:
                    resultado.append({
                        "id": img["id"],
                        "caminho": img["caminho"],
                        "nome": img["nome"],
                        "hash": hash_grupo,
                        "hash_perceptivo": img["hash_perceptivo"]
                    })
                    
        # Ordenar resultado final para consistência
        resultado.sort(key=lambda x: (x["hash"], x["caminho"], x["nome"]))
        return resultado

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
            send2trash.send2trash(file_path)
        
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



