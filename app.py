from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, time
import os
from dotenv import load_dotenv
import threading
import time as time_module

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configuração do banco de dados
# Para desenvolvimento local, usa SQLite
if os.environ.get('DATABASE_URL'):
    # Para produção (Render)
    # Psycopg3 usa 'postgresql://' ao invés de 'postgres://'
    database_url = os.environ.get('DATABASE_URL')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # Para desenvolvimento local
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///irrigacao.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo do banco para horários de rega
class HorarioRega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora = db.Column(db.String(5), nullable=False)  # Formato "HH:MM"
    duracao = db.Column(db.Integer, default=600)    # Duração em segundos (10 min = 600s)
    dias_semana = db.Column(db.String(50), default="Seg,Sex")  # Dias da semana
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

# Cria as tabelas (só roda uma vez)
with app.app_context():
    db.create_all()
    print("✅ Banco de dados configurado!")

# Variável global para controlar se está regando
esta_regando = False
ultimo_comando = None

# Função para verificar se é hora de regar (roda em background)
def verificador_horarios():
    global esta_regando, ultimo_comando
    
    while True:
        try:
            with app.app_context():
                agora = datetime.now()
                hora_atual = agora.strftime("%H:%M")
                dia_atual = agora.strftime("%a")  # "Mon", "Tue", etc.
                
                # Busca horários ativos
                horarios = HorarioRega.query.filter_by(ativo=True).all()
                
                for horario in horarios:
                    # Verifica se é o dia correto
                    dias = horario.dias_semana.split(",")
                    if dia_atual in [d.strip() for d in dias]:
                        # Verifica se é a hora exata
                        if horario.hora == hora_atual and not esta_regando:
                            print(f"🕐 {datetime.now()}: É hora de regar! ({horario.duracao}s)")
                            esta_regando = True
                            ultimo_comando = {
                                "regar": True,
                                "duracao": horario.duracao,
                                "hora": horario.hora,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            # Simula o tempo de rega (em produção, o ESP controlaria isso)
                            time_module.sleep(horario.duracao)
                            esta_regando = False
                            ultimo_comando = {
                                "regar": False,
                                "duracao": 0,
                                "hora": horario.hora,
                                "timestamp": datetime.now().isoformat(),
                                "status": "concluido"
                            }
                            print(f"✅ Rega concluída às {datetime.now().strftime('%H:%M')}")
        except Exception as e:
            print(f"❌ Erro no verificador: {e}")
        
        time_module.sleep(60)  # Verifica a cada minuto

# Inicia o verificador em background
threading.Thread(target=verificador_horarios, daemon=True).start()

# Rota principal - Dashboard web simples
@app.route('/')
def dashboard():
    horarios = HorarioRega.query.filter_by(ativo=True).all()
    status_atual = "Regando agora!" if esta_regando else "Aguardando próximo horário"
    
    # Template HTML simples embutido
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sistema de Irrigação Residencial</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { background: #f5f5f5; padding: 20px; border-radius: 10px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .regando { background: #d4edda; color: #155724; }
            .aguardando { background: #fff3cd; color: #856404; }
            .horario-item { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }
            form { background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }
            input, select, button { padding: 8px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; cursor: pointer; }
            button:hover { background: #0056b3; }
            .btn-delete { background: #dc3545; }
            .btn-ativar { background: #28a745; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌱 Sistema de Irrigação Residencial</h1>
            
            <div class="status {{'regando' if esta_regando else 'aguardando'}}">
                <strong>Status:</strong> {{ status_atual }}
                {% if ultimo_comando %}
                <br><small>Último comando: {{ ultimo_comando.timestamp }}</small>
                {% endif %}
            </div>
            
            <h2>📅 Horários Cadastrados</h2>
            {% if horarios %}
                {% for horario in horarios %}
                <div class="horario-item">
                    <strong>{{ horario.hora }}</strong> - {{ horario.duracao // 60 }} minutos
                    <br><small>Dias: {{ horario.dias_semana }}</small>
                    <br>
                    <button class="btn-delete" onclick="deletar({{ horario.id }})">❌ Deletar</button>
                    {% if not horario.ativo %}
                    <button class="btn-ativar" onclick="ativar({{ horario.id }}, true)">✅ Ativar</button>
                    {% else %}
                    <button class="btn-ativar" onclick="ativar({{ horario.id }}, false)">⏸️ Pausar</button>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <p>Nenhum horário cadastrado. Adicione o primeiro!</p>
            {% endif %}
            
            <h2>➕ Adicionar Novo Horário</h2>
            <form id="form-horario">
                <label>Hora (HH:MM):</label><br>
                <input type="time" id="hora" required>
                
                <label>Duração (minutos):</label><br>
                <input type="number" id="duracao" value="10" min="1" max="60" required>
                
                <label>Dias da semana:</label><br>
                <select id="dias" multiple size="3">
                    <option value="Seg" selected>Segunda</option>
                    <option value="Ter">Terça</option>
                    <option value="Qua">Quarta</option>
                    <option value="Qui">Quinta</option>
                    <option value="Sex" selected>Sexta</option>
                    <option value="Sab">Sábado</option>
                    <option value="Dom">Domingo</option>
                </select>
                <br><small>Segure Ctrl/Cmd para selecionar múltiplos dias</small>
                
                <br><button type="submit">💾 Salvar Horário</button>
            </form>
        </div>
        
        <script>
            // Função para adicionar horário
            document.getElementById('form-horario').addEventListener('submit', function(e) {
                e.preventDefault();
                const hora = document.getElementById('hora').value;
                const duracao = document.getElementById('duracao').value * 60; // Converte para segundos
                const dias = Array.from(document.getElementById('dias').selectedOptions).map(opt => opt.value);
                
                fetch('/adicionar_horario', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({hora: hora, duracao: duracao, dias_semana: dias.join(',')})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.sucesso) {
                        alert('Horário adicionado com sucesso!');
                        location.reload();
                    } else {
                        alert('Erro ao adicionar horário');
                    }
                });
            });
            
            // Funções para deletar e ativar/pausar
            function deletar(id) {
                if (confirm('Tem certeza que deseja deletar este horário?')) {
                    fetch(`/deletar_horario/${id}`, {method: 'DELETE'})
                    .then(() => location.reload());
                }
            }
            
            function ativar(id, ativo) {
                fetch(`/ativar_horario/${id}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ativo: ativo})
                })
                .then(() => location.reload());
            }
        </script>
    </body>
    </html>
    """
    
        return render_template_string(html_template, 
                                  horarios=horarios, 
                                  esta_regando=esta_regando, 
                                  status_atual=status_atual,
                                  ultimo_comando=ultimo_comando)