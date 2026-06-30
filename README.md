# NoDup

O **NoDup** é um localizador e gerenciador de imagens duplicadas.

---

## Como Usar

### Pré-requisitos
Certifique-se de ter o Python 3 instalado em sua máquina. O projeto já inclui o arquivo `requirements.txt` com as dependências necessárias (PySide6).

### Passo a Passo

1. **Instalar Dependências**:
   No terminal ou prompt de comando (com o seu ambiente virtual ativado, se preferir), instale os pacotes:
   ```bash
   pip install -r requirements.txt
   ```

2. **Executar o Programa**:
   Inicie a interface gráfica executando o arquivo `gui.py`:
   ```bash
   python gui.py
   ```

3. **Escanear**:
   - Clique em **"Selecionar Pasta"** na aba **Varredura**.
   - Escolha o diretório desejado e clique em **"Iniciar Varredura"**.
   - Ao concluir, o programa irá redirecionar você automaticamente para a aba **"Imagens Duplicadas"**.

4. **Gerenciar Duplicados**:
   - Dê um **duplo clique** na miniatura de qualquer imagem na grade para ver todos os locais onde ela existe.
   - Marque as caixas de seleção (checkboxes) das cópias que deseja apagar física e logicamente.
   - Clique em **"Excluir Cópias Selecionadas"** para apagá-las de seu computador de forma definitiva.

---

## Como Ele Age

O funcionamento do NoDup é dividido em três etapas otimizadas:

1. **Mapeamento Rápido**: O programa faz uma varredura listando todos os arquivos com as extensões `.png`, `.jpg` e `.jpeg`.
2. **Cálculo de Hash (SHA-256)**: Os arquivos são lidos e transformados em um hash SHA-256 único baseado no seu **conteúdo binário**. Isso garante que imagens idênticas sejam localizadas mesmo que tenham nomes ou extensões diferentes.

---

## Tecnologias Utilizadas

* **Python 3** - Linguagem principal do projeto.
* **PySide6** - Interface gráfica moderna (Qt6).
* **SQLite3** - Banco de dados local leve e veloz para indexação.
* **Hashlib** - Geração segura de hashes SHA-256 para comparação binária de arquivos.
