#!/bin/bash
# VPS Setup Script for Triply Travel Planner
# Run on Ubuntu 22.04 LTS with at least 2GB RAM

set -e

echo "======================================"
echo "Triply Travel Planner - VPS Setup"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root" 
   exit 1
fi

print_status "Starting VPS setup..."

# Update system
print_status "Updating system packages..."
apt update && apt upgrade -y

# Install essential packages
print_status "Installing essential packages..."
apt install -y \
    curl \
    wget \
    git \
    unzip \
    apt-transport-https \
    ca-certificates \
    software-properties-common \
    gnupg \
    lsb-release

# Install Docker
print_status "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    print_status "Docker installed successfully"
else
    print_warning "Docker already installed"
fi

# Install Docker Compose
print_status "Installing Docker Compose..."
apt install -y docker-compose-plugin

# Enable Docker service
systemctl enable docker
systemctl start docker

# Install system dependencies for PDF OCR
print_status "Installing PDF OCR dependencies..."
apt install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libpoppler-cpp-dev

# Verify installations
print_status "Verifying installations..."
docker --version
docker compose version
tesseract --version

# Install Nginx
print_status "Installing Nginx..."
apt install -y nginx

# Install Certbot for SSL
print_status "Installing Certbot for SSL certificates..."
apt install -y certbot python3-certbot-nginx

# Create app directory
APP_DIR="/opt/triply"
print_status "Creating application directory at $APP_DIR..."
mkdir -p $APP_DIR
cd $APP_DIR

# Prompt for repository URL
print_warning "Please enter your GitHub repository URL:"
read -p "Repository URL: " REPO_URL

if [ -z "$REPO_URL" ]; then
    print_error "Repository URL is required"
    exit 1
fi

# Clone repository
print_status "Cloning repository..."
git clone $REPO_URL .

# Create .env file
print_status "Creating environment file..."
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Database Configuration
POSTGRES_DB=triply
POSTGRES_USER=postgres
POSTGRES_PASSWORD=CHANGE_ME_SECURE_PASSWORD
POSTGRES_PORT=5432

# Redis Configuration
REDIS_PORT=6379

# API Keys (REQUIRED - Update these!)
OPENAI_API_KEY=sk-your-openai-key-here
WEATHER_API_KEY=your-weather-api-key-here

# JWT Keys (REQUIRED - Generate with: python scripts/generate_keys.py)
JWT_PRIVATE_KEY_PEM="-----BEGIN RSA PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
-----END RSA PRIVATE KEY-----"

JWT_PUBLIC_KEY_PEM="-----BEGIN PUBLIC KEY-----
YOUR_PUBLIC_KEY_HERE
-----END PUBLIC KEY-----"

# Application Configuration
UI_ORIGIN=https://yourdomain.com
MCP_WEATHER_ENDPOINT=http://mcp-weather:3001
MCP_ENABLED=true

# PDF OCR Configuration
ENABLE_PDF_OCR=true
OCR_DPI_SCALE=2.0
OCR_MIN_TEXT_THRESHOLD=50

# Port Configuration
BACKEND_PORT=8000
FRONTEND_PORT=8501
MCP_PORT=3001
EOF
    print_warning "Created .env file - PLEASE EDIT IT WITH YOUR ACTUAL VALUES!"
    print_warning "Run: nano $APP_DIR/.env"
else
    print_warning ".env file already exists"
fi

# Create uploads directory
mkdir -p uploads
chmod 755 uploads

# Pull Docker images
print_status "Pulling Docker images (this may take a while)..."
docker compose pull

# Build custom images
print_status "Building application images..."
docker compose build

# Create Nginx configuration
print_status "Creating Nginx configuration..."
DOMAIN=""
read -p "Enter your domain name (e.g., triply.example.com) or press Enter to skip: " DOMAIN

if [ ! -z "$DOMAIN" ]; then
    cat > /etc/nginx/sites-available/triply << EOF
# Triply Travel Planner - Nginx Configuration

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS Configuration
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;
    
    # SSL certificates (will be configured by Certbot)
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Frontend (Streamlit)
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
    
    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
    }
    
    # Backend health check
    location /healthz {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }
    
    # Static files and uploads
    location /uploads {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/triply /etc/nginx/sites-enabled/
    
    # Test Nginx configuration
    nginx -t
    
    if [ $? -eq 0 ]; then
        systemctl reload nginx
        print_status "Nginx configured successfully"
        
        # Obtain SSL certificate
        print_status "Obtaining SSL certificate..."
        print_warning "Make sure your domain DNS points to this server's IP!"
        read -p "Press Enter to continue or Ctrl+C to cancel..."
        
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || print_warning "SSL setup failed - you can run it manually later"
    else
        print_error "Nginx configuration test failed"
    fi
else
    print_warning "Skipping Nginx configuration - you can set it up manually later"
fi

# Start services
print_status "Starting Docker services..."
docker compose up -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 10

# Run database migrations
print_status "Running database migrations..."
docker compose exec -T backend alembic upgrade head || print_warning "Migrations failed - may need to run manually"

# Seed database
print_status "Seeding database with initial data..."
docker compose exec -T backend python seed_db.py || print_warning "Seeding failed - may need to run manually"

# Setup firewall
print_status "Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw --force enable
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw reload
    print_status "Firewall configured"
else
    print_warning "UFW not found - please configure firewall manually"
fi

# Create systemd service for auto-restart
print_status "Creating systemd service..."
cat > /etc/systemd/system/triply.service << 'EOF'
[Unit]
Description=Triply Travel Planner
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/triply
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable triply.service
print_status "Systemd service created and enabled"

# Setup log rotation
print_status "Setting up log rotation..."
cat > /etc/logrotate.d/triply << 'EOF'
/opt/triply/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        docker compose restart > /dev/null 2>&1 || true
    endscript
}
EOF

# Create backup script
print_status "Creating backup script..."
cat > /opt/triply/backup.sh << 'EOF'
#!/bin/bash
# Backup script for Triply

BACKUP_DIR="/opt/triply/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
docker compose exec -T postgres pg_dump -U postgres triply | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Backup uploads
tar -czf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" -C /opt/triply uploads/

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/triply/backup.sh

# Setup daily backup cron
print_status "Setting up daily backups..."
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/triply/backup.sh >> /opt/triply/logs/backup.log 2>&1") | crontab -

# Display status
echo ""
echo "======================================"
print_status "Setup completed successfully!"
echo "======================================"
echo ""
echo "📝 Important Next Steps:"
echo ""
echo "1. Edit environment variables:"
echo "   nano /opt/triply/.env"
echo ""
echo "2. Update these required values in .env:"
echo "   - POSTGRES_PASSWORD"
echo "   - OPENAI_API_KEY"
echo "   - JWT_PRIVATE_KEY_PEM & JWT_PUBLIC_KEY_PEM"
echo "   - UI_ORIGIN (your domain)"
echo ""
echo "3. Generate JWT keys:"
echo "   cd /opt/triply"
echo "   docker compose exec backend python scripts/generate_keys.py"
echo ""
echo "4. Restart services after updating .env:"
echo "   docker compose down && docker compose up -d"
echo ""
echo "5. Check service status:"
echo "   docker compose ps"
echo "   docker compose logs -f"
echo ""
echo "6. Access your application:"
if [ ! -z "$DOMAIN" ]; then
    echo "   https://$DOMAIN"
else
    echo "   http://$(curl -s ifconfig.me):8501"
fi
echo ""
echo "7. Backend API health check:"
if [ ! -z "$DOMAIN" ]; then
    echo "   https://$DOMAIN/healthz"
else
    echo "   http://$(curl -s ifconfig.me):8000/healthz"
fi
echo ""
echo "📚 Useful Commands:"
echo "   - View logs: docker compose logs -f"
echo "   - Restart: docker compose restart"
echo "   - Update app: cd /opt/triply && git pull && docker compose up -d --build"
echo "   - Backup now: /opt/triply/backup.sh"
echo "   - Run migrations: docker compose exec backend alembic upgrade head"
echo ""
print_warning "Don't forget to secure your .env file with sensitive credentials!"
echo ""
