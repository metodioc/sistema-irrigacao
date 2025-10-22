// Menu lateral responsivo
document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const mainContent = document.getElementById('main-content');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            sidebarOverlay.classList.toggle('active');
            mainContent.classList.toggle('expanded');
        });
    }
    
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
            mainContent.classList.remove('expanded');
        });
    }
    
    const sidebarLinks = document.querySelectorAll('.sidebar-menu a');
    sidebarLinks.forEach(link => {
        link.addEventListener('click', function() {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove('active');
                sidebarOverlay.classList.remove('active');
                mainContent.classList.remove('expanded');
            }
        });
    });
    
    const currentPath = window.location.pathname;
    sidebarLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});

// Gerenciamento de horários
function adicionarHorario() {
    const hora = document.getElementById('hora').value;
    const duracao = document.getElementById('duracao').value * 60;
    const diasSelect = document.getElementById('dias');
    const dias = Array.from(diasSelect.selectedOptions).map(option => option.value);
    
    if (!hora || !duracao || dias.length === 0) {
        alert('Por favor, preencha todos os campos');
        return;
    }
    
    const dados = {
        hora: hora,
        duracao: duracao,
        dias_semana: dias.join(',')
    };
    
    fetch('/adicionar_horario', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(dados)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            alert('Horário adicionado com sucesso!');
            location.reload();
        } else {
            alert('Erro ao adicionar horário: ' + (data.erro || 'Desconhecido'));
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro de conexão ao adicionar horário');
    });
}

function deletarHorario(id) {
    if (confirm('Tem certeza que deseja deletar este horário?')) {
        fetch(`/deletar_horario/${id}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.sucesso) {
                alert('Horário deletado com sucesso!');
                location.reload();
            } else {
                alert('Erro ao deletar horário');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('Erro de conexão');
        });
    }
}

function ativarHorario(id, ativo) {
    const status = ativo ? 'ativar' : 'pausar';
    if (confirm(`Tem certeza que deseja ${status} este horário?`)) {
        fetch(`/ativar_horario/${id}`, {
            method: 'PUT',
            headers: {                           // ✅ CORRIGIDO: chaves { } em vez de colchetes [ ]
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ativo: ativo })
        })
        .then(response => response.json())
        .then(data => {
            if (data.sucesso) {
                alert(`Horário ${status}do com sucesso!`);
                location.reload();
            } else {
                alert('Erro ao atualizar horário');
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('Erro de conexão');
        });
    }
}

// Auto-refresh do status
function atualizarStatus() {
    fetch('/status')
    .then(response => response.json())
    .then(data => {
        const statusElement = document.getElementById('status-atual');
        const statusClass = data.regar ? 'regando' : 'aguardando';
        
        if (statusElement) {
            statusElement.textContent = data.regar ? 'Regando agora!' : 'Aguardando próximo horário';
            const statusContainer = statusElement.closest('.status');
            if (statusContainer) {
                statusContainer.className = `status ${statusClass}`;
            }
        }
        
        const timestampElement = document.getElementById('ultimo-timestamp');
        if (timestampElement && data.timestamp) {
            const dataHora = new Date(data.timestamp);
            timestampElement.textContent = 'Última atualização: ' + dataHora.toLocaleString('pt-BR');
        }
    })
    .catch(error => {
        console.error('Erro ao atualizar status:', error);
    });
}

if (document.getElementById('status-atual')) {
    atualizarStatus();
    setInterval(atualizarStatus, 30000);
}

function confirmarLogout() {
    return confirm('Tem certeza que deseja sair?');
}

function validarLogin() {
    const email = document.getElementById('email').value;
    const senha = document.getElementById('senha').value;
    
    if (!email || !senha) {
        alert('Por favor, preencha email e senha');
        return false;
    }
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert('Por favor, insira um email válido');
        return false;
    }
    
    return true;
}

function validarCadastro() {
    const nome = document.getElementById('nome').value;
    const email = document.getElementById('email').value;
    const senha = document.getElementById('senha').value;
    const confirmarSenha = document.getElementById('confirmar_senha').value;
    
    if (!nome || !email || !senha || !confirmarSenha) {
        alert('Por favor, preencha todos os campos');
        return false;
    }
    
    if (nome.length < 3) {
        alert('Nome deve ter pelo menos 3 caracteres');
        return false;
    }
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert('Por favor, insira um email válido');
        return false;
    }
    
    if (senha.length < 6) {
        alert('Senha deve ter pelo menos 6 caracteres');
        return false;
    }
    
    if (senha !== confirmarSenha) {
        alert('As senhas não coincidem');
        return false;
    }
    
    return true;
}
