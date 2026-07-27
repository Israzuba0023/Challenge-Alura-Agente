#!/bin/bash

# ==============================================================================
# Script de Implantação Automatizada na Oracle Cloud Infrastructure (OCI)
# Projeto: Agente Inteligente Corporativo — Santos Pegasus Soluciones
# ==============================================================================

set -e

echo "🚀 Iniciando deployment do Agente Inteligente Pegasus na OCI..."

# 1. Atualizar pacotes do sistema (Ubuntu / Oracle Linux)
if [ -f /etc/debian_version ]; then
    echo "📦 Atualizando pacotes APT..."
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin git curl iptables-persistent ufw
elif [ -f /etc/redhat-release ]; then
    echo "📦 Atualizando pacotes YUM/DNF (Oracle Linux)..."
    sudo dnf update -y
    sudo dnf install -y docker docker-compose git curl iptables
    sudo systemctl enable --now docker
fi

# 2. Adicionar usuário atual ao grupo docker
sudo usermod -aG docker $USER || true

# 3. Liberação de portas no Firewall Linux (OCI Linux traz iptables restritivo)
echo "🔓 Configurando regras de firewall para as portas 8000 e 80..."
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT || true
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true

if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save || true
fi

if command -v ufw &> /dev/null; then
    sudo ufw allow 8000/tcp || true
    sudo ufw allow 80/tcp || true
fi

# 4. Compilar e Iniciar Containers Docker
echo "🐳 Subindo container da aplicação Santos Pegasus..."
docker compose down || true
docker compose up -d --build

# 5. Validação de Saúde (Healthcheck)
echo "⏳ Aguardando inicialização da API..."
sleep 5

if curl -s http://localhost:8000/api/health | grep -q "online"; then
    echo ""
    echo "======================================================================"
    echo "✅ DEPLOY NA ORACLE CLOUD INFRASTRUCTURE (OCI) CONCLUÍDO COM SUCESSO!"
    echo "======================================================================"
    echo "🌐 Acesse a aplicação na OCI através do IP Público da sua VM:"
    echo "👉 http://<OCI_PUBLIC_IP>:8000"
    echo "======================================================================"
else
    echo "⚠️ Aplicação iniciada, mas o healthcheck pendente. Verifique com: docker compose logs -f"
fi
