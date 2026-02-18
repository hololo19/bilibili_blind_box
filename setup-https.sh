#!/bin/bash

echo "========================================"
echo "  配置HTTPS和域名访问"
echo "========================================"
echo ""

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用root权限运行此脚本"
    echo "   使用: sudo bash setup-https.sh"
    exit 1
fi

# 提示输入域名
read -p "请输入你的域名（例如: example.com）: " DOMAIN

if [ -z "$DOMAIN" ]; then
    echo "❌ 域名不能为空"
    exit 1
fi

echo ""
echo "配置域名: $DOMAIN"
echo ""

# 安装Nginx和Certbot
echo "[1/5] 安装Nginx和Certbot..."
apt-get update
apt-get install -y nginx certbot python3-certbot-nginx

# 备份原配置
echo "[2/5] 备份Nginx配置..."
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# 配置Nginx
echo "[3/5] 配置Nginx反向代理..."
sed "s/your-domain.com/$DOMAIN/g" nginx.conf > /etc/nginx/sites-available/blind-box

# 创建软链接
ln -sf /etc/nginx/sites-available/blind-box /etc/nginx/sites-enabled/

# 测试配置
nginx -t

if [ $? -ne 0 ]; then
    echo "❌ Nginx配置测试失败"
    exit 1
fi

# 重启Nginx
echo "[4/5] 重启Nginx..."
systemctl restart nginx

# 获取SSL证书
echo "[5/5] 获取SSL证书..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  🎉 HTTPS配置完成！"
    echo "========================================"
    echo ""
    echo "访问地址："
    echo "  https://$DOMAIN"
    echo ""
    echo "OBS浏览器源配置："
    echo "  URL: https://$DOMAIN"
    echo "  宽度: 1920"
    echo "  高度: 1080"
    echo ""
    echo "证书自动续期已启用"
    echo ""
else
    echo ""
    echo "⚠️  SSL证书获取失败，但HTTP服务已启动"
    echo "  访问: http://$DOMAIN"
    echo ""
fi

echo "========================================"
