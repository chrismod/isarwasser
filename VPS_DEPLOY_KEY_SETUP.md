# VPS Deployment mit Deploy Key (Sicher!)

## 🔐 Warum Deploy Key?

- Nur für dieses Repository
- Read-only (Server kann nur Code holen)
- Kein privater Account-Key auf dem Server
- Best Practice für Production

## 📋 Setup Anleitung

### 1. Auf dem VPS: Key generieren

```bash
# SSH zum VPS
ssh root@YOUR_VPS_IP

# Neuen Deploy Key erstellen (OHNE Passphrase für automatische Pulls)
ssh-keygen -t ed25519 -C "isarwasser-vps-deploy" -f ~/.ssh/isarwasser_deploy
# Bei Passphrase: einfach Enter drücken (leer lassen)

# Public Key anzeigen
cat ~/.ssh/isarwasser_deploy.pub
```

### 2. Bei GitHub: Deploy Key hinzufügen

1. Geh zu: https://github.com/chrismod/isarwasser/settings/keys
2. "Add deploy key"
3. Title: `vps-production`
4. Key: Den Inhalt von `~/.ssh/isarwasser_deploy.pub` einfügen
5. ❌ **NICHT** "Allow write access" ankreuzen (read-only!)
6. "Add key"

### 3. Auf dem VPS: SSH Config

```bash
# SSH Config erstellen
cat > ~/.ssh/config <<'EOF'
Host github.com-isarwasser
    HostName github.com
    User git
    IdentityFile ~/.ssh/isarwasser_deploy
    IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config

# Testen
ssh -T git@github.com-isarwasser
# Sollte zeigen: "Hi chrismod/isarwasser! You've successfully authenticated..."
```

### 4. Repository klonen mit Deploy Key

```bash
# Mit speziellem Host-Alias klonen
cd /srv
git clone git@github.com-isarwasser:chrismod/isarwasser.git
cd isarwasser

# Verifizieren
git remote -v
# Sollte zeigen: git@github.com-isarwasser:chrismod/isarwasser.git
```

## 🚀 Rest wie gehabt

```bash
# Docker installieren (falls noch nicht)
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose

# Starten
docker-compose up -d --build

# Logs checken
docker-compose logs -f
```

## 🔄 Updates

```bash
cd /opt/isarwasser
./deploy.sh
```

Das funktioniert automatisch, da der Deploy Key für Pulls berechtigt ist!

## ✅ Vorteile

1. **Sicherer**: Nur dieses Repo, read-only
2. **Isoliert**: Kein Account-Key auf dem Server
3. **Einfach**: Automatische Updates mit `./deploy.sh`
4. **Standard**: GitHub empfiehlt das für Production

## 🔧 Troubleshooting

### "Permission denied (publickey)"

```bash
# Key-Pfad prüfen
ls -la ~/.ssh/isarwasser_deploy*

# SSH-Agent testen
ssh -Tv git@github.com-isarwasser
```

### Key neu generieren

```bash
# Alten Key löschen (falls vorhanden)
rm ~/.ssh/isarwasser_deploy*

# Neu erstellen
ssh-keygen -t ed25519 -C "isarwasser-vps-deploy" -f ~/.ssh/isarwasser_deploy

# Bei GitHub: alten Key löschen, neuen hinzufügen
```
