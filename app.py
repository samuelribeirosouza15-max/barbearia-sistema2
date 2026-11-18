
from flask import Flask, request, jsonify, render_template, session, redirect
import sqlite3
import urllib.parse
import datetime
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chave_secreta_barbearia'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def conectar_db():
    conn = sqlite3.connect('barbearia.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = conectar_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, email TEXT, telefone TEXT, senha TEXT, tipo TEXT, foto TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servicos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, preco REAL, duracao INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profissionais 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, especialidade TEXT, status TEXT DEFAULT 'Disponivel', foto TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agendamentos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, cliente_nome TEXT, profissional TEXT, data TEXT, hora TEXT, servico TEXT, avaliacao INTEGER DEFAULT 0)''')
    
    c.execute("SELECT * FROM usuarios WHERE tipo='barbeiro'")
    if not c.fetchone():
        senha_hash = generate_password_hash('123')
        c.execute("INSERT INTO usuarios (nome, email, telefone, senha, tipo) VALUES ('Admin', 'admin@barbearia.com', '62994016649', ?, 'barbeiro')", (senha_hash,))
    
    c.execute("SELECT * FROM servicos")
    if not c.fetchone():
        servicos = [('Corte', 40.00, 30), ('Barba', 30.00, 30), ('Corte + Barba', 60.00, 60), ('Pigmentação', 50.00, 30)]
        c.executemany("INSERT INTO servicos (nome, preco, duracao) VALUES (?, ?, ?)", servicos)

    c.execute("SELECT * FROM profissionais")
    if not c.fetchone():
        profissionais = [('Gestão (Dono)', 'Mestre', 'Disponivel', ''), ('Gustavo', 'Cabelo', 'Disponivel', ''), ('Japa', 'Barba', 'Disponivel', '')]
        c.executemany("INSERT INTO profissionais (nome, especialidade, status, foto) VALUES (?, ?, ?, ?)", profissionais)
    
    conn.commit()
    conn.close()

@app.route('/')
def home():
    nome_cliente = session.get('user_nome', None)
    return render_template('index.html', nome_cliente=nome_cliente)

@app.route('/tela_agendamento')
def tela_agendamento():
    if 'user_id' not in session:
        session['destino_pos_login'] = '/tela_agendamento'
        return redirect('/login')
    nome_cliente = session.get('user_nome', None)
    return render_template('agendar.html', nome_cliente=nome_cliente)

@app.route('/login')
def pagina_login():
    return render_template('login.html')

@app.route('/login_admin')
def login_admin():
    if session.get('user_tipo') == 'barbeiro':
        return redirect('/painel')
    return render_template('login_admin.html')

@app.route('/painel')
def painel():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return redirect('/login_admin') 
    return render_template('painel.html')

@app.route('/admin_secreto', methods=['POST'])
def admin_secreto():
    dados = request.json
    if dados.get('senha') == '123': 
        conn = conectar_db(); c = conn.cursor()
        c.execute("SELECT * FROM usuarios WHERE tipo='barbeiro'")
        admin = c.fetchone()
        conn.close()
        if admin:
            session['user_id'] = admin['id']
            session['user_tipo'] = admin['tipo']
            session['user_nome'] = admin['nome']
            return jsonify({"sucesso": True})
    return jsonify({"erro": "Senha incorreta"}), 401

@app.route('/api/servicos', methods=['GET'])
def get_servicos():
    conn = conectar_db(); c = conn.cursor()
    c.execute("SELECT * FROM servicos")
    dados = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(dados)

@app.route('/api/servicos', methods=['POST'])
def add_servico():
    dados = request.json
    conn = conectar_db(); c = conn.cursor()
    c.execute("INSERT INTO servicos (nome, preco, duracao) VALUES (?, ?, ?)", (dados['nome'], dados['preco'], dados['duracao']))
    conn.commit(); conn.close()
    return jsonify({"sucesso": True})

@app.route('/api/profissionais', methods=['GET'])
def get_profissionais():
    conn = conectar_db(); c = conn.cursor()
    c.execute("SELECT * FROM profissionais")
    dados = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(dados)

@app.route('/api/profissionais', methods=['POST'])
def add_profissional():
    nome = request.form.get('nome')
    especialidade = request.form.get('especialidade')
    foto = request.files.get('foto')
    caminho_foto = ''
    
    if foto and foto.filename != '':
        filename = secure_filename(foto.filename)
        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        caminho_foto = f'/static/uploads/{filename}'

    conn = conectar_db(); c = conn.cursor()
    c.execute("INSERT INTO profissionais (nome, especialidade, status, foto) VALUES (?, ?, 'Disponivel', ?)", (nome, especialidade, caminho_foto))
    conn.commit(); conn.close()
    return jsonify({"sucesso": True})

@app.route('/api/profissionais/<int:id>/status', methods=['PUT'])
def mudar_status_profissional(id):
    dados = request.json
    conn = conectar_db(); c = conn.cursor()
    c.execute("UPDATE profissionais SET status=? WHERE id=?", (dados['status'], id))
    conn.commit(); conn.close()
    return jsonify({"sucesso": True})

@app.route('/api/agendamentos_barbeiro')
def agendamentos_barbeiro():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401
    conn = conectar_db(); c = conn.cursor()
    c.execute("""SELECT a.*, u.email, u.telefone, u.foto 
                 FROM agendamentos a 
                 LEFT JOIN usuarios u ON a.cliente_id = u.id 
                 ORDER BY a.data, a.hora""")
    dados = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(dados)

@app.route('/api/horarios_ocupados')
def horarios_ocupados():
    profissional = request.args.get('profissional')
    data = request.args.get('data')
    conn = conectar_db(); c = conn.cursor()
    if profissional and data:
        c.execute("SELECT hora FROM agendamentos WHERE profissional=? AND data=?", (profissional, data))
    else:
        c.execute("SELECT hora FROM agendamentos")
    dados = [row['hora'] for row in c.fetchall()]
    conn.close()
    return jsonify(dados)

@app.route('/api/grafico')
def grafico():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401
    conn = conectar_db(); c = conn.cursor()
    dados = []
    for i in range(6, -1, -1):
        dia = datetime.datetime.now() - datetime.timedelta(days=i)
        data_str = dia.strftime("%Y-%m-%d")
        c.execute("""SELECT SUM(s.preco) as total FROM agendamentos a 
                     JOIN servicos s ON a.servico = s.nome 
                     WHERE a.data = ?""", (data_str,))
        res = c.fetchone()
        dados.append({"data": dia.strftime("%d/%m"), "total": res['total'] if res['total'] else 0.0})
    conn.close()
    return jsonify(dados)

@app.route('/api/avaliar', methods=['POST'])
def avaliar():
    if 'user_id' not in session:
        return jsonify({"erro": "Faça login para avaliar"}), 401
    dados = request.json
    nota = int(dados.get('nota', 0))
    if nota < 1 or nota > 5:
        return jsonify({"erro": "Nota inválida."}), 400
    conn = conectar_db(); c = conn.cursor()
    c.execute("UPDATE agendamentos SET avaliacao=? WHERE id=? AND cliente_id=?", (nota, dados['agendamento_id'], session['user_id']))
    conn.commit(); conn.close()
    return jsonify({"mensagem": "Avaliação registrada!"})

@app.route('/api/assistente', methods=['POST'])
def assistente():
    if 'user_id' not in session or session.get('user_tipo') != 'barbeiro':
        return jsonify({"erro": "Acesso negado"}), 401
    dados = request.json
    pergunta = dados.get('pergunta', '').lower()
    conn = conectar_db(); c = conn.cursor()
    resposta = ""

    if "hoje" in pergunta and ("cliente" in pergunta or "agendamento" in pergunta):
        hoje_str = datetime.datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT cliente_nome, hora, servico FROM agendamentos WHERE data=? ORDER BY hora", (hoje_str,))
        agenda = c.fetchall()
        if len(agenda) == 0: resposta = "Você não tem nenhum cliente agendado para hoje."
        else:
            resposta = f"Você tem {len(agenda)} cliente(s) hoje:\n"
            for a in agenda: resposta += f"⏰ {a['hora']} - {a['cliente_nome']} ({a['servico']})\n"

    elif "dados" in pergunta or "telefone" in pergunta or "email" in pergunta or "contato" in pergunta:
        nome_busca = pergunta.split()[-1].capitalize() 
        c.execute("SELECT nome, email, telefone FROM usuarios WHERE nome LIKE ?", ('%' + nome_busca + '%',))
        u = c.fetchone()
        if u: resposta = f"Dados de {u['nome']}:\n📧 E-mail: {u['email']}\n📱 Telefone: {u['telefone']}"
        else: resposta = f"Não encontrei ninguém com o nome '{nome_busca}'."

    elif "faturamento" in pergunta or "lucro" in pergunta:
        hoje_str = datetime.datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT s.preco FROM agendamentos a JOIN servicos s ON a.servico = s.nome WHERE a.data=?", (hoje_str,))
        precos = c.fetchall()
        total = sum([p['preco'] for p in precos])
        resposta = f"O faturamento de hoje é R$ {total:.2f}."
    else:
        resposta = "Sou seu assistente. Você pode perguntar:\n- 'Tem cliente hoje?'\n- 'Qual o telefone do João?'\n- 'Qual o faturamento?'"

    conn.close()
    return jsonify({"resposta": resposta})

@app.route('/cadastro', methods=['POST'])
def cadastro():
    nome = request.form.get('nome')
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    senha = request.form.get('senha')
    foto = request.files.get('foto')
    caminho_foto = ''

    if not nome or not telefone or not senha:
        return jsonify({"erro": "Preencha os campos obrigatórios (Nome, Celular e Senha)."}), 400

    if email and ("@" not in email or "." not in email):
        return jsonify({"erro": "Insira um e-mail válido ou deixe em branco."}), 400

    if foto and foto.filename != '':
        filename = secure_filename(foto.filename)
        foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        caminho_foto = f'/static/uploads/{filename}'

    conn = conectar_db(); c = conn.cursor()
    
    c.execute("SELECT * FROM usuarios WHERE telefone=?", (telefone,))
    if c.fetchone():
        conn.close()
        return jsonify({"erro": "Este celular já está cadastrado."}), 400

    senha_hash = generate_password_hash(senha)
    email_final = email if email else 'sem_email@barbearia.com'
    
    c.execute("INSERT INTO usuarios (nome, email, telefone, senha, tipo, foto) VALUES (?, ?, ?, ?, 'cliente', ?)", 
              (nome, email_final, telefone, senha_hash, caminho_foto))
    conn.commit(); conn.close()
    return jsonify({"mensagem": "Conta criada com sucesso!"})

@app.route('/login', methods=['POST'])
def fazer_login():
    dados = request.json
    conn = conectar_db(); c = conn.cursor()
    
    c.execute("SELECT * FROM usuarios WHERE (nome=? OR telefone=?)", (dados['login'], dados['login']))
    user = c.fetchone()
    conn.close()
    
    if user:
        if check_password_hash(user['senha'], dados['senha']):
            session['user_id'] = user['id']
            session['user_tipo'] = user['tipo']
            session['user_nome'] = user['nome']
            destino = session.pop('destino_pos_login', '/')
            return jsonify({"sucesso": True, "tipo": user['tipo'], "destino": destino})
        else:
            return jsonify({"erro": "Senha incorreta."}), 401
    return jsonify({"erro": "Usuário não encontrado."}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/agendar', methods=['POST'])
def agendar():
    if 'user_id' not in session:
        return jsonify({"erro": "Precisa estar logado"}), 401
    dados = request.json
    data = dados.get('data')
    hora = dados.get('hora')
    
    try:
        data_hora = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
        if data_hora < datetime.datetime.now():
            return jsonify({"erro": "Não é possível agendar para o passado."}), 400
    except:
        return jsonify({"erro": "Data inválida."}), 400

    conn = conectar_db(); c = conn.cursor()
    
    c.execute("SELECT * FROM agendamentos WHERE cliente_id=? AND data=?", (session['user_id'], data))
    if c.fetchone():
        conn.close()
        return jsonify({"erro": "Você já possui um agendamento neste dia."}), 400
        
    c.execute("SELECT * FROM agendamentos WHERE data=? AND hora=? AND profissional=?", (data, hora, dados['profissional']))
    if c.fetchone():
        conn.close()
        return jsonify({"erro": "Este horário já foi reservado."}), 400

    c.execute("INSERT INTO agendamentos (cliente_id, cliente_nome, profissional, data, hora, servico) VALUES (?, ?, ?, ?, ?, ?)", 
              (session['user_id'], session['user_nome'], dados['profissional'], data, hora, dados['servico']))
    conn.commit()
    
    texto = f"Novo agendamento! Cliente: {session['user_nome']}, Barbeiro: {dados['profissional']}, Serviço: {dados['servico']}, Data: {data} às {hora}."
    link_whatsapp = f"https://wa.me/62994016649?text={urllib.parse.quote(texto)}"
    conn.close()
    return jsonify({"mensagem": "Agendado com sucesso!", "link_wa": link_whatsapp})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
