# 盲盒统计Web服务 - Docker部署指南

## 📦 系统要求

- Linux服务器（CentOS/Ubuntu/Debian等）
- Docker已安装
- Docker Compose已安装
- 公网IP（可选，用于外网访问）

---

## 🚀 快速部署（推荐）

### 方式1：使用部署脚本（最简单）

```bash
# 1. 上传项目文件到服务器
scp -r /path/to/project user@your-server:/home/blind-box/

# 2. SSH连接到服务器
ssh user@your-server

# 3. 进入项目目录
cd /home/blind-box/

# 4. 给脚本执行权限
chmod +x deploy.sh

# 5. 运行部署脚本
./deploy.sh
```

### 方式2：使用Docker Compose

```bash
# 1. 上传项目文件到服务器

# 2. 进入项目目录
cd /path/to/project

# 3. 创建数据目录
mkdir -p data

# 4. 构建并启动
docker-compose up -d

# 5. 查看运行状态
docker-compose ps
```

---

## 📋 详细步骤

### 1. 安装Docker

#### Ubuntu/Debian
```bash
# 安装Docker
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun

# 启动Docker服务
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
```

#### CentOS
```bash
# 安装Docker
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun

# 启动Docker服务
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
```

### 2. 安装Docker Compose

```bash
# 下载Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 添加执行权限
chmod +x /usr/local/bin/docker-compose

# 验证安装
docker-compose --version
```

### 3. 部署应用

```bash
# 上传项目文件到服务器后

# 进入项目目录
cd /path/to/project

# 构建镜像
docker build -t blind-box-stats:latest .

# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 🌐 访问配置

### 本地访问
```
http://localhost:5000
```

### 局域网访问
```
http://192.168.x.x:5000
```

### 公网访问

如果服务器有公网IP：
```
http://YOUR_PUBLIC_IP:5000
```

#### 配置防火墙（开放5000端口）

**Ubuntu/Debian (ufw)**:
```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

**CentOS (firewalld)**:
```bash
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

**CentOS (iptables)**:
```bash
sudo iptables -I INPUT -p tcp --dport 5000 -j ACCEPT
sudo service iptables save
```

---

## 📁 目录结构

```
blind-box-stats/
├── web_server.py          # Web服务器主程序
├── Dockerfile             # Docker镜像构建文件
├── docker-compose.yml     # Docker Compose配置
├── requirements-docker.txt # Python依赖
├── .dockerignore          # Docker忽略文件
├── deploy.sh              # 部署脚本
├── templates/             # HTML模板
│   └── index.html
├── static/                # 静态资源
│   └── css/
│       └── style.css
└── data/                  # 数据目录（自动创建）
    └── blind_box_data.json
```

---

## 🔧 常用命令

### 查看运行状态
```bash
docker-compose ps
```

### 查看日志
```bash
# 实时查看日志
docker-compose logs -f

# 查看最近100行日志
docker-compose logs --tail=100
```

### 重启服务
```bash
docker-compose restart
```

### 停止服务
```bash
docker-compose stop
```

### 停止并删除容器
```bash
docker-compose down
```

### 重新构建并启动
```bash
docker-compose up -d --build
```

### 进入容器
```bash
docker-compose exec blind-box-web bash
```

---

## 💾 数据备份

### 备份数据
```bash
# 备份整个data目录
tar -czf blind-box-backup-$(date +%Y%m%d).tar.gz data/

# 或只备份JSON文件
cp data/blind_box_data.json data/blind_box_data.json.backup
```

### 恢复数据
```bash
# 解压备份
tar -xzf blind-box-backup-20250217.tar.gz

# 或恢复JSON文件
cp data/blind_box_data.json.backup data/blind_box_data.json
```

### 自动备份脚本
```bash
#!/bin/bash
# 添加到crontab: 0 2 * * * /path/to/backup.sh

BACKUP_DIR="/home/backups/blind-box"
DATA_DIR="/path/to/project/data"

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/blind-box-$(date +\%Y\%m\%d-\%H\%M\%S).tar.gz -C $DATA_DIR .

# 保留最近7天的备份
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

---

## 🔄 更新应用

### 方式1：使用Docker Compose
```bash
# 1. 拉取最新代码（如果使用Git）
git pull

# 2. 停止容器
docker-compose stop

# 3. 重新构建镜像
docker-compose build --no-cache

# 4. 启动容器
docker-compose up -d
```

### 方式2：使用部署脚本
```bash
# 1. 拉取最新代码
git pull

# 2. 运行部署脚本
./deploy.sh
```

---

## 🐛 故障排查

### 容器无法启动
```bash
# 查看详细日志
docker-compose logs -f

# 检查端口占用
netstat -tlnp | grep 5000

# 检查容器状态
docker ps -a
```

### 无法访问网页
```bash
# 1. 检查容器是否运行
docker-compose ps

# 2. 检查防火墙
sudo ufw status

# 3. 检查端口监听
netstat -tlnp | grep 5000

# 4. 测试本地访问
curl http://localhost:5000
```

### 数据丢失
```bash
# 检查data目录
ls -la data/

# 检查volume挂载
docker-compose config | grep volumes

# 恢复备份
tar -xzf blind-box-backup-YYYYMMDD.tar.gz
```

---

## 🔒 安全建议

### 1. 使用反向代理（推荐）

使用Nginx作为反向代理，并配置HTTPS：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. 限制访问IP

只允许特定IP访问（修改docker-compose.yml）：
```yaml
ports:
  - "127.0.0.1:5000:5000"  # 只允许本地访问
```

或使用防火墙规则：
```bash
# 只允许特定IP访问5000端口
iptables -A INPUT -p tcp -s YOUR_IP --dport 5000 -j ACCEPT
iptables -A INPUT -p tcp --dport 5000 -j DROP
```

### 3. 定期更新

```bash
# 定期更新Docker镜像
docker-compose pull
docker-compose up -d
```

---

## 📊 性能优化

### 1. 限制容器资源

修改docker-compose.yml：
```yaml
services:
  blind-box-web:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M
```

### 2. 使用多阶段构建

优化Dockerfile，减小镜像大小：
```dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements-docker.txt .
RUN pip install --user --no-cache-dir -r requirements-docker.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "web_server.py"]
```

---

## 📞 技术支持

如遇问题：
1. 查看日志：`docker-compose logs -f`
2. 检查状态：`docker-compose ps`
3. 重启服务：`docker-compose restart`
4. 查看文档：README.md

---

## ✅ 部署检查清单

- [ ] Docker已安装
- [ ] Docker Compose已安装
- [ ] 防火墙已开放5000端口
- [ ] 数据目录已创建
- [ ] 容器成功启动
- [ ] 网页可以访问
- [ ] 数据持久化正常
- [ ] 备份脚本已配置

---

**部署完成后，可以在OBS中添加浏览器源：**
```
URL: http://YOUR_IP:5000
宽度: 1920
高度: 1080
```

祝使用愉快！🎉
