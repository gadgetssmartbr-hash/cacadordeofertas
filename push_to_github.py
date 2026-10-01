"""
Helper script to push code to GitHub repository using dulwich (no local git CLI required).
Usage:
    python push_to_github.py [GITHUB_TOKEN]
"""

import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from dulwich import porcelain
from dulwich.client import HTTPUnauthorized


REPO_URL = "https://github.com/gadgetssmartbr-hash/cacadordeofertas.git"


def push(token=None):
    repo = porcelain.open_repo(".")

    # Auto commit any uncommitted changes first
    try:
        porcelain.add(repo)
        porcelain.commit(repo, message="Update: PriceGlitch Agent & GitHub Pages docs")
        print("📦 Alterações locais confirmadas (commit realizado).")
    except Exception as e:
        print(f"ℹ️ Nenhum novo arquivo para commitar: {e}")

    if not token and len(sys.argv) > 1:
        token = sys.argv[1].strip()

    if not token:
        print("\n🔑 Para enviar para o GitHub, informe seu Personal Access Token (PAT).")
        print("Como gerar seu token em 30 segundos no GitHub:")
        print("  1. Acesse: https://github.com/settings/tokens/new")
        print("  2. Em 'Note', digite: CacadorDeOfertas")
        print("  3. Marque a permissão: [x] repo (Full control of private repositories)")
        print("  4. Clique em 'Generate token' e copie o código (ghp_...).\n")
        try:
            token = input("Cole o seu token do GitHub aqui: ").strip()
        except EOFError:
            print("❌ Token não fornecido.")
            return

    if not token:
        print("❌ Token vazio. Operação cancelada.")
        return

    # Authenticated URL
    auth_url = f"https://oauth2:{token}@github.com/gadgetssmartbr-hash/cacadordeofertas.git"

    print("🚀 Enviando arquivos para o GitHub (gadgetssmartbr-hash/cacadordeofertas)...")
    try:
        porcelain.push(repo, auth_url, refspecs=["refs/heads/main"])
        print("\n✅ SUCESSO! Código e pasta docs/ enviados para o repositório.")
        print("🌐 Próximo passo: Acesse https://github.com/gadgetssmartbr-hash/cacadordeofertas/settings/pages")
        print("   e selecione a pasta /docs para ativar o site gratuito!")
    except HTTPUnauthorized:
        print("\n❌ Erro de autenticação: Token inválido ou sem permissão de 'repo'.")
    except Exception as e:
        print(f"\n⚠️ Detalhes do envio: {e}")
        # Try pushing to master if main wasn't the default
        try:
            porcelain.push(repo, auth_url, refspecs=["refs/heads/master"])
            print("✅ Enviado para a branch master!")
        except Exception:
            pass


if __name__ == "__main__":
    push()
