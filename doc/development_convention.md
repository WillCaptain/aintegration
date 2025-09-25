Development Convention（开发约定）

本项目采用“Backlog 驱动 + 测试优先”的方式迭代。以下约定用于统一研发流程、命名与测试规范。

测试规范
- 文件命名：`tests/test_blXXX_feature.py`（亦可概括为 `test_b**_testname.py`，`XXX` 为 backlog ID 数值）。
- 类命名：`TestBLXXXFeature`，一个 backlog 一个测试类，便于回归与定位。
- 用例标记：
  - 回归：`@pytest.mark.regression`
  - Backlog：`@pytest.mark.blXXX`（如 `@pytest.mark.bl011`）
- 测试分层：
  - 优先以行为/接口层面断言（黑盒），必要时增加模型/仓库层断言（白盒）。
  - 每个 backlog 至少一个端到端（或集成）用例覆盖主流程。
- 约定产物：
  - 测试报告：`reports/test_report.html` 与 `reports/junit.xml`
  - 测试运行元信息：通过 `pytest.ini` 中 `--metadata` 配置
  - 工具调用日志（Mock）：`tests/.artifacts/mock_tool_result.log`

运行与环境
- 端口约定：
  - MCP Server: `127.0.0.1:8004`
  - Mock API: `127.0.0.1:8009`
- 复用策略：
  - 同一测试类内，Mock API 与 MCP Server 只启动一次，复用整个类周期。
  - 若类级异步 fixture 使用到事件循环，需在该模块内提供类级 `event_loop` fixture：
    ```python
    @pytest.fixture(scope="class")
    def event_loop():
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    ```
- Fixture 建议：
  - 类级：启动/复用 Mock API、MCP Server（避免端口冲突）
  - 函数级：普通依赖、快速构造/销毁的数据

Backlog 与命名
- Backlog 文件：`doc/Backlog.md`
- 进度追踪：`doc/Progress.md`
- 测试→Backlog 映射：
  - 文件、类、标记均需包含 `BL-XXX`，以便快速过滤回归子集，例如：`pytest -k bl011 -m regression`

Agent/工具调用约定
- 统一通过 MCP 的 `call_tool` 转发，而非直连具体工具端点。
- 工具元数据在 MCP Server 注册/加载时固化 `endpoint`（支持 `${VAR:default}` 占位符）。
- Agent 侧：
  - 若模型未明确提出工具调用，则不猜测、不调用。
  - 工具调用失败具备通用重试（默认 3 次），失败后返回错误。

Plan/执行架构约定
- 移除 `PlanExecutor`，计划自执行：`Plan.execute(plan_module)`、`Plan.replan(plan_module, new_config)`
- `PlanModule.execute_plan`：从仓库反序列化 `Plan` 后调用其 `execute`
- `Plan` 支持点号路径配置读写：`get_config_value('metadata.author')`、`set_config_value('metadata.author', 'xx')`
- 仓库更新需深度合并 `config`，避免覆盖嵌套结构。
 - 删除策略：系统仅支持软删除（soft delete）。硬删除（hard delete）不提供对外接口；软删通过在 `metadata.deleted=true` 打标，并在默认查询中过滤。

代码风格与提交
- 遵循简洁清晰的命名，使用完整语义词（见代码风格规则）。
- 提交信息建议包含：Backlog ID、改动范围、影响面与验证方式。

运行示例
- 收集：`pytest -q --collect-only`
- 回归（示例）：`pytest -q -k "bl011 or bl001" -m regression`
- 仅 BL-011：`pytest -q -k bl011`


