# 项目与发布约定

当前项目是全球脉冲 Crossmarket Pulse。原始上游许可证和来源说明必须保留。

## 用户指定的仓库和版本规则

- 发布目标：https://github.com/W3217-SUDO/hangqingjiance.git 。
- 发布分支：`main`。
- 每次推送项目更新都必须同时推送对应版本标签。首版为 `1.0.0`，标签不带 `v` 前缀。
- 后续发布先检查远端标签，默认递增补丁号（例如 `1.0.1`）；用户指定版本时以用户要求为准。
- 发布前更新 `VERSION` 和 `CHANGELOG.md`，确保版本标签指向本次实际发布提交。
- 使用带注释的标签，并优先通过 `git push --atomic origin main <版本号>` 同时发布分支和标签。
- 不覆盖或移动已有远端版本标签，不强制推送，不将个人项目更新推送到原始上游。
- 不提交虚拟环境、数据库、日志、真实环境变量、密钥或其他凭据。

## 检查

- `./.venv/Scripts/python.exe -m unittest discover -s tests -v`
- `node --check src/market_stream/static/dashboard.js`
- `git diff --check`

本机启停和运行限制见 README.zh-CN.md。
