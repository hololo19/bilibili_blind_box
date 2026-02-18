# 盲盒统计Web服务 - Docker版

B站直播间盲盒统计系统的Docker部署版本，适用于Linux服务器部署。

---

## 🚀 一键部署

```bash
# 1. 上传项目到服务器
scp -r . user@your-server:/home/blind-box/

# 2. SSH连接服务器
ssh user@your-server

# 3. 进入项目目录
cd /home/blind-box/

# 4. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

完成！访问 `http://YOUR_IP:5000`

---

## 📦 文件说明

| 文件 | 说明 |
|------|------|
| `web_server.py` | Web服务器主程序 |
| `Dockerfile` | Docker镜像构建文件 |
| `docker-compose.yml` | Docker Compose配置 |
| `deploy.sh` | 一键部署脚本 |
| `DOCKER_DEPLOY.md` | 详细部署文档 |

---

## 🌐 访问配置

部署完成后，可以在OBS中添加浏览器源：

```
URL: http://YOUR_IP:5000
宽度: 1920
高度: 1080
帧率: 30
```

---

## 🔧 常用命令

```bash
# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新服务
git pull && docker-compose up -d --build
```

---

## 💾 数据备份

```bash
# 备份数据
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# 恢复数据
tar -xzf backup-20250217.tar.gz
```

---

## 📚 详细文档

查看 [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md) 获取完整的部署指南。

---

**问题反馈**：查看详细文档或查看日志 `docker-compose logs -f`
