from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime
import os
from dotenv import load_dotenv
import threading
import time as time_module
import pytz

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuração do fuso horário brasileiro
TIMEZONE = pytz.timezone('America/Sao_Paulo')

def agora_br():
    return datetime.now(TIMEZONE)

# Configuração do banco de dados
if os.environ.get('DATABASE_URL'):
    database_url = os.environ.get('DATABASE_URL')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"🔗 Configurando PostgreSQL com psycopg3")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///irrigacao.db'
    print("📱 Usando SQLite para desenvolvimento local")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'warning'

# ==================== MODELOS DO BANCO ====================

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    criado_em = db.Column(db.DateTime, default=lambda: agora_br())
    horarios = db.relationship('HorarioRega', backref='usuario', lazy=True, cascade='all, delete-orphan')
    
    def set_senha(self, senha):
        self.senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
    
    def check_senha(self, senha):
        return bcrypt.check_password_hash(self.senha_hash, senha)

class HorarioRega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora = db.Column(db.String(5), nullable=False)
    duracao = db.Column(db.Integer, default=600)
    dias_semana = db.Column(db.String(50), default="Seg,Sex")
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=lambda: agora_br())
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Cria as tabelas
with app.app_context():
    db.create_all()
    print(f"✅ Banco de dados configurado! Horário: {agora_br().strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")

# ==================== VARIÁVEIS GLOBAIS ====================

esta_regando = False
ultimo_comando = None

# ==================== THREAD VERIFICADOR ====================

def verificador_horarios():
    global esta_regando, ultimo_comando
    while True:
        try:
            with app.app_context():
                agora = agora_br()
                hora_atual = agora.strftime("%H:%M")
                dia_atual = agora.strftime("%a")
                
                dias_map = {
                    'Mon': 'Seg', 'Tue': 'Ter', 'Wed': 'Qua', 
                    'Thu': 'Qui', 'Fri': 'Sex', 'Sat': 'Sab', 'Sun': 'Dom'
                }
                dia_pt = dias_map.get(dia_atual, dia_atual)
                
                horarios = HorarioRega.query.filter_by(ativo=True).all()
                
                for horario in horarios:
                    dias = [d.strip() for d in horario.dias_semana.split(",")]
                    if dia_pt in dias:
                        if horario.hora == hora_atual and not esta_regando:
                            print(f"🕐 {agora.strftime('%d/%m/%Y %H:%M:%S')}: É hora de regar! ({horario.duracao}s)")
                            esta_regando = True
                            ultimo_comando = {
                                "regar": True, 
                                "duracao": horario.duracao, 
                                "hora": horario.hora, 
                                "timestamp": agora.isoformat()
                            }
                            time_module.sleep(horario.duracao)
                            esta_regando = False
                            ultimo_comando = {
                                "regar": False, 
                                "duracao": 0, 
                                "hora": horario.hora, 
                                "timestamp": agora_br().isoformat(), 
                                "status": "concluido"
                            }
                            print(f"✅ Rega concluída às {agora_br().strftime('%d/%m/%Y %H:%M:%S')}")
        except Exception as e:
            print(f"❌ Erro no verificador: {e}")
        time_module.sleep(60)

threading.Thread(target=verificador_horarios, daemon=True).start()

# ==================== ROTAS DE AUTENTICAÇÃO ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.check_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Email ou senha incorretos', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')
        
        # Validações
        if not nome or not email or not senha:
            flash('Por favor, preencha todos os campos', 'danger')
            return render_template('register.html')
        
        if len(nome) < 3:
            flash('Nome deve ter pelo menos 3 caracteres', 'danger')
            return render_template('register.html')
        
        if len(senha) < 6:
            flash('Senha deve ter pelo menos 6 caracteres', 'danger')
            return render_template('register.html')
        
        if senha != confirmar_senha:
            flash('As senhas não coincidem', 'danger')
            return render_template('register.html')
        
        # Verificar se email já existe
        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está cadastrado', 'danger')
            return render_template('register.html')
        
        # Criar novo usuário
        novo_usuario = Usuario(nome=nome, email=email)
        novo_usuario.set_senha(senha)
        
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Cadastro realizado com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar conta. Tente novamente.', 'danger')
            print(f"Erro ao criar usuário: {e}")
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta', 'info')
    return redirect(url_for('login'))

# ==================== ROTAS PROTEGIDAS ====================

@app.route('/dashboard')
@login_required
def dashboard():
    horarios_ativos = HorarioRega.query.filter_by(usuario_id=current_user.id, ativo=True).all()
    total_horarios = HorarioRega.query.filter_by(usuario_id=current_user.id).all()
    usuarios_count = Usuario.query.count()
    
    return render_template('dashboard.html', 
                         esta_regando=esta_regando,
                         ultimo_comando=ultimo_comando,
                         agora_br=agora_br(),
                         horarios_ativos=horarios_ativos,
                         total_horarios=total_horarios,
                         usuarios_count=usuarios_count)

@app.route('/horarios')
@login_required
def horarios():
    horarios_lista = HorarioRega.query.filter_by(usuario_id=current_user.id).order_by(HorarioRega.hora).all()
    return render_template('horarios.html', horarios=horarios_lista)

@app.route('/adicionar_horario', methods=['POST'])
@login_required
def adicionar_horario():
    data = request.json
    if not data or 'hora' not in data:
        return jsonify({"sucesso": False, "erro": "Dados inválidos"}), 400
    
    novo_horario = HorarioRega(
        hora=data['hora'], 
        duracao=data.get('duracao', 600), 
        dias_semana=data.get('dias_semana', 'Seg,Sex'),
        usuario_id=current_user.id
    )
    
    try:
        db.session.add(novo_horario)
        db.session.commit()
        print(f"✅ Novo horário: {data['hora']} (Usuário: {current_user.nome})")
        return jsonify({"sucesso": True, "id": novo_horario.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"sucesso": False, "erro": str(e)}), 500

@app.route('/deletar_horario/<int:id>', methods=['DELETE'])
@login_required
def deletar_horario(id):
    horario = HorarioRega.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    db.session.delete(horario)
    db.session.commit()
    return jsonify({"sucesso": True})

@app.route('/ativar_horario/<int:id>', methods=['PUT'])
@login_required
def ativar_horario(id):
    horario = HorarioRega.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    data = request.json
    horario.ativo = data.get('ativo', True)
    db.session.commit()
    return jsonify({"sucesso": True})

# ==================== API PÚBLICA (ESP32) ====================

@app.route('/status', methods=['GET'])
def status_api():
    global esta_regando, ultimo_comando
    if esta_regando:
        return jsonify({
            "regar": True, 
            "duracao": ultimo_comando["duracao"], 
            "timestamp": ultimo_comando["timestamp"]
        })
    
    agora = agora_br()
    hora_atual = agora.strftime("%H:%M")
    dia_atual = agora.strftime("%a")
    
    dias_map = {'Mon': 'Seg', 'Tue': 'Ter', 'Wed': 'Qua', 'Thu': 'Qui', 'Fri': 'Sex', 'Sat': 'Sab', 'Sun': 'Dom'}
    dia_pt = dias_map.get(dia_atual, dia_atual)
    
    horarios = HorarioRega.query.filter_by(ativo=True).all()
    for horario in horarios:
        dias = [d.strip() for d in horario.dias_semana.split(",")]
        if dia_pt in dias and horario.hora == hora_atual:
            return jsonify({
                "regar": True, 
                "duracao": horario.duracao, 
                "timestamp": agora.isoformat()
            })
    
    return jsonify({"regar": False, "timestamp": agora.isoformat()})

@app.route('/api/horarios', methods=['GET'])
def listar_horarios_api():
    horarios = HorarioRega.query.filter_by(ativo=True).all()
    return jsonify([{
        "id": h.id, 
        "hora": h.hora, 
        "duracao": h.duracao, 
        "dias_semana": h.dias_semana, 
        "ativo": h.ativo
    } for h in horarios])

# ==================== FILTROS JINJA2 ====================

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if fmt:
        return date.strftime(fmt)
    return date.strftime('%d/%m/%Y %H:%M:%S')

# ==================== INICIALIZAÇÃO ====================

if __name__ == '__main__':
    print(f"🚀 Iniciando Sistema de Irrigação... Horário: {agora_br().strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
