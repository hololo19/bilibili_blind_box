# B站直播间盲盒统计 - Web可视化版本

## 功能特点

### 📊 实时监控
- WebSocket实时推送盲盒数据
- 自动刷新排行榜和统计信息
- 美观的渐变色UI设计

### 📈 数据统计
- 总体统计：总盲盒数、总花费、总价值、总盈亏、参与人数
- 用户排行榜TOP 10
- 完整用户列表（支持搜索）
- 盈亏分布图表

### 💾 数据持久化
- 自动保存到JSON文件
- 程序重启后数据不丢失
- 每60秒自动保存

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 启动Web服务器

```bash
python web_server.py
```

### 2. 访问网页

在浏览器中打开：http://localhost:5000

### 3. 运行盲盒监听程序

在另一个终端运行：
```bash
python monitor_v4_persistent.py
```

**重要**：监听程序需要将数据发送到Web服务器！

## 修改监听程序以支持Web推送

需要修改 `monitor_v4_persistent.py`，添加HTTP请求来通知Web服务器：

```python
# 在文件顶部添加
import requests

WEB_SERVER_URL = "http://localhost:5000"

# 在 BlindBoxTracker.add_blind_box() 方法中添加
def add_blind_box(self, uid: int, uname: str, gift_name: str,
                 blind_price: int, gift_price: int):
    # ... 原有代码 ...

    # 发送到Web服务器
    try:
        requests.post(f"{WEB_SERVER_URL}/api/blind_box", json={
            'uid': uid,
            'uname': uname,
            'gift_name': gift_name,
            'blind_price': blind_price,
            'gift_price': gift_price
        }, timeout=1)
    except:
        pass
```

## 目录结构

```
d:\ntnt\
├── web_server.py           # Web服务器
├── monitor_v4_persistent.py # 盲盒监听程序
├── requirements.txt         # Python依赖
├── templates/
│   └── index.html          # 主页模板
└── static/
    ├── css/
    │   └── style.css       # 样式文件
    └── js/
        └── app.js          # 前端逻辑
```

## 配置

### web_server.py
- 默认端口：5000
- 数据文件：blind_box_data.json
- 自动保存间隔：60秒

### monitor_v4_persistent.py
- ROOM_ID：直播间ID
- COOKIE：B站Cookie
- DATA_FILE：数据文件路径

## API接口

### GET /api/stats
获取统计数据

### GET /api/ranking
获取排行榜TOP 20

### GET /api/users
获取所有用户列表

### WebSocket事件
- `new_blind_box`: 新盲盒记录
- `stats_update`: 统计数据更新
- `recent_records`: 最近记录列表

## 技术栈

- **后端**: Flask + Flask-SocketIO
- **前端**: HTML + CSS + JavaScript
- **图表**: Chart.js
- **实时通信**: Socket.IO
- **数据存储**: JSON文件

## 注意事项

1. 确保Web服务器和监听程序使用相同的数据文件
2. Web服务器需要先启动
3. 浏览器需要支持WebSocket
4. 如需外网访问，修改 `host='0.0.0.0'`

## 开发计划

- [ ] 添加用户详细历史记录查看
- [ ] 添加盲盒类型统计分析
- [ ] 添加数据导出功能（CSV/Excel）
- [ ] 添加时间范围筛选
- [ ] 添加移动端适配优化
