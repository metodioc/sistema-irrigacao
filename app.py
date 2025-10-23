from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Código de convite para registro controlado
CODIGO_CONVITE = os.environ.get('CODIGO_CONVITE', 'IRRIGACAO2025')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuração do banco de dados PostgreSQL
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Render fornece postgres://, mas SQLAlchemy precisa de postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Forçar uso do psycopg (versão 3) em vez do psycopg2
    if 'postgresql://' in database_url and '+psycopg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///irrigacao.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

# Fuso horário de Brasília
BRASILIA_TZ = pytz.timezone('America/Sao_Paulo')

def agora_br():
    """Retorna o horário atual em Brasília"""
    return datetime.now(BRASILIA_TZ)

# Modelos do banco de dados
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
    dias_semana = db.Column(db.String(50), default='Seg,Sex')
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=lambda: agora_br())
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Criar tabelas
with app.app_context():
    try:
        if 'psycopg' in str(db.engine.dialect):
            print("🔗 Configurando PostgreSQL com psycopg3")
        db.create_all()
        print(f"✅ Banco de dados configurado! Horário: {agora_br().strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
    except Exception as e:
        print(f"❌ Erro ao configurar banco: {e}")

# Função auxiliar para verificar horários
def verificar_horario_rega():
    """Verifica se deve regar agora"""
    try:
        agora = agora_br()
        hora_atual = agora.strftime('%H:%M')
        dia_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'][agora.weekday()]
        
        horarios = HorarioRega.query.filter_by(ativo=True).all()
        
        for horario in horarios:
            if hora_atual == horario.hora and dia_semana in horario.dias_semana:
                return True, horario.duracao
        
        return False, 0
    except Exception as e:
        print(f"❌ Erro no verificador: {e}")
        return False, 0

# Rotas de autenticação
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
            flash(f'Bem-vindo, {usuario.nome}!', 'success')
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
        codigo = request.form.get('codigo')
        
        # Validações básicas
        if not nome or not email or not senha or not codigo:
            flash('Por favor, preencha todos os campos', 'danger')
            return render_template('register.html')
        
        # Verificação do código de convite
        if codigo.strip() != CODIGO_CONVITE:
            flash('Código de convite inválido', 'danger')
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
        
        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está cadastrado', 'danger')
            return render_template('register.html')
        
        novo_usuario = Usuario(nome=nome, email=email)
        novo_usuario.set_senha(senha)
        
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Cadastro realizado com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            print(f"⚠️ Erro ao criar usuário: {e}")
            flash('Erro ao criar conta. Tente novamente.', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta', 'info')
    return redirect(url_for('login'))

# Rotas protegidas
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    agora = agora_br()
    regar, duracao = verificar_horario_rega()
    
    horarios_usuario = HorarioRega.query.filter_by(usuario_id=current_user.id).all()
    total_horarios = len(horarios_usuario)
    horarios_ativos = len([h for h in horarios_usuario if h.ativo])
    
    return render_template('dashboard.html',
                         horario_atual=agora.strftime('%d/%m/%Y %H:%M:%S'),
                         status='Regando agora!' if regar else 'Aguardando próximo horário',
                         duracao=duracao,
                         total_horarios=total_horarios,
                         horarios_ativos=horarios_ativos)

@app.route('/horarios')
@login_required
def horarios():
    horarios_usuario = HorarioRega.query.filter_by(usuario_id=current_user.id).order_by(HorarioRega.hora).all()
    return render_template('horarios.html', horarios=horarios_usuario)

@app.route('/adicionar_horario', methods=['POST'])
@login_required
def adicionar_horario():
    try:
        dados = request.get_json()
        novo_horario = HorarioRega(
            hora=dados['hora'],
            duracao=dados['duracao'],
            dias_semana=dados['dias_semana'],
            usuario_id=current_user.id
        )
        db.session.add(novo_horario)
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar horário: {e}")
        return jsonify({'sucesso': False, 'erro': str(e)})

@app.route('/deletar_horario/<int:id>', methods=['DELETE'])
@login_required
def deletar_horario(id):
    try:
        horario = HorarioRega.query.get_or_404(id)
        if horario.usuario_id != current_user.id:
            return jsonify({'sucesso': False, 'erro': 'Não autorizado'}), 403
        db.session.delete(horario)
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao deletar horário: {e}")
        return jsonify({'sucesso': False, 'erro': str(e)})

@app.route('/ativar_horario/<int:id>', methods=['PUT'])
@login_required
def ativar_horario(id):
    try:
        horario = HorarioRega.query.get_or_404(id)
        if horario.usuario_id != current_user.id:
            return jsonify({'sucesso': False, 'erro': 'Não autorizado'}), 403
        dados = request.get_json()
        horario.ativo = dados['ativo']
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar horário: {e}")
        return jsonify({'sucesso': False, 'erro': str(e)})

# API pública para ESP32
@app.route('/status')
def status_api():
    regar, duracao = verificar_horario_rega()
    return jsonify({
        'regar': regar,
        'duracao': duracao,
        'timestamp': agora_br().isoformat()
    })

@app.route('/api/horarios')
def listar_horarios_api():
    horarios = HorarioRega.query.filter_by(ativo=True).all()
    return jsonify([{
        'id': h.id,
        'hora': h.hora,
        'duracao': h.duracao,
        'dias_semana': h.dias_semana
    } for h in horarios])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
