# Job Auto — Summer 2027

个人实习搜索工具：Greenhouse / Lever 公开招聘源、简历技能匹配、本地 SQLite 去重与投递记录、中英文岗位页面。网页界面为中文。

## 启动

Python 3.12，无服务器端第三方依赖：

```sh
cd /workspace/job_auto
python -m job_auto.server
```

浏览器访问本机端口 8000。点击“收集最新岗位”。修改 `sources.json` 添加公司的公开 Greenhouse/Lever board slug。默认三个来源只是起点，不代表覆盖所有加美招聘。来源错误会显示在页面。

自动排除标题标明高中项目或说明明确面向高中生的实习；已收集的此类岗位也会隐藏，历史记录保留。大学岗位描述中仅提到高中毕业证或高中公益项目不会因此被排除。未写明学历要求的岗位仍需核对。

列表默认展示所有已收集的非高中岗位，每页 10 条，可翻页并查看总数。可以自行勾选学期、工资及地区筛选；展示不表示符合投递条件。

投递要求明确 Summer 2027、加美地区、时薪区间下限至少 25（加拿大 CAD，美国 USD）。年薪、未披露工资、未知币种/地区不会通过。匹配分是简历关键词启发式分数，不是录用概率。日期未明确的岗位需手动确认。最近发现不等于最近发布；首次导入可能包含旧岗位。已关闭岗位暂不自动清除，请打开原始页面确认。工资解析和地区识别为保守规则，需要人工核对原文。

## 辅助投递

```sh
python -m pip install -r requirements-apply.txt
python -m playwright install chromium
mkdir -p data
cp profile.example.json data/profile.json
# 在本地编辑 data/profile.json，填入真实信息及 PDF 的绝对路径
python -m job_auto.apply 'greenhouse:company:jobid'
```

需要有图形显示的本地环境。脚本只对达标岗位尝试填写姓名、邮箱、电话和简历；页面布局变化、iframe、多文件上传及其他字段可能不支持。不会猜测工作许可答案、处理验证码或自动点击最终提交，也不会自动标记投递成功。完成提交后在网页手动记录。无人值守自动投递尚未实现；不同 ATS 的认证及表单需逐个集成验证。

个人资料、简历及 SQLite 文件只放在被忽略的 `data/` 内，不要提交到 Git。不要在公共接口暴露该服务。

## 验证与定时收集

```sh
python -m unittest discover -s tests -v
python -c 'from job_auto.core import refresh; print(refresh())'
```

可用系统定时任务每天运行最后一条命令，工作目录须为本仓库。失败来源会单独报告，其他来源继续收集。刷新保留已有投递状态。
