# OilPulse-CN 油价脉搏

每天 06:00 和 22:00（北京时间）自动从 [mxnzp 油价接口](https://www.mxnzp.com/api/oil/search)
采集全国 31 个省级行政区的油价，并同步到本仓库。任何人都可以直接通过一个固定 URL 拿到最新
油价数据，无需自己申请接口密钥、无需自己搭服务器。

详细设计见 [DESIGN.md](./DESIGN.md)。

## 数据从哪里读

最新快照（始终是最近一次采集结果）：

```
https://raw.githubusercontent.com/<你的GitHub用户名>/oilpulse-cn/main/data/latest.json
```

jsDelivr CDN 版本（速度更快，可能有几分钟延迟）：

```
https://cdn.jsdelivr.net/gh/<你的GitHub用户名>/oilpulse-cn@main/data/latest.json
```

历史快照（按采集时间归档，路径中的 `0600`/`2200` 对应当次运行时间）：

```
https://raw.githubusercontent.com/<你的GitHub用户名>/oilpulse-cn/main/data/history/2026/07/15/0600.json
```

返回示例：

```json
{
  "updated_at": "2026-07-15T06:00:12+08:00",
  "source": "https://www.mxnzp.com/api/oil/search",
  "province_count": 31,
  "failed_provinces": [],
  "provinces": {
    "广东": { "province": "广东", "t0": "7.64", "t89": "7.42", "t92": "7.99", "t95": "8.65", "t98": "9.79" },
    "上海": { "province": "上海", "t0": "7.60", "t89": "7.40", "t92": "7.97", "t95": "8.63", "t98": "9.75" }
  }
}
```

字段说明：`t0` 0号柴油、`t89` 89号汽油、`t92` 92号汽油、`t95` 95号汽油、`t98` 98号汽油。

## 目录结构

```
oilpulse-cn/
├── .github/workflows/fetch-oil-price.yml   # 定时任务：06:00 / 22:00 采集并推送
├── scripts/fetch_oil_price.py              # 采集脚本
├── data/
│   ├── latest.json                         # 最新快照（每次运行覆盖）
│   └── history/YYYY/MM/DD/HHMM.json        # 历史归档（每次运行新增一份）
├── requirements.txt
├── DESIGN.md                               # 方案设计文档
└── README.md
```

## 本地运行 / 调试

```bash
pip install -r requirements.txt
MXNZP_APP_ID=你的appid MXNZP_APP_SECRET=你的appsecret python scripts/fetch_oil_price.py
```

## 常见问题

**Q: 为什么要保留历史文件，仓库会不会越来越大？**
每天两次、每次约几 KB，一年大概几 MB，对 Git 仓库几乎没有负担。如果未来数据量变大，可以
改为只保留最近 N 天历史，或迁移到单独的历史分支。

**Q: 某个省份采集失败会影响其他省份吗？**
不会。脚本按省份独立请求、独立重试，失败的省份会记录在 `failed_provinces` 字段里，
其余省份的数据仍正常发布。

**Q: 想换成别的采集时间怎么办？**
修改 `.github/workflows/fetch-oil-price.yml` 里的 `cron` 表达式即可（注意 cron 是 UTC 时间，
需要减 8 小时换算成北京时间）。

## License

MIT，见 [LICENSE](./LICENSE)。
