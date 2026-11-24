# 迁移验证

隔离验证环境：Windows / Python 3.11.7 / embedded-postgres 18.6.3；独立临时 PostgreSQL，包含 pgvector。以下自动化迁移用例未连接业务库。

命令（backend）：`.\.venv\Scripts\python.exe tests/test_migrations.py`。

结果：沙箱内 pg_ctl 受限令牌错误 87；经授权在沙箱外运行，最终退出码 0。验证包含：从 0014 插入历史有时刻/无时刻记录再升级、历史时刻不变、旧 INSERT 省略精度仍兼容、显式冲突触发约束、重复 upgrade head、无仅日期数据时 downgrade/re-upgrade、存在仅日期数据时拒绝结构降级且记录仍存在。

曾发现旧写入方默认精度与约束冲突，已通过仅对省略字段的 INSERT 推导精度修正；正常恢复和保护性拒绝降级分别验证。失败没有记为通过。

2026-11-08本机开发库现场修复：浏览器保存报internal server error；只读元数据确认运行库为0014_todo_location，todos缺新增日期列，运行容器的迁移目录也无0015。Compose此前仅绑定app目录，镜像中的迁移文件未跟随源文件更新。

获用户明确授权后，先用pg_dump自定义格式备份至仓库忽略的 `.local-backups/before-0015-20261108-203319.dump`，31905字节并核对PGDMP格式标识；复制0015迁移到当前api容器后执行 `docker compose exec -T api alembic upgrade head`，退出码0。随后 `alembic current` 返回0015_todo_time_precision (head)。未重启容器或删除业务数据；浏览器原草稿重试成功保存4条合成待办并重读日期精度。

Compose已补 `./backend/alembic:/app/alembic` 供后续开发容器重建时加载迁移，`docker compose config --quiet`通过。当前容器未重建，本次迁移使用的是明确复制的文件。新增备份目录已加入.gitignore；备份正文未输出。备份成功不等于恢复演练通过，本机备份尚未另做恢复演练；已有隔离迁移升降级验证结果仅在上述范围有效。规则：DATA-01/04/05、BE-15、OPS-07/08、REV-08。
