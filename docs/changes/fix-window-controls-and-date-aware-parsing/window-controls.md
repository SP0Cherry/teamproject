# Edge窗口历史状态修复

基线8671989，未提交工作区，日期2026-11-08。实施Codex；最终评审批准待维护者确认。总变更任务1.2/1.3，关联实施组backport-edge-history-fix。

## 原因证据

用户文章：[Vue3项目Edge浏览器无法最小化问题排查](https://www.cnblogs.com/misillas/p/19614838)。进一步以[Vue Router官方#2704](https://github.com/vuejs/router/pull/2704)及[17b58611修复](https://github.com/vuejs/router/commit/17b58611)核验：上游删除visibilitychange监听，保留pagehide保存。文章覆盖整个replaceState的临时措施没有采用。

本机已安装4.6.4，ESM源码确有隐藏时replaceState路径。此前只检索frontend/src不足以排除依赖层，是本次排查遗漏。历史用户反馈仍有效：工具页正常、手动页失效；重新导航后原登录页暂时恢复，不能因此认定根因已消失。

## 回归与实施

frontend中先执行 `node --test tests/router-history.test.mjs`：1 passed / 2 failed，退出码1；隐藏事件产生额外历史写入，visible状态下pagehide没有保存滚动位置。正常push/replace/back/forward通过。

回补官方修复后 `npm test`：先9 passed，追加错误版本/源码零修改检查后最新11 passed、退出码0；`npm run build`：通过、退出码0。补丁连续执行两次，第一次应用、第二次判为已应用，未重复改写。`npm install --package-lock-only --ignore-scripts --offline`更新锁文件，无新依赖；离线输出的0 vulnerabilities不能代替实时安全扫描。

包固定4.6.4，补丁仅处理应用使用的ESM入口，MIT许可保留；版本或源码变化失败。Docker采用npm ci并在安装前复制脚本；未覆盖浏览器history方法。变更不涉及API、数据库或模型配置。

## 运行与原生验收

获授权运行 `docker compose up -d --no-deps --build web`，退出码0，只重建重启web，未重启API/数据库。Docker中npm ci实际运行postinstall成功应用补丁。随后HTTP读取本机5173实际提供的/node_modules/.vite/deps/vue-router.js：200，旧document.visibilitychange注册不存在，window.pagehide注册仍存在。避免仅修改工作区却继续验收旧容器。

最小复现 `/src/edge-history-repro.html` 不加载Vue，可启用/停用隐藏时replaceState；静态空白对照 `/src/window-diagnostic.html` 禁止脚本。尚未声称在最小复现页完成原生启停A/B测试。

修复后用户在自己手动打开的项目标签刷新并测试，明确反馈“两种方式都正常，草稿保留”：右上角原生按钮和Alt+空格、N均能最小化、任务栏恢复后草稿仍在。此原生结果来自用户现场复测，扩展仅观察项目添加待办页面仍可用；[修复后页面截图](browser-window-fix.jpg)不作为原生窗口状态的独立证明。

环境元数据只读采集：已安装msedge.exe文件版本157.0.4341.42，Windows注册表DisplayVersion=22H2、Build=19045、UBR=6466；这不是通过浏览器about页确认的进程版本。浏览器正常/最大化模式及空白页/普通站点两种操作的完整矩阵仍未补齐，总任务1.2保留未完成；有依赖故障回归、官方修复及原项目功能验收后，总任务1.3与本组1.3已完成。最终维护者批准仍待完成。

## 依赖审计

镜像内npm ci报告3项moderate条目。本机默认npmmirror的audit接口返回404/NOT_IMPLEMENTED，退出码1，未记为通过；显式改用官方npm registry运行 `npm audit --registry=https://registry.npmjs.org --json`，退出码1：minimatch（7.0.0–11.0.0）及vue-tsc、@vue/language-core两项传递影响，来源[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249)。没有高危/严重条目出现在该结果中，但整体审计不通过。

这些为既有开发工具链条目，本次锁文件仅固定已安装路由版本，未新增依赖。未运行audit fix --force；报告建议升级vue-tsc到3.3.14，属于独立兼容性变更。负责人：项目维护者，整改期限2026-12-08（SEC-17）；待认领复核，不作为已批准例外或交付通过依据。
