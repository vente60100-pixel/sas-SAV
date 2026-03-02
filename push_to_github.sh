#!/bin/bash
echo '🚀 Push vers GitHub - sas-SAV'
echo '=============================='
echo ''
echo 'Tu vas avoir besoin de:'
echo '1. Ton username GitHub (vente60100-pixel)'
echo '2. Un Personal Access Token (PAS ton mot de passe)'
echo ''
echo 'Pour créer un token:'
echo '→ GitHub.com → Settings → Developer settings'
echo '→ Personal access tokens → Generate new token'
echo '→ Cocher: repo (tout)'
echo ''
read -p 'Username GitHub: ' username
read -sp 'Token GitHub: ' token
echo ''

# Configurer l'URL avec les credentials
git remote set-url origin https://${username}:${token}@github.com/vente60100-pixel/sas-SAV.git

# Push
echo '⏫ Envoi en cours...'
git push -u origin main

echo ''
echo '✅ Terminé ! Vérifie sur https://github.com/vente60100-pixel/sas-SAV'
