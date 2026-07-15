# OilPulse-CN 项目说明

## 部署步骤（首次上线）

1. 在 GitHub 新建一个仓库，例如命名为 `oilpulse-cn`（Public，便于其他人直接读取数据）。
2. 把本项目所有文件推送进去：

   ```bash
   cd oilpulse-cn
   git init
   git add .
   git commit -m "init: OilPulse-CN"
   git branch -M main
   git remote add origin https://github.com/ZhangHowie/oilpulse-cn.git
   git push -u origin main
   ```

3. 配置密钥：进入仓库 `Settings → Secrets and variables → Actions → New repository secret`，
   添加两个 Secret（**不要把它们写进任何代码文件或提交历史**）：
   - `MXNZP_APP_ID`
   - `MXNZP_APP_SECRET`
4. 进入 `Actions` 标签页，找到「采集油价数据」工作流，点击 `Run workflow` 手动跑一次，
   确认 `data/latest.json` 被正确更新。
5. 之后工作流会按 cron（北京时间 06:00 / 22:00）自动运行，无需人工干预。
