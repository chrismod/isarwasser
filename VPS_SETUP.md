# Isarwasser VPS Deployment Guide

## 🚀 Initial VPS Setup

### 1. Connect to VPS

```bash
ssh root@YOUR_VPS_IP
```

### 2. Install Docker & Docker Compose

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install -y docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 3. Setup Deploy Key (Secure!)

**📖 WICHTIG: Folge der detaillierten Anleitung in `VPS_DEPLOY_KEY_SETUP.md`**

Kurzfassung:

```bash
# Auf VPS: Key generieren
ssh-keygen -t ed25519 -C "isarwasser-vps-deploy" -f ~/.ssh/isarwasser_deploy
cat ~/.ssh/isarwasser_deploy.pub

# Bei GitHub: https://github.com/chrismod/isarwasser/settings/keys
# → "Add deploy key" → Public Key einfügen → Read-only!

# SSH Config
cat > ~/.ssh/config <<'EOF'
Host github.com-isarwasser
    HostName github.com
    User git
    IdentityFile ~/.ssh/isarwasser_deploy
    IdentitiesOnly yes
EOF

# Testen
ssh -T git@github.com-isarwasser
```

### 4. Clone Repository

```bash
# Option A: /srv (Empfohlen - für Services)
cd /srv
git clone git@github.com-isarwasser:chrismod/isarwasser.git
cd isarwasser

# Option B: Mit dediziertem User (Best Practice)
useradd -m -s /bin/bash deploy
su - deploy
git clone git@github.com-isarwasser:chrismod/isarwasser.git
cd isarwasser
```

## 🐳 Deploy Application

### Initial Deployment

```bash
# Wechsel ins Projekt-Verzeichnis
cd /srv/isarwasser
# ODER: cd /home/deploy/isarwasser

docker-compose up -d --build
```

### Check Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f web
docker-compose logs -f pipeline

# Check cron job execution
docker-compose exec pipeline tail -f /var/log/cron.log
```

## 🔄 Update Application

Simply run:

```bash
cd /srv/isarwasser  # oder dein Installations-Pfad
./deploy.sh
```

## 🌐 Setup Domain & HTTPS (Optional but recommended)

### Option 1: Using Nginx Proxy Manager (Recommended)

```bash
# Install Nginx Proxy Manager
mkdir -p /opt/nginx-proxy-manager
cd /opt/nginx-proxy-manager

# Create docker-compose.yml
cat > docker-compose.yml <<'EOF'
version: '3.8'
services:
  app:
    image: 'jc21/nginx-proxy-manager:latest'
    restart: unless-stopped
    ports:
      - '80:80'
      - '443:443'
      - '81:81'
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
EOF

docker-compose up -d
```

Then:
1. Open http://YOUR_VPS_IP:81
2. Login: `admin@example.com` / `changeme`
3. Change password
4. Add Proxy Host:
   - Domain: `isarwasser.yourdomain.com`
   - Forward: `isarwasser-web` port `80`
   - Enable SSL (Let's Encrypt)

### Option 2: Direct Traefik Setup

See `TRAEFIK_SETUP.md` for advanced setup.

## 🔧 Troubleshooting

### Web not accessible

```bash
# Check if containers are running
docker-compose ps

# Check web logs
docker-compose logs web

# Restart web container
docker-compose restart web
```

### Scraper not fetching data

```bash
# Check pipeline logs
docker-compose logs pipeline

# Manually trigger scraper
docker-compose exec pipeline python3 /app/pipeline/fetch_and_store_isar.py

# Check cron logs
docker-compose exec pipeline cat /var/log/cron.log
```

### Rebuild from scratch

```bash
docker-compose down -v
docker-compose up -d --build --force-recreate
```

## 📊 Monitoring

```bash
# Container stats
docker stats

# Disk usage
docker system df

# Clean up old images
docker system prune -a
```

## 🔐 Security Checklist

- [ ] Change default SSH port
- [ ] Setup UFW firewall
- [ ] Disable root login
- [ ] Setup fail2ban
- [ ] Enable automatic security updates
- [ ] Regular backups of `/opt/isarwasser/data`

## 🎯 Access Points

- **Web App**: http://YOUR_VPS_IP:3000
- **With domain**: https://isarwasser.yourdomain.com
- **Nginx Proxy Manager**: http://YOUR_VPS_IP:81 (if installed)

## 📝 Notes

- Scraper runs every 3 hours via cron
- Data persists in `<install-dir>/data`
- Logs persist in `<install-dir>/logs`
- To update: just run `./deploy.sh`

## 📂 Recommended Installation Paths

- **Best:** `/srv/isarwasser` (FHS standard for services)
- **Also good:** `/home/deploy/isarwasser` (with dedicated user)
- **Works:** `/opt/isarwasser` (common but not ideal)
- **Not recommended:** `/var/www` (for static content only)
