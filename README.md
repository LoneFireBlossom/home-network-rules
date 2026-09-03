# home-network-rules

一套家庭网络「始终直连」域名规则的生成器：把可信上游（Loyalsoldier通用直连规则、
MetaCubeX geosite的小红书／RedNote与抖音）与本地增删规则合并，编译成两份产物：

- `generated/managed-direct-domains.txt`——mosdns `domain_set` 消费的域名表，每行
  `domain:<域名>`。
- `generated/surge-direct-services.list`——Surge `RULE-SET` 消费的规则集，每行
  `DOMAIN-SUFFIX,<域名>` 或 `DOMAIN,<域名>`，不带策略；消费方在自己的
  `[Rule]` 段用一行引用并自选策略，例如：

  ```
  RULE-SET,https://testingcf.jsdelivr.net/gh/LoneFireBlossom/home-network-rules@main/generated/surge-direct-services.list,DIRECT,update-interval=43200
  ```

产物只承载域名，不含任何本地网络信息（局域网地址、主机名、密钥、令牌）。

## 输入

- `manifest.json`：定义可信上游来源、本地增删、数量闸门与发布目标（仓库、分支、
  产物路径、jsdelivr purge端点）。
- `state/baseline-direct-domains.txt`：启用本管线时固化的通用直连基线。上游后续
  新增的规则只增量累积，不因上游临时删除而静默撤销既有直连；需要删除时在
  `manifest.json` 的 `exclude` 显式声明。

`state/` 目录下除 `baseline-direct-domains.txt` 外的其余文件（`status.json`、
`last-change.json`、`upstream-additions.txt`、`services/`）是运行时本地状态，
只在生成器实际运行的机器上产生，不纳入版本库。

## 命令

只预览当前上游变化，不写文件、不提交：

```bash
python3 update_rules.py
```

编译、写入产物，产物或`manifest.json`有变化时提交并推送到`origin`，随后请求
jsdelivr刷新两份产物：

```bash
python3 update_rules.py --apply
```

运行测试：

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## 发布行为

产物字节内容与仓库当前内容一致时（`git diff --cached --quiet`判定），不产生
提交，不推送，不请求purge。有变化时提交、推送到`manifest.json`里
`distribution.branch`指定的分支；推送失败会把本地提交回滚到推送前的状态，
保持工作目录与远端一致。

所有来源都失败、来源为空或体积异常、解析到非域名规则、来源条数一次变化超过
20%，或通用来源一次带来超过5000条新规则时，整次运行在写入产物前失败退出，
不产生任何提交。

## 消费方

- 两台mosdns各自维护自己的定时拉取、校验、原子替换、重启与回滚，不由本仓库
  触达；它们只从`generated/managed-direct-domains.txt`的jsdelivr镜像地址拉取。
- Surge侧模块只用一行`RULE-SET`静态引用`generated/surge-direct-services.list`
  的jsdelivr镜像地址，按`update-interval`自行刷新；不由本仓库或生成器写入。

本仓库与生成器只负责编译与发布这两份产物；谁在什么频率、以什么方式消费它们，
是消费方自己的运维范畴。
