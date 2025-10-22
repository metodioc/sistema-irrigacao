from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from dotenv import load_dotenv
import threading
import time as time_module
import pytz

load_dotenv()

app = Flask(__name__)

# Configuração do fuso horário brasileiro
TIMEZONE = pytz.timezone('America/Sao_Paulo')

# Função auxiliar para pegar horário brasileiro
def agora_br():
    return datetime.now(TIMEZONE)

# Configuração do banco de dados - FORÇA PSYCOPG3
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

class HorarioRega(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora = db.Column(db.String(5), nullable=False)
    duracao = db.Column(db.Integer, default=600)
    dias_semana = db.Column(db.String(50), default="Seg,Sex")
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=lambda: agora_br())

# Cria as tabelas
with app.app_context():
    db.create_all()
    print(f"✅ Banco de dados configurado! Horário: {agora_br().strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")

esta_regando = False
ultimo_comando = None

def verificador_horarios():
    global esta_regando, ultimo_comando
    while True:
        try:
            with app.app_context():
                agora = agora_br()
                hora_atual = agora.strftime("%H:%M")
                dia_atual = agora.strftime("%a")
                
                # Mapeamento de dias da semana em português para inglês
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

@app.route('/')
def dashboard():
    horarios = HorarioRega.query.filter_by(ativo=True).all()
    status_atual = "Regando agora!" if esta_regando else "Aguardando próximo horário"
    hora_br = agora_br().strftime('%d/%m/%Y %H:%M:%S')
    
    html_template = """<!DOCTYPE html><html><head><title>Sistema de Irrigação</title><meta charset="UTF-8"><style>body{font-family:Arial;max-width:800px;margin:0 auto;padding:20px}.container{background:#f5f5f5;padding:20px;border-radius:10px}.status{padding:10px;margin:10px 0;border-radius:5px}.regando{background:#d4edda;color:#155724}.aguardando{background:#fff3cd;color:#856404}.horario-item{background:white;padding:15px;margin:10px 0;border-radius:5px;border-left:4px solid #007bff}form{background:white;padding:20px;border-radius:5px;margin:20px 0}input,select,button{padding:8px;margin:5px;border:1px solid #ddd;border-radius:4px}button{background:#007bff;color:white;cursor:pointer}button:hover{background:#0056b3}.btn-delete{background:#dc3545}.btn-ativar{background:#28a745}.hora-servidor{background:#e9ecef;padding:10px;border-radius:5px;margin:10px 0;text-align:center;font-size:14px}</style></head><body><div class="container"><h1>🌱 Sistema de Irrigação</h1><div class="hora-servidor">🕐 Horário do Servidor: <strong>{{hora_br}}</strong> (Brasília)</div><div class="status {{'regando' if esta_regando else 'aguardando'}}"><strong>Status:</strong> {{status_atual}}{% if ultimo_comando %}<br><small>Último: {{ultimo_comando.timestamp}}</small>{% endif %}</div><h2>📅 Horários</h2>{% if horarios %}{% for h in horarios %}<div class="horario-item"><strong>{{h.hora}}</strong> - {{h.duracao//60}} min<br><small>{{h.dias_semana}}</small><br><button class="btn-delete" onclick="deletar({{h.id}})">❌ Deletar</button>{% if not h.ativo %}<button class="btn-ativar" onclick="ativar({{h.id}},true)">✅ Ativar</button>{% else %}<button onclick="ativar({{h.id}},false)">⏸️ Pausar</button>{% endif %}</div>{% endfor %}{% else %}<p>Nenhum horário cadastrado</p>{% endif %}<h2>➕ Novo Horário</h2><form id="f"><label>Hora (horário de Brasília):</label><input type="time" id="hora" required><label>Duração (min):</label><input type="number" id="duracao" value="10" min="1" max="60"><label>Dias:</label><select id="dias" multiple size="3"><option value="Seg" selected>Segunda</option><option value="Ter">Terça</option><option value="Qua">Quarta</option><option value="Qui">Quinta</option><option value="Sex" selected>Sexta</option><option value="Sab">Sábado</option><option value="Dom">Domingo</option></select><br><small>Segure Ctrl/Cmd para selecionar múltiplos dias</small><br><button type="submit">💾 Salvar</button></form></div><script>document.getElementById('f').addEventListener('submit',function(e){e.preventDefault();const h=document.getElementById('hora').value;const d=document.getElementById('duracao').value*60;const dias=Array.from(document.getElementById('dias').selectedOptions).map(o=>o.value);fetch('/adicionar_horario',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hora:h,duracao:d,dias_semana:dias.join(',')})}).then(r=>r.json()).then(data=>{if(data.sucesso){alert('Horário adicionado!');location.reload();}else{alert('Erro');}});});function deletar(id){if(confirm('Deletar?')){fetch(`/deletar_horario/${id}`,{method:'DELETE'}).then(()=>location.reload());}};function ativar(id,a){fetch(`/ativar_horario/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({ativo:a})}).then(()=>location.reload());}</script></body></html>"""
    
    return render_template_string(html_template, horarios=horarios, esta_regando=esta_regando, status_atual=status_atual, ultimo_comando=ultimo_comando, hora_br=hora_br)

@app.route('/status', methods=['GET'])
def status_api():
    global esta_regando, ultimo_comando
    if esta_regando:
        return jsonify({"regar": True, "duracao": ultimo_comando["duracao"], "timestamp": ultimo_comando["timestamp"]})
    
    agora = agora_br()
    hora_atual = agora.strftime("%H:%M")
    dia_atual = agora.strftime("%a")
    
    dias_map = {'Mon': 'Seg', 'Tue': 'Ter', 'Wed': 'Qua', 'Thu': 'Qui', 'Fri': 'Sex', 'Sat': 'Sab', 'Sun': 'Dom'}
    dia_pt = dias_map.get(dia_atual, dia_atual)
    
    horarios = HorarioRega.query.filter_by(ativo=True).all()
    for horario in horarios:
        dias = [d.strip() for d in horario.dias_semana.split(",")]
        if dia_pt in dias and horario.hora == hora_atual:
            return jsonify({"regar": True, "duracao": horario.duracao, "timestamp": agora.isoformat()})
    
    return jsonify({"regar": False, "timestamp": agora.isoformat()})

@app.route('/adicionar_horario', methods=['POST'])
def adicionar_horario():
    data = request.json
    if not data or 'hora' not in data:
        return jsonify({"sucesso": False, "erro": "Dados inválidos"}), 400
    novo_horario = HorarioRega(hora=data['hora'], duracao=data.get('duracao', 600), dias_semana=data.get('dias_semana', 'Seg,Sex'))
    try:
        db.session.add(novo_horario)
        db.session.commit()
        print(f"✅ Novo horário: {data['hora']} (Brasília)")
        return jsonify({"sucesso": True, "id": novo_horario.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"sucesso": False, "erro": str(e)}), 500

@app.route('/deletar_horario/<int:id>', methods=['DELETE'])
def deletar_horario(id):
    horario = HorarioRega.query.get_or_404(id)
    db.session.delete(horario)
    db.session.commit()
    return jsonify({"sucesso": True})

@app.route('/ativar_horario/<int:id>', methods=['PUT'])
def ativar_horario(id):
    horario = HorarioRega.query.get_or_404(id)
    data = request.json
    horario.ativo = data.get('ativo', True)
    db.session.commit()
    return jsonify({"sucesso": True})

@app.route('/api/horarios', methods=['GET'])
def listar_horarios():
    horarios = HorarioRega.query.all()
    return jsonify([{"id": h.id, "hora": h.hora, "duracao": h.duracao, "dias_semana": h.dias_semana, "ativo": h.ativo} for h in horarios])

if __name__ == '__main__':
    print(f"🚀 Iniciando Sistema de Irrigação... Horário: {agora_br().strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
